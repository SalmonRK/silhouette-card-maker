"""Card catalog for SCM Studio: card data (name, stats, rarity, ...) for every fetched deck, kept in one SQLite file
and exported to Excel.

The upstream plugins only save images. During a fetch, capture.py keeps every JSON answer the plugin received in
<deck>/raw/; ingest() picks the card objects out of those answers, matches them to the image files the plugin wrote,
and stores them. Four plugins never ask a card database (they build image URLs from the card code), so their cards
are looked up here instead — through the same HTTP cache, so a card is only asked for once.

    data/library/library.sqlite   cards · decks · deck_cards
    data/library/images/<game>/   one image per card (the decks keep their own copies for printing)
    data/library/exports/         การ์ดทั้งหมด.xlsx
"""
from __future__ import annotations

import html
import json
import os
import re
import shutil
import sqlite3
import time
import unicodedata
from datetime import timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIB = Path(os.environ.get("SCM_LIBRARY") or HERE / "data" / "library")
DB = LIB / "library.sqlite"
IMAGES = LIB / "images"
EXPORTS = LIB / "exports"
XLSX_NAME = "การ์ดทั้งหมด.xlsx"
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS cards (
  key TEXT PRIMARY KEY, game TEXT, name TEXT, set_code TEXT, set_name TEXT, number TEXT, type TEXT, rarity TEXT,
  cost TEXT, power TEXT, defense TEXT, hp TEXT, color TEXT, text TEXT, stats TEXT, image TEXT, source_url TEXT,
  found INTEGER, updated REAL, code TEXT);
CREATE TABLE IF NOT EXISTS decks (
  id TEXT PRIMARY KEY, game TEXT, game_name TEXT, owner TEXT, name TEXT, author TEXT, format TEXT, source TEXT,
  folder TEXT, cards INTEGER, kinds INTEGER, found INTEGER, created REAL, updated REAL);
CREATE TABLE IF NOT EXISTS deck_cards (
  deck_id TEXT, position INTEGER, card_key TEXT, qty INTEGER, double_sided INTEGER, files TEXT,
  PRIMARY KEY (deck_id, position));
CREATE INDEX IF NOT EXISTS deck_cards_card ON deck_cards(card_key);
"""


def connect() -> sqlite3.Connection:
    LIB.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def norm(s) -> str:
    """Compare key: lower case letters and digits only (accents dropped), the way plugins sanitise file names."""
    s = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in s.lower() if c.isalnum() and not unicodedata.combining(c))


def slug(s: str, n: int = 60) -> str:
    s = re.sub(r"[^\w\-. ]+", "_", str(s or ""), flags=re.UNICODE).strip(" ._")
    return re.sub(r"\s+", " ", s)[:n] or "_"


# ---------------------------------------------------------------- card objects in raw JSON

# field -> keys tried in order ("a.b" reaches into a nested dict)
FIELDS = {
    "name": ("card_title", "cardName", "name", "name_en", "card_name", "cardName", "title", "Name"),
    "number": ("collector_number", "card_set_id", "card_number", "cardNumber", "number", "code", "card_code",
               "cardId", "card_id", "stub", "id"),
    "set_code": ("set", "set_code", "pack_code", "expansionAbbreviation", "set.ptcgoCode", "set_id", "setCode", "expansion.code", "set.id", "set.code"),
    "set_name": ("set_name", "pack_name", "set.name", "release.name", "expansion.name", "setName", "cycle_name"),
    "type": ("type_line", "type_name", "type_en", "card_type", "type", "types", "supertype", "cardType", "category", "kind"),
    "rarity": ("rarity", "rarity_name", "rarity_code", "Rarity", "set_rarity"),
    "cost": ("mana_cost", "cost.value", "cost", "card_cost", "play_cost", "ink_cost", "inkCost", "energy", "Cost", "convertedManaCost"),
    "power": ("power", "card_power", "atk", "attack", "strength", "dp", "ap", "AP", "Power", "might"),
    "defense": ("toughness", "def", "defense", "defence", "willpower", "health", "armor", "Defense", "durability", "life"),
    "hp": ("hp", "HP", "lore", "level", "loyalty"),
    "color": ("colors", "color", "card_color", "faction_name", "house", "aspects", "element", "elements", "ink", "faction"),
    "text": ("oracle_text", "text_en", "text", "effectText", "card_text", "main_effect", "desc", "effect", "rules_text", "rulesText", "body", "Text"),
}
SUBTITLES = ("version", "cardTitle", "subtitle")
DECK_LISTS = ("cards", "slots", "deck_cards", "mainboard", "main", "sideboard", "cardList", "list", "deck", "sections")
HINTS = {"rarity", "type", "type_line", "cost", "collector_number", "card_number", "cardNumber", "code", "set", "set_code",
         "oracle_text", "text", "card_text", "power", "hp", "image_uris", "images", "imagesrc", "image", "card_image",
         "atk", "def", "pack_code", "type_code", "stub", "life", "type_en", "editions", "cmc", "rarity_name", "card_set_id", "subtypes", "traits", "cardType"}
SKIP_STAT = re.compile(r"(^|_)(uri|url|uris|id|ids|image|images|imagesrc|img|src|link|href|price|prices|legalities|"
                       r"purchase|related|date|scraped|updated|created|octgn|tcgplayer|cardmarket|mtgo|arena|"
                       r"multiverse|position|object|highres|lang|games|finishes|uuid)($|_)", re.I)


SKIP_CAMEL = re.compile(r"[a-z](Id|Ids|Path|Url|Uri|Price|Count|Time|Date|At)$")  # variantId, frontImagePath, ...


REF_RE = re.compile(r"^[0-9a-f]{24}(, [0-9a-f]{24})*$")  # database ids (carde.io sends set/rarity/type as ids)


def is_ref(v) -> bool:
    if isinstance(v, list):
        return bool(v) and all(is_ref(x) for x in v)
    return isinstance(v, str) and bool(REF_RE.match(v))


def pick(d: dict, keys):
    for k in keys:
        cur = d
        for part in k.split("."):
            cur = cur.get(part) if isinstance(cur, dict) else None
        if cur in (None, "", [], {}) or isinstance(cur, bool) or is_ref(cur):
            continue
        if isinstance(cur, dict):
            cur = cur.get("name") or cur.get("code")
            if not cur:
                continue
        if isinstance(cur, list):
            cur = ", ".join(str(x.get("name", x) if isinstance(x, dict) else x) for x in cur if x not in (None, ""))
        if isinstance(cur, float) and cur.is_integer():
            cur = int(cur)
        return html.unescape(re.sub(r"<[^>]+>", "", str(cur))).strip()
    return None


def is_card(d: dict) -> bool:
    name = next((d.get(k) for k in FIELDS["name"] if isinstance(d.get(k), str) and d.get(k).strip()), None)
    if not name or len(d) < 3:
        return False
    # a deck is a dict holding the card list, not a card
    if any(isinstance(d.get(k), (list, dict)) and d.get(k) for k in DECK_LISTS):
        return False
    return len(HINTS & set(d)) >= 1


def walk(obj, depth=0):
    if depth > 8:
        return
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk(v, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v, depth + 1)


def stats_of(d: dict) -> dict:
    """Every short scalar field the card object has, for the per-game Excel sheet."""
    out = {}
    for k, v in d.items():
        if SKIP_STAT.search(k) or SKIP_CAMEL.search(k) or k in FIELDS["name"]:
            continue
        if isinstance(v, list) and v and all(isinstance(x, (str, int, float)) for x in v):
            v = ", ".join(map(str, v))
        if isinstance(v, dict) and isinstance(v.get("name"), str):
            v = v["name"]
        if isinstance(v, bool) or v in (None, "") or not isinstance(v, (str, int, float)):
            continue
        v = html.unescape(re.sub(r"<[^>]+>", "", str(v))).strip()
        if v and len(v) <= 400 and not is_ref(v):
            out[k] = v
        if len(out) >= 40:
            break
    return out


def record(game: str, d: dict, source_url: str = "") -> dict:
    r = {f: pick(d, keys) for f, keys in FIELDS.items()}
    sub = next((d[k].strip() for k in SUBTITLES if isinstance(d.get(k), str) and d[k].strip()), None)
    if r["name"] and sub and sub != r["name"]:  # Lorcana "Elsa - Spirit of Winter", SWU "Han Solo, Audacious Smuggler"
        r["name"] = f'{r["name"]}{", " if "cardTitle" in d else " - "}{sub}'
    if r["number"] and r["number"] == r["name"]:
        r["number"] = None
    # card_faces (MTG double-faced): take text/stats from the front face when the card has none of its own
    faces = d.get("card_faces")
    if isinstance(faces, list) and faces and isinstance(faces[0], dict):
        for f, keys in FIELDS.items():
            if f != "name" and not r[f]:
                r[f] = pick(faces[0], keys)
    r["stats"] = stats_of(d)
    url = d.get("url")
    r["source_url"] = d.get("scryfall_uri") or (url if isinstance(url, str) and url.startswith("http") else source_url)
    r["game"] = game
    return r


def records_from_raw(game: str, deck: Path) -> list[dict]:
    out = []
    for f in sorted((deck / "raw").glob("0*.json")):
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for d in walk(j.get("body")):
            if is_card(d):
                out.append(record(game, d, j.get("url", "")))
    return out


def deck_info_from_raw(deck: Path) -> dict:
    """Deck title and author when the source site sends them (a dict holding the card list)."""
    for f in sorted((deck / "raw").glob("0*.json")):
        try:
            body = json.loads(f.read_text(encoding="utf-8")).get("body")
        except (OSError, ValueError):
            continue
        for d in walk(body):
            if not isinstance(d, dict) or is_card(d):
                continue
            has_list = any(isinstance(v, (list, dict)) and k in DECK_LISTS
                           for k, v in d.items())
            if not has_list:
                continue
            name = pick(d, ("title", "name", "deck_name", "deckName", "deck.name"))
            author = pick(d, ("user.username", "user.name", "user.profile.nickname", "author", "owner", "user_name",
                              "username", "creator", "createdBy"))
            if name or author:
                return {"name": name, "author": author}
    return {}


# ---------------------------------------------------------------- look-ups for plugins that never ask a database

CODE_RE = {
    "one_piece": re.compile(r"((?:OP|ST|EB|PRB|P)\d{0,2}-\d{3})", re.I),
    "gundam": re.compile(r"((?:GD|ST|EXB|EXR|EXRP|R|T|B)\d{0,2}-\d{3})", re.I),
    "digimon": re.compile(r"((?:BT|EX|ST|RB|LM|P)\d{0,2}-\d{2,3})", re.I),
    "yugioh": re.compile(r"^(\d{5,10})_"),
}
_session = None


def session():
    global _session
    if _session is None:
        import requests_cache
        _session = requests_cache.CachedSession(str(HERE / "data" / "library" / "http-cache"), backend="sqlite", expire_after=timedelta(days=30),
                                                allowable_codes=(200,), stale_if_error=True)
        _session.headers["User-Agent"] = "SCM-Studio card catalog (local)"
    return _session


def pokemon(s, code: str) -> dict | None:
    """code = "SSP 32|Charcadet". pokemontcg.io first (often answers 500/502), then TCGdex (has the newest sets)."""
    set_code, number = code.split("|")[0].split(" ", 1)
    name = code.split("|", 1)[1] if "|" in code else ""
    try:
        r = s.get("https://api.pokemontcg.io/v2/cards", params={"q": f"set.ptcgoCode:{set_code} number:{number}"}, timeout=40)
        d = (r.json().get("data") or [None])[0] if r.ok else None
    except (ValueError, OSError):
        d = None
    if d:
        return {**d, "set_code": set_code, "attacks": " / ".join(
            f'{a.get("name")} {a.get("damage") or ""}'.strip() for a in d.get("attacks") or []),
            "weaknesses": ", ".join(f'{w.get("type")} {w.get("value")}' for w in d.get("weaknesses") or []),
            "abilities": " / ".join(a.get("name", "") for a in d.get("abilities") or [])}
    if not name:
        return None
    found = s.get("https://api.tcgdex.net/v2/en/cards", params={"name": f"eq:{name}", "localId": number}, timeout=30)
    found = found.json() if found.ok else []
    best = None
    for c in found[:6]:
        detail = s.get(f'https://api.tcgdex.net/v2/en/cards/{c["id"]}', timeout=30).json()
        st = s.get(f'https://api.tcgdex.net/v2/en/sets/{detail["set"]["id"]}', timeout=30).json()
        if (st.get("abbreviation") or {}).get("official", "").upper() == set_code:
            best = detail
            break
        best = best or detail
    if not best:
        return None
    return {"name": best.get("name"), "number": number, "set_code": set_code, "set_name": best["set"].get("name"),
            "rarity": best.get("rarity"), "supertype": best.get("category"), "hp": best.get("hp"), "types": best.get("types"),
            "stage": best.get("stage"), "attacks": " / ".join(f'{a.get("name")} {a.get("damage") or ""}'.strip() for a in best.get("attacks") or []),
            "weaknesses": ", ".join(f'{w.get("type")} {w.get("value")}' for w in best.get("weaknesses") or []),
            "abilities": " / ".join(a.get("name", "") for a in best.get("abilities") or []),
            "retreat": best.get("retreat"), "regulationMark": best.get("regulationMark"), "illustrator": best.get("illustrator"),
            "url": f'https://tcgdex.dev/cards/{best.get("id")}'}


def lookup(game: str, code: str) -> dict | None:
    s = session()
    try:
        if game == "yugioh":
            j = s.get(f"https://db.ygoprodeck.com/api/v7/cardinfo.php?id={int(code)}", timeout=25).json()
            d = (j.get("data") or [None])[0]
            if d:
                sets = d.get("card_sets") or []
                d = {**d, "rarity": ", ".join(dict.fromkeys(x.get("set_rarity", "") for x in sets if x.get("set_rarity"))),
                     "number": str(d["id"]), "set_name": sets[0].get("set_name") if sets else None,
                     "url": d.get("ygoprodeck_url")}
                d.pop("card_sets", None)
            return d
        if game == "pokemon":
            return pokemon(s, code)
        if game == "digimon":
            j = s.get(f"https://digimoncard.io/api-public/search?card={code}", timeout=25).json()
            return next((x for x in j if isinstance(x, dict) and str(x.get("id", "")).upper() == code.upper()), None) if isinstance(j, list) else None
        if game == "one_piece":
            kind = "decks" if code.upper().startswith("ST") else "sets"
            r = s.get(f"https://optcgapi.com/api/{kind}/card/{code.upper()}/", timeout=25)
            j = r.json() if r.ok else []
            return j[0] if isinstance(j, list) and j else None
        if game == "gundam":
            r = s.get(f"https://www.gundam-gcg.com/en/cards/detail.php?detailSearch={code.upper()}", timeout=25)
            if not r.ok:
                return None
            t = re.sub(r"\s+", " ", r.text)
            d = {re.sub("<[^>]+>", "", k).strip().rstrip("."): re.sub("<[^>]+>", "", v).strip()
                 for k, v in re.findall(r"<dt[^>]*>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>", t)}
            name = re.search(r'class="cardName[^"]*"[^>]*>(.*?)<', t)
            rarity = re.search(r'class="rarity[^"]*"[^>]*>(.*?)<', t)
            if not name:
                return None
            return {"name": html.unescape(name.group(1).strip()), "rarity": rarity and rarity.group(1).strip(),
                    "number": code.upper(), "type": d.get("TYPE"), "cost": d.get("COST"), "power": d.get("AP"),
                    "hp": d.get("HP"), "color": d.get("COLOR"), "set_name": d.get("Where to get it"),
                    "level": d.get("Lv"), "zone": d.get("Zone"), "trait": d.get("Trait"), "link": d.get("Link"),
                    "source_title": d.get("Source Title"),
                    "url": f"https://www.gundam-gcg.com/en/cards/detail.php?detailSearch={code.upper()}"}
    except Exception:
        return None
    return None


# ---------------------------------------------------------------- image files -> deck entries

def image_files(d: Path) -> list[Path]:
    if not d.exists():
        return []
    key = lambda p: [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", p.name)]
    return sorted((p for p in d.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXT), key=key)


def groups(deck: Path, game: str) -> list[dict]:
    """Plugins name copies "<deck index><card label><copy no>" (yugioh: "<passcode>_<copy no>"); put copies back together."""
    out: dict[str, dict] = {}
    ds = {p.stem for p in image_files(deck / "double_sided")}
    for p in image_files(deck / "front"):
        stem = p.stem
        m = re.match(r"^(.*?)_(\d+)$", stem) or re.match(r"^(.*?\D)(\d+)$", stem)
        base = m.group(1) if m else stem
        g = out.setdefault(base, {"base": base, "files": [], "ds": False})
        g["files"].append(p.name)
        g["ds"] = g["ds"] or stem in ds
        if len(g["files"]) == 1:
            im = re.match(r"^(\d+)(.*)$", stem) if game != "yugioh" else None
            g["index"] = int(im.group(1)) if im else len(out)
            g["indexed"] = bool(im)
            g["body"] = im.group(2) if im else stem  # label + copy number
            g["label"] = re.sub(r"_?\d+$", "", g["body"]) if "_" in stem else g["body"]
    return list(out.values())


def match(g: dict, recs: list[dict]) -> dict | None:
    """The record whose name or code the file label starts with (only a copy number may follow). The deck index in
    front is taken as short as possible first, so a name that starts with a digit (".45 Automatic") still matches."""
    stem = Path(g["files"][0]).stem
    lead = len(re.match(r"^\d*", stem).group(0)) if g.get("indexed") else 0
    for k in range(1, lead + 1) if lead else [0]:
        body = norm(stem[k:])
        best, best_len = None, 0
        for r in recs:
            for cand in (r.get("name"), (r.get("name") or "").split("//")[0], r.get("number"), r["stats"].get("stub")):
                c = norm(cand)
                if c and len(c) > best_len and body.startswith(c) and (body == c or body[len(c):].isdigit()):
                    best, best_len = r, len(c)
        if best:
            if lead:
                g["index"] = int(stem[:k])
            return best
    return None


def decklist(game: str, text: str) -> dict[int, str]:
    """Look-up codes the file names do not carry, by the plugin's deck index (Pokémon: "3 Charcadet SSP 32")."""
    out = {}
    if game == "pokemon":
        lines = [m for m in (re.match(r"^\s*(\d+)\s+(.+?)\s+([A-Z0-9-]{2,6})\s+(\d+[a-z]?)\s*$", l, re.I)
                             for l in (text or "").splitlines()) if m]
        out = {i: f"{m.group(3).upper()} {m.group(4)}|{m.group(2).strip()}" for i, m in enumerate(lines, 1)}
    return out


def code_for(game: str, g: dict, listed: dict[int, str]) -> str | None:
    if listed:
        return listed.get(g["index"])
    if game in CODE_RE:
        m = CODE_RE[game].search(g["files"][0] if game == "yugioh" else g["label"])
        return m.group(1).upper() if m else None
    return None


def card_key(game: str, r: dict) -> str:
    return ":".join([game, norm(r.get("set_code")), norm(r.get("number")), norm(r.get("name"))])


def pretty(label: str) -> str:
    return re.sub(r"([a-z])([A-Z])", r"\1 \2", label).replace("_", " ").strip()


def ingest(deck: Path, meta: dict) -> dict:
    """Store one fetched deck's cards; returns a summary for deck.json."""
    game = meta["plugin"]
    recs = records_from_raw(game, deck)
    gs = groups(deck, game)
    listed = decklist(game, meta.get("deck", ""))
    con = connect()
    now = time.time()
    found = 0
    rows = []
    for pos, g in enumerate(sorted(gs, key=lambda g: g["index"]), 1):
        r = match(g, recs)
        code = None if r else code_for(game, g, listed)
        if code:  # cards already looked up once come from the catalog, the rest from the source (HTTP cache)
            hit = con.execute("SELECT * FROM cards WHERE game=? AND code=? AND found=1", (game, code)).fetchone()
            if hit:
                r = {**dict(hit), "stats": json.loads(hit["stats"] or "{}")}
            elif d := lookup(game, code):
                r = record(game, d)
                r["number"] = r.get("number") or code
        ok = r is not None
        if not r:
            r = {"game": game, "name": pretty(g["label"]), "stats": {}, "source_url": ""}
        found += ok
        key = r.get("key") or card_key(game, r)
        img = IMAGES / game / (slug(key.split(":", 1)[1].replace(":", "_") or g["label"], 90) + Path(g["files"][0]).suffix.lower())
        if not img.exists():
            img.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copyfile(deck / "front" / g["files"][0], img)
            except OSError:
                pass
        con.execute("""INSERT INTO cards (key, game, name, set_code, set_name, number, type, rarity, cost, power, defense, hp,
                       color, text, stats, image, source_url, found, updated, code) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(key) DO UPDATE SET name=excluded.name, set_code=excluded.set_code, set_name=excluded.set_name,
                       number=excluded.number, type=excluded.type, rarity=excluded.rarity, cost=excluded.cost, power=excluded.power,
                       defense=excluded.defense, hp=excluded.hp, color=excluded.color, text=excluded.text, stats=excluded.stats,
                       source_url=excluded.source_url, found=excluded.found, updated=excluded.updated,
                       code=COALESCE(excluded.code, cards.code)
                       WHERE excluded.found >= cards.found""",
                    (key, game, r.get("name"), r.get("set_code"), r.get("set_name"), r.get("number"), r.get("type"),
                     r.get("rarity"), r.get("cost"), r.get("power"), r.get("defense"), r.get("hp"), r.get("color"),
                     r.get("text"), json.dumps(r.get("stats") or {}, ensure_ascii=False), str(img.relative_to(LIB)),
                     r.get("source_url"), int(ok), now, code))
        rows.append((meta["id"], pos, key, len(g["files"]), int(g["ds"]), json.dumps(g["files"], ensure_ascii=False)))
    con.execute("DELETE FROM deck_cards WHERE deck_id=?", (meta["id"],))
    con.executemany("INSERT INTO deck_cards VALUES (?,?,?,?,?,?)", rows)
    summary = {"cards": sum(r[3] for r in rows), "kinds": len(rows), "found": found}
    save_deck(con, meta, deck, summary)
    con.commit()
    con.close()
    return summary


def save_deck(con, meta: dict, deck: Path, summary: dict | None = None) -> None:
    s = summary or {}
    con.execute("""INSERT INTO decks (id, game, game_name, owner, name, author, format, source, folder, cards, kinds, found, created, updated)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET owner=excluded.owner, name=excluded.name,
                   author=excluded.author, folder=excluded.folder, updated=excluded.updated,
                   cards=COALESCE(?, decks.cards), kinds=COALESCE(?, decks.kinds), found=COALESCE(?, decks.found)""",
                (meta["id"], meta["plugin"], meta.get("game"), meta.get("owner"), meta.get("name"), meta.get("author"),
                 meta.get("format"), meta.get("deck", "")[:2000], str(deck.relative_to(LIB.parent)), s.get("cards"), s.get("kinds"),
                 s.get("found"), meta.get("created"), time.time(), s.get("cards"), s.get("kinds"), s.get("found")))


def update_deck(deck: Path, meta: dict) -> None:
    con = connect()
    save_deck(con, meta, deck)
    con.commit()
    con.close()


def forget_deck(deck_id: str) -> None:
    con = connect()
    con.execute("DELETE FROM deck_cards WHERE deck_id=?", (deck_id,))
    con.execute("DELETE FROM decks WHERE id=?", (deck_id,))
    con.commit()
    con.close()


# ---------------------------------------------------------------- reading

def cards(game: str = "", q: str = "", owner: str = "") -> list[dict]:
    con = connect()
    sql = """SELECT c.*, SUM(dc.qty) AS copies, COUNT(DISTINCT dc.deck_id) AS deck_count,
                    GROUP_CONCAT(DISTINCT COALESCE(NULLIF(d.owner, ''), 'ไม่ระบุเจ้าของ') || ' / ' || d.name) AS used_in
             FROM cards c JOIN deck_cards dc ON dc.card_key = c.key JOIN decks d ON d.id = dc.deck_id WHERE 1=1"""
    args: list = []
    if game:
        sql += " AND c.game=?"
        args.append(game)
    if owner:  # "-" = decks without an owner
        sql += " AND COALESCE(d.owner, '')=?"
        args.append("" if owner == "-" else owner)
    if q:
        sql += " AND (c.name LIKE ? OR c.number LIKE ? OR c.rarity LIKE ? OR c.type LIKE ?)"
        args += [f"%{q}%"] * 4
    sql += " GROUP BY c.key ORDER BY c.game, c.name"
    out = [{**dict(r), "stats": json.loads(r["stats"] or "{}")} for r in con.execute(sql, args)]
    con.close()
    return out


def owners() -> list[str]:
    con = connect()
    out = [r[0] for r in con.execute("SELECT DISTINCT owner FROM decks WHERE owner<>'' ORDER BY owner")]
    con.close()
    return out


# ---------------------------------------------------------------- Excel

COMMON = [("game_name", "เกม"), ("name", "ชื่อการ์ด"), ("set_code", "ชุด"), ("set_name", "ชื่อชุด"), ("number", "เลข/รหัส"),
          ("type", "ประเภท"), ("rarity", "Rarity"), ("cost", "Cost"), ("power", "Power/ATK"), ("defense", "Defense/HP รอง"),
          ("hp", "HP/Level"), ("color", "สี/ฝ่าย"), ("copies", "จำนวนใบรวม"), ("deck_count", "อยู่ในกี่เด็ค"),
          ("used_in", "เจ้าของ / เด็ค"), ("text", "ข้อความบนการ์ด"), ("image", "ไฟล์รูป"), ("source_url", "แหล่งข้อมูล")]


def export_xlsx(path: Path | None = None) -> Path:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.table import Table, TableStyleInfo

    path = path or EXPORTS / XLSX_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    con = connect()
    names = {r["game"]: r["game_name"] for r in con.execute("SELECT DISTINCT game, game_name FROM decks")}
    rows = cards()
    for r in rows:
        r["game_name"] = names.get(r["game"], r["game"])
    decks = [dict(r) for r in con.execute("SELECT * FROM decks ORDER BY game_name, owner, created")]
    lines = [dict(r) for r in con.execute(
        """SELECT d.game_name, d.owner, d.name AS deck, dc.position, c.name, c.number, c.rarity, dc.qty, dc.double_sided
           FROM deck_cards dc JOIN decks d ON d.id=dc.deck_id JOIN cards c ON c.key=dc.card_key
           ORDER BY d.game_name, d.owner, d.name, dc.position""")]
    con.close()

    wb = Workbook()
    head_font = Font(bold=True, color="FFFFFF")
    head_fill = PatternFill("solid", fgColor="1F4E46")
    used_titles: set[str] = set()

    def sheet(title: str, header: list[str], data: list[list], widths: dict[int, int] | None = None, first=False):
        ws = wb.active if first else wb.create_sheet()
        t = re.sub(r"[\[\]:*?/\\]", " ", title)[:31]
        while t in used_titles:
            t = t[:28] + f" {len(used_titles)}"
        used_titles.add(t)
        ws.title = t
        ws.append(header)
        for row in data:
            ws.append(["" if v is None else v for v in row])
        for c in ws[1]:
            c.font, c.fill = head_font, head_fill
            c.alignment = Alignment(vertical="center")
        ws.freeze_panes = "B2" if len(header) > 3 else "A2"
        for i, h in enumerate(header, 1):
            w = (widths or {}).get(i) or min(45, max(10, len(str(h)) + 4, *(len(str(r[i - 1])) + 2 for r in data[:200] if i - 1 < len(r))))
            ws.column_dimensions[get_column_letter(i)].width = w
        if data:
            ref = f"A1:{get_column_letter(len(header))}{len(data) + 1}"
            tab = Table(displayName=f"T{len(used_titles)}", ref=ref)
            tab.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
            ws.add_table(tab)
        return ws

    # summary
    per = {}
    for d in decks:
        k = (d["game_name"], d["owner"] or "-")
        a = per.setdefault(k, [0, 0])
        a[0] += 1
        a[1] += d["cards"] or 0
    sheet("สรุป", ["เกม", "เจ้าของ", "จำนวนเด็ค", "จำนวนการ์ด (ใบ)"], [[g, o, n, c] for (g, o), (n, c) in sorted(per.items())], first=True)
    ws = wb["สรุป"]
    ws.append([])
    ws.append(["การ์ดไม่ซ้ำทั้งหมด", len(rows)])
    ws.append(["มีข้อมูลครบ (ชื่อ/ค่าพลัง/rarity)", sum(1 for r in rows if r["found"])])
    ws.append(["สร้างเมื่อ", time.strftime("%Y-%m-%d %H:%M")])

    def common_row(r):
        return [r.get(k) for k, _ in COMMON]

    ws = sheet("การ์ดทั้งหมด", [h for _, h in COMMON], [common_row(r) for r in rows], {16: 60, 17: 30, 18: 30})
    img_col = [k for k, _ in COMMON].index("image") + 1
    for i, r in enumerate(rows, 2):
        c = ws.cell(row=i, column=img_col)
        if r.get("image"):
            c.hyperlink = (LIB / r["image"]).as_uri()
        c.alignment = Alignment(wrap_text=False)

    # one sheet per game: the common columns plus every stat that game's source sends
    for game in sorted({r["game"] for r in rows}):
        g_rows = [r for r in rows if r["game"] == game]
        keys = []
        for r in g_rows:
            for k in r["stats"]:
                if k not in keys:
                    keys.append(k)
        base = [("name", "ชื่อการ์ด"), ("number", "เลข/รหัส"), ("set_name", "ชื่อชุด"), ("rarity", "Rarity"), ("type", "ประเภท"),
                ("copies", "จำนวนใบรวม"), ("used_in", "เจ้าของ / เด็ค")]
        sheet(names.get(game, game), [h for _, h in base] + keys,
              [[r.get(k) for k, _ in base] + [r["stats"].get(k) for k in keys] for r in g_rows])

    sheet("เด็ค", ["เกม", "เจ้าของ", "ชื่อเด็ค", "ผู้สร้าง (จากเว็บ)", "format", "จำนวนใบ", "ชนิด", "มีข้อมูล", "วันที่", "โฟลเดอร์", "ต้นทาง"],
          [[d["game_name"], d["owner"], d["name"], d["author"], d["format"], d["cards"], d["kinds"], d["found"],
            time.strftime("%Y-%m-%d %H:%M", time.localtime(d["created"] or 0)), d["folder"], (d["source"] or "").split("\n")[0][:200]]
           for d in decks])
    sheet("การ์ดในเด็ค", ["เกม", "เจ้าของ", "เด็ค", "ลำดับ", "ชื่อการ์ด", "เลข/รหัส", "Rarity", "จำนวน", "สองหน้า"],
          [[x["game_name"], x["owner"], x["deck"], x["position"], x["name"], x["number"], x["rarity"], x["qty"],
            "ใช่" if x["double_sided"] else ""] for x in lines])
    wb.save(path)
    return path
