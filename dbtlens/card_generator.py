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
    """Render the 1200x630 share card for a project.

    This is a TOOL PROMO card — not a personal score card.
    The viral loop is "I built this / here's a useful tool", not "here's my grade".
    Nobody posts their internal code health score on LinkedIn.
    """
    img = _gradient_bg(CARD_W, CARD_H)
    draw = ImageDraw.Draw(img)

    # ── Accent stripe on left edge ─────────────────────────────────────
    draw.rectangle((0, 0, 10, CARD_H), fill=ACCENT)

    # ── TOP SECTION — Brand + Headline ─────────────────────────────────

    brand_font = _load_font(_FONT_CANDIDATES_BOLD, 34)
    draw.text((46, 44), "dbt Lens", font=brand_font, fill=ACCENT)

    tagline_font = _load_font(_FONT_CANDIDATES_REG, 20)
    draw.text((46, 92), "Free dbt project health auditor", font=tagline_font, fill=TEXT_SECONDARY)

    # Thin divider
    draw.rectangle((46, 132, CARD_W - 46, 133), fill=(51, 65, 85))

    # ── MAIN COPY — What it does ─────────────────────────────────────────

    headline_font = _load_font(_FONT_CANDIDATES_BOLD, 52)
    draw.text((46, 155),
              "Drop your manifest.json.",
              font=headline_font, fill=TEXT_PRIMARY)

    sub_font = _load_font(_FONT_CANDIDATES_REG, 30)
    draw.text((46, 222),
              "Get a 0-100 health score, interactive DAG,",
              font=sub_font, fill=TEXT_SECONDARY)
    draw.text((46, 262),
              "and know exactly what to fix next.",
              font=sub_font, fill=TEXT_SECONDARY)

    # ── FEATURE BULLETS — 3 reasons to use it ─────────────────────────

    bullet_font = _load_font(_FONT_CANDIDATES_REG, 22)
    bullet_bold = _load_font(_FONT_CANDIDATES_BOLD, 22)
    bullet_y = 330
    bullets = [
        ("6 dimensions scored", "test coverage, docs, DAG, naming, exposures, materialization"),
        ("Interactive DAG", "color-coded by health — zoom, drag, explore"),
        ("Top 3 fixes", "copy-paste code snippets to improve your score"),
    ]
    for label, detail in bullets:
        # Checkmark icon (simple circle with check shape)
        bx, by = 46, bullet_y
        draw.ellipse([bx, by, bx + 26, by + 26], fill=ACCENT)
        # Draw a simple checkmark in the circle
        check_font = _load_font(_FONT_CANDIDATES_BOLD, 16)
        draw.text((bx + 5, by + 3), "✓", font=check_font, fill=(15, 23, 42))

        lb = draw.textbbox((0, 0), label, font=bullet_bold)
        lw = lb[2] - lb[0]
        draw.text((bx + 36, bullet_y), label, font=bullet_bold, fill=TEXT_PRIMARY)

        detail_font = _load_font(_FONT_CANDIDATES_REG, 22)
        draw.text((bx + 36 + lw + 12, bullet_y), detail, font=detail_font, fill=TEXT_SECONDARY)
        bullet_y += 46

    # ── CTA BADGE — prominent bottom-left ───────────────────────────────

    cta_x, cta_y = 46, CARD_H - 110
    cta_font = _load_font(_FONT_CANDIDATES_BOLD, 24)
    draw.rounded_rectangle([cta_x, cta_y, cta_x + 380, cta_y + 62],
                            radius=12, fill=ACCENT)
    cta_tb = draw.textbbox((0, 0), "Scan your project for free", font=cta_font)
    cta_tw = cta_tb[2] - cta_tb[0]
    draw.text((cta_x + 190 - cta_tw // 2 - cta_tb[0], cta_y + 16),
              "Scan your project for free", font=cta_font, fill=(15, 23, 42))

    # ── RIGHT PANEL — Product visual / social proof ─────────────────────

    panel_x = 660

    # Panel background
    draw.rounded_rectangle(
        (panel_x, 100, CARD_W - 30, CARD_H - 30),
        radius=18, fill=(30, 41, 59)
    )

    # "Open-source" badge
    badge_font = _load_font(_FONT_CANDIDATES_BOLD, 16)
    draw.rounded_rectangle([panel_x + 36, 130, panel_x + 180, 162],
                            radius=8, fill=(34, 197, 94, 40))
    draw.text((panel_x + 54, 133), "OPEN SOURCE", font=badge_font, fill=(34, 197, 94))

    # "MIT License"
    draw.rounded_rectangle([panel_x + 196, 130, panel_x + 320, 162],
                            radius=8, fill=(212, 175, 55, 40))
    draw.text((panel_x + 214, 133), "MIT LICENSE", font=badge_font, fill=ACCENT)

    # "No login" badge
    draw.rounded_rectangle([panel_x + 36, 172, panel_x + 160, 204],
                            radius=8, fill=(59, 130, 246, 40))
    draw.text((panel_x + 54, 175), "NO LOGIN", font=badge_font, fill=(59, 130, 246))

    # "Client-side" badge
    draw.rounded_rectangle([panel_x + 176, 172, panel_x + 320, 204],
                            radius=8, fill=(168, 85, 247, 40))
    draw.text((panel_x + 194, 175), "CLIENT-SIDE", font=badge_font, fill=(168, 85, 247))

    # Stats row — social proof numbers
    stats_y = 250
    stats = [
        ("6", "dimensions"),
        ("0", "login required"),
        ("100%", "client-side"),
    ]
    stat_w = (CARD_W - panel_x - 72) // 3
    stat_val_font = _load_font(_FONT_CANDIDATES_BOLD, 42)
    stat_label_font = _load_font(_FONT_CANDIDATES_REG, 15)
    for i, (val, label) in enumerate(stats):
        sx = panel_x + 36 + i * (stat_w + 12)
        draw.rounded_rectangle([sx, stats_y, sx + stat_w, stats_y + 90],
                                radius=10, fill=(51, 65, 85))
        tb = draw.textbbox((0, 0), val, font=stat_val_font)
        vw = tb[2] - tb[0]
        draw.text((sx + stat_w // 2 - vw // 2 - tb[0], stats_y + 12),
                  val, font=stat_val_font, fill=ACCENT)
        tb2 = draw.textbbox((0, 0), label, font=stat_label_font)
        lw2 = tb2[2] - tb2[0]
        draw.text((sx + stat_w // 2 - lw2 // 2 - tb2[0], stats_y + 62),
                  label, font=stat_label_font, fill=TEXT_SECONDARY)

    # CTA button — "Try dbt Lens"
    cta2_y = stats_y + 120
    cta2_font = _load_font(_FONT_CANDIDATES_BOLD, 24)
    draw.rounded_rectangle(
        [panel_x + 36, cta2_y, panel_x + 36 + 460, cta2_y + 60],
        radius=12, fill=ACCENT
    )
    tb2 = draw.textbbox((0, 0), "Try dbt Lens — it's free", font=cta2_font)
    tb2w = tb2[2] - tb2[0]
    draw.text((panel_x + 36 + 230 - tb2w // 2 - tb2[0], cta2_y + 16),
              "Try dbt Lens — it's free", font=cta2_font, fill=(15, 23, 42))

    # URL below CTA
    url_font = _load_font(_FONT_CANDIDATES_REG, 17)
    url_text = "dbt-lens.streamlit.app"
    tb_u = draw.textbbox((0, 0), url_text, font=url_font)
    uw = tb_u[2] - tb_u[0]
    draw.text((panel_x + 36 + 230 - uw // 2 - tb_u[0], cta2_y + 72),
              url_text, font=url_font, fill=TEXT_SECONDARY)

    # ── Footer (bottom right) ───────────────────────────────────────────
    footer_font = _load_font(_FONT_CANDIDATES_REG, 17)
    footer_text = "github.com/noobigang/dbt-lens"
    tb_f = draw.textbbox((0, 0), footer_text, font=footer_font)
    fw = tb_f[2] - tb_f[0]
    draw.text((CARD_W - fw - 40, CARD_H - 45), footer_text,
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
