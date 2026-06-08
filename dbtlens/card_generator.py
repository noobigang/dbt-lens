"""Generate a 1200x630 PNG share card for a project's health score.

The card dimensions (1200x630) are the canonical size for LinkedIn and
Twitter link previews. The output is a :class:`PIL.Image.Image` ready to
be saved to a file or served via ``st.download_button``.
"""

from __future__ import annotations

import io
import math
import os
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

CARD_W = 1200
CARD_H = 630

# Colors
BG_TOP = (15, 23, 42)  # slate-900
BG_BOT = (30, 41, 59)  # slate-800
ACCENT = (212, 175, 55)  # gold — dbt brand
TEXT_PRIMARY = (248, 250, 252)  # slate-50
TEXT_SECONDARY = (148, 163, 184)  # slate-400
WHITE = (255, 255, 255)

# Score color bands
SCORE_RED = (239, 68, 68)
SCORE_YELLOW = (234, 179, 8)
SCORE_GREEN = (34, 197, 94)


# ---------------------------------------------------------------------------
# Font loading
# ---------------------------------------------------------------------------

_FONT_DIRS = [
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"),
    "/usr/share/fonts",
    "/usr/local/share/fonts",
    "/Library/Fonts",
    "/System/Library/Fonts",
]

_FONT_CANDIDATES_BOLD = [
    "arialbd.ttf",
    "Arial-Bold.ttf",
    "Arial Bold.ttf",
    "DejaVuSans-Bold.ttf",
    "Helvetica-Bold.ttf",
]

_FONT_CANDIDATES_REG = [
    "arial.ttf",
    "Arial.ttf",
    "DejaVuSans.ttf",
    "Helvetica.ttf",
]

_FONT_CANDIDATES_LIGHT = [
    "seguisb.ttf",
    "Segoe-UI-Light.ttf",
    "Arial Light.ttf",
    "DejaVuSans.ttf",
]


def _load_font(candidates: Iterable[str], size: int) -> ImageFont.FreeTypeFont:
    """Load the first available TTF from ``candidates``.

    Falls back to PIL's load_default() if nothing matches — that font has
    a fixed size and limited coverage, but the card still renders.
    """
    for d in _FONT_DIRS:
        if not d or not os.path.isdir(d):
            continue
        for c in candidates:
            path = os.path.join(d, c)
            if os.path.isfile(path):
                try:
                    return ImageFont.truetype(path, size=size)
                except OSError:
                    continue
    return ImageFont.load_default()


def _score_color(score: int) -> tuple[int, int, int]:
    if score < 50:
        return SCORE_RED
    if score < 75:
        return SCORE_YELLOW
    return SCORE_GREEN


def _gradient_bg(w: int, h: int) -> Image.Image:
    """Build a vertical gradient from BG_TOP to BG_BOT."""
    img = Image.new("RGB", (w, h), BG_TOP)
    px = img.load()
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(BG_TOP[0] * (1 - t) + BG_BOT[0] * t)
        g = int(BG_TOP[1] * (1 - t) + BG_BOT[1] * t)
        b = int(BG_TOP[2] * (1 - t) + BG_BOT[2] * t)
        for x in range(w):
            px[x, y] = (r, g, b)
    return img


def _draw_text_centered(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    center: tuple[int, int],
    fill: tuple[int, int, int],
) -> None:
    """Draw text centered on (cx, cy)."""
    bbox = draw.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = center[0] - w // 2 - bbox[0]
    y = center[1] - h // 2 - bbox[1]
    draw.text((x, y), text, font=font, fill=fill)


def _draw_text_left(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    left: int,
    top: int,
    fill: tuple[int, int, int],
) -> tuple[int, int]:
    """Draw text at (left, top); returns (w, h) of the rendered glyphs."""
    bbox = draw.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((left - bbox[0], top - bbox[1]), text, font=font, fill=fill)
    return w, h


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_card(
    project_name: str,
    score: int,
    *,
    footer_url: str = "dbt-lens.streamlit.app",
    grade: str | None = None,
) -> Image.Image:
    """Render the 1200x630 share card.

    This is a PRODUCT DEMO card — it shows both the tool AND an example
    score so people can see what the output looks like. The viral hook
    is "I built this / here's a useful tool" not "here's my grade".
    """
    img = _gradient_bg(CARD_W, CARD_H)
    draw = ImageDraw.Draw(img)

    # ── Accent stripe on left edge ─────────────────────────────────────
    draw.rectangle((0, 0, 10, CARD_H), fill=ACCENT)

    # ── TOP LEFT — Brand + tagline ──────────────────────────────────────

    brand_font = _load_font(_FONT_CANDIDATES_BOLD, 34)
    draw.text((46, 44), "dbt Lens", font=brand_font, fill=ACCENT)

    tagline_font = _load_font(_FONT_CANDIDATES_REG, 20)
    draw.text((46, 90), "Free dbt project health auditor", font=tagline_font, fill=TEXT_SECONDARY)

    # ── LEFT — Example score preview ───────────────────────────────────

    # Thin divider
    draw.rectangle((46, 130, 580, 131), fill=(51, 65, 85))

    # "Example output" label
    label_font = _load_font(_FONT_CANDIDATES_BOLD, 14)
    draw.text((46, 142), "EXAMPLE OUTPUT", font=label_font, fill=TEXT_SECONDARY)

    # Big score
    big_score_font = _load_font(_FONT_CANDIDATES_BOLD, 120)
    score_color = _score_color(score)
    draw.text((46, 165), str(score), font=big_score_font, fill=score_color)

    # "/100"
    slash_font = _load_font(_FONT_CANDIDATES_REG, 40)
    bbox = draw.textbbox((0, 0), str(score), font=big_score_font)
    sw = bbox[2] - bbox[0]
    draw.text((46 + sw + 14, 225), "/100", font=slash_font, fill=TEXT_SECONDARY)

    # Grade circle
    if grade:
        grade_font = _load_font(_FONT_CANDIDATES_BOLD, 80)
        badge_r = 40
        badge_cx = 46 + sw + 100
        badge_cy = 220
        draw.ellipse(
            [badge_cx - badge_r, badge_cy - badge_r,
             badge_cx + badge_r, badge_cy + badge_r],
            fill=ACCENT,
        )
        tb_g = draw.textbbox((0, 0), grade, font=grade_font)
        gw = tb_g[2] - tb_g[0]
        gh = tb_g[3] - tb_g[1]
        draw.text(
            (badge_cx - gw // 2 - tb_g[0], badge_cy - gh // 2 - tb_g[1]),
            grade, font=grade_font, fill=(15, 23, 42)
        )

    # Verdict below score
    verdict = _verdict_for(score)
    verdict_font = _load_font(_FONT_CANDIDATES_REG, 20)
    draw.text((46, 320), verdict, font=verdict_font, fill=TEXT_SECONDARY)

    # "6 dimensions" stat row below verdict
    dim_font = _load_font(_FONT_CANDIDATES_BOLD, 18)
    dim_label = _load_font(_FONT_CANDIDATES_REG, 16)
    dim_items = [
        ("6", "dimensions"),
        ("0", "login"),
        ("100%", "client-side"),
    ]
    dx = 46
    for val, lbl in dim_items:
        draw.text((dx, 360), val, font=dim_font, fill=ACCENT)
        tb_d = draw.textbbox((0, 0), val, font=dim_font)
        vw2 = tb_d[2] - tb_d[0]
        draw.text((dx + vw2 + 4, 362), lbl, font=dim_label, fill=TEXT_SECONDARY)
        dx += 130

    # ── CTA at bottom left ─────────────────────────────────────────────

    cta_x, cta_y = 46, CARD_H - 100
    cta_font = _load_font(_FONT_CANDIDATES_BOLD, 22)
    draw.rounded_rectangle([cta_x, cta_y, cta_x + 350, cta_y + 58],
                            radius=12, fill=ACCENT)
    tb_cta = draw.textbbox((0, 0), "Scan your project free", font=cta_font)
    ctw = tb_cta[2] - tb_cta[0]
    draw.text((cta_x + 175 - ctw // 2 - tb_cta[0], cta_y + 14),
              "Scan your project free", font=cta_font, fill=(15, 23, 42))

    # ── RIGHT PANEL — What it does ─────────────────────────────────────

    panel_x = 600

    draw.rounded_rectangle(
        (panel_x, 100, CARD_W - 30, CARD_H - 30),
        radius=18, fill=(30, 41, 59)
    )

    # Panel header
    panel_head_font = _load_font(_FONT_CANDIDATES_BOLD, 22)
    draw.text((panel_x + 36, 124), "What you get", font=panel_head_font, fill=TEXT_PRIMARY)

    # Feature list with icons
    features = [
        ("0-100 health score", "across 6 weighted dimensions"),
        ("Interactive DAG", "color-coded by health status"),
        ("Top 3 fixes", "with copy-paste YAML/SQL code"),
        ("Score breakdown", "per dimension with notes"),
    ]
    feat_y = 175
    feat_bold = _load_font(_FONT_CANDIDATES_BOLD, 18)
    feat_reg = _load_font(_FONT_CANDIDATES_REG, 18)
    for label, detail in features:
        # Check circle
        draw.ellipse([panel_x + 36, feat_y, panel_x + 58, feat_y + 22], fill=ACCENT)
        check_f = _load_font(_FONT_CANDIDATES_BOLD, 13)
        draw.text((panel_x + 44, feat_y + 1), "✓", font=check_f, fill=(15, 23, 42))
        draw.text((panel_x + 70, feat_y), label, font=feat_bold, fill=TEXT_PRIMARY)
        tb_f = draw.textbbox((0, 0), label, font=feat_bold)
        fw = tb_f[2] - tb_f[0]
        draw.text((panel_x + 70 + fw + 8, feat_y), detail, font=feat_reg, fill=TEXT_SECONDARY)
        feat_y += 44

    # "6 dimensions" in panel
    draw.rectangle((panel_x + 36, feat_y + 8, CARD_W - 66, feat_y + 9), fill=(51, 65, 85))
    dim_heading = _load_font(_FONT_CANDIDATES_BOLD, 15)
    draw.text((panel_x + 36, feat_y + 22), "6 SCORED DIMENSIONS", font=dim_heading, fill=TEXT_SECONDARY)

    dims = [
        ("Test Coverage", "35 pts"),
        ("Documentation", "20 pts"),
        ("DAG Structure", "20 pts"),
        ("Naming", "10 pts"),
        ("Exposures", "10 pts"),
        ("Materialization", "5 pts"),
    ]
    col_w = (CARD_W - panel_x - 72) // 3
    for i, (d_name, d_pts) in enumerate(dims):
        cx = panel_x + 36 + (i % 3) * (col_w + 8)
        cy = feat_y + 50 + (i // 3) * 40
        draw.rounded_rectangle([cx, cy, cx + col_w, cy + 32],
                                radius=6, fill=(51, 65, 85))
        d_font = _load_font(_FONT_CANDIDATES_REG, 14)
        draw.text((cx + 8, cy + 7), d_name, font=d_font, fill=TEXT_PRIMARY)
        tb_d = draw.textbbox((0, 0), d_name, font=d_font)
        dw = tb_d[2] - tb_d[0]
        draw.text((cx + col_w - 8 - (len(d_pts) * 9), cy + 7), d_pts,
                  font=d_font, fill=ACCENT)

    # CTA button at bottom of panel
    cta2_y = CARD_H - 100
    cta2_font = _load_font(_FONT_CANDIDATES_BOLD, 22)
    draw.rounded_rectangle(
        [panel_x + 36, cta2_y, panel_x + 36 + 460, cta2_y + 58],
        radius=12, fill=ACCENT
    )
    tb2 = draw.textbbox((0, 0), "Try it — dbt-lens.streamlit.app", font=cta2_font)
    tb2w = tb2[2] - tb2[0]
    draw.text((panel_x + 36 + 230 - tb2w // 2 - tb2[0], cta2_y + 14),
              "Try it — dbt-lens.streamlit.app", font=cta2_font, fill=(15, 23, 42))

    # ── Footer ─────────────────────────────────────────────────────────
    footer_font = _load_font(_FONT_CANDIDATES_REG, 16)
    footer_text = "github.com/noobigang/dbt-lens"
    tb_f = draw.textbbox((0, 0), footer_text, font=footer_font)
    fw = tb_f[2] - tb_f[0]
    draw.text((CARD_W - fw - 40, CARD_H - 42), footer_text,
              font=footer_font, fill=TEXT_SECONDARY)

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
    """Serialize a card image to bytes (in-memory)."""
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def save_card(img: Image.Image, path: str) -> None:
    """Save a card image to disk as PNG."""
    img.save(path, format="PNG")


__all__ = [
    "generate_card",
    "card_to_bytes",
    "save_card",
    "CARD_W",
    "CARD_H",
]
