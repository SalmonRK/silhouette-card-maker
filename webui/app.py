"""SCM Studio — local web UI for Silhouette Card Maker.

Run:  python webui/app.py   (then open http://127.0.0.1:5190)

Each browser session works in its own job folder (webui/jobs/<id>/{front,back,double_sided,output}), so the
upstream game/ folders are never touched.
"""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import socket
import threading
import time
import traceback
import urllib.request
import uuid
import webbrowser
import zipfile
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_file, send_from_directory

import fetch_bridge
import scm_bridge as scm

HERE = Path(__file__).resolve().parent
JOBS = HERE / "jobs"
DATA = HERE / "data"
DECKS = DATA / "decks"
STATIC = HERE / "static"
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
KINDS = {"front": "front", "back": "back", "ds": "double_sided"}
MAX_UPLOAD = 512 * 1024 * 1024

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD
_status: dict[str, dict] = {}
_decks: dict[str, dict] = {}  # deck fetches in progress: state, log tail, child process


# ---------------------------------------------------------------- helpers

def job_dir(job_id: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{12}", job_id or ""):
        abort(404)
    d = JOBS / job_id
    if not d.exists():
        abort(404)
    return d


def safe_name(name: str) -> str:
    stem, ext = os.path.splitext(os.path.basename(name or "card"))
    stem = re.sub(r"[^\w\-. ]+", "_", stem, flags=re.UNICODE).strip(" .") or "card"
    return f"{stem[:80]}{ext.lower()}"


def list_files(d: Path) -> list[dict]:
    if not d.exists():
        return []
    files = [p for p in d.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXT]
    # natural sort, the same order upstream uses (natsort on names)
    key = lambda p: [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", p.name)]
    return [{"name": p.name, "stem": p.stem, "size": p.stat().st_size} for p in sorted(files, key=key)]


def job_state(job_id: str) -> dict:
    d = job_dir(job_id)
    out = d / "output"
    pages = sorted((out / "pages").glob("page*.png"), key=lambda p: int(re.sub(r"\D", "", p.stem) or 0))
    return {
        "id": job_id,
        "front": list_files(d / "front"),
        "back": list_files(d / "back"),
        "ds": list_files(d / "double_sided"),
        "pdf": (out / "cards.pdf").exists(),
        "png": load_meta(d),
        "pages": [p.name for p in pages],
        "status": _status.get(job_id, {"state": "idle"}),
    }


def load_meta(d: Path) -> dict | None:
    try:
        return json.loads((d / "output" / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def load_offset() -> dict:
    try:
        return json.loads((DATA / "offset.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"x": 0, "y": 0, "angle": 0, "enabled": False}


# ---------------------------------------------------------------- static

@app.get("/")
def index():
    return send_from_directory(STATIC, "index.html")


@app.get("/static/<path:p>")
def static_files(p):
    return send_from_directory(STATIC, p)


# ---------------------------------------------------------------- options & layout

@app.get("/api/options")
def api_options():
    return jsonify(scm.options())


@app.get("/api/layout")
def api_layout():
    try:
        return jsonify(scm.resolve_layout(
            request.args.get("paper", "a4"), request.args.get("card", "standard"),
            request.args.get("borderless") == "1", request.args.get("specialty") or None,
        ))
    except (ValueError, KeyError) as e:
        return jsonify({"error": str(e)}), 400


@app.get("/api/template/<name>")
def api_template(name):
    if not re.fullmatch(r"[\w\-]+", name):
        abort(404)
    p = scm.template_path(name, request.args.get("borderless") == "1")
    if not p:
        abort(404)
    return send_file(p, as_attachment=True, download_name=p.name)


@app.get("/api/calibration/<paper>")
def api_calibration(paper):
    if not re.fullmatch(r"\w+", paper):
        abort(404)
    p = scm.calibration_pdf(paper)
    if not p:
        abort(404)
    return send_file(p, as_attachment=True, download_name=p.name)


@app.get("/api/marks")
def api_marks():
    """Registration marks alone, for re-feeding a front sheet that came out of the printer without them."""
    kind = request.args.get("kind", "pdf")
    if kind not in ("pdf", "png", "upright"):
        abort(404)
    try:
        r = scm.marks_only(
            request.args.get("paper", "a4"), request.args.get("card", "standard"),
            request.args.get("borderless") == "1", request.args.get("specialty") or None,
            scm.Registration(request.args.get("registration", "3")), DATA / "marks",
        )
    except (ValueError, KeyError) as e:
        return jsonify({"error": str(e)}), 400
    p = r["files"].get(kind)
    if not p:
        abort(404)
    return send_file(p, as_attachment=True, download_name=p.name, max_age=0)


@app.route("/api/offset", methods=["GET", "POST"])
def api_offset():
    if request.method == "POST":
        b = request.get_json(force=True) or {}
        data = {
            "x": int(b.get("x", 0)), "y": int(b.get("y", 0)),
            "angle": float(b.get("angle", 0)), "enabled": bool(b.get("enabled", True)),
        }
        DATA.mkdir(exist_ok=True)
        (DATA / "offset.json").write_text(json.dumps(data), encoding="utf-8")
    return jsonify(load_offset())


# ---------------------------------------------------------------- jobs

@app.post("/api/jobs")
def api_new_job():
    job_id = uuid.uuid4().hex[:12]
    d = JOBS / job_id
    for sub in ("front", "back", "double_sided", "output"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    return jsonify(job_state(job_id))


@app.get("/api/jobs/<job_id>")
def api_job(job_id):
    return jsonify(job_state(job_id))


@app.post("/api/jobs/<job_id>/files/<kind>")
def api_upload(job_id, kind):
    d = job_dir(job_id)
    if kind not in KINDS:
        abort(400)
    target = d / KINDS[kind]
    files = request.files.getlist("files")
    if kind == "back":
        # upstream asks on the console when several backs exist → keep exactly one
        for p in target.iterdir():
            p.unlink()
        files = files[:1]
    pair_with = request.form.get("front")  # double-sided back: must share the front's file stem
    skipped = []
    for f in files:
        name = safe_name(f.filename)
        ext = os.path.splitext(name)[1]
        if ext not in IMAGE_EXT:
            skipped.append(f.filename)
            continue
        if kind == "ds":
            if not pair_with:
                abort(400)
            stem = os.path.splitext(safe_name(pair_with))[0]
            for old in target.glob(f"{glob_escape(stem)}.*"):
                old.unlink()
            name = f"{stem}{ext}"
        f.save(target / name)
    return jsonify({**job_state(job_id), "skipped": skipped})


def glob_escape(s: str) -> str:
    return re.sub(r"([\[\]*?])", r"[\1]", s)


@app.post("/api/jobs/<job_id>/sample")
def api_sample(job_id):
    """Fill the job with the demo deck (webui/tools/make_demo_cards.py): 8 framed fronts + 1 back."""
    d = job_dir(job_id)
    src = STATIC / "assets" / "demo"
    for f in sorted(src.glob("demo-front-*.png")):
        shutil.copy(f, d / "front" / f.name.replace("demo-front-", "demo-"))
    for p in (d / "back").iterdir():
        p.unlink()
    if (src / "demo-back.png").exists():
        shutil.copy(src / "demo-back.png", d / "back" / "back.png")
    return jsonify(job_state(job_id))


@app.delete("/api/jobs/<job_id>/files/<kind>/<path:name>")
def api_delete(job_id, kind, name):
    d = job_dir(job_id)
    if kind not in KINDS:
        abort(400)
    p = (d / KINDS[kind] / safe_name(name))
    if p.exists():
        p.unlink()
    if kind == "front":  # its paired back is meaningless without it
        for q in (d / "double_sided").glob(f"{glob_escape(p.stem)}.*"):
            q.unlink()
    return jsonify(job_state(job_id))


@app.get("/api/jobs/<job_id>/img/<kind>/<path:name>")
def api_img(job_id, kind, name):
    d = job_dir(job_id)
    if kind not in KINDS:
        abort(404)
    p = d / KINDS[kind] / safe_name(name)
    if not p.exists():
        abort(404)
    return send_file(p, max_age=0)


@app.post("/api/jobs/<job_id>/generate")
def api_generate(job_id):
    d = job_dir(job_id)
    opts = request.get_json(force=True) or {}
    if _status.get(job_id, {}).get("state") == "running":
        return jsonify({"error": "busy"}), 409
    if not list_files(d / "front"):
        return jsonify({"error": "no-fronts"}), 400
    off = load_offset()
    offset = off if (off.get("enabled") and opts.get("useOffset", True)) else None
    _status[job_id] = {"state": "running", "started": time.time()}

    def run():
        try:
            out = d / "output"
            shutil.rmtree(out / "pages", ignore_errors=True)
            pdf, log, meta = scm.generate(d, opts, offset)
            (out / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
            scm.render_pages(pdf, out / "pages")
            _status[job_id] = {"state": "done", "log": log, "took": round(time.time() - _status[job_id]["started"], 1)}
        except Exception as e:  # upstream raises bare Exception with a readable message
            _status[job_id] = {"state": "error", "error": str(e), "trace": traceback.format_exc(limit=3)}

    threading.Thread(target=run, daemon=True).start()
    return jsonify(job_state(job_id))


@app.get("/api/plugins")
def api_plugins():
    games = STATIC / "assets" / "games"
    return jsonify([{**p, "art": (games / f"{p['id']}.jpg").exists()} for p in fetch_bridge.plugins()])


@app.get("/api/templates")
def api_templates():
    """Every ready-made .studio3 for one paper (the machine page lists them for download)."""
    paper = request.args.get("paper", "a4")
    if not re.fullmatch(r"\w+", paper):
        abort(404)
    return jsonify(scm.templates_for(paper))


# ---------------------------------------------------------------- deck library (decklist import + history)
# A fetch never writes into a job: the plugin fills webui/data/decks/<id>/ first, the user checks the result, and
# "use" copies the images into a job. The folder stays as history, so the same deck can be reused without
# downloading it again.

WARN_RE = re.compile(r"(error|not found|couldn't|could not|unable|failed|no card|skipp)", re.I)


def deck_dir(deck_id: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{12}", deck_id or ""):
        abort(404)
    d = DECKS / deck_id
    if not (d / "deck.json").exists():
        abort(404)
    return d


def deck_meta(d: Path) -> dict:
    try:
        return json.loads((d / "deck.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_deck_meta(d: Path, meta: dict) -> None:
    (d / "deck.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")


def deck_state(d: Path) -> dict:
    meta = deck_meta(d)
    live = _decks.get(d.name)
    if live:  # still fetching: status lives in memory until the run thread writes it back
        meta = {**meta, **{k: v for k, v in live.items() if k != "proc"}}
    elif meta.get("state") == "running":  # server restarted mid-fetch
        meta["state"] = "cancelled"
    return {**meta, "front": list_files(d / "front"), "ds": list_files(d / "double_sided")}


@app.get("/api/decks")
def api_decks():
    out = []
    for d in DECKS.glob("*/deck.json"):
        s = deck_state(d.parent)
        s.pop("log", None)
        s["count"] = len(s.pop("front"))
        s["dsCount"] = len(s.pop("ds"))
        s["cover"] = next((f["name"] for f in list_files(d.parent / "front")), None)
        out.append(s)
    return jsonify(sorted(out, key=lambda m: m.get("created", 0), reverse=True))


@app.post("/api/decks/fetch")
def api_deck_fetch():
    b = request.get_json(force=True) or {}
    if any(v.get("state") == "running" for v in _decks.values()):
        return jsonify({"error": "busy"}), 409  # plugins hit public APIs; one deck at a time is kinder to them
    deck_id = uuid.uuid4().hex[:12]
    d = DECKS / deck_id
    for sub in ("front", "double_sided"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    plugin_id = str(b.get("plugin", ""))
    try:
        argv = fetch_bridge.build_args(d, plugin_id, str(b.get("format", "")), str(b.get("deck", "")), b.get("options") or {})
    except ValueError as e:
        shutil.rmtree(d, ignore_errors=True)
        return jsonify({"error": str(e)}), 400
    p = next(x for x in fetch_bridge.plugins() if x["id"] == plugin_id)
    meta = {"id": deck_id, "plugin": plugin_id, "game": p["name"], "format": b["format"], "deck": str(b["deck"]).strip(),
            "options": b.get("options") or {}, "created": time.time(), "state": "running"}
    save_deck_meta(d, meta)
    live = _decks[deck_id] = {"state": "running", "log": [], "started": time.time()}

    def line(s):
        if s:
            live["log"] = (live["log"] + [s])[-400:]

    def run():
        try:
            code = fetch_bridge.run(d, plugin_id, argv, lambda pr: live.__setitem__("proc", pr), line)
            state = "cancelled" if live.get("cancel") else "done" if code == 0 else "error"
            live.update(state=state, code=code)
        except Exception as e:
            live.update(state="error", error=str(e))
        live.pop("proc", None)
        warnings = [s for s in live["log"] if WARN_RE.search(s)][:50]
        (d / "log.txt").write_text("\n".join(live["log"]), encoding="utf-8")
        save_deck_meta(d, {**meta, "state": live["state"], "code": live.get("code"), "error": live.get("error"),
                           "took": round(time.time() - live["started"], 1), "warnings": warnings})
        _decks.pop(deck_id, None)

    threading.Thread(target=run, daemon=True).start()
    return jsonify(deck_state(d))


@app.get("/api/decks/<deck_id>")
def api_deck(deck_id):
    d = deck_dir(deck_id)
    s = deck_state(d)
    if "log" not in s:
        try:
            s["log"] = (d / "log.txt").read_text(encoding="utf-8").splitlines()[-400:]
        except OSError:
            s["log"] = []
    return jsonify(s)


@app.post("/api/decks/<deck_id>/cancel")
def api_deck_cancel(deck_id):
    d = deck_dir(deck_id)
    live = _decks.get(deck_id, {})
    if live.get("proc"):
        live["cancel"] = True
        live["proc"].terminate()
    return jsonify(deck_state(d))


@app.delete("/api/decks/<deck_id>")
def api_deck_delete(deck_id):
    d = deck_dir(deck_id)
    if deck_id in _decks:
        return jsonify({"error": "busy"}), 409
    shutil.rmtree(d, ignore_errors=True)
    return jsonify({"ok": True})


@app.get("/api/decks/<deck_id>/img/<kind>/<path:name>")
def api_deck_img(deck_id, kind, name):
    d = deck_dir(deck_id)
    if kind not in ("front", "ds"):
        abort(404)
    p = d / KINDS[kind] / safe_name(name)
    if not p.exists():
        abort(404)
    return send_file(p, max_age=3600)


@app.post("/api/decks/<deck_id>/use")
def api_deck_use(deck_id):
    """Copy a fetched deck into a job. append (default) keeps the cards already there and puts these after them."""
    d = deck_dir(deck_id)
    b = request.get_json(force=True) or {}
    jd = job_dir(str(b.get("job", "")))
    mode = b.get("mode", "append")
    if mode == "replace":
        for sub in ("front", "double_sided"):
            for p in (jd / sub).iterdir():
                p.unlink()
    # upstream orders fronts by natural file name; a "zz<n>-" prefix sorts after any earlier upload or deck, and
    # keeps a front and its own back sharing one stem
    n = 1 + max([int(m.group(1)) for f in list_files(jd / "front") if (m := re.match(r"zz(\d+)-", f["name"]))] or [0])
    prefix = f"zz{n:02d}-"
    added = 0
    for sub in ("front", "double_sided"):
        for f in list_files(d / sub):
            shutil.copy(d / sub / f["name"], jd / sub / (prefix + f["name"]))
            added += sub == "front"
    meta = deck_meta(d)
    save_deck_meta(d, {**meta, "used": time.time()})
    return jsonify({**job_state(jd.name), "added": added})


@app.get("/api/jobs/<job_id>/pdf")
def api_pdf(job_id):
    p = job_dir(job_id) / "output" / "cards.pdf"
    if not p.exists():
        abort(404)
    name = re.sub(r"[^\w\-]+", "-", request.args.get("name") or "cards").strip("-") or "cards"
    return send_file(p, as_attachment=request.args.get("dl") == "1", download_name=f"{name}.pdf", max_age=0)


@app.get("/api/jobs/<job_id>/png.zip")
def api_png_zip(job_id):
    """The sheets as PNG with the real DPI and the printed marks (for printing from any image viewer)."""
    d = job_dir(job_id)
    meta = load_meta(d)
    if not meta:
        abort(404)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:  # PNG is already compressed
        for f in meta["files"]:
            z.write(d / "output" / "png" / f["name"], f["name"])
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=f"{meta['name']}-png.zip", mimetype="application/zip")


@app.get("/api/jobs/<job_id>/studio.zip")
def api_studio_zip(job_id):
    """Everything for printing from Silhouette Studio: mark-free fronts, backs, the matching .studio3, steps."""
    d = job_dir(job_id)
    meta = load_meta(d)
    if not meta:
        abort(404)
    if meta["borderless"]:
        # borderless templates fake a page 13 mm larger than the paper; Studio would print that page shifted and
        # cropped, so these sheets only work printed from the PDF (Studio just cuts)
        return jsonify({"error": "borderless-pdf-only"}), 409
    tpl = scm.template_path(meta["template"], meta["borderless"])
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        for f in meta["files"]:
            z.write(d / "output" / "studio" / f["name"], f["name"])
        if tpl:
            z.write(tpl, tpl.name)
        z.writestr("README.txt", studio_readme(meta, tpl.name if tpl else None).encode("utf-8-sig"))
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=f"{meta['name']}-studio.zip", mimetype="application/zip")


def studio_readme(meta: dict, tpl: str | None) -> str:
    f0 = meta["files"][0]
    w, h = f0.get("studioMm", f0["mm"])
    px = f0.get("studioPx", f0["px"])
    fronts = [f["name"] for f in meta["files"] if f["side"] == "front"]
    backs = [f["name"] for f in meta["files"] if f["side"] == "back"]
    return "\r\n".join([
        "SCM Studio - พิมพ์จาก Silhouette Studio / print from Silhouette Studio",
        "",
        f"ไฟล์ตัด / cut file: {tpl or '(ไม่มี template สำหรับขนาดนี้ / no template for this size)'}",
        f"ภาพหน้า / fronts (ลบ mark ออกแล้ว / marks removed): {', '.join(fronts)}",
        f"ภาพหลัง / backs (ไม่ต้องตัด / not cut): {', '.join(backs) or '-'}",
        "แนวกระดาษ / page: " + ("ตั้ง / portrait" if meta.get("portrait") else "นอน / landscape")
        + " (ตรงกับไฟล์ตัด / same as the cut file)",
        f"ขนาดทุกภาพ / every sheet: {px[0]} x {px[1]} px @ {meta['ppi']} dpi = {w} x {h} mm",
        "",
        "ขั้นตอน (ต่อแผ่น) / steps per sheet",
        f"1. เปิด {tpl or 'ไฟล์ตัด'} ใน Silhouette Studio (มี mark และเส้นตัดตั้งไว้แล้ว ห้ามแก้)",
        "   Open the .studio3 (marks and cut lines are already set - do not change them).",
        "   เส้นตัดเป็นสีเทา ไม่ต้องเปลี่ยนเป็นแดง สีเส้นไม่มีผล ดูที่แท็บ ส่ง ว่าการ์ดทุกใบถูกเน้นเป็นเส้นตัด",
        "   Cut lines are grey - colour does not matter; check the Send tab highlights every card.",
        "2. File > Merge แล้วเลือก PNG หน้า (…-front.png) / File > Merge the front PNG.",
        f"3. เช็กขนาดภาพในแผง Transform ต้องได้ W {w} / H {h} mm ถ้าไม่ใช่ ให้ล็อกสัดส่วนแล้วพิมพ์ W = {w}",
        f"   Check W {w} / H {h} mm in Transform; if not, lock ratio and type W = {w}.",
        "4. ตั้งตำแหน่ง X 0 / Y 0 (Move To) แล้ว Send to Back ให้เส้นตัดอยู่ด้านบน",
        "   Position X 0 / Y 0, then Send to Back so the cut lines stay on top.",
        "5. ภาพต้องตรงกับเส้นตัดแดงทุกใบ และ mark ของ Studio ต้องไม่ทับภาพ (ภาพนี้ลบ mark ของ SCM ออกแล้ว Studio จะพิมพ์ mark เอง)",
        "   Every card must sit inside its red cut line; Studio prints its own marks (SCM's were removed from this PNG).",
        "6. File > Print: Scale 100% / Actual size, ปิด Fit to page, ปิด borderless ในไดรเวอร์",
        "   Print at 100% / actual size - no fit-to-page, no driver borderless.",
        "7. ใส่กระดาษบนแผ่นรองตัดมุมซ้ายบน แล้ว Send > ตัด (ใบมีด/แรงตามกระดาษ)",
        "   Load the sheet on the mat top-left and Send to cut.",
        "",
        "ภาพหลัง: พิมพ์อีกด้านจาก PDF หรือ Studio (ไม่ต้องเปิด mark ไม่ต้องตัด)",
        "Backs: print on the other side from the PDF or Studio - no marks, no cut.",
        "",
        "ถ้าเครื่องเปิด PDF ได้ ทาง PDF (Actual size) แม่นกว่า เพราะ mark กับภาพอยู่ในไฟล์เดียวกัน",
        "If you can print the PDF at actual size, that route is safer: marks and art come from one file.",
    ])


@app.get("/api/jobs/<job_id>/page/<name>")
def api_page(job_id, name):
    if not re.fullmatch(r"page\d+\.png", name):
        abort(404)
    p = job_dir(job_id) / "output" / "pages" / name
    if not p.exists():
        abort(404)
    return send_file(p, max_age=0)


def port_in_use(port: int) -> bool:
    # Windows lets a second server bind a busy port (requests then split between both), so probe first
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def is_scm_studio(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/options", timeout=2) as r:
            return "combos" in json.loads(r.read())
    except (OSError, ValueError):
        return False


if __name__ == "__main__":
    port = int(os.environ.get("SCM_WEBUI_PORT", "5190"))
    open_browser = os.environ.get("NO_BROWSER") != "1"
    if port_in_use(port):
        if is_scm_studio(port):
            print(f"SCM Studio is already running at http://127.0.0.1:{port} (close that window first to restart it)")
            if open_browser:
                webbrowser.open(f"http://127.0.0.1:{port}")
            raise SystemExit(0)
        start = port
        while port_in_use(port) and port < start + 20:
            port += 1
        print(f"Port {start} is used by another program, using {port}")
    if open_browser:
        threading.Timer(1.2, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    print(f"SCM Studio: http://127.0.0.1:{port}  (keep this window open, Ctrl+C to stop)")
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
