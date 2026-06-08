"""Generate a 1200x630 PNG share card for dbt Lens.

Card dimensions: 1200x630 (standard social sharing size).
Output is a PIL Image ready for st.download_button or file save.
"""

from __future__ import annotations

import io
import os


from PIL import Image, ImageDraw, ImageFont


# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

CARD_W = 1200
CARD_H = 630

# Palette
BG_TOP = (8, 12, 22)        # deep navy top
BG_BOT = (18, 28, 55)       # dark blue bottom
ACCENT = (212, 175, 55)     # gold
ACCENT_DIM = (155, 128, 38) # darker gold
TEXT_PRIMARY = (248, 250, 252)
TEXT_SECONDARY = (140, 155, 185)  # brighter gray for readability
PANEL_BG = (25, 38, 68)
BAR_BG = (60, 75, 115)  # brighter so empty bars are clearly visible, not invisible gaps
GREEN = (34, 197, 94)
ORANGE = (249, 115, 22)
RED = (239, 68, 68)


# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------

_FONT_DIRS = [
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"),
    "/usr/share/fonts",
    "/usr/local/share/fonts",
    "/Library/Fonts",
    "/System/Library/Fonts",
]

_FONT_BOLD = ["arialbd.ttf", "Arial-Bold.ttf", "DejaVuSans-Bold.ttf", "Helvetica-Bold.ttf"]
_FONT_REG = ["arial.ttf", "Arial.ttf", "DejaVuSans.ttf", "Helvetica.ttf"]
_FONT_LIGHT = ["seguisb.ttf", "Arial-Light.ttf", "Arial Light.ttf", "DejaVuSans.ttf"]


def _font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont:
    for d in _FONT_DIRS:
        if not d or not os.path.isdir(d):
            continue
        for c in candidates:
            p = os.path.join(d, c)
            if os.path.isfile(p):
                try:
                    return ImageFont.truetype(p, size=size)
                except OSError:
                    continue
    return ImageFont.load_default()  # type: ignore[return-value]


def _rounded(img: Image.Image, color: tuple[int, int, int],
             bounds: tuple[int, int, int, int], radius: int) -> None:
    """Draw a rounded rectangle using a clip mask."""
    x0, y0, x1, y1 = bounds
    mask = Image.new("L", img.size, 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle(bounds, radius=radius, fill=255)
    under = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ud = ImageDraw.Draw(under)
    ud.rounded_rectangle(bounds, radius=radius, fill=(*color, 255))
    img.paste(under, (0, 0), mask)


def _text_centered(draw: ImageDraw.ImageDraw, text: str,
                   font: ImageFont.FreeTypeFont, cx: int, cy: int,
                   fill: tuple[int, int, int]) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((cx - tw // 2, cy - th // 2), text, font=font, fill=fill)


# ---------------------------------------------------------------------------
# Card generation
# ---------------------------------------------------------------------------

def score_to_grade(s: int) -> str:
    """Map a 0-100 score to a letter grade (matches scorer.grade)."""
    if s >= 95:
        return "A+"
    if s >= 90:
        return "A"
    if s >= 80:
        return "B"
    if s >= 70:
        return "C"
    if s >= 60:
        return "D"
    return "F"


def _score_color(s: int) -> tuple[int, int, int]:
    if s >= 85:
        return GREEN
    if s >= 65:
        return ACCENT
    if s >= 45:
        return ORANGE
    return RED


def _verdict_text(s: int) -> str:
    if s >= 90:
        return "Battle-tested dbt project. Ship it."
    if s >= 75:
        return "Healthy project. A few polish items."
    if s >= 60:
        return "Decent foundation. Real gaps to close."
    if s >= 40:
        return "Risky. Production data is exposed."
    return "Critical. Do not trust the numbers yet."


# Human-readable dimension names matching the 6 dimensions
DIM_LABELS = [
    "Test Coverage",
    "Documentation",
    "DAG Structure",
    "Naming Conv.",
    "Exposures",
    "Materialization",
]


def generate_card(
    project_name: str,
    score: int,
    *,
    footer_url: str = "dbt-lens-ewpztmgj8ppbnlk5ddyvsy.streamlit.app",
    grade: str | None = None,
    dimension_scores: list[tuple[float, float]] | None = None,
) -> Image.Image:
    """Render a 1200x630 share card."""
    letter = grade if grade is not None else score_to_grade(score)
    sc = _score_color(score)
    verdict = _verdict_text(score)

    # ── Background ──────────────────────────────────────────────────────────
    img = Image.new("RGB", (CARD_W, CARD_H), BG_TOP)
    draw = ImageDraw.Draw(img)

    # Vertical gradient
    px = img.load()  # type: ignore[assignment]
    for y in range(CARD_H):
        t = y / (CARD_H - 1)
        r = int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t)
        gv = int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t)
        for x in range(CARD_W):
            px[x, y] = (r, gv, b)  # type: ignore[index]

    # ── Left gold accent stripe ─────────────────────────────────────────────
    draw.rectangle((0, 0, 5, CARD_H), fill=ACCENT)

    # ── TOP ROW: Brand ─────────────────────────────────────────────────────
    brand_f = _font(_FONT_BOLD, 38)
    draw.text((30, 35), "dbt Lens", font=brand_f, fill=ACCENT)

    tagline_f = _font(_FONT_REG, 22)
    draw.text((30, 85), "Free dbt project health auditor", font=tagline_f, fill=TEXT_SECONDARY)

    # Project name badge
    badge_bg_f = _font(_FONT_REG, 18)
    proj_text = f"  {project_name}  "
    tb = draw.textbbox((0, 0), proj_text, font=badge_bg_f)
    bw = tb[2] - tb[0] + 20
    bh = tb[3] - tb[1] + 12
    bx = CARD_W // 2 - bw // 2
    by = 32
    draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=8, fill=PANEL_BG)
    draw.text((bx + 10, by + 4), proj_text.strip(), font=badge_bg_f, fill=TEXT_SECONDARY)

    # ── LEFT: Score circle ──────────────────────────────────────────────────
    cx, cy = 270, 330
    r_outer = 150

    # Outer glow rings
    for i in range(6):
        rr = r_outer + i * 4
        draw.ellipse(
            [cx - rr, cy - rr, cx + rr, cy + rr],
            outline=(*ACCENT, 50 - i * 8)
        )

    # Main circle
    draw.ellipse(
        [cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer],
        fill=(20, 32, 60), outline=ACCENT, width=5
    )

    # Score number — centered, large
    big_f = _font(_FONT_BOLD, 96)
    score_str = str(score)
    tb = draw.textbbox((0, 0), score_str, font=big_f)
    tw = tb[2] - tb[0]
    draw.text((cx - tw // 2, cy - 68), score_str, font=big_f, fill=sc)

    # "/100" below
    slash_f = _font(_FONT_REG, 26)
    draw.text((cx - 26, cy + 65), "/100", font=slash_f, fill=TEXT_SECONDARY)

    # Grade badge — top-right of circle
    badge_f = _font(_FONT_BOLD, 52)
    bx2 = cx + 105
    by2 = cy - 115
    # shadow
    draw.ellipse([bx2 - 2, by2 + 2, bx2 + 42, by2 + 46], fill=(0, 0, 0, 80))
    # gold circle
    draw.ellipse([bx2 - 4, by2, bx2 + 40, by2 + 44], fill=ACCENT)
    # letter
    draw.text((bx2 - 1, by2 - 5), letter, font=badge_f, fill=(10, 15, 30))

    # Verdict text
    verdict_f = _font(_FONT_REG, 22)
    draw.text((30, 500), verdict, font=verdict_f, fill=TEXT_SECONDARY)

    # ── CTA button — bottom left ────────────────────────────────────────────
    cta_f = _font(_FONT_BOLD, 26)
    btn_x, btn_y = 30, 555
    draw.rounded_rectangle(
        [btn_x + 3, btn_y + 3, btn_x + 400, btn_y + 62], radius=12, fill=(0, 0, 0, 100)
    )
    draw.rounded_rectangle(
        [btn_x, btn_y, btn_x + 400, btn_y + 60], radius=12, fill=ACCENT
    )
    cta_text = "Scan your project free"
    tb = draw.textbbox((0, 0), cta_text, font=cta_f)
    tw = tb[2] - tb[0]
    draw.text((btn_x + 200 - tw // 2, btn_y + 14), cta_text, font=cta_f, fill=(10, 15, 30))

    # ── RIGHT PANEL ─────────────────────────────────────────────────────────
    px_start = 580

    # Panel shadow + fill
    draw.rounded_rectangle(
        [px_start + 5, 25, CARD_W - 20, CARD_H - 20], radius=24, fill=(0, 0, 0, 70)
    )
    draw.rounded_rectangle(
        [px_start, 20, CARD_W - 24, CARD_H - 24], radius=24, fill=PANEL_BG
    )

    # "What you get" header
    head_f = _font(_FONT_BOLD, 28)
    draw.text((px_start + 40, 50), "What you get", font=head_f, fill=TEXT_PRIMARY)

    # Feature list with checkmarks
    features = [
        ("0-100 health score", "across 6 weighted dimensions"),
        ("Interactive DAG", "color-coded by health status"),
        ("Top fixes", "with copy-paste YAML / SQL code"),
        ("Score breakdown", "per dimension with notes"),
    ]
    feat_y = 110
    feat_bold_f = _font(_FONT_BOLD, 21)
    feat_reg_f = _font(_FONT_REG, 21)
    check_f = _font(_FONT_BOLD, 17)

    for label, detail in features:
        # check circle
        draw.ellipse(
            [px_start + 40, feat_y, px_start + 68, feat_y + 28], fill=ACCENT
        )
        draw.text((px_start + 50, feat_y + 2), "✓", font=check_f, fill=(10, 15, 30))
        draw.text((px_start + 80, feat_y), label, font=feat_bold_f, fill=TEXT_PRIMARY)
        tb = draw.textbbox((0, 0), label, font=feat_bold_f)
        fw = tb[2] - tb[0]
        draw.text(
            (px_start + 82 + fw + 6, feat_y), detail,
            font=feat_reg_f, fill=TEXT_SECONDARY
        )
        feat_y += 52

    # Divider
    feat_y += 5
    draw.rectangle(
        (px_start + 40, feat_y, CARD_W - 64, feat_y + 1), fill=(50, 60, 90)
    )

    # "6 SCORED DIMENSIONS" heading
    dim_head_f = _font(_FONT_BOLD, 15)
    draw.text(
        (px_start + 40, feat_y + 14),
        "6 SCORED DIMENSIONS",
        font=dim_head_f, fill=TEXT_SECONDARY
    )

    # Mini bar chart — filled to the actual earned/possible ratio
    feat_y += 52

    # dimension_scores: list of (earned, possible) per dimension
    # Falls back to static weight proportions when not provided
    dims_data: list[tuple[str, float, float]] = []
    if dimension_scores is None:
        bar_weights = [35, 20, 20, 10, 10, 5]
        bar_max_total = 35.0
        for i in range(6):
            dims_data.append((DIM_LABELS[i], bar_weights[i] / bar_max_total, float(bar_weights[i])))
    else:
        for i, (earned, possible) in enumerate(dimension_scores):
            if i < len(DIM_LABELS):
                ratio = earned / possible if possible > 0 else 0.0
                dims_data.append((DIM_LABELS[i], ratio, earned))

    bar_max_w = CARD_W - px_start - 90

    for i, (d_name, fill_ratio, earned) in enumerate(dims_data):
        row = i // 2
        col = i % 2
        col_gap = (CARD_W - px_start - 80) // 2 - 10

        bx3 = px_start + 40 + col * col_gap
        by3 = feat_y + row * 46

        # bar background
        bar_w = bar_max_w // 2 - 10
        bar_h = 18
        draw.rounded_rectangle(
            [bx3, by3 + 18, bx3 + bar_w, by3 + 18 + bar_h],
            radius=6, fill=BAR_BG
        )

        # filled portion — proportional to earned/possible, colored by %
        fill_w = int(bar_w * fill_ratio)
        if fill_w > 0:
            # Color based on this dimension's own score
            dim_pct = int(fill_ratio * 100)
            fill_color = _score_color(dim_pct)
            draw.rounded_rectangle(
                [bx3, by3 + 18, bx3 + fill_w, by3 + 18 + bar_h],
                radius=6, fill=fill_color
            )

        # label with earned value
        d_f = _font(_FONT_REG, 17)
        draw.text((bx3, by3), d_name, font=d_f, fill=TEXT_PRIMARY)

    # CTA button — bottom right panel
    cta2_f = _font(_FONT_BOLD, 22)
    cta2_y = CARD_H - 100
    draw.rounded_rectangle(
        [px_start + 44, cta2_y + 3, CARD_W - 68, cta2_y + 63],
        radius=12, fill=(0, 0, 0, 80)
    )
    draw.rounded_rectangle(
        [px_start + 40, cta2_y, CARD_W - 72, cta2_y + 60],
        radius=12, fill=ACCENT
    )
    cta2_text = f"Try it \u2014 {footer_url}"
    tb2 = draw.textbbox((0, 0), cta2_text, font=cta2_f)
    tb2w = tb2[2] - tb2[0]
    draw.text(
        (
            px_start + 40 + (CARD_W - px_start - 116) // 2 - tb2w // 2 - tb2[0],
            cta2_y + 15,
        ),
        cta2_text, font=cta2_f, fill=(10, 15, 30)
    )

    # ── Footer ─────────────────────────────────────────────────────────────
    footer_f = _font(_FONT_REG, 17)
    ft = "github.com/noobigang/dbt-lens"
    tb_f = draw.textbbox((0, 0), ft, font=footer_f)
    fw = tb_f[2] - tb_f[0]
    draw.text(
        (CARD_W - fw - 36, CARD_H - 42), ft, font=footer_f, fill=TEXT_SECONDARY
    )

    return img


def card_to_bytes(img: Image.Image, *, fmt: str = "PNG") -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def save_card(img: Image.Image, path: str) -> None:
    img.save(path, format="PNG")


__all__ = [
    "generate_card", "card_to_bytes", "save_card",
    "CARD_W", "CARD_H",
]