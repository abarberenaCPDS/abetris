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

Use the MCP `rom_build` tool. The CLI prints only `buildTask process terminated
with error: 1` when the compiler fails; the MCP tool returns the diagnostics.
Pass `captureDebugArtifacts: true` to also get a `symbols.noi` for the same ROM.

CLI alternative:

```sh
CLI="/Users/abe/Library/Application Support/modretro-chromatic/toolchain/.local/vendor/gb-studio/out/cli/gb-studio-cli.js"
node "$CLI" make:rom project.gbsproj build/project.gb > build/rom-build.log 2>&1
```

Checklist, with the results for build `7e3213…` (2026-10-17):

| Check | Expected | Result |
| --- | --- | --- |
| Compile | no errors; the plugin, sounds and music compile | pass |
| Link | no `ROM_CAPACITY_EXCEEDED` | pass |
| Header | Nintendo logo and header checksum valid (`rom_inspect`) | pass |
| Size and type | 131,072 bytes, MBC5, GBC-only, title `ABETRIS` | pass |
| Project health | 0 errors, 0 warnings | pass |

## 6. Playing it in the emulator

Headless checks use PyBoy from the toolchain venv. Read the game's RAM at the
addresses in the `symbols.noi` from the same build, so the addresses match the
ROM.

Verified on build `7e3213…`:

- The title renders with PRESS START, and Start opens the play scene.
- The piece falls from the top centre; A turns it; Start shows PAUSED and resumes.
- Down speeds the fall, and soft drop adds to the score.
- A stack reaches the top: GAME OVER shows, and Start returns to the title.
- The rotate sound request is raised for one frame, then consumed.

Not yet verified:

- Left and Right moves (not probed).
- A four-row ABETRIS clear and LEVEL UP on screen.
- The music and the sound effects, by ear or by sample count.

## 7. Hardware

**Stream (`play`):** a 60-second stream to Chromatic player 1 (`GWU2X`) on
2026-10-17. The vendor reported success, the process closed, and
`cartridgeWrite` was `not-dispatched`. Saves were off. The host can't send input,
so a Start-gated ROM waits on its title screen.

**Flash (`flash`):** written to Chromatic player 1 on 2026-10-17 (build
`7e3213…`, 131,072 bytes). The vendor reported success after 23 seconds. The
tool reports `manualBootAndPlayVerified: false`, so the boot check below is still
needed.

On the device, check:

1. The ABETRIS title with PRESS START appears.
2. Start begins a game, and the piece falls from the top centre.
3. A and B rotate both ways; Left and Right move; Down drops faster.
4. Start pauses and resumes.
5. Music plays and loops, and the sound effects are audible.
6. A stack that reaches the top shows GAME OVER, and Start returns to the title.

Record the result in [`CHANGELOG.md`](CHANGELOG.md).

Rules for hardware actions:

- `play` and `flash` each need a token from a fresh `device list_devices`. Tokens
  are single-use and lasted about five minutes.
- `rom_inspect` must show the same path, size and SHA-256 that you pass in.
- The first flash on a device needs the owner's explicit acceptance that the
  cartridge's game data and saves are erased and no backup is made. The owner
  accepted it for Chromatic player 1 on 2026-10-17.
- If a reply is lost or an operation is uncertain, read `device operation_status`
  for the same request ID. Never send a second write.
