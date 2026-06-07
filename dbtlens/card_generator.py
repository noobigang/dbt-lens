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
    footer_url: str = "dbtlens.streamlit.app",
    grade: str | None = None,
) -> Image.Image:
    """Render the 1200x630 share card for a project.

    Args:
        project_name: The project name to display. Will be truncated to
            50 characters with an ellipsis if longer.
        score: 0..100 score.
        footer_url: The text shown in the bottom-right footer.
        grade: Optional letter grade (e.g. "B") to draw next to the score.

    Returns:
        A :class:`PIL.Image.Image` in RGB mode.
    """
    name = (project_name or "Your dbt Project").strip() or "Your dbt Project"
    if len(name) > 50:
        name = name[:47] + "..."

    img = _gradient_bg(CARD_W, CARD_H)
    draw = ImageDraw.Draw(img)

    # --- Accent stripe on left edge ---
    draw.rectangle((0, 0, 6, CARD_H), fill=ACCENT)

    # --- Top-left brand mark ---
    brand_font = _load_font(_FONT_CANDIDATES_BOLD, 26)
    draw.text((48, 42), "dbt Lens", font=brand_font, fill=ACCENT)
    sub_brand = _load_font(_FONT_CANDIDATES_REG, 17)
    draw.text((48, 78), "Health Score", font=sub_brand, fill=TEXT_SECONDARY)

    # --- Divider line ---
    draw.rectangle((48, 110, 560, 111), fill=(100, 116, 139))

    # --- Big score (center-left) ---
    big_font = _load_font(_FONT_CANDIDATES_BOLD, 200)
    score_text = str(score)
    _draw_text_centered(draw, score_text, big_font, (300, 340), _score_color(score))

    # --- "/100" denominator ---
    slash_font = _load_font(_FONT_CANDIDATES_REG, 52)
    bbox = draw.textbbox((0, 0), score_text, font=big_font)
    score_w = bbox[2] - bbox[0]
    _draw_text_left(draw, "/100", slash_font, 300 + score_w // 2 + 30, 340, TEXT_SECONDARY)

    # --- Grade badge ---
    if grade:
        grade_font = _load_font(_FONT_CANDIDATES_BOLD, 110)
        _draw_text_centered(
            draw, grade, grade_font, (300 + score_w // 2 + 280, 340), ACCENT
        )

    # --- Project name ---
    name_font = _load_font(_FONT_CANDIDATES_BOLD, 42)
    _draw_text_centered(draw, name, name_font, (300, 490), TEXT_PRIMARY)

    # --- Verdict tagline ---
    verdict = _verdict_for(score)
    verdict_font = _load_font(_FONT_CANDIDATES_LIGHT, 21)
    _draw_text_centered(draw, verdict, verdict_font, (300, 545), TEXT_SECONDARY)

    # --- Right panel: score band + scan badge ---
    panel_x = 660
    # Panel background
    draw.rounded_rectangle(
        (panel_x, 120, panel_x + 500, CARD_H - 50),
        radius=16,
        fill=(30, 41, 59),
    )

    # Score band section
    bar_x0, bar_y0 = panel_x + 40, 170
    bar_w, bar_h = 400, 28

    band_label_font = _load_font(_FONT_CANDIDATES_BOLD, 17)
    draw.text((bar_x0, bar_y0 - 30), "SCORE", font=band_label_font, fill=TEXT_SECONDARY)

    # track
    draw.rounded_rectangle(
        (bar_x0, bar_y0, bar_x0 + bar_w, bar_y0 + bar_h), radius=14, fill=(51, 65, 85)
    )
    fill_w = max(4, int(bar_w * (score / 100.0)))
    draw.rounded_rectangle(
        (bar_x0, bar_y0, bar_x0 + fill_w, bar_y0 + bar_h),
        radius=14,
        fill=_score_color(score),
    )
    # tick labels
    tick_font = _load_font(_FONT_CANDIDATES_REG, 15)
    for tick in (0, 25, 50, 75, 100):
        tx = bar_x0 + int(bar_w * (tick / 100.0))
        draw.text((tx - 5, bar_y0 + bar_h + 6), str(tick), font=tick_font, fill=TEXT_SECONDARY)

    # Grade + verdict in panel
    if grade:
        grade_big_font = _load_font(_FONT_CANDIDATES_BOLD, 80)
        _draw_text_centered(draw, grade, grade_big_font, (panel_x + 250, 330), ACCENT)
        grade_label_font = _load_font(_FONT_CANDIDATES_REG, 16)
        draw.text((panel_x + 40, 390), "GRADE", font=grade_label_font, fill=TEXT_SECONDARY)

    verdict_panel_font = _load_font(_FONT_CANDIDATES_LIGHT, 18)
    _draw_text_centered(draw, verdict, verdict_panel_font, (panel_x + 250, 450), TEXT_SECONDARY)

    # Scan badge
    draw.rounded_rectangle(
        (panel_x + 40, 490, panel_x + 460, 540),
        radius=10,
        fill=(212, 175, 55, 30),
    )
    scan_font = _load_font(_FONT_CANDIDATES_BOLD, 16)
    draw.text(
        (panel_x + 60, 502),
        f"🔬  Scanned with dbt Lens",
        font=scan_font,
        fill=ACCENT,
    )

    # --- Footer URL (bottom right) ---
    footer_font = _load_font(_FONT_CANDIDATES_REG, 18)
    bbox = draw.textbbox((0, 0), footer_url, font=footer_font)
    fw = bbox[2] - bbox[0]
    draw.text(
        (CARD_W - fw - 48, CARD_H - 48), footer_url, font=footer_font, fill=TEXT_SECONDARY
    )

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
