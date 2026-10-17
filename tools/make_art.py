#!/usr/bin/env python3
"""Generate the Abetris art, its GB Studio sidecars and the C layout header.

Run with the toolchain venv (needs Pillow), from anywhere:
    "$PY" tools/make_art.py

Outputs (never hand-edit them; change this file and re-run):
    assets/backgrounds/title.png (+ .gbsres)   20x18 tiles: ABETRIS in [] blocks
    assets/backgrounds/play.png  (+ .gbsres)   32x18 tiles: 20 visible + glyph atlas
    assets/fonts/abetris-term.png (+ .json, .png.gbsres)
    assets/ui/frame.png, assets/ui/cursor.png
    assets/sprites/player_hidden.png (+ .gbsres)
    plugins/abetris/engine/include/abetris_layout.h

How the pieces fit together:
- The play screen is 20x18 tiles. Each well cell is ONE 8x8 tile holding two
  half-width ASCII characters ("[]", " ." ...), so 10 columns fit with walls.
- Columns 20..31 of play.png are an off-screen glyph atlas. The camera never
  scrolls there; the C scene type reads the atlas tile ids/attributes from the
  background's ROM tilemap, so it never guesses VRAM tile numbers.
- GB Studio picks a pixel's colour index from the GREEN channel only
  (g<65 -> 3, g<130 -> 2, g<205 -> 1, else 0). The scene palette maps index
  0..3 to bright green .. black, so these PNGs already look like the game.
"""
import hashlib
import json
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION = open(os.path.join(ROOT, "VERSION")).read().strip()

# Background shades, by GB Studio colour index (green channel decides).
BRIGHT = (51, 255, 51)   # index 0
MID = (32, 160, 32)      # index 1
DARK = (16, 100, 16)     # index 2
BLACK = (0, 0, 0)        # index 3
SHADES = {"#": BRIGHT, "o": MID, ":": DARK, ".": BLACK}

# UI / font / sprite images use the standard GB Studio reference shades.
UI_LIGHT = (224, 248, 207)   # index 0
UI_DARK = (7, 24, 33)        # index 3
SPRITE_CLEAR = (101, 255, 0)  # index 0 = transparent for sprites

T = 8  # tile size in pixels

# ---------------------------------------------------------------- font ---
# 5x7 terminal glyphs, drawn at x=1..5, y=0..6 of an 8x8 cell.
FONT = {
    "A": "01110 10001 10001 11111 10001 10001 10001",
    "B": "11110 10001 10001 11110 10001 10001 11110",
    "C": "01110 10001 10000 10000 10000 10001 01110",
    "D": "11100 10010 10001 10001 10001 10010 11100",
    "E": "11111 10000 10000 11110 10000 10000 11111",
    "F": "11111 10000 10000 11110 10000 10000 10000",
    "G": "01110 10001 10000 10111 10001 10001 01111",
    "H": "10001 10001 10001 11111 10001 10001 10001",
    "I": "01110 00100 00100 00100 00100 00100 01110",
    "J": "00111 00010 00010 00010 00010 10010 01100",
    "K": "10001 10010 10100 11000 10100 10010 10001",
    "L": "10000 10000 10000 10000 10000 10000 11111",
    "M": "10001 11011 10101 10101 10001 10001 10001",
    "N": "10001 10001 11001 10101 10011 10001 10001",
    "O": "01110 10001 10001 10001 10001 10001 01110",
    "P": "11110 10001 10001 11110 10000 10000 10000",
    "Q": "01110 10001 10001 10001 10101 10010 01101",
    "R": "11110 10001 10001 11110 10100 10010 10001",
    "S": "01111 10000 10000 01110 00001 00001 11110",
    "T": "11111 00100 00100 00100 00100 00100 00100",
    "U": "10001 10001 10001 10001 10001 10001 01110",
    "V": "10001 10001 10001 10001 10001 01010 00100",
    "W": "10001 10001 10001 10101 10101 10101 01010",
    "X": "10001 10001 01010 00100 01010 10001 10001",
    "Y": "10001 10001 10001 01010 00100 00100 00100",
    "Z": "11111 00001 00010 00100 01000 10000 11111",
    "0": "01110 10001 10011 10101 11001 10001 01110",
    "1": "00100 01100 00100 00100 00100 00100 01110",
    "2": "01110 10001 00001 00010 00100 01000 11111",
    "3": "11111 00010 00100 00010 00001 10001 01110",
    "4": "00010 00110 01010 10010 11111 00010 00010",
    "5": "11111 10000 11110 00001 00001 10001 01110",
    "6": "00110 01000 10000 11110 10001 10001 01110",
    "7": "11111 00001 00010 00100 01000 01000 01000",
    "8": "01110 10001 10001 01110 10001 10001 01110",
    "9": "01110 10001 10001 01111 00001 00010 01100",
    "!": "00100 00100 00100 00100 00100 00000 00100",
    ".": "00000 00000 00000 00000 00000 01100 01100",
    ",": "00000 00000 00000 00000 01100 00100 01000",
    "-": "00000 00000 00000 11111 00000 00000 00000",
    ":": "00000 01100 01100 00000 01100 01100 00000",
    "/": "00000 00001 00010 00100 01000 10000 00000",
    "?": "01110 10001 00001 00010 00100 00000 00100",
    "'": "00100 00100 01000 00000 00000 00000 00000",
    '"': "01010 01010 00000 00000 00000 00000 00000",
    "(": "00010 00100 01000 01000 01000 00100 00010",
    ")": "01000 00100 00010 00010 00010 00100 01000",
    "[": "01110 01000 01000 01000 01000 01000 01110",
    "]": "01110 00010 00010 00010 00010 00010 01110",
    "<": "00010 00100 01000 10000 01000 00100 00010",
    ">": "01000 00100 00010 00001 00010 00100 01000",
    "=": "00000 00000 11111 00000 11111 00000 00000",
    "+": "00000 00100 00100 11111 00100 00100 00000",
    "*": "00000 00100 10101 01110 10101 00100 00000",
    "#": "01010 01010 11111 01010 11111 01010 01010",
    "_": "00000 00000 00000 00000 00000 00000 11111",
}


def text_tile(ch, ink):
    """8x8 tile (rows of RGB) for one full-width character."""
    tile = [[BLACK] * T for _ in range(T)]
    rows = FONT.get(ch.upper())
    if rows:
        for y, row in enumerate(rows.split()):
            for x, bit in enumerate(row):
                if bit == "1":
                    tile[y][x + 1] = ink
    return tile


# ------------------------------------------------- half-width well glyphs ---
# Each 8x8 tile holds two 4px-wide characters, so "[]" is a single cell.
ART = {
    "BLANK": ["........"] * 8,
    "CELL": [  # "[]"
        "###.###.",
        "#.....#.",
        "#.....#.",
        "#.....#.",
        "#.....#.",
        "#.....#.",
        "###.###.",
        "........",
    ],
    "EMPTY": [  # " ."
        "........",
        "........",
        "........",
        "...o....",
        "........",
        "........",
        "........",
        "........",
    ],
    "WALL_L": [  # "<!"
        "......#.",
        "...#..#.",
        "..#...#.",
        ".#....#.",
        "..#...#.",
        "...#....",
        "......#.",
        "........",
    ],
    "WALL_R": [  # "!>"
        "#.......",
        "#..#....",
        "#...#...",
        "#....#..",
        "#...#...",
        "...#....",
        "#.......",
        "........",
    ],
    "FLOOR": [  # "=="
        "........",
        "........",
        "########",
        "........",
        "########",
        "........",
        "........",
        "........",
    ],
    "SOLID": ["########"] * 8,
    "VEE": [  # "\/"
        "#......#",
        "#......#",
        ".#....#.",
        ".#....#.",
        "..#..#..",
        "..#..#..",
        "...##...",
        "........",
    ],
}


def art_tile(name):
    return [[SHADES[c] for c in row] for row in ART[name]]


# ----------------------------------------------------------- atlas order ---
# Index order is the C contract (GLYPH_* in abetris_layout.h).
GLYPHS = [
    ("BLANK", ("art", "BLANK")),
    ("CELL", ("art", "CELL")),
    ("EMPTY", ("art", "EMPTY")),
    ("FLASH", ("art", "SOLID")),   # cleared rows flash solid
    ("WALL_L", ("art", "WALL_L")),
    ("WALL_R", ("art", "WALL_R")),
    ("FLOOR", ("art", "FLOOR")),
    ("VEE", ("art", "VEE")),
]
GLYPHS += [(f"DIGIT{d}", ("text", str(d), BRIGHT)) for d in range(10)]
GLYPHS += [(ch, ("text", ch, BRIGHT)) for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"]
GLYPHS += [
    ("BANG", ("text", "!", BRIGHT)),
    ("DOT", ("text", ".", BRIGHT)),
    ("DASH", ("text", "-", BRIGHT)),
    ("COLON", ("text", ":", BRIGHT)),
    ("SLASH", ("text", "/", BRIGHT)),
]

# ---------------------------------------------------------------- layout ---
BOARD_W, BOARD_H = 10, 16
WELL_X, WELL_Y = 1, 0          # screen tile of board cell (0, 0)
ATLAS_X, ATLAS_Y, ATLAS_W = 20, 0, 12
PLAY_W, PLAY_H = 32, 18

PANEL_X = 13
SCORE_X, SCORE_Y, SCORE_DIGITS = 13, 2, 6
LEVEL_X, LEVEL_Y = 18, 5
LINES_X, LINES_Y, LINES_DIGITS = 16, 8, 3
NEXT_X, NEXT_Y = 14, 12        # 4x2 preview area

TITLE_W, TITLE_H = 20, 18
PROMPT_TEXT = "PRESS START"
PROMPT_X, PROMPT_Y = (TITLE_W - len(PROMPT_TEXT)) // 2, 13

# 3x5 block letters for the title logo (each '#' is one "[]" cell).
LOGO = {
    "A": [".#.", "#.#", "###", "#.#", "#.#"],
    "B": ["##.", "#.#", "##.", "#.#", "##."],
    "E": ["###", "#..", "##.", "#..", "###"],
    "T": ["###", ".#.", ".#.", ".#.", ".#."],
    "R": ["##.", "#.#", "##.", "#.#", "#.#"],
    "I": ["###", ".#.", ".#.", ".#.", "###"],
    "S": [".##", "#..", ".#.", "..#", "##."],
}


class Grid:
    """A tile map of tile specs, rendered to an RGB image."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.cells = [[("art", "BLANK")] * w for _ in range(h)]

    def put(self, x, y, spec):
        assert 0 <= x < self.w and 0 <= y < self.h, (x, y)
        self.cells[y][x] = spec

    def text(self, x, y, s, ink):
        for i, ch in enumerate(s):
            self.put(x + i, y, ("text", ch, ink) if ch != " " else ("art", "BLANK"))

    def render(self):
        img = Image.new("RGB", (self.w * T, self.h * T), BLACK)
        px = img.load()
        for ty, row in enumerate(self.cells):
            for tx, spec in enumerate(row):
                tile = art_tile(spec[1]) if spec[0] == "art" else text_tile(spec[1], spec[2])
                for y in range(T):
                    for x in range(T):
                        px[tx * T + x, ty * T + y] = tile[y][x]
        return img


def draw_well(g, x0, rows, floor_y):
    """Walls '<!' '!>' around `rows` rows, floor '<!==!>' and '\\/' below."""
    for y in range(rows):
        g.put(x0, y, ("art", "WALL_L"))
        for x in range(BOARD_W):
            g.put(x0 + 1 + x, y, ("art", "EMPTY"))
        g.put(x0 + 1 + BOARD_W, y, ("art", "WALL_R"))
    g.put(x0, floor_y, ("art", "WALL_L"))
    for x in range(BOARD_W):
        g.put(x0 + 1 + x, floor_y, ("art", "FLOOR"))
        g.put(x0 + 1 + x, floor_y + 1, ("art", "VEE"))
    g.put(x0 + 1 + BOARD_W, floor_y, ("art", "WALL_R"))


def build_play():
    g = Grid(PLAY_W, PLAY_H)
    draw_well(g, WELL_X - 1, BOARD_H, BOARD_H)
    g.text(PANEL_X, SCORE_Y - 1, "SCORE", MID)
    g.text(SCORE_X, SCORE_Y, "0" * SCORE_DIGITS, BRIGHT)
    g.text(PANEL_X, LEVEL_Y - 1, "LEVEL", MID)
    g.text(LEVEL_X, LEVEL_Y, "0", BRIGHT)
    g.text(PANEL_X, LINES_Y - 1, "LINES", MID)
    g.text(LINES_X, LINES_Y, "0" * LINES_DIGITS, BRIGHT)
    g.text(PANEL_X, NEXT_Y - 2, "NEXT", MID)
    tag = "V" + VERSION
    g.text(PLAY_W - 12 - len(tag), PLAY_H - 1, tag, DARK)
    for i, (_, spec) in enumerate(GLYPHS):
        g.put(ATLAS_X + i % ATLAS_W, ATLAS_Y + i // ATLAS_W, spec)
    return g


def build_title():
    g = Grid(TITLE_W, TITLE_H)
    # The whole title is a big well: walls, floor and '\/' like the play field.
    for y in range(TITLE_H - 2):
        g.put(0, y, ("art", "WALL_L"))
        g.put(TITLE_W - 1, y, ("art", "WALL_R"))
    g.put(0, TITLE_H - 2, ("art", "WALL_L"))
    g.put(TITLE_W - 1, TITLE_H - 2, ("art", "WALL_R"))
    for x in range(1, TITLE_W - 1):
        g.put(x, TITLE_H - 2, ("art", "FLOOR"))
        g.put(x, TITLE_H - 1, ("art", "VEE"))

    def word(text, y):
        width = len(text) * 4 - 1
        x0 = (TITLE_W - width) // 2
        for i, ch in enumerate(text):
            for dy, row in enumerate(LOGO[ch]):
                for dx, c in enumerate(row):
                    if c == "#":
                        g.put(x0 + i * 4 + dx, y + dy, ("art", "CELL"))

    word("ABE", 1)
    word("TRIS", 7)
    g.text(PROMPT_X, PROMPT_Y, PROMPT_TEXT, BRIGHT)
    tag = "V" + VERSION
    g.text(TITLE_W - 1 - len(tag), TITLE_H - 3, tag, DARK)
    return g


# ------------------------------------------------------------- writers ---
def write_json(rel, data):
    path = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def save_png(img, rel):
    path = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, optimize=True)
    return path


def background_sidecar(rel_png, res_id, name, symbol, w, h):
    write_json(rel_png + ".gbsres", {
        "_resourceType": "background",
        "id": res_id,
        "name": name,
        "symbol": symbol,
        "tileColors": "",
        "filename": os.path.basename(rel_png),
        "width": w,
        "height": h,
        "imageWidth": w * T,
        "imageHeight": h * T,
        "autoColor": False,
    })


def unique_tiles(img):
    seen = set()
    for ty in range(img.height // T):
        for tx in range(img.width // T):
            seen.add(img.crop((tx * T, ty * T, tx * T + T, ty * T + T)).tobytes())
    return len(seen)


def build_font():
    """128x112 GB Studio font sheet: 16x14 cells from ASCII 32, caps only."""
    img = Image.new("RGB", (128, 112), UI_LIGHT)
    px = img.load()
    for i in range(16 * 14):
        ch = chr(32 + i)
        rows = FONT.get(ch.upper()) if ch.isascii() else None
        if not rows:
            continue
        cx, cy = (i % 16) * T, (i // 16) * T
        for y, row in enumerate(rows.split()):
            for x, bit in enumerate(row):
                if bit == "1":
                    px[cx + x + 1, cy + y] = UI_DARK
    return img


def build_frame():
    """24x24 dialogue frame (3x3 slices): a thin terminal box."""
    img = Image.new("RGB", (24, 24), UI_LIGHT)
    px = img.load()
    for i in range(24):
        for j in (1, 22):
            px[i, j] = UI_DARK
            px[j, i] = UI_DARK
    return img


def build_cursor():
    img = Image.new("RGB", (T, T), UI_LIGHT)
    px = img.load()
    for y, row in enumerate(FONT[">"].split()):
        for x, bit in enumerate(row):
            if bit == "1":
                px[x + 1, y] = UI_DARK
    return img


def build_player_sprite():
    """16x16 placeholder player. Hidden in both scenes (the engine still
    loads a player sprite for non-LOGO scene types). Ink in both 8x16 halves,
    not mirror copies, so the compiler keeps both tiles."""
    img = Image.new("RGB", (16, 16), SPRITE_CLEAR)
    px = img.load()
    for x, y in [(2, 10), (3, 10), (12, 5)]:
        px[x, y] = UI_DARK
    return img


def sprite_sidecar(rel_png, sha1):
    empty = lambda aid, fid: {"id": aid, "frames": [{"id": fid, "tiles": []}]}
    anims = [{
        "id": "1f0fc1b1-6828-4497-a871-d9085f875b26",
        "frames": [{
            "id": "785d2006-a586-455a-a7c0-310aa7b27b2f",
            "tiles": [
                {"id": "d5d630f4-8e0c-48d5-b495-d0e4613c9237", "x": 0, "y": 0,
                 "sliceX": 0, "sliceY": 0, "flipX": False, "flipY": False,
                 "palette": 0, "paletteIndex": 0, "objPalette": "OBP0", "priority": False},
                {"id": "01eae9e2-011b-46ef-a1c7-ca6a996d064f", "x": 8, "y": 0,
                 "sliceX": 8, "sliceY": 0, "flipX": False, "flipY": False,
                 "palette": 0, "paletteIndex": 0, "objPalette": "OBP0", "priority": False},
            ],
        }],
    }]
    for n in range(1, 8):
        anims.append(empty(f"6f432ff2-b054-4387-8a1f-00000000a0{n:02d}",
                           f"6f432ff2-b054-4387-8a1f-00000000f0{n:02d}"))
    write_json(rel_png + ".gbsres", {
        "_resourceType": "sprite",
        "id": "6f432ff2-b054-4387-8a1f-876e567b7f70",
        "name": "Player (hidden)",
        "symbol": "sprite_player_hidden",
        "states": [{
            "id": "38dcb5f1-9e7d-41b7-8d61-520e70177bd7",
            "name": "",
            "animationType": "multi",
            "flipLeft": False,
            "animations": anims,
        }],
        "numTiles": 2,
        "canvasOriginX": 0,
        "canvasOriginY": 0,
        "canvasWidth": 16,
        "canvasHeight": 16,
        "boundsX": 0,
        "boundsY": -8,
        "boundsWidth": 16,
        "boundsHeight": 16,
        "animSpeed": 15,
        "filename": os.path.basename(rel_png),
        "width": 16,
        "height": 16,
        "checksum": sha1,
    })


def write_layout_header():
    lines = [
        "// Generated by tools/make_art.py - do not edit; change the generator.",
        "#ifndef ABETRIS_LAYOUT_H",
        "#define ABETRIS_LAYOUT_H",
        "",
        f"#define BOARD_W {BOARD_W}",
        f"#define BOARD_H {BOARD_H}",
        f"#define WELL_X {WELL_X}",
        f"#define WELL_Y {WELL_Y}",
        "",
        "// Glyph atlas inside play.png (read from the ROM tilemap at scene start)",
        f"#define ATLAS_X {ATLAS_X}",
        f"#define ATLAS_Y {ATLAS_Y}",
        f"#define ATLAS_W {ATLAS_W}",
        f"#define GLYPH_COUNT {len(GLYPHS)}",
    ]
    for i, (name, _) in enumerate(GLYPHS):
        lines.append(f"#define GLYPH_{name} {i}")
    lines += [
        "",
        "// Side panel",
        f"#define SCORE_X {SCORE_X}",
        f"#define SCORE_Y {SCORE_Y}",
        f"#define SCORE_DIGITS {SCORE_DIGITS}",
        f"#define LEVEL_X {LEVEL_X}",
        f"#define LEVEL_Y {LEVEL_Y}",
        f"#define LINES_X {LINES_X}",
        f"#define LINES_Y {LINES_Y}",
        f"#define LINES_DIGITS {LINES_DIGITS}",
        f"#define NEXT_X {NEXT_X}",
        f"#define NEXT_Y {NEXT_Y}",
        "",
        "// Title screen blinking prompt",
        f"#define TITLE_PROMPT_X {PROMPT_X}",
        f"#define TITLE_PROMPT_Y {PROMPT_Y}",
        f"#define TITLE_PROMPT_W {len(PROMPT_TEXT)}",
        "",
        "#endif",
        "",
    ]
    path = os.path.join(ROOT, "plugins/abetris/engine/include/abetris_layout.h")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write("\n".join(lines))


def main():
    play = build_play().render()
    save_png(play, "assets/backgrounds/play.png")
    background_sidecar("assets/backgrounds/play.png",
                       "0513ea42-3da5-4ae4-a5b2-c6b55f9bc15c", "Play", "bg_play",
                       PLAY_W, PLAY_H)
    title = build_title().render()
    save_png(title, "assets/backgrounds/title.png")
    background_sidecar("assets/backgrounds/title.png",
                       "84b94bdd-d114-41b7-bee6-4ca2fd015119", "Title", "bg_title",
                       TITLE_W, TITLE_H)

    save_png(build_font(), "assets/fonts/abetris-term.png")
    write_json("assets/fonts/abetris-term.json", {"name": "Abetris Term", "mapping": {}})
    write_json("assets/fonts/abetris-term.png.gbsres", {
        "_resourceType": "font",
        "id": "4168bfad-1e66-4506-8ef7-aa695170310e",
        "name": "Abetris Term",
        "symbol": "font_abetris_term",
        "width": 128,
        "height": 112,
        "mapping": {},
        "filename": "abetris-term.png",
    })

    save_png(build_frame(), "assets/ui/frame.png")
    save_png(build_cursor(), "assets/ui/cursor.png")

    sprite_path = save_png(build_player_sprite(), "assets/sprites/player_hidden.png")
    sha1 = hashlib.sha1(open(sprite_path, "rb").read()).hexdigest()
    sprite_sidecar("assets/sprites/player_hidden.png", sha1)

    write_layout_header()

    # Budget checks: keep well under the CGB background tile banks.
    for name, img in (("play", play), ("title", title)):
        n = unique_tiles(img)
        assert n <= 192, f"{name}.png has {n} unique tiles"
        print(f"{name}.png: {img.width}x{img.height}, {n} unique tiles")
    assert len(GLYPHS) <= ATLAS_W * PLAY_H
    print(f"atlas: {len(GLYPHS)} glyphs; version tag V{VERSION}")


if __name__ == "__main__":
    main()
