# Material 3 desktop: generated files

`cachyos-ntsync/p11/0003-*.patch` adds a Material 3 style to the explorer
desktop and `0009-*.patch` the Material 3 visual style for programs. Their
generated inputs come from here.

## Color schemes (`programs/explorer/material.c`)

The tonal spot schemes (light and dark) of the six seed colors, computed with
Google's Material Color Utilities (Apache 2.0):

```sh
npm install @material/material-color-utilities@0.4.0 esbuild
npx esbuild gen-palettes.mjs --bundle --platform=node --format=esm --outfile=gen.bundle.mjs
node gen.bundle.mjs > palettes.json
```

The package imports without file extensions, so it has to be bundled first.
`palettes.json` is the output used for the patch; `material.c` takes the
roles in the order of `struct m3_colors`.

## Fonts (`programs/explorer/*.ttf`)

```sh
pip install fonttools
# symbols.ttf: variablefont/MaterialSymbolsRounded[FILL,GRAD,opsz,wght].ttf
# symbols.codepoints: the .codepoints file next to it
# from https://github.com/google/material-design-icons
python3 mkfonts.py
```

This writes `wine_m3_symbols.ttf` and `wine_m3_symbols_filled.ttf` (the
symbols listed in the script, instanced at FILL 0 and 1, renamed) and
`roboto_regular.ttf` and `roboto_medium.ttf` (Debian's `fonts-roboto-unhinted`,
subset to Latin, Greek and Cyrillic). Licenses: `programs/explorer/material_fonts.txt`.

## Visual style (`dlls/m3.msstyles`)

```sh
pip install pillow numpy   # and rsvg-convert (librsvg2-bin)
python3 mkmsstyles.py /path/to/wine [--check]
```

Writes `dlls/m3.msstyles/` (`Makefile.in`, `m3.rc`, `m3_*.bmp`) from the tree's
`dlls/light.msstyles`: the Material 3 controls drawn by the script, the other
images of the light theme with their colors mapped to Material 3 roles, and one
ini per color scheme (the six accents of `palettes.json` in light and dark).
The images use eight key colors, the corners of the RGB cube; the
`[WineRecolor]` section of each scheme maps them to the scheme's colors, and
uxtheme recolors the images when it loads them (`p11/0008`). `--check`
compares every recolored image with the same image drawn in the scheme's
colors. `m3.rc.in` is the head of `m3.rc`.
