"""HTTP cache + response capture for plugin runs (used by tools/run_plugin.py, in the plugin's child process).

install(deck_dir) must run before the plugin is imported:
- every requests / cloudscraper call goes through one persistent cache (data/library/http-cache.sqlite), so an
  API answer or a card image that was downloaded once is read from disk next time;
- every JSON answer is also written to <deck_dir>/raw/NNNN.json ({url, cached, body}) — the plugins only keep the
  image, the card data (name, stats, rarity, ...) is picked out of these files later by catalog.py.
"""
from __future__ import annotations

import atexit
import json
from datetime import timedelta
from pathlib import Path

import requests_cache
from requests_cache import NEVER_EXPIRE

HERE = Path(__file__).resolve().parent
CACHE = HERE / "data" / "library" / "http-cache"

IMAGE_PATTERNS = ("*.png", "*.jpg", "*.jpeg", "*.webp", "*.gif", "*/images/*", "*/card-printings/*", "*/cards/large/*")


def install(deck_dir: str | Path) -> None:
    raw = Path(deck_dir) / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    requests_cache.install_cache(
        str(CACHE),
        backend="sqlite",
        expire_after=timedelta(days=30),  # card databases change (errata, new printings); images never do
        urls_expire_after={p: NEVER_EXPIRE for p in IMAGE_PATTERNS},
        allowable_methods=("GET", "HEAD", "POST"),
        allowable_codes=(200,),
        stale_if_error=True,  # a site that is down still answers from the cache
    )
    stats = {"requests": 0, "cached": 0, "json": 0}
    send = requests_cache.CachedSession.send

    def capture(self, request, **kwargs):
        response = send(self, request, **kwargs)
        stats["requests"] += 1
        cached = bool(getattr(response, "from_cache", False))
        stats["cached"] += cached
        if response.status_code == 200 and "json" in response.headers.get("Content-Type", "").lower():
            try:
                body = response.json()
            except ValueError:
                return response
            stats["json"] += 1
            (raw / f"{stats['json']:04d}.json").write_text(
                json.dumps({"url": request.url, "method": request.method, "cached": cached, "body": body}, ensure_ascii=False),
                encoding="utf-8")
        return response

    requests_cache.CachedSession.send = capture
    atexit.register(lambda: (raw / "_stats.json").write_text(json.dumps(stats), encoding="utf-8"))
