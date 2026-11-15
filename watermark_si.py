# SI-assisted: written with Claude (Anthropic's AI assistant); reviewed, tested and directed by the project developer.
"""Stamp a VISIBLE "SI-generated" watermark and a metadata note on an image made with an SI (AI) tool.

    python watermark_si.py avatar.png "Name of the image tool"     ->  avatar_SI.png

The watermark sits at the bottom centre, small enough to survive the round crop of a Telegram avatar.
The tool name is also written into the PNG metadata (Description / Comment)."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from PIL.PngImagePlugin import PngInfo


def _font(size):
    for name in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def stamp(src, tool="an SI image tool", text="SI-generated"):
    im = Image.open(src).convert("RGBA")
    w, h = im.size
    d0 = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    size = max(10, int(w * 0.1))
    for _ in range(3):  # fit the text to about half of the image width
        l, t, r, b = d0.textbbox((0, 0), text, font=_font(size))
        size = max(10, int(size * (w * 0.5) / max(r - l, 1)))
    font = _font(size)
    l, t, r, b = d0.textbbox((0, 0), text, font=font)
    tw, th, pad = r - l, b - t, max(4, size // 3)
    x, y = (w - tw) // 2, int(h * 0.84)
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    d.rounded_rectangle([x - pad, y - pad // 2, x + tw + pad, y + th + pad], radius=pad, fill=(0, 0, 0, 175))
    d.text((x - l, y - t + pad // 4), text, font=font, fill=(255, 255, 255, 255))
    out = Image.alpha_composite(im, ov)
    meta = PngInfo()
    note = f"SI-generated image (tool: {tool}). Visible watermark added by the developer."
    meta.add_text("Description", note)
    meta.add_text("Comment", note)
    meta.add_text("Software", "SKYDAR watermark_si.py")
    dst = Path(src).with_name(Path(src).stem + "_SI.png")
    out.save(dst, pnginfo=meta)
    return dst


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit('Usage: python watermark_si.py image.png "Name of the image tool"')
    print("Saved:", stamp(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "an SI image tool"))
