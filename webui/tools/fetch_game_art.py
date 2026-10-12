"""Download one sample card image per game for the deck-import game picker (static/assets/games/<plugin>.jpg).

Run once:  venv/Scripts/python webui/tools/fetch_game_art.py   (start.bat does it on first run)
The images belong to each game's publisher, so they are fetched to your machine and not kept in git; without them
the picker shows each game's initials. Best effort: a source that changed or is down is skipped.
"""
import io, json, os, urllib.request, urllib.parse

from PIL import Image

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'static', 'assets', 'games')
os.makedirs(OUT, exist_ok=True)
UA = {'User-Agent': 'SCM-Studio-design/0.1', 'Accept': 'application/json'}

def get(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read(), r.headers.get('Content-Type', '')

def js(url, **kw):
    return json.loads(get(url, **kw)[0])

def first(d, *keys):
    for k in keys:
        cur = d
        try:
            for p in k.split('.'):
                cur = cur[int(p)] if p.isdigit() else cur[p]
            if cur:
                return cur
        except Exception:
            pass

SRC = {
    'riftbound': lambda: 'https://cdn.piltoverarchive.com/cards/OGN-001.webp',
    'ashes_reborn': lambda: 'https://cdn.ashes.live/images/cards/aradel-summergaard.jpg',
    'mtg': lambda: 'https://api.scryfall.com/cards/named?exact=Lightning+Bolt&format=image&version=normal',
    'pokemon': lambda: 'https://images.pokemontcg.io/base1/4.png',
    'yugioh': lambda: 'https://images.ygoprodeck.com/images/cards/46986414.jpg',
    'one_piece': lambda: 'https://en.onepiece-cardgame.com/images/cardlist/card/OP01-001.png',
    'digimon': lambda: 'https://world.digimoncard.com/images/cardlist/card/BT1-010.png',
    'lorcana': lambda: first(js('https://api.lorcast.com/v0/cards/search?q=' + urllib.parse.quote('mickey mouse')), 'results.0.image_uris.digital.normal'),
    'star_wars_unlimited': lambda: first(js('https://api.swu-db.com/cards/SOR/010'), 'FrontArt'),
    'netrunner': lambda: first(js('https://api.netrunnerdb.com/api/v3/public/cards/hedge_fund'), 'data.attributes.latest_printing_images.nrdb_classic.large', 'data.attributes.images.nrdb_classic.large'),
    'arkham_horror_lcg': lambda: 'https://arkhamdb.com' + js('https://arkhamdb.com/api/public/card/01001')['imagesrc'],
    'lotr_lcg': lambda: 'https://ringsdb.com' + js('https://ringsdb.com/api/public/card/01001')['imagesrc'],
    'grand_archive': lambda: 'https://api.gatcg.com' + first(js('https://api.gatcg.com/cards/search?name=' + urllib.parse.quote('Lorraine')), 'data.0.editions.0.image'),
    'altered': lambda: first(js('https://api.altered.gg/cards?itemsPerPage=1&locale=en-us'), 'hydra:member.0.imagePath', 'member.0.imagePath'),
    'gundam': lambda: 'https://www.gundam-gcg.com/en/images/cards/card/GD01-001.webp',
    'flesh_and_blood': lambda: first(js('https://api.cardvault.fabtcg.com/carddb/api/v1/card_id/WTR001'), 'image', 'images.0.url', 'printings.0.image_url'),
    'final_fantasy': lambda: first(js('https://fftcg.square-enix-games.com/na/get-cards', data=json.dumps({'language': 'en', 'text': 'Cloud', 'type': [], 'element': [], 'cost': [], 'rarity': [], 'power': [], 'category_1': [], 'set': [], 'multicard': '', 'ex_burst': '', 'code': '', 'special': '', 'exactmatch': 0}).encode(), headers={'Content-Type': 'application/json'}), 'cards.0.images.full.0', 'cards.0.images.thumbs.0'),
}

done = {}
for gid, fn in SRC.items():
    try:
        url = fn()
        if not url:
            raise ValueError('no url')
        data, ct = get(url, headers={'Accept': 'image/*'})
        if len(data) < 2000 or 'html' in ct:
            raise ValueError(f'not an image ({ct}, {len(data)} B)')
        ext = '.png' if data[:4] == b'\x89PNG' else '.webp' if data[8:12] == b'WEBP' else '.jpg'
        path = os.path.join(OUT, gid + ext)
        open(path, 'wb').write(data)
        done[gid] = os.path.basename(path)
        print('ok  ', gid, len(data))
    except Exception as e:
        print('FAIL', gid, str(e)[:120])
print(f'{len(done)} of {len(SRC)} games -> {os.path.normpath(OUT)}')
