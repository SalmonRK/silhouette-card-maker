"""Thin adapter over Silhouette Card Maker's own modules.

Everything here *reads* upstream code (layouts.json, page_manager, utilities) and never edits it, so the fork can
keep merging upstream. If upstream renames something, this is the only file that should need a touch-up.
"""
from __future__ import annotations

import contextlib
import io
import math
import os
import re
import shutil
import sys
import threading
from pathlib import Path

# upstream pulls in matplotlib; its default Tk backend crashes when used from a worker thread
os.environ.setdefault("MPLBACKEND", "Agg")

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import page_manager  # noqa: E402
import size_convert  # noqa: E402
import utilities  # noqa: E402
from enums import Orientation, Registration, Variant  # noqa: E402

PPI = 300
MM_PER_PX = 25.4 / PPI

# generate_pdf prints progress and reads ./data for the saved offset → one job at a time, cwd pinned per job.
_job_lock = threading.Lock()


def _mm(size: str | None) -> float | None:
    return None if size is None else round(size_convert.size_to_mm(size), 3)


def options() -> dict:
    """Card sizes, paper sizes and which (paper, card, variant) combinations have a layout + template."""
    cfg = utilities.load_layout_config()
    cards = {
        name: {"w": _mm(c.width), "h": _mm(c.height), "radius": _mm(c.radius or cfg.defaults.card_radius)}
        for name, c in cfg.card_sizes.items()
    }
    papers = {name: {"w": _mm(p.width), "h": _mm(p.height)} for name, p in cfg.paper_sizes.items()}
    combos = []
    for paper, by_card in cfg.layouts.items():
        for card, variants in by_card.items():
            for variant in variants:
                combos.append({"paper": paper, "card": card, "variant": variant})
    specialty = list((cfg.specialty_layouts or {}).keys())
    return {"cards": cards, "papers": papers, "combos": combos, "specialty": specialty}


def template_path(name: str, borderless: bool) -> Path | None:
    base = utilities.resolve_cutting_templates_dir(REPO / "cutting_templates")
    p = (base / "borderless" if borderless else base) / f"{name}.studio3"
    return p if p.exists() else None


def templates_for(paper: str) -> list[dict]:
    """Ready-made cut files for one paper: [{name, card, borderless}] (name without .studio3, as template_path wants)."""
    base = utilities.resolve_cutting_templates_dir(REPO / "cutting_templates")
    out = []
    for borderless, d in ((False, base), (True, base / "borderless")):
        for p in sorted(d.glob(f"{paper}-*.studio3")):
            card = re.sub(r"-v\d+$", "", p.stem[len(paper) + 1:]).replace("-borderless", "")
            out.append({"name": p.stem, "card": card, "borderless": borderless})
    return out


def resolve_layout(paper: str, card: str, borderless: bool = False, specialty: str | None = None) -> dict:
    """Same geometry generate_pdf will produce (mirrors utilities.generate_pdf's layout block), in millimetres."""
    return _resolve(paper, card, borderless, specialty)[0]


def _resolve(paper: str, card: str, borderless: bool, specialty: str | None) -> tuple[dict, dict]:
    """(geometry in mm for the UI, the raw unit strings + orientations upstream draws the marks from)."""
    cfg = utilities.load_layout_config()
    default_reg = cfg.defaults.registration.default
    if specialty:
        spec = cfg.specialty_layouts[specialty]
        if spec.card_size.name:
            base = cfg.card_sizes[spec.card_size.name]
            cw, ch, radius = base.width, base.height, spec.card_size.radius or base.radius
        else:
            cw, ch, radius = spec.card_size.width, spec.card_size.height, spec.card_size.radius
        pdef = cfg.paper_sizes[spec.paper_size.name] if spec.paper_size.name else spec.paper_size
        orientation = spec.orientation
        reg_orientation = spec.registration_orientation or orientation
        lr = spec.registration or utilities.RegistrationSettings()
        inset = lr.inset or default_reg.inset
        template = f"{specialty}-v{spec.version}"
        paper_name = spec.paper_size.name or specialty
    else:
        card = utilities.resolve_card_size_alias(cfg, card)
        paper = utilities.resolve_paper_size_alias(cfg, paper)
        variant = Variant.BORDERLESS if borderless else Variant.DEFAULT
        try:
            ldef = cfg.layouts[paper][card][variant.value]
        except KeyError:
            raise ValueError(f'No {variant.value} layout for paper "{paper}" + card "{card}".')
        cdef = cfg.card_sizes[card]
        cw, ch, radius = cdef.width, cdef.height, cdef.radius
        pdef = cfg.paper_sizes[paper]
        orientation = ldef.orientation
        reg_orientation = ldef.registration_orientation or orientation
        lr = ldef.registration or utilities.RegistrationSettings()
        inset = lr.inset or (cfg.defaults.registration.borderless if borderless else default_reg).inset
        template = utilities.template_name(paper, card, variant, ldef.version)
        paper_name = paper

    thickness = lr.thickness or default_reg.thickness
    length = lr.length or default_reg.length
    exclusion = f"{size_convert.size_to_mm(default_reg.length) + page_manager.REG_PADDING_MM}mm"
    lay = page_manager.generate_layout(
        orientation=orientation, card_width=cw, card_height=ch, paper_width=pdef.width,
        paper_height=pdef.height, inset=inset, length=exclusion, ppi=PPI,
    )
    cwm, chm = lay.card_width_px * MM_PER_PX, lay.card_height_px * MM_PER_PX
    slots = [
        {"x": round(x * MM_PER_PX, 3), "y": round(y * MM_PER_PX, 3), "w": round(cwm, 3), "h": round(chm, 3)}
        for y in lay.y_pos for x in lay.x_pos
    ]
    # how far the art runs past each cut line (copies: upstream sorts the lists in place)
    bleed = utilities.calculate_max_print_bleed(list(lay.x_pos), list(lay.y_pos), lay.card_width_px,
                                                lay.card_height_px, utilities.MINIMUM_BLEED)
    tpl = template_path(template, borderless and not specialty)
    marks = {
        "paper": pdef, "inset": inset, "thickness": thickness, "length": length,
        "orientation": orientation, "reg_orientation": reg_orientation,
    }
    return {
        "paper": paper_name,
        "orientation": getattr(orientation, "value", orientation),
        "pageW": round(lay.paper_width_px * MM_PER_PX, 3),
        "pageH": round(lay.paper_height_px * MM_PER_PX, 3),
        "cardW": round(cwm, 3),
        "cardH": round(chm, 3),
        "radius": _mm(radius or cfg.defaults.card_radius),
        "cols": len(lay.x_pos),
        "rows": len(lay.y_pos),
        "slots": slots,
        "bleed": [round(v * MM_PER_PX, 3) for v in bleed],
        "registration": {"inset": _mm(inset), "thickness": _mm(thickness), "length": _mm(length)},
        "template": template,
        "templateAvailable": tpl is not None,
    }, marks


def generate(job_dir: Path, opts: dict, offset: dict | None) -> tuple[Path, str, dict]:
    """Run upstream generate_pdf for one job folder: the PDF, then the same sheets as PNG.

    Returns (pdf path, captured log, meta). The PNG pass is a second upstream run with output_images=True, so the
    pixels are upstream's own; we only stamp the DPI and, for the Studio set, erase the printed marks.
    """
    out = job_dir / "output"
    out_pdf = out / "cards.pdf"
    raw = out / "png_raw"
    for d in (raw, out / "png", out / "studio"):
        shutil.rmtree(d, ignore_errors=True)
    raw.mkdir(parents=True)
    ppi = int(opts.get("ppi", 300))
    registration = Registration(str(opts.get("registration", "3")))
    only_fronts = bool(opts.get("onlyFronts"))
    args = dict(
        front_dir_path=str(job_dir / "front"),
        back_dir_path=str(job_dir / "back"),
        ds_dir_path=str(job_dir / "double_sided"),
        card_size=opts.get("card", "standard"),
        paper_size=opts.get("paper", "a4"),
        registration=registration,
        only_fronts=only_fronts,
        fit=utilities.FitMode(opts.get("fit", "stretch")),
        fit_backs=opts.get("fitBacks") or None,
        crop_string=opts.get("crop") or None,
        crop_backs_string=opts.get("cropBacks") or None,
        extend_edges=opts.get("extendEdges") or None,
        extend_edges_backs=None,
        extend_corners=opts.get("extendCorners") or None,
        extend_corners_backs=None,
        extend_bleed=opts.get("extendBleed") or None,
        extend_bleed_backs=None,
        ppi=ppi,
        quality=int(opts.get("quality", 100)),
        skip_indices=[int(i) for i in opts.get("skip", [])],
        load_offset=bool(offset),
        label=opts.get("label") or None,
        show_outline=bool(opts.get("showOutline")),
        specialty=opts.get("specialty") or None,
        borderless=bool(opts.get("borderless")),
        registration_orientation_override=None,
    )
    log = io.StringIO()
    with _job_lock:
        prev = os.getcwd()
        try:
            os.chdir(job_dir)  # upstream reads/writes ./data/offset_data.json relative to cwd
            if offset:
                utilities.save_offset(int(offset.get("x", 0)), int(offset.get("y", 0)), float(offset.get("angle", 0)))
            with contextlib.redirect_stdout(log):
                utilities.generate_pdf(output_path=str(out_pdf), output_images=False, **args)
            with contextlib.redirect_stdout(io.StringIO()):
                utilities.generate_pdf(output_path=str(raw), output_images=True, **args)
        finally:
            os.chdir(prev)

    geom, marks = _resolve(args["paper_size"], args["card_size"], args["borderless"], args["specialty"])
    meta = export_pngs(raw, out, marks, registration, ppi, only_fronts, f"{geom['paper']}-{args['card_size']}")
    shutil.rmtree(raw, ignore_errors=True)
    meta.update(template=geom["template"], templateAvailable=geom["templateAvailable"],
                borderless=bool(args["borderless"] and not args["specialty"]))
    return out_pdf, log.getvalue(), meta


def mark_mask(marks: dict, registration: Registration, ppi: int):
    """Where upstream prints the registration marks on a page, as an 'L' mask (255 = mark, grown by ~0.4 mm)."""
    from PIL import ImageFilter

    grow = max(1, round(0.4 / 25.4 * ppi))
    im = mark_page(marks, registration, ppi)
    return im.point(lambda v: 255 if v < 200 else 0).filter(ImageFilter.MaxFilter(grow * 2 + 1))


def mark_page(marks: dict, registration: Registration, ppi: int):
    """The registration marks alone, exactly as they land on upstream's output page ('L', black on white).

    Redraws the marks with upstream's own page_manager.generate_reg_mark and repeats generate_pdf's resize and
    rotations, so they sit where the printed marks sit for every paper, card and orientation.
    """
    cfg = utilities.load_layout_config()
    reg_portrait = marks["reg_orientation"] == Orientation.PORTRAIT
    pdef = marks["paper"]
    w, h = (pdef.height, pdef.width) if reg_portrait else (pdef.width, pdef.height)
    ratio = ppi / 300
    with page_manager.generate_reg_mark(w, h, marks["inset"], marks["thickness"], marks["length"], cfg.ppi,
                                        registration) as reg:
        im = reg.convert("L")
    if ratio != 1:
        im = im.resize([math.floor(im.width * ratio), math.floor(im.height * ratio)])
    if marks["reg_orientation"] != marks["orientation"]:
        im = im.rotate(90 if reg_portrait else -90, expand=True)
    if marks["orientation"] == Orientation.PORTRAIT:  # add_front_back_pages turns portrait sheets landscape
        im = im.rotate(90, expand=True)
    return im


def marks_only(paper: str, card: str, borderless: bool, specialty: str | None, registration: Registration,
               out_dir: Path, ppi: int = 300) -> dict:
    """A sheet with nothing but the registration marks, for re-feeding a front that was printed without them.

    pdf  = same page and orientation as upstream's PDF (print it the same way the cards were printed)
    png  = the same, with the real DPI
    upright png = turned back to the layout orientation, for sheets printed from the Studio set
    """
    from PIL import Image

    geom, marks = _resolve(paper, card, borderless, specialty)
    im = mark_page(marks, registration, ppi).point(lambda v: 0 if v < 128 else 255).convert("RGB")
    portrait = marks["orientation"] == Orientation.PORTRAIT
    name = f"{geom['paper']}-{card}{'-borderless' if borderless and not specialty else ''}-marks-{registration.value}"
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf, png = out_dir / f"{name}.pdf", out_dir / f"{name}.png"
    im.save(pdf, format="PDF", resolution=ppi)
    im.save(png, dpi=(ppi, ppi))
    files = {"pdf": pdf, "png": png}
    if portrait:
        up = out_dir / f"{name}-upright.png"
        im.rotate(-90, expand=True).save(up, dpi=(ppi, ppi))
        files["upright"] = up
    return {"name": name, "files": files, "mm": [round(v / ppi * 25.4, 2) for v in im.size], "portrait": portrait,
            "template": geom["template"]}


def export_pngs(raw: Path, out: Path, marks: dict, registration: Registration, ppi: int,
                only_fronts: bool, name: str) -> dict:
    """Stamp the real DPI on upstream's PNG sheets (png/) and make a mark-free copy of the fronts (studio/).

    Without a pHYs chunk Silhouette Studio guesses the size; with it a 3507 px wide A4 sheet imports at 296.93 mm,
    the same as the PDF page.

    Upstream turns portrait sheets landscape (the printer driver turns them back), but a portrait layout's .studio3
    page is portrait, so the studio/ copies are turned back upright to drop straight onto the template.
    """
    from PIL import Image

    (out / "png").mkdir(exist_ok=True)
    (out / "studio").mkdir(exist_ok=True)
    pages = sorted(raw.glob("page*.png"), key=lambda p: int(re.sub(r"\D", "", p.stem)))
    mask = mark_mask(marks, registration, ppi) if pages else None
    portrait = marks["orientation"] == Orientation.PORTRAIT
    files = []
    for i, p in enumerate(pages):
        side = "front" if only_fronts or i % 2 == 0 else "back"
        sheet = i + 1 if only_fronts else i // 2 + 1
        fname = f"{name}-s{sheet}-{side}.png"
        with Image.open(p) as src:
            im = src.convert("RGB")
        im.save(out / "png" / fname, dpi=(ppi, ppi))
        erased = False
        if side == "front" and mask is not None and mask.size == im.size:
            im.paste((255, 255, 255), mask=mask)
            erased = True
        # backs keep their marks: the saved offset may have shifted them, and backs are never cut
        upright = im.rotate(-90, expand=True) if portrait else im  # undo add_front_back_pages' rotate(90)
        upright.save(out / "studio" / fname, dpi=(ppi, ppi))
        mm = lambda size: [round(v / ppi * 25.4, 2) for v in size]
        files.append({"name": fname, "side": side, "sheet": sheet, "px": list(im.size), "mm": mm(im.size),
                      "studioPx": list(upright.size), "studioMm": mm(upright.size), "marksErased": erased})
    return {"name": name, "ppi": ppi, "portrait": portrait, "files": files}


def render_pages(pdf: Path, out_dir: Path, width_px: int = 900) -> list[Path]:
    """Small PNG previews of every PDF page (pypdfium2 is already an upstream dependency)."""
    import pypdfium2 as pdfium

    out_dir.mkdir(parents=True, exist_ok=True)
    doc = pdfium.PdfDocument(str(pdf))
    paths = []
    try:
        for i in range(len(doc)):
            page = doc[i]
            scale = width_px / page.get_width()
            img = page.render(scale=scale).to_pil()
            p = out_dir / f"page{i + 1}.png"
            img.save(p)
            paths.append(p)
    finally:
        doc.close()
    return paths


def calibration_pdf(paper: str) -> Path | None:
    p = REPO / "calibration" / f"{paper}-calibration.pdf"
    return p if p.exists() else None
