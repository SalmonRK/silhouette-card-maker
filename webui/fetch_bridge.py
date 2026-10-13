"""Decklist import for SCM Studio: wraps the upstream plugins/ (one per game) without modifying them.

plugins() describes every plugin from its own click command (formats + options), and run() executes one in a
child process (tools/run_plugin.py) so a slow or crashing plugin never takes the web server down with it.
"""
from __future__ import annotations

import importlib
import os
import re
import subprocess
import sys
from pathlib import Path

import click

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
RUNNER = HERE / "tools" / "run_plugin.py"
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

_cache: list[dict] | None = None

# formats whose fetch.py uses DECK_PATH as the deck itself (a share link, a deck id or a ydke:// code)
DIRECT_FORMATS = {
    "url", "arkhamdb_url", "ashes_share_url", "ashesdb_share_url", "bushiroad_url", "astrabuilder_url", "elestrals",
    "master_vault_url", "decks_of_keyforge_url", "ringsdb_url", "ringsdb_fellowship_url", "ringsdb_scenario_url",
    "hallofbeorn_url", "curiosa_url", "ydke",
}


def _title(plugin_dir: Path) -> str:
    try:
        first = (plugin_dir / "README.md").read_text(encoding="utf-8").splitlines()[0]
        return re.sub(r"^#\s*|\s*Plugin\s*$", "", first).strip() or plugin_dir.name
    except (OSError, IndexError):
        return plugin_dir.name


def _describe(param: click.Option) -> dict:
    kind = "flag" if param.is_flag else "choice" if isinstance(param.type, click.Choice) else "text"
    return {
        "name": param.name,
        "flag": max(param.opts, key=len),
        "kind": kind,
        "multiple": bool(param.multiple),
        "choices": list(param.type.choices) if kind == "choice" else [],
        "default": None if param.multiple or param.default is None else param.default,
        "help": param.help or "",
    }


def plugins() -> list[dict]:
    global _cache
    if _cache is None:
        out = []
        for d in sorted((REPO / "plugins").iterdir()):
            if not (d / "fetch.py").exists():
                continue
            try:
                cli = importlib.import_module(f"plugins.{d.name}.fetch").cli
            except Exception as e:  # a missing optional dependency should hide one game, not the panel
                out.append({"id": d.name, "name": _title(d), "error": str(e), "formats": [], "options": []})
                continue
            fmt = next(p for p in cli.params if p.name == "format")
            out.append({
                "id": d.name,
                "name": _title(d),
                "formats": list(fmt.type.choices),
                "direct": [f for f in fmt.type.choices if f in DIRECT_FORMATS],
                "options": [_describe(p) for p in cli.params if isinstance(p, click.Option) and p.name != "help"],
            })
        _cache = out
    return _cache


def build_args(job_dir: Path, plugin_id: str, fmt: str, deck: str, opts: dict) -> list[str]:
    """Validate the request against the plugin's own click definition and turn it into argv."""
    p = next((x for x in plugins() if x["id"] == plugin_id and not x.get("error")), None)
    if not p:
        raise ValueError("unknown-plugin")
    if fmt not in p["formats"]:
        raise ValueError("unknown-format")
    deck = deck.strip()
    if not deck:
        raise ValueError("empty-deck")
    # link / code formats: fetch.py takes the deck argument itself (a bare Elestrals deck id is no URL, so decide by
    # format, not by how the text looks); every other format reads a file
    if fmt in DIRECT_FORMATS:
        deck_arg = next(l.strip() for l in deck.splitlines() if l.strip())
    else:
        src = job_dir / "decklist" / "deck.txt"
        src.parent.mkdir(exist_ok=True)
        src.write_text(deck + "\n", encoding="utf-8")
        deck_arg = str(src)
    argv = [deck_arg, fmt]
    by_name = {o["name"]: o for o in p["options"]}
    for name, value in (opts or {}).items():
        o = by_name.get(name)
        if not o or value in (None, "", False, []):
            continue
        if o["kind"] == "flag":
            argv.append(o["flag"])
            continue
        values = value if isinstance(value, list) else [v.strip() for v in str(value).split(",")] if o["multiple"] else [str(value)]
        for v in filter(None, values):
            if o["kind"] == "choice" and v not in o["choices"]:
                raise ValueError(f"bad-option:{name}")
            argv += [o["flag"], v]
    return argv


def run(job_dir: Path, plugin_id: str, argv: list[str], on_start, on_line) -> int:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1"}
    proc = subprocess.Popen(
        [sys.executable, str(RUNNER), str(job_dir), plugin_id, *argv],
        cwd=str(REPO), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    on_start(proc)
    for line in proc.stdout:
        on_line(line.rstrip())
    return proc.wait()
