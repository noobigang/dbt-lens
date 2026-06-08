"""Generate a 1200x630 PNG share card for dbt Lens.

Card dimensions match LinkedIn/Twitter link preview spec (1200x630).
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
BG_TOP = (10, 14, 25)       # deep navy
BG_BOT = (20, 28, 50)        # dark blue
ACCENT = (212, 175, 55)     # gold
ACCENT_DARK = (155, 128, 38) # darker gold for borders
TEXT_PRIMARY = (248, 250, 252)
TEXT_SECONDARY = (100, 116, 139)
WHITE = (255, 255, 255)
PANEL_BG = (30, 40, 65)
DIM_BG = (40, 50, 80)
GREEN = (34, 197, 94)


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
    # paste with alpha
    under = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ud = ImageDraw.Draw(under)
    ud.rounded_rectangle(bounds, radius=radius, fill=(*color, 255))
    img.paste(under, (0, 0), mask)


def _text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont,
          x: int, y: int, fill: tuple[int, int, int]) -> None:
    draw.text((x, y), text, font=font, fill=fill)


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

def generate_card(
    project_name: str,
    score: int,
    *,
    footer_url: str = "dbt-lens.streamlit.app",
    grade: str | None = None,
) -> Image.Image:
    """Render a 1200x630 share card.

    This is a TOOL PROMO card — shows a compelling example score (78/B)
    so people see the value immediately. Viral hook = "I built this / try it"
    not "here's my personal score".
    """
    # ── Background ──────────────────────────────────────────────────────────
    img = Image.new("RGB", (CARD_W, CARD_H), BG_TOP)
    draw = ImageDraw.Draw(img)
    # Vertical gradient
    px = img.load()  # type: ignore[assignment]
    for y in range(CARD_H):
        t = y / (CARD_H - 1)
        r = int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t)
        for x in range(CARD_W):
            px[x, y] = (r, g, b)  # type: ignore[index]

    # ── Left accent stripe ──────────────────────────────────────────────────
    draw.rectangle((0, 0, 7, CARD_H), fill=ACCENT)

    # ── TOP ROW: Brand ─────────────────────────────────────────────────────
    brand_f = _font(_FONT_BOLD, 36)
    draw.text((40, 40), "dbt Lens", font=brand_f, fill=ACCENT)

    tagline_f = _font(_FONT_REG, 22)
    draw.text((40, 88), "Free dbt project health auditor", font=tagline_f, fill=TEXT_SECONDARY)

    # ── Divider ────────────────────────────────────────────────────────────
    draw.rectangle((40, 130, 580, 131), fill=(50, 60, 90))

    # "EXAMPLE OUTPUT" label
    label_f = _font(_FONT_BOLD, 15)
    draw.text((40, 142), "EXAMPLE OUTPUT", font=label_f, fill=TEXT_SECONDARY)

    # ── LEFT: Big score circle ─────────────────────────────────────────────
    # Draw score circle background
    cx, cy = 210, 300
    r_outer = 130
    # outer glow ring
    for i in range(4):
        rr = r_outer + i * 3
        draw.ellipse([cx - rr, cy - rr, cx + rr, cy + rr],
                     outline=(*ACCENT, 60 - i * 15))

    # score circle
    draw.ellipse([cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer],
                 fill=(30, 40, 65), outline=ACCENT, width=4)

    # Example score: 78
    big_f = _font(_FONT_BOLD, 90)
    draw.text((cx - 60, cy - 65), "78", font=big_f, fill=GREEN)

    # "/100" below circle
    slash_f = _font(_FONT_REG, 24)
    draw.text((cx - 22, cy + 60), "/100", font=slash_f, fill=TEXT_SECONDARY)

    # Grade badge
    badge_f = _font(_FONT_BOLD, 48)
    bx, by = 330, 230
    draw.ellipse([bx - 36, by - 36, bx + 36, by + 36], fill=ACCENT)
    draw.text((bx - 16, by - 28), "B", font=badge_f, fill=(15, 23, 42))

    # Verdict
    verdict_f = _font(_FONT_REG, 22)
    draw.text((40, 465), "Healthy. A few polish items.", font=verdict_f, fill=TEXT_SECONDARY)

    # Stats row
    stat_val_f = _font(_FONT_BOLD, 22)
    stat_lbl_f = _font(_FONT_REG, 18)
    stats = [("6", "dimensions"), ("0", "login"), ("100%", "client-side")]
    sx = 40
    for val, lbl in stats:
        draw.text((sx, 510), val, font=stat_val_f, fill=ACCENT)
        tb = draw.textbbox((0, 0), val, font=stat_val_f)
        draw.text((sx + (tb[2] - tb[0]) + 6, 513), lbl, font=stat_lbl_f, fill=TEXT_SECONDARY)
        sx += 150

    # CTA button — bottom left
    cta_f = _font(_FONT_BOLD, 24)
    btn_x, btn_y = 40, CARD_H - 80
    # shadow
    draw.rounded_rectangle([btn_x + 3, btn_y + 3, btn_x + 380, btn_y + 63],
                            radius=12, fill=(0, 0, 0, 80))
    draw.rounded_rectangle([btn_x, btn_y, btn_x + 380, btn_y + 60],
                            radius=12, fill=ACCENT)
    tb = draw.textbbox((0, 0), "Scan your project free", font=cta_f)
    tw = tb[2] - tb[0]
    draw.text((btn_x + 190 - tw // 2 - tb[0], btn_y + 14),
              "Scan your project free", font=cta_f, fill=(15, 23, 42))

    # ── RIGHT PANEL ─────────────────────────────────────────────────────────
    px_start = 600
    # panel shadow
    draw.rounded_rectangle([px_start + 4, 100 + 4, CARD_W - 24, CARD_H - 24],
                            radius=20, fill=(0, 0, 0, 60))
    draw.rounded_rectangle([px_start, 100, CARD_W - 28, CARD_H - 28],
                            radius=20, fill=PANEL_BG)

    # "What you get" header
    head_f = _font(_FONT_BOLD, 26)
    draw.text((px_start + 40, 130), "What you get", font=head_f, fill=TEXT_PRIMARY)

    # Feature list
    features = [
        ("0-100 health score", "across 6 weighted dimensions"),
        ("Interactive DAG", "color-coded by health status"),
        ("Top 3 fixes", "with copy-paste YAML/SQL code"),
        ("Score breakdown", "per dimension with notes"),
    ]
    feat_y = 180
    feat_bold_f = _font(_FONT_BOLD, 20)
    feat_reg_f = _font(_FONT_REG, 20)
    check_f = _font(_FONT_BOLD, 16)

    for label, detail in features:
        # check circle
        draw.ellipse([px_start + 40, feat_y, px_start + 66, feat_y + 26],
                     fill=ACCENT)
        draw.text((px_start + 50, feat_y + 2), "✓", font=check_f, fill=(15, 23, 42))
        draw.text((px_start + 78, feat_y), label, font=feat_bold_f, fill=TEXT_PRIMARY)
        tb = draw.textbbox((0, 0), label, font=feat_bold_f)
        fw = tb[2] - tb[0]
        draw.text((px_start + 80 + fw + 8, feat_y), detail,
                  font=feat_reg_f, fill=TEXT_SECONDARY)
        feat_y += 52

    # Divider
    feat_y += 8
    draw.rectangle((px_start + 40, feat_y, CARD_W - 68, feat_y + 1),
                   fill=(50, 60, 90))

    # "6 SCORED DIMENSIONS" heading
    dim_head_f = _font(_FONT_BOLD, 15)
    draw.text((px_start + 40, feat_y + 16), "6 SCORED DIMENSIONS",
              font=dim_head_f, fill=TEXT_SECONDARY)

    # Dimension pills — cleaner, bigger
    dims = [
        ("Test Coverage", "35 pts"),
        ("Documentation", "20 pts"),
        ("DAG Structure", "20 pts"),
        ("Naming", "10 pts"),
        ("Exposures", "10 pts"),
        ("Materialization", "5 pts"),
    ]
    feat_y += 52
    col_w = (CARD_W - px_start - 80) // 3 - 8

    for i, (d_name, d_pts) in enumerate(dims):
        col = i % 3
        row = i // 3
        cx = px_start + 40 + col * (col_w + 8)
        cy = feat_y + row * 52
        draw.rounded_rectangle([cx, cy, cx + col_w, cy + 44],
                                radius=8, fill=DIM_BG)
        d_f = _font(_FONT_REG, 17)
        draw.text((cx + 12, cy + 8), d_name, font=d_f, fill=TEXT_PRIMARY)
        tb = draw.textbbox((0, 0), d_pts, font=d_f)
        draw.text((cx + col_w - (tb[2] - tb[0]) - 12, cy + 8),
                  d_pts, font=d_f, fill=ACCENT)

    # CTA button — bottom right panel
    cta2_f = _font(_FONT_BOLD, 22)
    cta2_y = CARD_H - 120
    # shadow
    draw.rounded_rectangle([px_start + 44, cta2_y + 3, CARD_W - 72, cta2_y + 63],
                            radius=12, fill=(0, 0, 0, 80))
    draw.rounded_rectangle([px_start + 40, cta2_y, CARD_W - 76, cta2_y + 60],
                            radius=12, fill=ACCENT)
    cta2_text = "Try it — dbt-lens.streamlit.app"
    tb2 = draw.textbbox((0, 0), cta2_text, font=cta2_f)
    tb2w = tb2[2] - tb2[0]
    draw.text((px_start + 40 + (CARD_W - px_start - 116) // 2 - tb2w // 2 - tb2[0],
               cta2_y + 15), cta2_text, font=cta2_f, fill=(15, 23, 42))

    # ── Footer ─────────────────────────────────────────────────────────────
    footer_f = _font(_FONT_REG, 18)
    ft = "github.com/noobigang/dbt-lens"
    tb_f = draw.textbbox((0, 0), ft, font=footer_f)
    fw = tb_f[2] - tb_f[0]
    draw.text((CARD_W - fw - 40, CARD_H - 46), ft, font=footer_f, fill=TEXT_SECONDARY)

    return img


def _verdict_for(score: int) -> str:
    if score >= 90:
        return "Battle-tested dbt project."
    if score >= 75:
        return "Healthy. A few polish items."
    if score >= 60:
        return "Decent foundation, real gaps to close."
    if score >= 40:
        return "Risky. Production data is exposed."
    return "Critical. Don't trust the numbers yet."


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