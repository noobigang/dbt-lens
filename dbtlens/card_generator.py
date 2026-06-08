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

    # ── Accent stripe on left edge ─────────────────────────────────────
    draw.rectangle((0, 0, 8, CARD_H), fill=ACCENT)

    # ── LEFT SIDE — Brand + Score + Grade + Project name ────────────────

    # Brand name at top-left
    brand_font = _load_font(_FONT_CANDIDATES_BOLD, 28)
    draw.text((46, 40), "dbt Lens", font=brand_font, fill=ACCENT)

    # Big score number — large, readable, left-aligned
    big_font = _load_font(_FONT_CANDIDATES_BOLD, 180)
    score_color = _score_color(score)
    # Draw score at a fixed left position so it's readable
    draw.text((46, 150), str(score), font=big_font, fill=score_color)

    # "/100" beside the score
    slash_font = _load_font(_FONT_CANDIDATES_REG, 56)
    bbox = draw.textbbox((0, 0), str(score), font=big_font)
    score_w = bbox[2] - bbox[0]
    draw.text((46 + score_w + 16, 240), "/100", font=slash_font, fill=TEXT_SECONDARY)

    # Grade badge — to the right of the score
    if grade:
        grade_font = _load_font(_FONT_CANDIDATES_BOLD, 120)
        # Position grade to the right of the score number
        grade_x = 46 + score_w + 120
        # Draw grade in a circle-ish badge
        badge_r = 55
        badge_cx = grade_x + 60
        badge_cy = 290
        draw.ellipse(
            [badge_cx - badge_r, badge_cy - badge_r,
             badge_cx + badge_r, badge_cy + badge_r],
            fill=ACCENT,
        )
        # Draw grade letter centered
        bbox_g = draw.textbbox((0, 0), grade, font=grade_font)
        gw = bbox_g[2] - bbox_g[0]
        gh = bbox_g[3] - bbox_g[1]
        draw.text(
            (badge_cx - gw // 2 - bbox_g[0], badge_cy - gh // 2 - bbox_g[1]),
            grade, font=grade_font, fill=(15, 23, 42)
        )

    # Project name below score
    name_font = _load_font(_FONT_CANDIDATES_BOLD, 38)
    draw.text((46, 420), name, font=name_font, fill=TEXT_PRIMARY)

    # Verdict below project name
    verdict = _verdict_for(score)
    verdict_font = _load_font(_FONT_CANDIDATES_REG, 22)
    draw.text((46, 472), verdict, font=verdict_font, fill=TEXT_SECONDARY)

    # ── RIGHT SIDE — Progress bar + Scan badge ─────────────────────────

    panel_x = 660
    # Panel background
    draw.rounded_rectangle(
        (panel_x, 100, CARD_W - 30, CARD_H - 30),
        radius=18,
        fill=(30, 41, 59),
    )

    # "YOUR SCORE" label
    label_font = _load_font(_FONT_CANDIDATES_BOLD, 16)
    draw.text((panel_x + 36, 130), "YOUR SCORE", font=label_font, fill=TEXT_SECONDARY)

    # Progress bar track
    bar_x0, bar_y0 = panel_x + 36, 170
    bar_w, bar_h = CARD_W - panel_x - 72, 32

    draw.rounded_rectangle(
        (bar_x0, bar_y0, bar_x0 + bar_w, bar_y0 + bar_h),
        radius=16, fill=(51, 65, 85)
    )
    fill_w = max(8, int(bar_w * (score / 100.0)))
    draw.rounded_rectangle(
        (bar_x0, bar_y0, bar_x0 + fill_w, bar_y0 + bar_h),
        radius=16, fill=score_color
    )

    # Tick labels below bar
    tick_font = _load_font(_FONT_CANDIDATES_REG, 14)
    for tick in (0, 25, 50, 75, 100):
        tx = bar_x0 + int(bar_w * (tick / 100.0))
        lbl = str(tick)
        tb = draw.textbbox((0, 0), lbl, font=tick_font)
        lw = tb[2] - tb[0]
        draw.text((tx - lw // 2 - tb[0], bar_y0 + bar_h + 8), lbl,
                  font=tick_font, fill=TEXT_SECONDARY)

    # Grade — only show on left (it's the hero). Skip duplicate on right.
    # Right panel focuses on the score bar and call to action.

    # "Open in dbt Lens" CTA badge — bottom of panel
    cta_y = CARD_H - 90
    cta_font = _load_font(_FONT_CANDIDATES_BOLD, 22)
    draw.rounded_rectangle(
        (panel_x + 36, cta_y, panel_x + 36 + 460, cta_y + 56),
        radius=12, fill=ACCENT
    )
    # Center text in button
    tb_cta = draw.textbbox((0, 0), "Open in dbt Lens", font=cta_font)
    cta_tw = tb_cta[2] - tb_cta[0]
    draw.text((panel_x + 36 + 230 - cta_tw // 2 - tb_cta[0], cta_y + 14),
              "Open in dbt Lens", font=cta_font, fill=(15, 23, 42))

    # ── Footer URL (bottom right corner) ────────────────────────────────
    footer_font = _load_font(_FONT_CANDIDATES_REG, 18)
    bbox = draw.textbbox((0, 0), footer_url, font=footer_font)
    fw = bbox[2] - bbox[0]
    draw.text((CARD_W - fw - 40, CARD_H - 45), footer_url,
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
