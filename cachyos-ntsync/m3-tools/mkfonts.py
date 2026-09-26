from fontTools.ttLib import TTFont
from fontTools import subset
from fontTools.varLib import instancer

ICONS = ["apps","power_settings_new","palette","folder","folder_open","terminal","edit_note","tune","settings",
         "monitoring","account_tree","description","image","music_note","hard_drive","refresh","expand_less",
         "sports_esports","check","person","close","remove","crop_square","search","chevron_right","computer",
         "public","restart_alt","logout","dark_mode","light_mode","grid_view","play_arrow","download",
         "arrow_drop_down","filter_none","open_in_new","delete","widgets","keyboard_arrow_up","keyboard_arrow_down"]
cp = {}
for line in open("symbols.codepoints"):
    name, code = line.split()
    cp.setdefault(name, int(code, 16))
codes = [cp[i] for i in ICONS]

def rename(font, family, ps):
    name = font["name"]
    for rec in list(name.names):
        if rec.nameID in (16, 17, 21, 22, 25):
            name.removeNames(nameID=rec.nameID)
    for nid, val in ((1, family), (2, "Regular"), (3, ps + ";wine"), (4, family), (6, ps)):
        name.setName(val, nid, 3, 1, 0x409)
        name.setName(val, nid, 1, 0, 0)

# the symbols of Files (programs/files), a font of its own
FILES_ICONS = ["album","apps","arrow_forward","arrow_upward","article","check","chevron_right","close","code",
               "computer","content_copy","content_cut","content_paste","create_new_folder","delete","deployed_code",
               "description","desktop_windows","draft","edit","expand_more","extension","folder","folder_zip",
               "font_download","grid_view","hard_drive","image","info","link","more_vert","movie","music_note",
               "note_add","picture_as_pdf","refresh","search","select_all","settings","terminal","view_list"]

def symbols(icons, family, out_name):
    codes = [cp[i] for i in icons]
    for fill, suffix in ((0, ""), (1, " Filled")):
        font = TTFont("symbols.ttf")
        opts = subset.Options()
        opts.layout_features = []
        opts.name_IDs = ["*"]
        opts.notdef_outline = True
        opts.glyph_names = False
        sub = subset.Subsetter(opts)
        sub.populate(unicodes=codes)
        sub.subset(font)
        font = instancer.instantiateVariableFont(font, {"FILL": fill, "wght": 400, "GRAD": 0, "opsz": 24})
        fam = family + suffix
        rename(font, fam, fam.replace(" ", ""))
        out = out_name % ("_filled" if fill else "")
        font.save(out)
        print(out, len(open(out, "rb").read()))

symbols(FILES_ICONS, "Wine Files Symbols", "files_symbols%s.ttf")

for fill, suffix in ((0, ""), (1, " Filled")):
    font = TTFont("symbols.ttf")
    opts = subset.Options()
    opts.layout_features = []
    opts.name_IDs = ["*"]
    opts.notdef_outline = True
    opts.glyph_names = False
    sub = subset.Subsetter(opts)
    sub.populate(unicodes=codes)
    sub.subset(font)
    font = instancer.instantiateVariableFont(font, {"FILL": fill, "wght": 400, "GRAD": 0, "opsz": 24})
    fam = "Wine M3 Symbols" + suffix
    rename(font, fam, fam.replace(" ", ""))
    out = "wine_m3_symbols%s.ttf" % ("_filled" if fill else "")
    font.save(out)
    print(out, len(open(out, "rb").read()))

LATIN = ("U+0000-024F,U+0259,U+02B0-02FF,U+0300-036F,U+0370-03FF,U+0400-052F,U+1E00-1EFF,"
         "U+2000-206F,U+20A0-20CF,U+2100-2122,U+2190-2199,U+2200-2212,U+25CB-25CF,U+FB00-FB04,U+FEFF,U+FFFD")
for src, out in (("/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/Roboto-Regular.ttf", "roboto_regular.ttf"),
                 ("/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/Roboto-Medium.ttf", "roboto_medium.ttf")):
    font = TTFont(src)
    opts = subset.Options()
    opts.layout_features = ["kern", "liga", "ccmp", "locl", "mark", "mkmk"]
    opts.name_IDs = ["*"]
    opts.name_languages = ["*"]
    opts.notdef_outline = True
    sub = subset.Subsetter(opts)
    sub.populate(unicodes=subset.parse_unicodes(LATIN))
    sub.subset(font)
    font.save(out)
    n = font["name"]
    print(out, len(open(out, "rb").read()), n.getDebugName(1), "|", n.getDebugName(2), "| weight", font["OS/2"].usWeightClass)
