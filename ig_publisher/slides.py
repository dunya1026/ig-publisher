"""슬라이드 구성 만들기.

두 가지 입력을 지원합니다.
1) 노션 '인스타슬라이드' 속성 (원고 작성 루틴이 써 둔 인스타 전용 문구)
2) 없으면 블로그 본문 블록에서 자동 추출 (글머리/번호 목록 기반)

슬라이드 dict 형식
  {"type": "cover",   "title": str, "subtitle": str, "hook": str, "swipe": str}
  {"type": "list",    "title": str, "items": [(label, text), ...], "teaser": str}
  {"type": "numbered","title": str, "items": [(label, text), ...], "teaser": str}
  {"type": "closing", "text": str, "action": str}
"""
from __future__ import annotations

import re

MAX_SLIDES = 10          # 인스타 캐러셀 최대 10장


def _split_item(line: str) -> tuple[str, str]:
    """'라벨: 내용' -> (라벨, 내용). 콜론이 없으면 ('', 전체)."""
    line = line.strip()
    line = re.sub(r"^(\d+\.|-|•)\s*", "", line)
    line = line.replace("**", "")
    m = re.match(r"^([^:：]{1,24})[:：]\s*(.+)$", line)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return "", line


def _finalize(slides: list[dict]) -> list[dict]:
    cover = [s for s in slides if s["type"] == "cover"][:1]
    closing = [s for s in slides if s["type"] == "closing"][:1]
    body = [s for s in slides if s["type"] in ("list", "numbered") and s["items"]]
    # 장 수 조절(항목이 많으면 나눠 담기)은 render.paginate()에서 처리
    return cover + body + closing


def from_ig_text(text: str, fallback_title: str) -> list[dict]:
    """노션 '인스타슬라이드' 속성 파싱.

    형식 예)
        표지: 조정지역 일시적 2주택 / 10월부터 2년 안에 팔아야
        부제: 양도세·종부세 특례 3년 → 2년
        ## 핵심 내용
        - 적용: 8월 4일 이후 새 집 취득분
        ## 체크포인트
        1. 계약일 확인: 8월 3일 이전 계약금 지급 여부
        정리: 갈아타기 계획이 있다면 날짜부터 확인하세요

    선택 줄(있으면 반영, 없으면 기본값)
        훅: 표지 제목 위 한 줄 질문 (캡션 첫 줄에도 사용)
        넘김: 표지 하단 '넘겨보기' 문구
        > 문구   (## 슬라이드 안) 그 장 하단에 다음 장 예고
        행동: 마지막 장 하단 행동 유도 문구
    """
    slides: list[dict] = []
    title, subtitle, closing = fallback_title, "", ""
    hook, swipe, action = "", "", ""
    current: dict | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("표지:"):
            title = line[3:].strip()
        elif line.startswith("부제:"):
            subtitle = line[3:].strip()
        elif line.startswith("정리:"):
            closing = line[3:].strip()
        elif line.startswith("훅:"):
            hook = line[2:].strip()
        elif line.startswith("넘김:"):
            swipe = line[3:].strip()
        elif line.startswith("행동:"):
            action = line[3:].strip()
        elif line.startswith(">") and current is not None:
            current["teaser"] = line.lstrip(">").strip()
        elif line.startswith("## "):
            current = {"type": "list", "title": line[3:].strip(), "items": []}
            slides.append(current)
        elif re.match(r"^\d+\.\s", line) and current is not None:
            current["type"] = "numbered"
            current["items"].append(_split_item(line))
        elif line.startswith(("- ", "• ")) and current is not None:
            current["items"].append(_split_item(line))
    out = [{"type": "cover", "title": title, "subtitle": subtitle, "hook": hook, "swipe": swipe}] + slides
    if closing:
        out.append({"type": "closing", "text": closing, "action": action})
    return _finalize(out)


def _rt(block: dict) -> str:
    data = block.get(block["type"], {})
    return "".join(t.get("plain_text", "") for t in data.get("rich_text", []))


def from_blog_blocks(title: str, blocks: list[dict]) -> list[dict]:
    """블로그 본문(노션 블록)에서 카드 구성 추출."""
    subtitle = ""
    sections: list[dict] = []
    current: dict | None = None
    closing_paras: list[str] = []
    in_closing = False
    for b in blocks:
        t = b.get("type")
        text = _rt(b).strip() if t else ""
        if t == "quote" and not subtitle:
            subtitle = text
        elif t in ("heading_1", "heading_2", "heading_3"):
            in_closing = text.startswith("정리")
            current = {"type": "list", "title": text, "items": []}
            sections.append(current)
        elif t == "bulleted_list_item" and current is not None:
            current["items"].append(_split_item(text))
        elif t == "numbered_list_item" and current is not None:
            current["type"] = "numbered"
            current["items"].append(_split_item(text))
        elif t == "paragraph" and in_closing and text and not text.startswith("※"):
            closing_paras.append(text)

    # 제목을 2줄로: 쉼표 기준
    cover_title = " / ".join(p.strip() for p in title.split(",", 1))
    slides = [{"type": "cover", "title": cover_title, "subtitle": subtitle}]
    slides += [s for s in sections if s["items"]]
    if closing_paras:
        sentences = re.split(r"(?<=[.다요])\s+", closing_paras[0])
        slides.append({"type": "closing", "text": sentences[0]})
    return _finalize(slides)
