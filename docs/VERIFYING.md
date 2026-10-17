# Verifying Abetris

Builds are not byte-reproducible, so judge a build by what it contains: the ROM
header, the size, the project health, and what the game does. Do not compare
hashes between two builds.

## 1. Rule tests (host, no toolchain)

```sh
mkdir -p build && cc -std=c99 -Wall -Wextra -Werror -Iplugins/abetris/engine/include \
  tests/test_logic.c plugins/abetris/engine/src/abetris_logic.c -o build/test_logic
build/test_logic
```

Expected: `256 checks, 0 failures` and exit code 0. The tests cover piece
shapes, rotation cycles, wall kicks, locking, row removal, scoring caps, level
thresholds, gravity, the 7-bag and game over.

## 2. Art

`"$PY" tools/make_art.py` regenerates the backgrounds, the font, the player
sprite and `abetris_layout.h`. It asserts the unique-tile budget (≤192 per
background) and prints the glyph count (49 expected). If the atlas layout
changes, the C constants change with it — the header is generated, so re-run
the generator rather than editing it.

## 3. Sound

`python3 tools/make_sfx.py` writes the eight WAVs. They are unsigned 8-bit mono
at 8000 Hz, as the toolchain requires.

Playback on the hardware runs at 8192 samples per second (one 32-sample block
per 256 Hz timer tick, in the engine's `sfx_player.c`). The effects are tuned
for that rate. On a computer they sound about 41 cents flat. To tune them for a
computer instead, set `DEVICE_RATE = SAMPLE_RATE` in `tools/make_sfx.py`.

## 4. Music

`assets/music/korobeiniki.json` is the composition. Build the `.uge` with the
hUGETracker pipeline (same contract as the gardener project):

```sh
HT="/Users/abe/src/modretro-chromatic/hUGETracker"
python3 "$HT/abe/composer/validate.py" assets/music/korobeiniki.json
docker run --rm -v "$PWD":/w uge-builder /usr/local/bin/uge_gen /w/assets/music/korobeiniki.json /w/assets/music/korobeiniki.uge
python3 "$HT/abe/composer/verify_uge.py" assets/music/korobeiniki.json assets/music/korobeiniki.uge
```

## 5. ROM build

```sh
CLI="/Users/abe/Library/Application Support/modretro-chromatic/toolchain/.local/vendor/gb-studio/out/cli/gb-studio-cli.js"
node "$CLI" make:rom project.gbsproj build/project.gb > build/rom-build.log 2>&1
```

Checklist after a build:

| Check | Expected |
| --- | --- |
| Build log | no errors; the plugin compiles; the eight sound ids and the music id appear |
| Header | Nintendo logo valid, header checksum valid (`rom_inspect`) |
| Size | 131,072 bytes (MBC5, GBC-only) |
| Project health | 0 errors, 0 warnings |

## 6. Playing it

- Browser: MCP `web_preview` (use the URL it returns). The preview server lives in
  the MCP process; keep that process running while you look at it.
- Headless: PyBoy in the toolchain venv (`sound_emulated=True`). Count non-zero
  audio samples to confirm music is playing (expect continuous non-zero samples
  after the title loads). To check one sound effect, count samples with and
  without the effect (see the gardener project's `docs/VERIFYING.md`).
- Gameplay checks to run by hand: title → Start → the piece falls from top
  centre; A and B turn it both ways; Left/Right auto-repeat; Down speeds it up;
  Start pauses and resumes; four rows give ABETRIS; game over returns to the
  title with Start.

## 7. Hardware

`play` streams video and audio to a real Chromatic and never writes the
cartridge. `flash` overwrites the cartridge. Do not use it without explicit
data-loss consent, a fresh device discovery, and the exact ROM hash.
