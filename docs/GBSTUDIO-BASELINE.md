# GB Studio / Chromatic baseline (agent reference)

Verified setup, tools, workflow and engine traps for building a ModRetro Chromatic
(GBC, MBC5) game on this Mac. Supersedes README/CHANGELOG when they conflict.

## Environment (this Mac)
No toolchain is vendored in the repo; no package test/lint task and no CI.

```sh
CLI="/Users/abe/Library/Application Support/modretro-chromatic/toolchain/.local/vendor/gb-studio/out/cli/gb-studio-cli.js"
PY="/Users/abe/Library/Application Support/modretro-chromatic/toolchain/.local/pyboy-venv/bin/python"
TS="/Users/abe/Library/Application Support/modretro-chromatic/toolchain/.local/vendor/gb-studio"

node "$CLI" make:rom project.gbsproj build/project.gb   # ROM
node "$CLI" make:web project.gbsproj build/web         # browser export
python3 tools/check_dialogue.py                        # stdlib-only check
```

- The CLI is a JS bundle: run it with `node`, never as a native executable.
- Use `$PY` for Pillow/SDL tooling (sprite/background generators, PyBoy).
- Toolchain source of truth: `$TS/src/lib/...` (compiler/events) and
  `$TS/appData/engine/gbvm/src/...` (shipped engine). Read it instead of guessing.

## Project format
- Native distributed GB Studio project. `project.gbsproj` is **metadata only**;
  settings, scenes, actors, assets live in JSON `.gbsres` resources beside their
  assets. Do not invent an asset array in the descriptor.
- Read `project/settings.gbsres` and the scene scripts for current wiring.
- Edit generators, not their outputs. Regenerate assets with `$PY tools/*.py`.

## MCP workflow (preferred)
1. Select the intended project (only one can be selected at a time).
2. `project_refresh` **strong** after any hand-edited `.gbsres`.
3. `rom_build` / `web_build`; then inspect project health.
4. `web_preview` to show a playable build: `action: open|recover|status`, then
   `capture_state`/`restore_state`, `input` (≤2 s), `start_recording`/`read_capture`.
5. Headless play checks: `emulator_run`/`emulator_step`/`emulator_observe`/`emulator_review`.
6. Hardware: `device` (discovery/operation_status) and `device_capture` (video only).

Gotchas:
- The `plugins/hUGETracker` external symlink can make MCP fail with
  `PATH_OUTSIDE_PROJECT`. Temporarily park the link, do the MCP work, then restore
  it (restore even on failure). Never delete its target.
- Preview URLs are process-local; reuse the URL the tool returns.
- On "unknown closure/recording acknowledgement": resolve status, do not
  repeatedly rebuild or force-close.
- ROM 128 KiB is the observed size, not proof of exhausted ROM space.

## Engine / toolchain traps
- Scripts: event objects use `command`, `args`, `id`; ids unique per script.
  Walk nested `children` branches — top-level-only searches miss events.
  Unknown commands silently compile away. Scene change = `EVENT_SWITCH_SCENE`
  (not `EVENT_SCENE_SWITCH`). Verify ids in `$TS/src/lib/events/`.
- Interaction: the top-down engine processes A only when the player is exactly
  tile-aligned; stand below a target and face up. `isPinned` draws in screen
  space and clears collision — non-solid actors need
  `EVENT_ACTOR_COLLISIONS_DISABLE` in `startScript`.
- Sprites: a 16×16 frame needs ink in **both** 8×16 halves, and the two halves
  must not be mirror copies (blank/flip-duplicate halves get dropped).
  `numTiles` is reserved VRAM — compute it the way `optimiseTiles` counts
  (mirror reuse), never guess. Wide metasprites must follow the toolchain canvas
  convention (`canvasOriginX`, `canvasWidth`, `tile.x = sliceX - (canvasWidth/2 - 8)`,
  `boundsX = -(canvasWidth/2 - 8)`) or out-of-canvas pixels are treated as blank
  and dropped.
- `LOGO` scenes: only **24 usable sprite tiles** (actor VRAM indices 104–127).
  The oversized background takes sprite slots 0–103 and the `is360` compile path
  skips the CGB bank-1 split, so slots ≥128 alias BG tiles. Keep active sprites
  within the budget.
- Palettes: `load_scene` loads the whole scene `spritePaletteIds` array — add
  extra OBJ colours there. Select a tile's palette with `paletteIndex` (not
  `palette`) and ink from that palette. A runtime `EVENT_PALETTE_SET_SPRITE` on a
  new slot did not take in testing.
- `autoColor` backgrounds derive palettes from the image; keep at most eight
  groups of four colours to avoid aliasing.
- Dialogue: max **17 characters per line** (incl. cursor cell). Sentence case;
  opening briefings caps. `tools/check_dialogue.py` enforces it.
- Audio: SFX must be **WAV** — unsigned 8-bit mono, 8000 Hz (toolchain's WAV
  compiler packs to 4-bit wave samples). Music needs a `.uge` + sidecar id.
  Registration ≠ use: music needs `EVENT_MUSIC_PLAY`, WAVs need
  `EVENT_SOUND_PLAY_EFFECT`; unused assets may not reach the ROM.
- Scene main scripts are locked: the scene's `script` runs with `VM_LOCK` and
  unlocks only when it ends. The engine runs the scene update only while
  unlocked, so an endless `EVENT_LOOP` in the main script freezes the scene. Put
  loops in `EVENT_THREAD_START`. Yield with `EVENT_IDLE`; `EVENT_WAIT` locks too.
- Custom scene types: an engine plugin (`plugin.json` with
  `"type": "enginePlugin"`, `engine/engine.json` with `sceneTypes`) plus
  `engine/src/states/<key>.c` that defines `<key>_init` and `<key>_update` as
  `BANKED`. Only used scene types get enum values, and the state table follows
  them.
- Bank 0 overflow: the linker reports `ROM_CAPACITY_EXCEEDED: Possible overflow
  from Bank 0 into Bank 1`. Non-banked code lands in bank 0, so move larger code
  into a banked bank (`#pragma bank 255`, and `BANKED` on functions called from
  other files).
- The CLI hides compiler errors (`buildTask process terminated with error: 1`).
  The MCP `rom_build` returns the diagnostics, and `captureDebugArtifacts: true`
  returns a `symbols.noi` for the same ROM.
- `EVENT_MUSIC_PLAY` always compiles with `.MUSIC_NO_LOOP`. For hUGE songs the
  driver ignores that flag, so looping comes from the song's order data.
- Hardware WAV playback runs at 8192 samples/s (32 samples per 256 Hz timer
  tick), so an 8000 Hz file plays about 2.4% fast on the device.

## Release / versioning
- Patch bumps unless told otherwise. Order: edit `VERSION` → regenerate version
  art (`$PY tools/render_version.py`) → dialogue check → ROM + web builds →
  update `docs/CHANGELOG.md`. The on-screen tag is generated, not live.
- One-line conventional commit subjects, no body. Use worktrees for risky work.

## Verification
- Builds are not byte-reproducible: check ROM header/logo/checksum, mapper, size
  and gameplay, not hash equality.
- PyBoy audio is signed int8 stereo (`sound.ndarray`); silence is zero, unlike
  unsigned WAV silence at 128. Check live samples, not screenshots.
- Compare served bytes via the preview HTTP URL's ROM hash, but that cannot prove
  an already-open browser loaded them.

## Hardware
- `play` streams host video/audio and never writes the cartridge.
- `flash` permanently overwrites cartridge data; no read-back/vendor backup here.
  Requires explicit data-loss consent, fresh device discovery, a returned token,
  the exact ROM hash/size and a unique request id. Vendor "write success" is not
  manual boot verification. Never flash a guessed ROM.
- Device tokens are single-use: `play` and `flash` each consume one. Get a fresh
  `device list_devices` before each action. A token lasted about five minutes.
- `play` cannot send button presses from the host, so a Start-gated ROM waits on
  its title screen. Whether the handheld's own buttons reach it is not verified.
- The first `flash` on each device needs the owner's explicit acceptance of data
  loss. A lost reply is checked with `device operation_status` for the same
  request ID; never send a second write.
