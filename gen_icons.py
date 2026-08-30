import os
from PIL import Image, ImageDraw, ImageFont

SIZES = [76, 120, 152, 180, 192, 512]
OUT = os.path.join(os.path.dirname(__file__), "static", "icons")
os.makedirs(OUT, exist_ok=True)


def draw_icon(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    radius = int(size * 0.22)
    d.rounded_rectangle(
        [0, 0, size, size],
        radius=radius,
        fill=(255, 45, 85, 255),
    )

    inv = int(size * 0.30)
    d.rounded_rectangle(
        [inv, inv, size - inv, size - inv],
        radius=radius // 2,
        fill=(255, 255, 255, 255),
    )

    pts = int(size * 0.175)
    cx = size / 2
    cy = size / 2
    color = (26, 26, 46, 255)

    left = (cx - pts * 2.2, cy + pts * 0.4)
    mid = (cx - pts * 2.2, cy - pts * 0.6)
    d.line([left, mid], fill=color, width=max(1, int(size * 0.06)))

    d.ellipse(
        [left[0] - pts * 0.9, left[1] - pts * 0.9, left[0] + pts * 0.9, left[1] + pts * 0.9],
        fill=color,
    )
    d.ellipse(
        [mid[0] - pts * 0.9, mid[1] - pts * 0.9, mid[0] + pts * 0.9, mid[1] + pts * 0.9],
        fill=color,
    )

    bar_w = int(size * 0.16)
    d.rounded_rectangle(
        [mid[0], mid[1] - bar_w * 0.6, mid[0] + bar_w, mid[1] + bar_w * 0.6],
        radius=int(bar_w * 0.3),
        fill=color,
    )

    head = (mid[0] + bar_w * 1.5, mid[1])
    r = pts * 1.15
    d.ellipse(
        [head[0] - r, head[1] - r, head[0] + r, head[1] + r],
        outline=color,
        width=max(1, int(size * 0.08)),
    )

    return img


for s in SIZES:
    draw_icon(s).save(os.path.join(OUT, f"icon-{s}.png"))
    print(f"Generated icon-{s}.png")