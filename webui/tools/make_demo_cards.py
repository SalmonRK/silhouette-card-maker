"""Draw the demo deck (8 fronts + 1 back) used by "Try with demo cards".

Each card is 63 x 88 mm at 300 ppi with a dark frame whose inner edge is exactly 2 mm inside the trim, plus a thin
light line 1 mm inside the trim: after cutting, the frame width on each side shows how far the cut drifted.
Run:  python webui/tools/make_demo_cards.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "static" / "assets" / "demo"
PPI = 300
MM = PPI / 25.4
W, H = round(63 * MM), round(88 * MM)
FONT = Path(__file__).resolve().parents[2] / "assets" / "arial.ttf"
PALETTE = [  # (frame, field, accent)
    ("#14322B", "#E7EFEC", "#E5322D"), ("#1B2B4A", "#E9EEF7", "#F2A93B"),
    ("#3A1E2E", "#F4EAEF", "#1F9D57"), ("#2B2B2B", "#EEEEEA", "#2F7DD1"),
    ("#123B44", "#E5F1F2", "#D9534F"), ("#3B2A12", "#F5EFE4", "#2C8C99"),
    ("#26164A", "#ECE8F6", "#E8B10C"), ("#0F3320", "#E4F0E8", "#C2410C"),
]


def font(size):
    try:
        return ImageFont.truetype(str(FONT), size)
    except OSError:
        return ImageFont.load_default()


def front(i, frame, field, accent):
    im = Image.new("RGB", (W, H), frame)
    d = ImageDraw.Draw(im)
    m2 = round(2 * MM)
    d.rounded_rectangle([m2, m2, W - m2, H - m2], radius=round(2 * MM), fill=field)
    m1 = round(1 * MM)
    d.rectangle([m1, m1, W - m1, H - m1], outline="#FFFFFF", width=2)
    cx, cy = W // 2, int(H * 0.44)
    r = int(W * 0.30)
    # a different simple emblem per card: polygon with i+3 sides
    import math
    n = 3 + i
    pts = [(cx + r * math.cos(-math.pi / 2 + k * 2 * math.pi / n), cy + r * math.sin(-math.pi / 2 + k * 2 * math.pi / n)) for k in range(n)]
    d.polygon(pts, fill=accent)
    d.ellipse([cx - r // 3, cy - r // 3, cx + r // 3, cy + r // 3], fill=field)
    d.text((cx, cy), str(i + 1), font=font(int(r * 0.5)), fill=frame, anchor="mm")
    d.text((cx, int(H * 0.80)), f"DEMO {i + 1:02d}", font=font(int(4.2 * MM)), fill=frame, anchor="mm")
    d.text((cx, int(H * 0.87)), "63 x 88 mm  |  frame 2 mm", font=font(int(2.4 * MM)), fill=frame, anchor="mm")
    return im


def back():
    im = Image.new("RGB", (W, H), "#14322B")
    d = ImageDraw.Draw(im)
    step = round(4 * MM)
    for x in range(-H, W + H, step):
        d.line([(x, 0), (x + H, H)], fill="#1D463C", width=6)
        d.line([(x, H), (x + H, 0)], fill="#1D463C", width=6)
    m2 = round(2 * MM)
    d.rounded_rectangle([m2, m2, W - m2, H - m2], radius=round(2 * MM), outline="#E5322D", width=6)
    cx, cy = W // 2, H // 2
    r = int(W * 0.22)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill="#14322B", outline="#FFFFFF", width=8)
    s = r // 2
    d.rectangle([cx - s, cy - s, cx + s, cy + s], fill="#FFFFFF")  # echo of the registration square
    return im


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for i, (fr, fi, ac) in enumerate(PALETTE):
        front(i, fr, fi, ac).save(OUT / f"demo-front-{i + 1:02d}.png", dpi=(PPI, PPI))
    back().save(OUT / "demo-back.png", dpi=(PPI, PPI))
    print("wrote", OUT)
