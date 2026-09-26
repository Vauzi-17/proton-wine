#!/usr/bin/env python3
# files.ico of programs/files: a folder on a rounded square, in the purple light scheme
# (the running program draws its window icon in the colors of the current scheme).
#   python3 mkfilesicon.py files_symbols_filled.ttf files.ico
import sys
from PIL import Image, ImageDraw, ImageFont

font_path, out = sys.argv[1], sys.argv[2]
container, content = (0xe9, 0xdd, 0xff), (0x4d, 0x3d, 0x75)
folder = chr(0xe2c7)
images = []
for size in (16, 24, 32, 48, 64, 128, 256):
    scale = 4
    big = size * scale
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, big - 1, big - 1), radius=big * 7 // 24, fill=container + (255,))
    font = ImageFont.truetype(font_path, big * 2 // 3)
    box = draw.textbbox((0, 0), folder, font=font)
    x = (big - (box[2] - box[0])) / 2 - box[0]
    y = (big - (box[3] - box[1])) / 2 - box[1]
    draw.text((x, y), folder, font=font, fill=content + (255,))
    images.append(img.resize((size, size), Image.LANCZOS))
images[-1].save(out, format="ICO", sizes=[(i.width, i.height) for i in images], append_images=images[:-1])
print(out)
