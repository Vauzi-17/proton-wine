#!/usr/bin/env python3
# The folder, drive, computer and documents icons the Material 3 style gives the shell
# (programs/explorer/m3_*.ico), from the filled Material Symbols of the variable font.
#   python3 mkshellicons.py symbols.ttf symbols.codepoints outdir
import sys
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from PIL import Image, ImageDraw, ImageFont

font_path, codepoints, outdir = sys.argv[1:4]
cp = {}
for line in open(codepoints):
    name, code = line.split()
    cp.setdefault(name, int(code, 16))

filled = instancer.instantiateVariableFont(TTFont(font_path), {"FILL": 1, "wght": 400, "GRAD": 0, "opsz": 48})
filled.save(outdir + "/.symbols_filled.ttf")

FOLDER, NEUTRAL = (0x6c, 0x8f, 0xd0), (0x8d, 0x91, 0x99)
icons = [("m3_folder.ico", "folder", FOLDER), ("m3_folder_open.ico", "folder_open", FOLDER),
         ("m3_drive.ico", "hard_drive", NEUTRAL), ("m3_computer.ico", "computer", NEUTRAL),
         ("m3_documents.ico", "description", FOLDER)]
for name, symbol, color in icons:
    images = []
    for size in (16, 20, 24, 32, 48, 64, 256):
        big = size * 4
        img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype(outdir + "/.symbols_filled.ttf", big)
        glyph = chr(cp[symbol])
        box = draw.textbbox((0, 0), glyph, font=font)
        draw.text(((big - (box[2] - box[0])) / 2 - box[0], (big - (box[3] - box[1])) / 2 - box[1]), glyph,
                  font=font, fill=color + (255,))
        images.append(img.resize((size, size), Image.LANCZOS))
    images[-1].save(outdir + "/" + name, format="ICO", sizes=[(i.width, i.height) for i in images],
                    append_images=images[:-1])
    print(name)
