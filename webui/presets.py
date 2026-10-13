"""SRK presets: layouts that upstream's layouts.json cannot describe, added without touching upstream files.

Upstream spaces every layout with a fixed 1.25 mm gap (page_manager.generate_layout's CARD_DISTANCE), so a
print/cut misregistration over ~0.6 mm lands on the neighbouring card. A preset here sets its own gap and
mark inset and shows up as an extra specialty layout ("srk-…" names never collide with upstream's
"{paper}-{card}[-borderless]-vN" templates).

How it plugs in (all reversible, process-local):
- utilities.load_layout_config() returns upstream's config plus one SpecialtyLayoutDef per preset;
- page_manager.generate_layout() is wrapped: inside `active(name)` it lays the cards out with the preset gap,
  everywhere else it is upstream's own function, untouched.

Inset below Studio's 10 mm minimum uses upstream's borderless trick: the cut file declares a page
2 × (10 − inset) larger, so the sheet sits (10 − inset) mm in from the mat grid and is printed from the PDF.
"""
from __future__ import annotations

import contextlib
import contextvars
from pathlib import Path

import dxf_manager
import page_manager
import size_convert
import utilities
from enums import Orientation

PRESETS: dict[str, dict] = {
    # 3 × 3 poker/standard on A4 portrait, 3 mm between cards (1.5 mm bleed each side) instead of 1.25 mm,
    # marks 5 mm from the paper edge instead of borderless' 3.5 mm. RESEARCH-cameo5 §21 item 3.
    "srk-a4-standard-gap3": {
        "card": "standard", "paper": "a4", "orientation": "portrait",
        "cols": 3, "rows": 3, "gap": "3mm",
        "inset": "5mm", "thickness": "1mm", "length": "5mm",
        "version": 1,
    },
}

_active: contextvars.ContextVar[str | None] = contextvars.ContextVar("srk_preset", default=None)
_upstream_load = utilities.load_layout_config
_upstream_layout = page_manager.generate_layout


def is_preset(name: str | None) -> bool:
    return bool(name) and name in PRESETS


def expansion_mm(name: str) -> float:
    """How much larger the cut file's page is than the paper (0 when the inset is Studio-legal)."""
    inset = size_convert.size_to_mm(PRESETS[name]["inset"])
    return round(max(0.0, (page_manager.MIN_REG_INSET_MM - inset) * 2), 3)


def _load_layout_config():
    cfg = _upstream_load()
    specs = dict(cfg.specialty_layouts or {})
    for name, p in PRESETS.items():
        specs[name] = utilities.SpecialtyLayoutDef(
            card_size=utilities.SpecialtyCardSizeDef(name=p["card"]),
            paper_size=utilities.SpecialtyPaperSizeDef(name=p["paper"]),
            orientation=Orientation(p["orientation"]),
            version=p["version"],
            registration=utilities.RegistrationSettings(inset=p["inset"], thickness=p["thickness"], length=p["length"]),
        )
    cfg.specialty_layouts = specs
    return cfg


def layout(name: str, card_width: str, card_height: str, paper_width: str, paper_height: str, ppi: int,
           orientation: Orientation) -> page_manager.CardLayout:
    """Fixed cols × rows grid centred on the page with the preset gap; checks the marks stay clear of the art."""
    p = PRESETS[name]
    px = lambda s: size_convert.size_to_pixel(s, ppi)
    page_w, page_h = page_manager.normalize_page_size(orientation, px(paper_width), px(paper_height))
    cw, ch, gap = px(card_width), px(card_height), px(p["gap"])
    cols, rows = p["cols"], p["rows"]
    start_x = round((page_w - (cols * cw + (cols - 1) * gap)) / 2)
    start_y = round((page_h - (rows * ch + (rows - 1) * gap)) / 2)
    x_pos = [start_x + i * (cw + gap) for i in range(cols)]
    y_pos = [start_y + j * (ch + gap) for j in range(rows)]

    # Same corner rule as upstream: the art (cards + half-gap bleed) must clear the mark zone on at least one axis.
    inset, corner = px(p["inset"]), px(p["length"]) + px(f"{page_manager.REG_PADDING_MM}mm")
    clear_x, clear_y = start_x - gap // 2 - inset, start_y - gap // 2 - inset
    if min(clear_x, clear_y) < 0 or (clear_x < corner and clear_y < corner):
        raise ValueError(f'Preset "{name}" does not fit: cards run into the registration marks.')
    max_len = round((max(clear_x, clear_y) - px(f"{page_manager.REG_PADDING_MM}mm")) * 25.4 / ppi, 2)
    return page_manager.CardLayout(cw, ch, page_w, page_h, x_pos, y_pos, max_len)


def _generate_layout(orientation, card_width, card_height, paper_width, paper_height, inset, length, ppi):
    name = _active.get()
    if name is None:
        return _upstream_layout(orientation=orientation, card_width=card_width, card_height=card_height,
                                paper_width=paper_width, paper_height=paper_height, inset=inset, length=length,
                                ppi=ppi)
    return layout(name, card_width, card_height, paper_width, paper_height, ppi, orientation)


@contextlib.contextmanager
def active(name: str | None):
    """Use the preset's geometry for every generate_layout call inside the block (no-op for other names)."""
    token = _active.set(name if is_preset(name) else None)
    try:
        yield
    finally:
        _active.reset(token)


def write_dxf(name: str, out: Path) -> Path:
    """Cut lines for the preset on the real paper (upstream's own DXF writer, origin = paper corner)."""
    p = PRESETS[name]
    cfg = utilities.load_layout_config()
    card, paper = cfg.card_sizes[p["card"]], cfg.paper_sizes[p["paper"]]
    lay = layout(name, card.width, card.height, paper.width, paper.height, cfg.ppi, Orientation(p["orientation"]))
    out.parent.mkdir(parents=True, exist_ok=True)
    dxf_manager.generate_dxf(card.width, card.height, card.radius or cfg.defaults.card_radius,
                             list(lay.x_pos), list(lay.y_pos), cfg.ppi, output_path=str(out))
    return out


def install():
    utilities.load_layout_config = _load_layout_config
    page_manager.generate_layout = _generate_layout
