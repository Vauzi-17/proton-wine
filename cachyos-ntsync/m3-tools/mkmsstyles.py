#!/usr/bin/env python3
#
# Generates dlls/m3.msstyles, the Material 3 visual style, from Wine's light.msstyles.
#
#   mkmsstyles.py <wine source tree> [--check]
#
# The images are drawn in eight key colors, one per Material 3 color role. uxtheme maps the key
# colors to the colors of the selected color scheme when it loads an image (the [WineRecolor]
# section of each scheme), so one set of images serves the twelve schemes: six accents in light
# and dark. Anti-aliased pixels are mixes of two key colors and become the same mix of the two
# scheme colors; the recoloring below is the same as recolor_bitmap() in dlls/uxtheme/msstyles.c.
# The keys are corners of the RGB cube, so a mix of two of them is never a mix of two others.
#
# The controls people see most (buttons, check boxes, radio buttons, edit and combo boxes,
# scroll bars, tabs, headers, toolbars, tree views, track bars, spin buttons, tooltips) are drawn
# here in the Material 3 style. The other images are light.msstyles images whose colors are
# mapped to the key colors. --check compares every recolored image with the same image drawn
# directly in the colors of each scheme.
#
# Needs rsvg-convert, Pillow and numpy.

import json
import os
import re
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))

KEYS = {
    'primary':             (255, 0, 0),
    'on_primary':          (0, 255, 0),
    'on_surface_variant':  (0, 0, 255),
    'secondary_container': (255, 255, 0),
    'outline':             (255, 0, 255),
    'outline_variant':     (0, 255, 255),
    'on_surface':          (0, 0, 0),
    'surface':             (255, 255, 255),
}

ACCENTS = ['purple', 'blue', 'teal', 'green', 'orange', 'pink']

# light.msstyles colors, for the images taken from it
LIGHT_COLORS = {
    '#aeaeae': 'outline', '#bdbdbd': 'outline', '#a6a6a6': 'outline',
    '#909090': 'on_surface_variant', '#787878': 'on_surface_variant', '#5a5a5a': 'on_surface_variant',
    '#3096fa': 'primary', '#2979ff': 'primary', '#0091ea': 'primary', '#ff1744': 'primary', '#d50000': 'primary',
    '#ffffff': 'surface', '#fffffe': 'surface', '#fefefe': 'surface', '#fffff9': 'surface', '#fdffff': 'surface',
    '#f5f5f5': 'surface',
    '#000000': 'on_surface', '#282828': 'on_surface', '#0a0a0a': 'on_surface', '#2d2d2d': 'on_surface',
    '#b3e5fc': 'secondary_container', '#e1f5fe': 'secondary_container', '#e3f2fd': 'secondary_container',
    '#bbdefb': 'secondary_container',
}


def hexrgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgbhex(c):
    return '#%02x%02x%02x' % tuple(c)


def camel(role):
    parts = role.split('_')
    return parts[0] + ''.join(p.title() for p in parts[1:])


def load_schemes():
    palettes = json.load(open(os.path.join(HERE, 'palettes.json')))
    schemes = []
    for accent in ACCENTS:
        for mode in ('light', 'dark'):
            p = palettes[accent][mode]
            colors = {role: hexrgb(p[camel(role)]) for role in (
                'primary', 'on_primary', 'primary_container', 'on_primary_container', 'secondary_container',
                'on_secondary_container', 'tertiary_container', 'on_tertiary_container', 'error', 'surface',
                'on_surface', 'on_surface_variant', 'surface_dim', 'surface_container_lowest',
                'surface_container_low', 'surface_container', 'surface_container_high',
                'surface_container_highest', 'outline', 'outline_variant', 'inverse_surface',
                'inverse_on_surface')}
            schemes.append((accent.title() + mode.title(), '%s (%s)' % (accent.title(), mode), colors))
    return schemes


def blend(base, over, alpha):
    return tuple(int(b + (o - b) * alpha + 0.5) for b, o in zip(base, over))


# ---------------------------------------------------------------------------------------------
# recoloring, as in uxtheme

def recolor(rgba, keys, colors, present_only=False):
    """rgba: HxWx4 uint8, straight alpha. keys/colors: lists of rgb tuples. uxtheme takes all the
    keys into account; present_only, for light's colors, only the ones found unmixed in the image."""
    out = rgba.copy()
    flat = out.reshape(-1, 4)
    visible = flat[:, 3] > 0
    if not visible.any():
        return out
    present = list(range(len(keys)))
    if present_only:
        # translucent pixels are off by the rounding of premultiplied alpha
        tolerance = np.maximum(1, 510 // np.maximum(flat[:, 3].astype(int), 1))
        present = [k for k, key in enumerate(keys)
                   if np.any(visible & (np.abs(flat[:, :3].astype(int) - key).max(axis=1) <= tolerance))]
        if not present:
            present = list(range(len(keys)))
    pk = np.array([keys[k] for k in present], dtype=np.float32)
    pc = np.array([colors[k] for k in present], dtype=np.float32)
    uniq, inverse = np.unique(flat[visible, :3], axis=0, return_inverse=True)
    c = uniq.astype(np.float32)
    best = np.full(len(c), 1e9, dtype=np.float32)
    result = np.zeros_like(c)
    for i in range(len(pk)):
        d = ((c - pk[i]) ** 2).sum(axis=1)
        better = d < best
        best[better] = d[better]
        result[better] = pc[i]
    for i in range(len(pk)):
        for j in range(i + 1, len(pk)):
            v = pk[j] - pk[i]
            length = (v * v).sum()
            t = np.clip(((c - pk[i]) * v).sum(axis=1) / length, 0, 1) if length else np.zeros(len(c))
            d = ((c - pk[i] - t[:, None] * v) ** 2).sum(axis=1)
            better = (d < best) & (best > 0)
            best[better] = d[better]
            result[better] = pc[i] + t[better, None] * (pc[j] - pc[i])
    result = np.floor(result + 0.5).clip(0, 255).astype(np.uint8)
    rgb = flat[:, :3]
    rgb[visible] = result[inverse.reshape(-1)]
    return out


# ---------------------------------------------------------------------------------------------
# drawing

def render_svg(svg, width, height):
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, 'image.svg')
        png = os.path.join(tmp, 'image.png')
        with open(src, 'w') as f:
            f.write(svg)
        subprocess.run(['rsvg-convert', '-w', str(width), '-h', str(height), src, '-o', png], check=True)
        return np.array(Image.open(png).convert('RGBA'))


class Canvas:
    """An image of frames stacked vertically, drawn as SVG in key colors."""

    def __init__(self, width, height, frames=1):
        self.width, self.height, self.frames = width, height, frames
        self.fh = height / frames
        self.items = []
        self.opaque = False

    def fill_all(self, role):
        self.opaque = True
        self.items.insert(0, '<rect width="%g" height="%g" fill="{%s}"/>' % (self.width, self.height, role))

    def add(self, item):
        self.items.append(item)

    def rect(self, frame, x, y, w, h, r=0, fill=None, alpha=1, stroke=None, sw=1, stroke_alpha=1, corners=None):
        """a rounded rectangle; with corners (tl, tr, br, bl) only those corners are rounded"""
        y += frame * self.fh
        attrs = self.paint(fill, alpha, stroke, sw, stroke_alpha)
        if corners is None:
            self.add('<rect x="%g" y="%g" width="%g" height="%g" rx="%g" %s/>' % (x, y, w, h, r, attrs))
            return
        radii = [r if c else 0 for c in corners]
        d = 'M%g %g' % (x + radii[0], y)
        d += 'H%g' % (x + w - radii[1])
        if radii[1]: d += 'A%g %g 0 0 1 %g %g' % (radii[1], radii[1], x + w, y + radii[1])
        d += 'V%g' % (y + h - radii[2])
        if radii[2]: d += 'A%g %g 0 0 1 %g %g' % (radii[2], radii[2], x + w - radii[2], y + h)
        d += 'H%g' % (x + radii[3])
        if radii[3]: d += 'A%g %g 0 0 1 %g %g' % (radii[3], radii[3], x, y + h - radii[3])
        d += 'V%g' % (y + radii[0])
        if radii[0]: d += 'A%g %g 0 0 1 %g %g' % (radii[0], radii[0], x + radii[0], y)
        self.add('<path d="%sZ" %s/>' % (d, attrs))

    def circle(self, frame, cx, cy, r, fill=None, alpha=1, stroke=None, sw=1, stroke_alpha=1):
        self.add('<circle cx="%g" cy="%g" r="%g" %s/>' % (cx, cy + frame * self.fh, r,
                                                          self.paint(fill, alpha, stroke, sw, stroke_alpha)))

    def lines(self, frame, points, role, sw, alpha=1, cap='round'):
        pts = ' '.join('%g,%g' % (x, y + frame * self.fh) for x, y in points)
        self.add('<polyline points="%s" fill="none" stroke="{%s}" stroke-width="%g" stroke-linecap="%s" '
                 'stroke-linejoin="round" stroke-opacity="%g"/>' % (pts, role, sw, cap, alpha))

    def chevron(self, frame, cx, cy, size, direction, role, sw, alpha=1):
        """a chevron pointing in direction, size wide (or high)"""
        s = size / 2
        points = {'down': [(cx - s, cy - s / 2), (cx, cy + s / 2), (cx + s, cy - s / 2)],
                  'up': [(cx - s, cy + s / 2), (cx, cy - s / 2), (cx + s, cy + s / 2)],
                  'right': [(cx - s / 2, cy - s), (cx + s / 2, cy), (cx - s / 2, cy + s)],
                  'left': [(cx + s / 2, cy - s), (cx - s / 2, cy), (cx + s / 2, cy + s)]}[direction]
        self.lines(frame, points, role, sw, alpha)

    @staticmethod
    def paint(fill, alpha, stroke, sw, stroke_alpha):
        attrs = 'fill="{%s}" fill-opacity="%g"' % (fill, alpha) if fill else 'fill="none"'
        if stroke:
            attrs += ' stroke="{%s}" stroke-width="%g" stroke-opacity="%g"' % (stroke, sw, stroke_alpha)
        return attrs

    def svg(self, colors):
        body = '\n'.join(self.items)
        for role in KEYS:
            body = body.replace('{%s}' % role, rgbhex(colors[role]))
        return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %g %g">\n%s\n</svg>\n'
                % (self.width, self.height, self.width, self.height, body))

    def render(self, colors):
        pixels = render_svg(self.svg(colors), self.width, self.height)
        if self.opaque:
            pixels[..., 3] = 255
        return pixels


def state_layer(c, frame, role='on_surface', level=0.08, **shape):
    c.rect(frame, fill=role, alpha=level, **shape)


HOVER, PRESSED = 0.08, 0.12
DISABLED_CONTENT, DISABLED_CONTAINER = 0.38, 0.12


# ---------------------------------------------------------------------------------------------
# Material 3 controls. Each function draws one image of light.msstyles, same size and frames
# unless it says otherwise.

def draw_checkbox(n):
    c = Canvas(n, n * 20, 20)
    u = n / 18
    sw = max(1.5, 2 * u)
    box = dict(x=sw / 2, y=sw / 2, w=n - sw, h=n - sw, r=2 * u)
    solid = dict(x=0, y=0, w=n, h=n, r=2 * u + sw / 2)
    check = [(4 * u, 9.25 * u), (7.25 * u, 12.5 * u), (14 * u, 5.75 * u)]
    dash = [(5 * u, 9 * u), (13 * u, 9 * u)]
    # unchecked, checked, mixed, implicit (drawn checked), excluded (drawn unchecked)
    for group, mark in enumerate((None, check, dash, check, None)):
        for state in range(4):  # normal, hot, pressed, disabled
            f = group * 4 + state
            if mark is None:
                if state == 3:
                    c.rect(f, stroke='on_surface', sw=sw, stroke_alpha=DISABLED_CONTENT, **box)
                else:
                    c.rect(f, stroke='on_surface_variant' if state == 0 else 'on_surface', sw=sw, **box)
                    if state == 2:
                        state_layer(c, f, level=PRESSED, **box)
                continue
            if state == 3:
                c.rect(f, fill='on_surface', alpha=DISABLED_CONTENT, **solid)
                c.lines(f, mark, 'surface', sw)
                continue
            c.rect(f, fill='primary', **solid)
            if state:
                state_layer(c, f, 'on_primary', HOVER if state == 1 else PRESSED, **solid)
            c.lines(f, mark, 'on_primary', sw)
    return c


def draw_radiobutton(n):
    c = Canvas(n, n * 8, 8)
    u = n / 20
    sw = max(1.5, 2 * u)
    r = n / 2 - sw / 2
    for f in range(8):
        checked, state = f >= 4, f % 4
        if state == 3:
            c.circle(f, n / 2, n / 2, r, stroke='on_surface', sw=sw, stroke_alpha=DISABLED_CONTENT)
            if checked:
                c.circle(f, n / 2, n / 2, 5 * u, fill='on_surface', alpha=DISABLED_CONTENT)
            continue
        role = 'primary' if checked else 'on_surface_variant' if state == 0 else 'on_surface'
        c.circle(f, n / 2, n / 2, r, stroke=role, sw=sw)
        if state:
            c.circle(f, n / 2, n / 2, r, fill=role, alpha=HOVER if state == 1 else PRESSED)
        if checked:
            c.circle(f, n / 2, n / 2, 5 * u, fill='primary')
    return c


# frame size of the push button, SizingMargins 16: a pill up to 34 pixels high. On lower
# buttons uxtheme keeps the ends of the arcs, which still meet at the middle of the sides.
BUTTON = 34


def draw_button():
    # tonal buttons; the default button gets a primary outline
    c = Canvas(BUTTON, BUTTON * 6, 6)
    shape = dict(x=0, y=0, w=BUTTON, h=BUTTON, r=BUTTON / 2 - 0.5)
    for f in range(6):  # normal, hot, pressed, disabled, defaulted, defaulted animating
        if f == 3:
            c.rect(f, fill='on_surface', alpha=DISABLED_CONTAINER, **shape)
            continue
        c.rect(f, fill='secondary_container', **shape)
        if f in (1, 2):
            state_layer(c, f, level=HOVER if f == 1 else PRESSED, **shape)
        if f >= 4:
            c.rect(f, x=1, y=1, w=BUTTON - 2, h=BUTTON - 2, r=BUTTON / 2 - 1.5, stroke='primary', sw=2)
    return c


def draw_groupbox():
    c = Canvas(24, 24, 1)
    c.rect(0, 0.5, 0.5, 23, 23, r=8, stroke='outline_variant', sw=1)
    return c


FIELD = 12  # frame size of edit and combo box borders, SizingMargins 5


def draw_field(filled=True):
    # outlined text field: normal, hot, focused (pressed for combo boxes), disabled
    c = Canvas(FIELD, FIELD * 4, 4)
    outer = dict(x=0.5, y=0.5, w=FIELD - 1, h=FIELD - 1, r=4)
    for f in range(4):
        if f == 3:
            c.rect(f, stroke='on_surface', sw=1, stroke_alpha=DISABLED_CONTAINER, **outer)
            continue
        if filled:
            c.rect(f, fill='surface', **outer)
        if f == 2:
            c.rect(f, x=1, y=1, w=FIELD - 2, h=FIELD - 2, r=3.5, stroke='primary', sw=2)
        else:
            c.rect(f, stroke='outline' if f == 0 else 'on_surface', sw=1, **outer)
    return c


def draw_edit_text():
    # Wine draws the frame of edit controls with the EditText part: normal, hot, selected,
    # disabled, focused, read only, assist, cue banner
    c = Canvas(FIELD, FIELD * 8, 8)
    outer = dict(x=0.5, y=0.5, w=FIELD - 1, h=FIELD - 1, r=4)
    for f in range(8):
        if f == 3:
            c.rect(f, stroke='on_surface', sw=1, stroke_alpha=DISABLED_CONTAINER, **outer)
        elif f == 5:
            c.rect(f, stroke='outline_variant', sw=1, **outer)
        elif f in (2, 4):
            c.rect(f, fill='surface', **outer)
            c.rect(f, x=1, y=1, w=FIELD - 2, h=FIELD - 2, r=3.5, stroke='primary', sw=2)
        else:
            c.rect(f, fill='surface', stroke='on_surface' if f == 1 else 'outline', sw=1, **outer)
    return c


# images light.msstyles has no counterpart for
EXTRA_IMAGES = {'edit_text': draw_edit_text}


def draw_readonly_combo():
    c = draw_field()
    for f in (1, 2):
        state_layer(c, f, level=HOVER if f == 1 else PRESSED, x=0.5, y=0.5, w=FIELD - 1, h=FIELD - 1, r=4)
    return c


def draw_transparent(w, h, frames):
    return Canvas(w, h, frames)


def draw_glyphs(w, h, frames, direction, roles, size_factor=0.5, sw_factor=None):
    """chevron glyphs, one per frame: roles[i] is (role, alpha) or None"""
    c = Canvas(w, h, frames)
    fh = h / frames
    size = max(3, min(w, fh) * size_factor)
    sw = sw_factor * min(w, fh) if sw_factor else max(1.25, min(w, fh) / 9)
    for f in range(frames):
        if roles[f] is None:
            continue
        role, alpha = roles[f]
        d = direction[f] if isinstance(direction, (list, tuple)) else direction
        c.chevron(f, w / 2, fh / 2, size, d, role, sw, alpha)
    return c


GLYPH4 = [('on_surface_variant', 1), ('on_surface', 1), ('on_surface', 1), ('on_surface', DISABLED_CONTENT)]


def draw_scroll_arrows():
    # arrow button backgrounds: up, down, left, right x normal, hot, pressed, disabled; then hover
    c = Canvas(17, 17 * 20, 20)
    c.fill_all('surface')
    for f in range(16):
        state = f % 4
        if state in (1, 2):
            state_layer(c, f, level=HOVER if state == 1 else PRESSED, x=1, y=1, w=15, h=15, r=4)
    return c


def draw_scroll_arrow_glyphs(n):
    directions = ['up'] * 4 + ['down'] * 4 + ['left'] * 4 + ['right'] * 4 + ['up', 'down', 'left', 'right']
    roles = GLYPH4 * 4 + [('on_surface_variant', 1)] * 4
    return draw_glyphs(n, n * 20, 20, directions, roles, 0.42, 0.12)


def draw_scroll_thumb(vertical):
    # normal, hot, pressed, disabled, hover
    w, fh = (17, 11) if vertical else (20, 17)
    c = Canvas(w, fh * 5, 5)
    c.fill_all('surface')
    for f, (role, width) in enumerate([('outline', 7), ('on_surface_variant', 9), ('on_surface_variant', 9),
                                       ('outline_variant', 7), ('outline', 7)]):
        if vertical:
            c.rect(f, (w - width) / 2, 1, width, fh - 2, r=width / 2, fill=role)
        else:
            c.rect(f, 1, (fh - width) / 2, w - 2, width, r=width / 2, fill=role)
    return c


def draw_solid(w, h, frames, role='surface'):
    c = Canvas(w, h, frames)
    c.fill_all(role)
    return c


def draw_header_item(frames=12):
    # normal, hot, pressed, then sorted and with icon: separator on the right, divider below
    c = Canvas(8, 24 * frames, frames)
    c.fill_all('surface')
    for f in range(frames):
        state = f % 3
        if state:
            state_layer(c, f, level=HOVER if state == 1 else PRESSED, x=0, y=0, w=8, h=23)
        c.rect(f, 7, 6, 1, 12, fill='outline_variant')
        c.rect(f, 0, 23, 8, 1, fill='outline_variant')
    return c


def draw_header_background():
    c = Canvas(3, 48, 2)
    c.fill_all('surface')
    for f in range(2):
        c.rect(f, 0, 23, 3, 1, fill='outline_variant')
    return c


def draw_header_sort_arrow(w, h):
    return draw_glyphs(w, h, 2, ['up', 'down'], [('on_surface_variant', 1)] * 2, 0.6, 0.1)


TAB = 16  # tab item frame size, SizingMargins 6


def draw_tab_item():
    # normal, hot, selected, disabled, focused: no container, a primary indicator when selected
    c = Canvas(TAB, TAB * 5, 5)
    for f in range(5):
        if f == 1:
            state_layer(c, f, x=0, y=0, w=TAB, h=TAB - 2, r=6, corners=(1, 1, 0, 0))
        if f in (2, 4):
            c.rect(f, 2, TAB - 5, TAB - 4, 3, r=1.5, fill='primary', corners=(1, 1, 0, 0))
    return c


def draw_tab_pane():
    c = Canvas(24, 24, 1)
    c.rect(0, 0.5, 0.5, 23, 23, r=8, fill='surface', stroke='outline_variant', sw=1)
    return c


def draw_toolbar_button():
    # normal, hot, pressed, disabled, checked, hot checked, near hot, other side hot
    c = Canvas(17, 17 * 8, 8)
    shape = dict(x=0, y=0, w=17, h=17, r=8)
    for f, (role, level) in enumerate([(None, 0), ('on_surface', HOVER), ('on_surface', PRESSED), (None, 0),
                                       ('secondary_container', 1), ('secondary_container', 1),
                                       ('on_surface', 0.04), ('on_surface', HOVER)]):
        if role:
            c.rect(f, fill=role, alpha=level, **shape)
        if f == 5:
            state_layer(c, f, **shape)
    return c


def draw_list_item(kind):
    c = Canvas(9, 9, 1)
    shape = dict(x=0, y=0, w=9, h=9, r=4)
    if kind == 'hot':
        state_layer(c, 0, **shape)
    elif kind == 'selected_not_focus':
        state_layer(c, 0, level=PRESSED, **shape)
    else:
        c.rect(0, fill='secondary_container', **shape)
        if kind == 'hot_selected':
            state_layer(c, 0, **shape)
    return c


def draw_tree_glyph(w, h, hot=False, explorer=False):
    role = ('on_surface', 1) if hot else ('on_surface_variant', 1)
    return draw_glyphs(w, h, 2, ['right', 'down'], [role, role], 0.5 if explorer else 0.56,
                       0.09 if explorer else 0.12)


def draw_trackbar_track(vertical=False):
    c = Canvas(8, 4, 1) if not vertical else Canvas(4, 8, 1)
    c.rect(0, 0, 0, c.width, c.height, r=2, fill='secondary_container')
    return c


def draw_trackbar_thumb(w, h, vertical):
    # normal, hot, pressed, focused, disabled: a primary handle across the track
    c = Canvas(w, h, 5)
    fh = h / 5
    for f, (role, alpha, width) in enumerate([('primary', 1, 4), ('primary', 1, 4), ('primary', 1, 2),
                                              ('primary', 1, 4), ('on_surface', DISABLED_CONTENT, 4)]):
        if vertical:
            c.rect(f, 1, (fh - width) / 2, w - 2, width, r=width / 2, fill=role, alpha=alpha)
        else:
            c.rect(f, (w - width) / 2, 1, width, fh - 2, r=width / 2, fill=role, alpha=alpha)
    return c


def draw_spin_background(w, h):
    c = Canvas(w, h, 4)
    fh = h / 4
    for f in (1, 2):
        state_layer(c, f, level=HOVER if f == 1 else PRESSED, x=0, y=0, w=w, h=fh, r=min(w, fh) / 3)
    return c


def draw_tooltip():
    c = Canvas(9, 22, 1)
    c.rect(0, 0, 0, 9, 22, r=4, fill='on_surface')
    return c


def custom_image(name, w, h, frames):
    """the Material 3 image for light's blue_<name>, or None to recolor light's image"""
    m = re.match(r'(.*?)_(\d+)px$', name)
    base, n = (m.group(1), int(m.group(2))) if m else (name, None)
    if base == 'checkbox':
        return draw_checkbox(n)
    if base == 'radiobutton':
        return draw_radiobutton(n)
    if name == 'button':
        return draw_button()
    if name == 'groupbox':
        return draw_groupbox()
    if name in ('edit_border_noscroll', 'edit_border_hscroll', 'edit_border_vscroll', 'edit_border_hvscroll',
                'combobox_border'):
        return draw_field()
    if name == 'combobox_readonly':
        return draw_readonly_combo()
    if name in ('combobox_dropdownbutton', 'combobox_dropdownbutton_left', 'combobox_dropdownbutton_right'):
        return draw_transparent(w, h, frames)
    if re.match(r'combobox_dropdownbutton(_left|_right)?_glyph_\d+px$', name):
        return draw_glyphs(w, h, frames, 'down', GLYPH4, 0.62, 0.11)
    if name.startswith('edit_background'):
        return draw_solid(w, h, frames)
    if name == 'scrollbar_arrows':
        return draw_scroll_arrows()
    if base == 'scrollbar_arrow_glyphs':
        return draw_scroll_arrow_glyphs(n)
    if name in ('scrollbar_thumb_vertical', 'scrollbar_thumb_horizontal'):
        return draw_scroll_thumb(name.endswith('vertical'))
    if re.match(r'scrollbar_(lower|upper)_track_', name):
        return draw_solid(w, h, frames)
    if base.startswith('scrollbar_gripper'):
        return draw_transparent(w, h, frames)
    if name == 'header_item':
        return draw_header_item()
    if name == 'header':
        return draw_header_background()
    if base == 'header_sort_arrow':
        return draw_header_sort_arrow(w, h)
    if name in ('tab_item', 'tab_item_left', 'tab_item_right'):
        return draw_tab_item()
    if name == 'tab_pane_edge':
        return draw_tab_pane()
    if name == 'tab_background':
        return draw_solid(10, 10, 1)
    if name == 'toolbar_buttons':
        return draw_toolbar_button()
    if name.startswith('explorer_listview_item_') or name.startswith('explorer_treeview_item_'):
        return draw_list_item(name.split('_item_')[1])
    if base == 'treeview_expand_collapse':
        return draw_tree_glyph(w, h)
    if base in ('explorer_treeview_glyph', 'explorer_treeview_hot_glyph'):
        return draw_tree_glyph(w, h, 'hot' in base, True)
    if name == 'trackbar_slider_track':
        return draw_trackbar_track()
    if name in ('trackbar_thumb_horizontal', 'trackbar_thumb_vertical'):
        return draw_trackbar_thumb(w, h, name.endswith('vertical'))
    if base in ('trackbar_thumb_down', 'trackbar_thumb_up'):
        return draw_trackbar_thumb(w, h, False)
    if base in ('trackbar_thumb_left', 'trackbar_thumb_right'):
        return draw_trackbar_thumb(w, h, True)
    if name.startswith('spin_background_'):
        return draw_spin_background(w, h)
    if name.startswith('spin_glyph_'):
        direction = name.split('_')[2]
        return draw_glyphs(w, h, frames, direction, GLYPH4, 0.62, 0.12)
    if name == 'tooltip_standard':
        return draw_tooltip()
    return None


# ---------------------------------------------------------------------------------------------
# ini

def parse_rc(path):
    rc = open(path).read()
    m = re.search(r'BLUE_INI TEXTFILE\s*\{(.*?)\n\}', rc, re.S)
    lines = re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1))
    ini = ''.join(lines).replace('\\r\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
    bitmaps = re.findall(r'^(\w+) BITMAP "([\w.]+)"', rc, re.M)
    return ini, bitmaps


def parse_ini(text):
    sections = []
    for line in text.split('\n'):
        line = line.strip()
        if not line or line.startswith(';'):
            continue
        if line.startswith('['):
            sections.append([line[1:line.index(']')], []])
        else:
            key, value = [s.strip() for s in line.split('=', 1)]
            sections[-1][1].append([key, value])
    return sections


def image_frames(sections):
    frames = {}
    for name, values in sections:
        d = {k.lower(): v for k, v in values}
        count = int(d.get('imagecount', '1'))
        for k, v in d.items():
            if k.startswith('imagefile'):
                frames.setdefault(v.lower(), count)
    return frames


def section(sections, name):
    for s in sections:
        if s[0].lower() == name.lower():
            return s
    s = [name, []]
    sections.append(s)
    return s


def set_values(sections, name, **values):
    s = section(sections, name)
    for key, value in values.items():
        for item in s[1]:
            if item[0].lower() == key.lower():
                item[1] = value
                break
        else:
            s[1].append([key, value])


def system_colors(c):
    """the system colors of the scheme, as set by explorer (material.c)"""
    disabled = blend(c['surface_container'], c['on_surface'], 0.38)
    return {
        'Scrollbar': c['surface_container_high'], 'Background': c['surface_container_lowest'],
        'ActiveCaption': c['surface_container_high'], 'InactiveCaption': c['surface_container'],
        'Menu': c['surface_container'], 'Window': c['surface'], 'WindowFrame': c['outline_variant'],
        'MenuText': c['on_surface'], 'WindowText': c['on_surface'], 'CaptionText': c['on_surface'],
        'ActiveBorder': c['surface_container_high'], 'InactiveBorder': c['surface_container'],
        'AppWorkSpace': c['surface_container_low'], 'Highlight': c['primary_container'],
        'HighlightText': c['on_primary_container'], 'BtnFace': c['surface_container'],
        'BtnShadow': c['outline_variant'], 'GrayText': disabled, 'BtnText': c['on_surface'],
        'InactiveCaptionText': c['on_surface_variant'], 'BtnHighlight': c['surface_container_highest'],
        'DkShadow3d': c['outline'], 'Light3d': c['surface_container_high'], 'InfoText': c['inverse_on_surface'],
        'InfoBk': c['inverse_surface'], 'ButtonAlternateFace': c['surface_container'],
        'HotTracking': c['primary'], 'GradientActiveCaption': c['surface_container_high'],
        'GradientInactiveCaption': c['surface_container'], 'MenuHilight': c['primary_container'],
        'MenuBar': c['surface_container'],
    }


def scheme_ini(sections, c):
    """the ini of the scheme with colors c: light's ini with Material 3 colors and images"""
    sections = [[name, [list(v) for v in values]] for name, values in sections]
    disabled_text = blend(c['surface_container'], c['on_surface'], 0.38)
    field_disabled_text = blend(c['surface'], c['on_surface'], 0.38)

    def color(section_name, key, value):
        rgb = tuple(int(x) for x in value.split())
        s, k = section_name.lower(), key.lower()
        if k == 'textcolor':
            if 'disabled' in s:
                return field_disabled_text if s.startswith('edit') or s.startswith('combobox') else disabled_text
            if s.startswith('tooltip.standard'):
                return c['inverse_on_surface']
            if s.startswith('combobox.dropdownitem(highlighted)'):
                return c['on_secondary_container']
            if s.startswith('button.pushbutton'):
                return c['on_secondary_container']
            if rgb in ((41, 121, 255), (48, 150, 250)):
                return c['primary']
            if rgb == (174, 174, 174):
                return c['on_surface_variant']
            if rgb in ((166, 166, 166), (189, 189, 189)):
                return disabled_text
            return c['on_surface']
        if k in ('bodytextcolor', 'heading1textcolor', 'heading2textcolor'):
            return c['on_surface'] if k == 'bodytextcolor' else c['primary']
        if k == 'fillcolor':
            if s.startswith('combobox.dropdownitem(highlighted)'):
                return c['secondary_container']
            if s.startswith('combobox.dropdownitem'):
                return c['surface_container']
            if rgb == (48, 150, 250):
                return c['primary']
            if rgb == (213, 0, 0):
                return c['error']
            if rgb == (255, 238, 88):
                return c['tertiary_container']
            if rgb == (189, 189, 189):
                return c['outline']
            if rgb == (227, 227, 227):
                return c['surface_container_high']
            if rgb in ((244, 244, 244), (245, 245, 245)):
                return c['surface_container']
            if s.startswith('progress'):
                return c['secondary_container']
            return c['surface']
        if k == 'bordercolor':
            return c['outline']
        if k == 'color':
            return c['outline']
        if k in ('edgelightcolor', 'edgehighlightcolor', 'edgefillcolor'):
            return c['surface_container_high']
        if k == 'edgeshadowcolor':
            return c['outline_variant']
        if k == 'edgedkshadowcolor':
            return c['outline']
        raise ValueError('no color for %s %s' % (section_name, key))

    sysmetrics = system_colors(c)
    for name, values in sections:
        for item in values:
            key, value = item
            if key.lower().startswith('imagefile'):
                item[1] = re.sub(r'^blue_', 'm3_', value)
            elif name.lower() == 'sysmetrics' and key in sysmetrics:
                item[1] = '%d %d %d' % sysmetrics[key]
            elif re.fullmatch(r'\d+ \d+ \d+', value):
                item[1] = '%d %d %d' % color(name, key, value)

    # the Material 3 images
    set_values(sections, 'Button.Pushbutton', SizingMargins='16, 16, 16, 16', ContentMargins='6, 6, 3, 3')
    set_values(sections, 'Button.Pushbutton(Defaulted)', TextColor='%d %d %d' % c['on_secondary_container'])
    set_values(sections, 'Button.Pushbutton(Pressed)', TextColor='%d %d %d' % c['on_secondary_container'])
    set_values(sections, 'Button.Groupbox', SizingMargins='8, 8, 8, 8')
    for name in ('Edit.EditBorder_NoScroll', 'Edit.EditBorder_HScroll', 'Edit.EditBorder_VScroll',
                 'Edit.EditBorder_HVScroll', 'ComboBox.Border'):
        set_values(sections, name, SizingMargins='5, 5, 5, 5', Transparent='True')
    set_values(sections, 'ComboBox.ReadOnly', SizingMargins='5, 5, 5, 5', Transparent='True')
    set_values(sections, 'Edit.EditText', BgType='ImageFile', ImageFile='m3_edit_text.bmp', ImageCount='8',
               ImageLayout='Vertical', SizingType='Stretch', SizingMargins='5, 5, 5, 5', Transparent='True')
    # Wine draws the frame of combo boxes with the class, not with the Border and ReadOnly parts
    set_values(sections, 'ComboBox', BgType='ImageFile', ImageFile='m3_combobox_border.bmp', ImageCount='4',
               ImageLayout='Vertical', SizingType='Stretch', SizingMargins='5, 5, 5, 5', Transparent='True')
    for name in ('ComboBox.DropDownButton', 'ComboBox.DropDownButtonRight', 'ComboBox.DropDownButtonLeft'):
        set_values(sections, name, Transparent='True', GlyphTransparent='True')
    set_values(sections, 'ScrollBar.ThumbBtnVert', SizingMargins='8, 8, 5, 5')
    set_values(sections, 'ScrollBar.ThumbBtnHorz', SizingMargins='9, 10, 8, 8')
    for name in ('ScrollBar.LowerTrackHorz', 'ScrollBar.LowerTrackVert', 'ScrollBar.UpperTrackHorz',
                 'ScrollBar.UpperTrackVert'):
        set_values(sections, name, SizingMargins='0, 0, 0, 0', SizingType='Stretch')
    set_values(sections, 'ScrollBar.SizeBoxBkgnd', FillColor='%d %d %d' % c['surface'])
    set_values(sections, 'Header.HeaderItem', SizingMargins='1, 2, 7, 7')
    for name in ('Tab.TabItem', 'Tab.TabItemLeftEdge', 'Tab.TabItemRightEdge', 'Tab.TabItemBothEdge',
                 'Tab.TopTabItem', 'Tab.TopTabItemLeftEdge', 'Tab.TopTabItemRightEdge', 'Tab.TopTabItemBothEdge'):
        set_values(sections, name, SizingMargins='6, 6, 6, 6', Transparent='True',
                   TextColor='%d %d %d' % c['on_surface_variant'])
        for state in ('Selected', 'Focused', 'Hot'):
            set_values(sections, '%s(%s)' % (name, state),
                       TextColor='%d %d %d' % (c['primary'] if state != 'Hot' else c['on_surface']))
        set_values(sections, '%s(Disabled)' % name, TextColor='%d %d %d' % disabled_text)
    set_values(sections, 'Tab.Pane', SizingMargins='8, 8, 8, 8', Transparent='True')
    set_values(sections, 'Tab.Body', SizingType='Stretch', SizingMargins='0, 0, 0, 0')
    set_values(sections, 'Toolbar.Button', SizingMargins='8, 8, 8, 8')
    for name in ('Explorer::ListView.ListItem', 'Explorer::TreeView.TreeItem'):
        set_values(sections, name, SizingMargins='4, 4, 4, 4')
    set_values(sections, 'TreeView.Glyph', Transparent='True')
    set_values(sections, 'TrackBar.Track', SizingMargins='2, 2, 2, 2', Transparent='True')
    set_values(sections, 'TrackBar.TrackVert', SizingMargins='2, 2, 2, 2', Transparent='True')
    for name in ('TrackBar.Thumb', 'TrackBar.ThumbVert'):
        set_values(sections, name, SizingType='Stretch', SizingMargins='2, 2, 3, 3' if name.endswith('Thumb')
                   else '3, 3, 2, 2', Transparent='True')
    for name in ('Spin.Up', 'Spin.Down', 'Spin.UpHorz', 'Spin.DownHorz'):
        set_values(sections, name, SizingMargins='4, 4, 4, 4', Transparent='True')
    set_values(sections, 'Tooltip.Standard', SizingMargins='4, 4, 4, 4')
    set_values(sections, 'Progress', BorderSize='0', BgType='BorderFill')
    set_values(sections, 'Progress.Bar', FillColor='%d %d %d' % c['secondary_container'])
    set_values(sections, 'Progress.BarVert', FillColor='%d %d %d' % c['secondary_container'])

    recolors = [[role.title().replace('_', ''), '%d %d %d %d %d %d' % (KEYS[role] + c[role])]
                for role in KEYS]
    sections.append(['WineRecolor', recolors])
    return sections


def ini_text(sections):
    out = []
    for name, values in sections:
        out.append('[%s]' % name)
        out.extend('%s = %s' % (k, v) for k, v in values)
        out.append('')
    return '\r\n'.join(out)


def rc_string(text):
    lines = []
    for line in text.split('\r\n'):
        lines.append('"%s\\r\\n"' % line.replace('\\', '\\\\').replace('"', '\\"'))
    return '\n'.join(lines)


# ---------------------------------------------------------------------------------------------
# files

def write_bmp(path, pixels):
    """32-bit BI_RGB bitmap with straight alpha"""
    h, w = pixels.shape[:2]
    bgra = pixels[::-1, :, [2, 1, 0, 3]].tobytes()
    header = (b'BM' + (54 + len(bgra)).to_bytes(4, 'little') + b'\0\0\0\0' + (54).to_bytes(4, 'little')
              + (40).to_bytes(4, 'little') + w.to_bytes(4, 'little') + h.to_bytes(4, 'little', signed=True)
              + (1).to_bytes(2, 'little') + (32).to_bytes(2, 'little') + (0).to_bytes(4, 'little')
              + len(bgra).to_bytes(4, 'little') + (2835).to_bytes(4, 'little') * 2 + b'\0' * 8)
    with open(path, 'wb') as f:
        f.write(header + bgra)


def light_image(light_dir, name):
    """light's blue_<name> drawn in key colors, and its source pixels and colors"""
    svg = open(os.path.join(light_dir, 'blue_%s.svg' % name)).read()
    m = re.search(r'<svg[^>]*\sid="bitmap:\d+-(\d+)"', svg)
    w = int(re.search(r'<svg[^>]*\swidth="(\d+)"', svg).group(1))
    h = int(re.search(r'<svg[^>]*\sheight="(\d+)"', svg).group(1))
    pixels = render_svg(svg, w, h)
    if m.group(1) == '24':
        pixels[..., 3] = 255
    return pixels


def main():
    wine = sys.argv[1]
    check = '--check' in sys.argv
    light_dir = os.path.join(wine, 'dlls', 'light.msstyles')
    out_dir = os.path.join(wine, 'dlls', 'm3.msstyles')
    os.makedirs(out_dir, exist_ok=True)
    schemes = load_schemes()

    ini, bitmaps = parse_rc(os.path.join(light_dir, 'light.rc'))
    sections = parse_ini(ini)
    frames = image_frames(sections)
    source_keys = [hexrgb(h) for h in LIGHT_COLORS]
    source_roles = [LIGHT_COLORS[h] for h in LIGHT_COLORS]
    key_list = [KEYS[r] for r in KEYS]

    images = []
    worst = []
    for res, filename in bitmaps + [(None, 'blue_%s.bmp' % name) for name in EXTRA_IMAGES]:
        name = re.sub(r'^blue_', '', filename[:-4])
        if name in EXTRA_IMAGES:
            canvas = EXTRA_IMAGES[name]()
        else:
            svg = open(os.path.join(light_dir, filename[:-4] + '.svg')).read()
            w = int(re.search(r'<svg[^>]*\swidth="(\d+)"', svg).group(1))
            h = int(re.search(r'<svg[^>]*\sheight="(\d+)"', svg).group(1))
            count = frames.get(filename.lower(), 1)
            canvas = custom_image(name, w, h, count)
        if canvas:
            keyed = canvas.render(KEYS)
        else:
            source = light_image(light_dir, name)
            keyed = recolor(source, source_keys, [KEYS[r] for r in source_roles], True)
        out_name = 'm3_%s.bmp' % name
        write_bmp(os.path.join(out_dir, out_name), keyed)
        images.append(('M3_%s_BMP' % name.upper(), out_name))

        if check:
            for scheme, _, colors in schemes:
                got = recolor(keyed, key_list, [colors[r] for r in KEYS]).astype(int)
                if canvas:
                    want = canvas.render(colors).astype(int)
                else:
                    want = recolor(source, source_keys, [colors[r] for r in source_roles], True).astype(int)
                visible = (got[..., 3] > 16) | (want[..., 3] > 16)
                diff = np.abs(got[..., :3] - want[..., :3]).max(axis=2) * visible
                worst.append((int(diff.max()), int((diff > 24).sum()), out_name, scheme))

    # ini files and resources
    rc = [open(os.path.join(HERE, 'm3.rc.in')).read()]
    for i, (scheme, display, colors) in enumerate(schemes):
        rc.append('/* %s */\n%s_INI TEXTFILE\n{\n%s\n}\n' % (display, scheme.upper(),
                                                           rc_string(ini_text(scheme_ini(sections, colors)))))
    for res, filename in images:
        rc.append('/* @makedep: %s */\n%s BITMAP "%s"\n' % (filename, res, filename))
    names = '\n'.join('    %-4d "%s"' % (1000 + i, d) for i, (_, d, _) in enumerate(schemes))
    tips = '\n'.join('    %-4d "%s"' % (2000 + i, d) for i, (_, d, _) in enumerate(schemes))
    colornames = '\n'.join('"%s\\0"' % s for s, _, _ in schemes)
    inis = '\n'.join('"%s_INI\\0"' % s.upper() for s, _, _ in schemes)
    text = '\n'.join(rc).replace('@COLOR_DISPLAY_NAMES@', names).replace('@COLOR_TOOLTIPS@', tips)
    text = text.replace('@COLORNAMES@', colornames).replace('@FILERESNAMES@', inis)
    open(os.path.join(out_dir, 'm3.rc'), 'w').write(text)
    with open(os.path.join(out_dir, 'Makefile.in'), 'w') as f:
        f.write('MODULE = m3.msstyles\n\nEXTRADLLFLAGS = -Wb,--data-only\n\nSOURCES = \\\n\tm3.rc\n')

    if check:
        bad = {}
        for error, pixels, name, scheme in worst:
            if pixels and error > bad.get(name, (0,))[0]:
                bad[name] = (error, pixels, scheme)
        print('%d images, %d with pixels off by more than 24 in a scheme:' % (len(images), len(bad)))
        for name, (error, pixels, scheme) in sorted(bad.items(), key=lambda x: -x[1][0]):
            print('  %3d max, %4d pixels  %s  %s' % (error, pixels, name, scheme))


if __name__ == '__main__':
    main()
