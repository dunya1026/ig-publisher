"""노션 발행 큐 → 인스타그램 캐러셀 자동 게시.

선정 규칙 (안전장치)
  - 블로그 '상태'가 발행완료 인 원고만 (블로그가 먼저 나간 뒤 인스타)
  - '인스타상태'가 인스타대기
  - '작성일'이 오늘(KST)  → 밀린 원고가 한꺼번에 나가지 않음
  - 분야별 게시 시각(IG_SLOTS)이 지난 것만
  - 한 번 실행에 최대 IG_MAX_PER_RUN 건, 하루 최대 IG_MAX_PER_DAY 건

사용
  python -m ig_publisher.main                 # 실제 게시 (GitHub Actions)
  python -m ig_publisher.main --dry-run       # 이미지·캡션만 만들어 out/ 에 저장
  python -m ig_publisher.main --page <ID>     # 특정 원고 1건 (날짜·시각 조건 무시)
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import traceback
from pathlib import Path
from zoneinfo import ZoneInfo

from . import notion as N
from .render import render_all
from .slides import from_blog_blocks, from_ig_text

KST = ZoneInfo("Asia/Seoul")

DISCLAIMER_SHORT = "공개된 정보를 정리한 개인 의견이며 특정 투자·계약을 권유하지 않습니다. 실제 결정은 관련 기관 공지를 확인하세요."


def env(name, default=None, required=False):
    v = os.environ.get(name, default)
    if required and not v:
        sys.exit(f"환경변수 {name} 가 필요합니다.")
    return v


def parse_slots(s: str) -> dict[str, int]:
    # "부동산=8,금융=13,생활꿀팁=17"
    out = {}
    for part in s.split(","):
        if "=" in part:
            k, v = part.split("=")
            out[k.strip()] = int(v)
    return out


def build_caption(page: dict, slides: list[dict], n_tags: int, cta: str) -> str:
    custom = N.text(page, "인스타캡션").strip()
    tags = [t.lstrip("#") for t in N.text(page, "해시태그").split() if t.strip()]
    tags = list(dict.fromkeys(tags))[:min(n_tags, 30)]   # 인스타 해시태그 최대 30개
    tag_line = " ".join("#" + t for t in tags)

    if custom:
        body = custom
    else:
        cover = slides[0]
        head = N.text(page, "제목")
        lines = [head, ""]
        if cover.get("subtitle"):
            lines += [cover["subtitle"], ""]
        pts = []
        for s in slides:
            if s["type"] in ("list", "numbered"):
                for it in s["items"]:
                    label, text = it[-2], it[-1]
                    pts.append(f"✔️ {label}: {text}" if label else f"✔️ {text}")
        lines += pts[:4]
        body = "\n".join(lines).strip()

    parts = [body]
    if cta:
        parts.append(cta)
    parts.append("※ " + DISCLAIMER_SHORT)
    if tag_line and "#" not in body:
        parts.append(tag_line)
    caption = "\n\n".join(parts)
    return caption[:2200]   # 인스타 캡션 최대 2,200자


def make_slides(nc: N.Notion, page: dict) -> list[dict]:
    title = N.text(page, "제목")
    ig_text = N.text(page, "인스타슬라이드").strip()
    if ig_text:
        return from_ig_text(ig_text, title)
    return from_blog_blocks(title, nc.blocks(page["id"]))


def candidates(nc, ds_id, today, now_hour, slots, force_page=None):
    if force_page:
        return [nc._req("GET", f"/pages/{force_page}")]
    flt = {"and": [
        {"property": "상태", "select": {"equals": "발행완료"}},
        {"property": "인스타상태", "select": {"equals": "인스타대기"}},
        {"property": "작성일", "date": {"equals": today}},
    ]}
    pages = nc.query(ds_id, flt)
    ready = [p for p in pages if now_hour >= slots.get(N.text(p, "분야"), 99)]
    order = {k: i for i, k in enumerate(slots)}
    return sorted(ready, key=lambda p: order.get(N.text(p, "분야"), 99))


def posted_today(nc, ds_id, today) -> int:
    flt = {"and": [
        {"property": "인스타상태", "select": {"equals": "인스타완료"}},
        {"property": "작성일", "date": {"equals": today}},
    ]}
    return len(nc.query(ds_id, flt))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="게시하지 않고 out/에 이미지·캡션만 생성")
    ap.add_argument("--page", help="특정 노션 페이지 ID 1건만 처리")
    args = ap.parse_args()

    nc = N.Notion(env("NOTION_TOKEN", required=True))
    ds_id = env("NOTION_DATA_SOURCE_ID", required=True)
    slots = parse_slots(env("IG_SLOTS", "부동산=8,금융=13,생활꿀팁=17"))
    max_run = int(env("IG_MAX_PER_RUN", "1"))
    max_day = int(env("IG_MAX_PER_DAY", "3"))
    handle = env("IG_HANDLE", "")
    n_tags = int(env("IG_HASHTAG_COUNT", "15"))
    cta = env("IG_CTA", "자세한 내용은 프로필 링크의 블로그에서 볼 수 있어요.")

    now = dt.datetime.now(KST)
    today = now.date().isoformat()

    todo = candidates(nc, ds_id, today, now.hour, slots, args.page)
    if not args.page and not args.dry_run:
        room = max_day - posted_today(nc, ds_id, today)
        todo = todo[:max(0, min(room, max_run))]
    if not todo:
        print("게시할 원고 없음")
        return

    ig = None
    if not args.dry_run:
        from .instagram import Instagram
        ig = Instagram(env("IG_USER_ID", required=True), env("IG_ACCESS_TOKEN", required=True),
                       env("GRAPH_API_VERSION", "v25.0"), env("GRAPH_HOST", "graph.facebook.com"))

    for page in todo:
        pid = page["id"]
        title = N.text(page, "제목")
        category = N.text(page, "분야")
        print(f"▶ {category} | {title}")
        try:
            slides = make_slides(nc, page)
            date_label = (N.text(page, "작성일") or today).replace("-", ".")
            out_dir = Path("out" if args.dry_run else "cards") / (N.text(page, "작성일") or today) / pid.replace("-", "")
            paths = render_all(slides, category, out_dir, handle=handle,
                               date_label=date_label, disclaimer=DISCLAIMER_SHORT)
            caption = build_caption(page, slides, n_tags, cta)
            (out_dir / "caption.txt").write_text(caption, encoding="utf-8")
            print(f"  이미지 {len(paths)}장 → {out_dir}")
            if args.dry_run:
                continue

            nc.update(pid, {"인스타상태": N.select("인스타발행중")})
            from .hosting import publish_to_github
            urls = publish_to_github(paths)
            media_id, permalink = ig.publish_carousel(urls, caption)
            nc.update(pid, {"인스타상태": N.select("인스타완료"),
                            "인스타URL": N.url(permalink),
                            "인스타오류": N.rich("")})
            print(f"  게시 완료: {permalink}")
        except Exception as e:  # 한 건 실패해도 다음 건 진행
            traceback.print_exc()
            if not args.dry_run:
                try:
                    nc.update(pid, {"인스타상태": N.select("인스타실패"),
                                    "인스타오류": N.rich(str(e)[:1800])})
                except Exception:
                    traceback.print_exc()


if __name__ == "__main__":
    main()
