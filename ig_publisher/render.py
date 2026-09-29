"""카드뉴스 이미지 렌더러 (1080x1350, JPEG).

폰트: Noto Sans CJK KR (Ubuntu: apt install fonts-noto-cjk / Mac: 자동 탐색 또는 FONT_DIR 지정)
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
PAD = 88

ACCENT = {
    "부동산": (224, 106, 44),
    "금융": (43, 104, 222),
    "생활꿀팁": (34, 150, 102),
}
DEFAULT_ACCENT = (70, 70, 80)
BG = (247, 245, 240)
INK = (26, 26, 30)
MUTED = (110, 110, 118)
CARD = (255, 255, 255)
WHITE = (255, 255, 255)

# ---------------------------------------------------------------- fonts
_FONT_CANDIDATES = {
    "bold": [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc",
        "/Library/Fonts/NotoSansKR-Bold.otf",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    ],
    "regular": [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/Library/Fonts/NotoSansKR-Regular.otf",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    ],
}


def _find_font_file(weight: str) -> str:
    font_dir = os.environ.get("FONT_DIR")
    if font_dir:
        for p in Path(font_dir).glob("*"):
            name = p.name.lower()
            if weight == "bold" and "bold" in name:
                return str(p)
            if weight == "regular" and "regular" in name:
                return str(p)
    for p in _FONT_CANDIDATES[weight]:
        if Path(p).exists():
            return p
    raise FileNotFoundError(
        "한글 폰트를 찾지 못했습니다. fonts-noto-cjk 설치 또는 FONT_DIR 환경변수로 폰트 폴더를 지정하세요."
    )


@lru_cache(maxsize=None)
def _ttc_index(path: str) -> int:
    """TTC 안에서 한국어(KR) 페이스 번호 찾기."""
    if not path.endswith(".ttc"):
        return 0
    for i in range(12):
        try:
            f = ImageFont.truetype(path, 20, index=i)
        except OSError:
            break
        fam = " ".join(f.getname())
        if "KR" in fam or "Korean" in fam or "Gothic Neo" in fam:
            return i
    return 0


@lru_cache(maxsize=None)
def font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    path = _find_font_file(weight)
    return ImageFont.truetype(path, size, index=_ttc_index(path))


# ---------------------------------------------------------------- text utils
def _text_w(draw: ImageDraw.ImageDraw, text: str, f) -> float:
    return draw.textlength(text, font=f)


def wrap(draw, text: str, f, max_w: int) -> list[str]:
    """한국어 친화 줄바꿈: 공백 단위, 긴 단어는 글자 단위로 자름."""
    lines: list[str] = []
    for para in text.split("\n"):
        words = para.split(" ")
        line = ""
        for word in words:
            cand = f"{line} {word}".strip()
            if _text_w(draw, cand, f) <= max_w:
                line = cand
                continue
            if line:
                lines.append(line)
            # 단어 자체가 너무 길면 글자 단위
            line = ""
            for ch in word:
                if _text_w(draw, line + ch, f) <= max_w:
                    line += ch
                else:
                    lines.append(line)
                    line = ch
        lines.append(line)
    return [l for l in lines if l != ""] or [""]


def _line_h(f) -> int:
    asc, desc = f.getmetrics()
    return int((asc + desc) * 1.12)


def _draw_lines(draw, xy, lines, f, fill, spacing=None):
    x, y = xy
    lh = spacing or _line_h(f)
    for ln in lines:
        draw.text((x, y), ln, font=f, fill=fill)
        y += lh
    return y


# ---------------------------------------------------------------- chrome
def _chip(draw, x, y, text, bg, fg, size=30):
    f = font(size, "bold")
    tw = _text_w(draw, text, f)
    h = size + 26
    draw.rounded_rectangle((x, y, x + tw + 44, y + h), radius=h // 2, fill=bg)
    draw.text((x + 22, y + 11), text, font=f, fill=fg)
    return x + tw + 44


def _footer(draw, idx, total, handle, color):
    f = font(26, "regular")
    if handle:
        draw.text((PAD, H - 70), handle, font=f, fill=color)
    page = f"{idx}/{total}"
    draw.text((W - PAD - _text_w(draw, page, f), H - 70), page, font=f, fill=color)


# ---------------------------------------------------------------- slides
def render_cover(slide, category, date_label, handle, total):
    accent = ACCENT.get(category, DEFAULT_ACCENT)
    img = Image.new("RGB", (W, H), accent)
    d = ImageDraw.Draw(img)
    # 은은한 장식 원
    d.ellipse((W - 420, -220, W + 220, 420), fill=tuple(min(255, c + 22) for c in accent))
    _chip(d, PAD, PAD, category, WHITE, accent, 32)
    if date_label:
        f = font(28, "regular")
        d.text((W - PAD - _text_w(d, date_label, f), PAD + 14), date_label, font=f, fill=WHITE)

    title_lines_raw = [t.strip() for t in slide["title"].split("/") if t.strip()]
    max_w = W - PAD * 2
    size = 96
    while size > 56:
        f = font(size, "bold")
        lines = [ln for part in title_lines_raw for ln in wrap(d, part, f, max_w)]
        if len(lines) * _line_h(f) <= 480:
            break
        size -= 4
    f = font(size, "bold")
    lines = [ln for part in title_lines_raw for ln in wrap(d, part, f, max_w)]
    y = 330
    y = _draw_lines(d, (PAD, y), lines, f, WHITE)

    if slide.get("subtitle"):
        d.rectangle((PAD, y + 36, PAD + 90, y + 44), fill=WHITE)
        limit = H - 200 - (y + 80)
        fs_size = 40
        while True:
            fs = font(fs_size, "regular")
            sub = wrap(d, slide["subtitle"], fs, max_w)
            if len(sub) * _line_h(fs) <= limit or fs_size <= 30:
                break
            fs_size -= 2
        max_lines = max(1, limit // _line_h(fs))
        if len(sub) > max_lines:
            sub = sub[:max_lines]
            sub[-1] = sub[-1].rstrip(" .,") + "…"
        _draw_lines(d, (PAD, y + 80), sub, fs, (255, 255, 255))

    f2 = font(30, "bold")
    swipe = "옆으로 넘겨보세요  →"
    d.text((W - PAD - _text_w(d, swipe, f2), H - 132), swipe, font=f2, fill=WHITE)
    _footer(d, 1, total, handle, WHITE)
    return img


LARGE_SCALES = [(50, 46), (46, 42), (42, 40)]
TYPE_SCALES = [(38, 36), (36, 34), (34, 32)]  # (라벨, 본문) 크기, 장 수가 넘치면 작은 단계로
ITEM_GAP = 22
TITLE_TOP = PAD + 110


def _item_block(d, label, text, numbered, scale):
    ls, bs = scale
    fl, fb = font(ls, "bold"), font(bs, "regular")
    inner = W - PAD * 2 - 64 - (74 if numbered else 0)
    lab = wrap(d, label, fl, inner) if label else []
    body = wrap(d, text, fb, inner)
    h = 52 + len(lab) * _line_h(fl) + (8 if lab else 0) + len(body) * _line_h(fb)
    return lab, body, h


def _title_block(d, title):
    ft = font(60, "bold")
    lines = wrap(d, title, ft, W - PAD * 2)[:2]
    return lines, ft, TITLE_TOP + len(lines) * _line_h(ft) + 64


def paginate(section, scale, d=None):
    """한 섹션의 항목을 높이 기준으로 여러 장에 나눠 담기."""
    d = d or ImageDraw.Draw(Image.new("RGB", (10, 10)))
    numbered = section["type"] == "numbered"
    pages, cur, used = [], [], 0
    title = section["title"]
    _, _, top = _title_block(d, title)
    avail = H - 130 - top
    for n, (label, text) in enumerate(section["items"], start=1):
        _, _, h = _item_block(d, label, text, numbered, scale)
        if cur and used + h > avail:
            pages.append(cur)
            cur, used = [], 0
        cur.append((n, label, text))
        used += h + ITEM_GAP
    if cur:
        pages.append(cur)
    # 균등 재배분: 마지막 장에 1개만 남는 식의 쏠림 방지
    k = len(pages)
    if k > 1:
        flat = [it for pg in pages for it in pg]
        per = -(-len(flat) // k)
        cand = [flat[i:i + per] for i in range(0, len(flat), per)]
        def fits(pg):
            return sum(_item_block(d, l, t, numbered, scale)[2] + ITEM_GAP for _, l, t in pg) <= avail
        if len(cand) == k and all(fits(pg) for pg in cand):
            pages = cand
    out = []
    for i, items in enumerate(pages):
        out.append({"type": section["type"], "items": items, "scale": scale,
                    "title": title if i == 0 else f"{title} (계속)"})
    return out


def render_list(slide, category, handle, idx, total):
    accent = ACCENT.get(category, DEFAULT_ACCENT)
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    _chip(d, PAD, PAD, category, accent, WHITE, 28)

    tlines, ft, top = _title_block(d, slide["title"])
    y = _draw_lines(d, (PAD, TITLE_TOP), tlines, ft, INK)
    d.rectangle((PAD, y + 14, PAD + 72, y + 22), fill=accent)
    y = top

    numbered = slide["type"] == "numbered"
    scale = slide.get("scale", TYPE_SCALES[0])
    fl, fb = font(scale[0], "bold"), font(scale[1], "regular")
    for n, label, text in slide["items"]:
        lab, body, h = _item_block(d, label, text, numbered, scale)
        d.rounded_rectangle((PAD, y, W - PAD, y + h), radius=28, fill=CARD)
        x = PAD + 32
        if numbered:
            r = 26
            cx, cy = x + r, y + 26 + r
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=accent)
            fn = font(30, "bold")
            s = str(n)
            d.text((cx - _text_w(d, s, fn) / 2, cy - 22), s, font=fn, fill=WHITE)
            x += 74
        ty = y + 26
        if lab:
            ty = _draw_lines(d, (x, ty), lab, fl, accent) + 8
        _draw_lines(d, (x, ty), body, fb, INK)
        y += h + ITEM_GAP

    _footer(d, idx, total, handle, MUTED)
    return img


def layout(slides, max_slides=10):
    """섹션들을 실제 장으로 펼치기. 10장을 넘으면 글자 크기를 한 단계씩 줄이고, 그래도 넘치면 뒤쪽 본문 장을 생략."""
    cover = [s for s in slides if s["type"] == "cover"]
    closing = [s for s in slides if s["type"] == "closing"]
    sections = [s for s in slides if s["type"] in ("list", "numbered")]
    body = None
    # 1) 내용이 짧으면: 모든 섹션이 한 장씩에 들어가는 가장 큰 글자 크기
    for scale in LARGE_SCALES + TYPE_SCALES:
        cand = [p for sec in sections for p in paginate(sec, scale)]
        if len(cand) == len(sections) and len(cover) + len(cand) + len(closing) <= max_slides:
            body = cand
            break
    # 2) 길면: 10장 안에 들어가는 첫 크기(기본 크기부터 줄여가며)
    if body is None:
        for scale in TYPE_SCALES:
            body = [p for sec in sections for p in paginate(sec, scale)]
            if len(cover) + len(body) + len(closing) <= max_slides:
                break
    room = max_slides - len(cover) - len(closing)
    return cover + body[:room] + closing


def render_closing(slide, category, handle, idx, total, disclaimer):
    accent = ACCENT.get(category, DEFAULT_ACCENT)
    img = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(img)
    _chip(d, PAD, PAD, "정리", accent, WHITE, 30)
    f = font(66, "bold")
    lines = wrap(d, slide["text"], f, W - PAD * 2)
    while len(lines) * _line_h(f) > 520 and f.size > 40:
        f = font(f.size - 4, "bold")
        lines = wrap(d, slide["text"], f, W - PAD * 2)
    y = _draw_lines(d, (PAD, 330), lines, f, WHITE)

    fs = font(34, "bold")
    d.text((PAD, y + 70), "저장해두고 필요할 때 꺼내보세요", font=fs, fill=accent)

    if disclaimer:
        fd = font(24, "regular")
        dl = wrap(d, disclaimer, fd, W - PAD * 2)
        _draw_lines(d, (PAD, H - 150 - len(dl) * _line_h(fd)), dl, fd, (170, 170, 176))
    _footer(d, idx, total, handle, (170, 170, 176))
    return img


def render_all(slides, category, out_dir, handle="", date_label="", disclaimer=""):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    slides = layout(slides)
    total = len(slides)
    paths = []
    for i, s in enumerate(slides, start=1):
        if s["type"] == "cover":
            img = render_cover(s, category, date_label, handle, total)
        elif s["type"] == "closing":
            img = render_closing(s, category, handle, i, total, disclaimer)
        else:
            img = render_list(s, category, handle, i, total)
        p = out / f"{i:02d}.jpg"
        img.save(p, "JPEG", quality=92, optimize=True, progressive=False)
        paths.append(p)
    return paths
