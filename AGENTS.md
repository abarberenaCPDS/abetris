# Abetris — agent notes

Read in this order, and treat these as authoritative over README and CHANGELOG:
1. `AGENTS.md` (this file)
2. `docs/GBSTUDIO-BASELINE.md` — toolchain, MCP workflow, engine traps
3. `docs/VERIFYING.md` — how to check a build
4. `docs/GAME-DESIGN.md` — the rules the code must follow

## Rules of engagement

- Prefer the modretro-chromatic MCP tools for build and preview. Fall back to the
  CLI in `docs/GBSTUDIO-BASELINE.md`.
- After hand-editing any `*.gbsres`, run a **strong** `project_refresh` before
  `rom_build` / `web_build`.
- The browser simulator is MCP `web_preview`. Use the URL it returns; never a
  remembered port.
- Never flash the cartridge. No device write without explicit data-loss consent.
- Builds are not byte-reproducible. Verify content, header and gameplay, not hashes.
- Keep changes focused. Commit subjects are one line, conventional commit style,
  no body. Semantic versioning: patch bumps unless the owner says otherwise.

## Run the game (web preview)

Do this when someone clones the repo and asks to run or try the game.

**What you need**

- The ModRetro Chromatic plugin's MCP server (`modretro-chromatic`). It ships as a
  Codex plugin: `.mcp.json` runs `node ./scripts/start-mcp.mjs` over stdio from the
  plugin root. If your session has no `modretro-chromatic` tools, register that
  server in your client first. It has to stay running, because the preview server
  lives inside its process.
- The prepared toolchain, which the plugin's setup flow installs: GB Studio CLI
  4.3.2, GBDK 4.5.0, a Python venv with PyBoy 2.7.0 and Pillow, and Node. Check it
  with `toolchain_doctor` (`tasks: ["authoring","projectBuild","play"]`,
  `probes: ["cli-version","gbdk-version","emulator-import"]`). Expect `ready: true`;
  a missing `desktop` component is fine.
- The server finds the toolchain through environment variables. If
  `toolchain_doctor` reports the CLI, GBDK or PyBoy as missing, set
  `GB_STUDIO_SETUP_ROOT` and `GB_STUDIO_TOOLCHAIN_ROOT` to the prepared root, and
  `GB_STUDIO_RUNTIME_ROOT` and `GB_STUDIO_PLUGIN_ROOT` to the plugin folder.
  `GB_STUDIO_WORKSPACE_ROOT` must be a folder that contains this repo.
- Nothing else for playing. Docker (`uge-builder`) is only for regenerating the
  music, and `cc` is only for the rule tests.

**Steps**

1. `session_status`. If no project is selected, or another one is, run
   `project_select` with the absolute path to this repo's `project.gbsproj`. Only
   one project can be selected at a time.
2. `project_refresh` with `mode: "strong"` if you hand-edited any `*.gbsres`.
3. `web_preview {}`. It runs the official web export into `build/web`, serves it,
   and returns a `url` on `127.0.0.1`. Use `force: true` to rebuild after source
   changes; the same URL is reused.
4. Open the URL in a browser. The plugin's rules say to use Codex's built-in
   browser and never launch an external one. If you can't open it, give the URL to
   the user and say you couldn't open it.
5. Controls: Start begins; D-pad moves; A / B rotate; Start pauses.
6. When finished, `web_preview_close`. The URL stops working when the MCP process
   stops, and a new run gives a new URL.

If the build fails, run `rom_build` for the compiler diagnostics (the CLI hides
them). Not tested here: without MCP, `node "$CLI" make:web project.gbsproj build/web`
(see the baseline for `$CLI`) produces a static export that any local web server
should be able to serve.

## Hardware

- `play` streams the ROM to a Chromatic for a set time. It never writes the
  cartridge. Use it only when the owner asks for a live demo.
- `flash` overwrites the cartridge's game data and saves, with no backup. The
  first flash on a device needs the owner's explicit acceptance of that. The
  owner accepted it for Chromatic player 1 on 2026-10-17. Later writes the owner
  asks for on the same device don't need the acceptance again, but they still
  need a fresh discovery, `rom_inspect` values and a unique request ID.
- Never flash a guessed ROM. Never request or accept Developer Mode activation
  codes; activation is handled with ModRetro Updater.
- Device tokens are single-use and expire after a few minutes. A lost reply is
  checked with `device operation_status` for the same request ID, never by
  sending a second write.

## Layout

- `project.gbsproj`, `project/` — GB Studio resources: settings, scenes, palettes,
  variables. Start scene is the title.
- `assets/` — backgrounds, font, sprite, music, sounds and their `.gbsres` sidecars.
  The PNG, WAV and UGE files are generated; the sidecars are GB Studio's.
- `plugins/abetris/` — engine plugin that adds the `ABETRIS` scene type.
- `tools/` — generators. Change the generator and re-run it; do not hand-edit
  its output.
  - `make_art.py`: title and play backgrounds, font, player sprite, UI tiles, and
    `plugins/abetris/engine/include/abetris_layout.h` (glyph atlas indices).
  - `make_sfx.py`: the eight WAVs.
  - `make_music.py`: writes `assets/music/korobeiniki.json`; that JSON becomes
    `korobeiniki.uge` through the `uge-builder` Docker image.
- `tests/test_logic.c` — host tests of the rules (see `docs/VERIFYING.md`).
- `docs/` — design, verification, baseline, changelog and the original brief.

## Engine notes

- The rules live in `plugins/abetris/engine/src/abetris_logic.c`. It includes no
  GBDK headers on purpose, so `tests/test_logic.c` can build it on the host. Keep
  it that way.
- `plugins/abetris/engine/src/states/abetris.c` is the scene glue: input, drawing
  and the state machine. It runs as the `ABETRIS` scene type.
- The C code cannot start a sound or change scene. It writes requests into script
  variables (`var_sfx_request`, `var_goto_title`), and a thread that the play scene
  starts (`EVENT_THREAD_START` around an `EVENT_LOOP`, in
  `project/scenes/play/scene.gbsres`) acts on them. When you add a sound, change
  both: the C constants `SFX_*` and the `EVENT_SWITCH` cases.
- Keep that loop inside the thread. A scene's main script is locked until it ends,
  and the engine runs the scene's update only while unlocked. An endless loop in
  the main script freezes the game. Idle with `EVENT_IDLE`, not `EVENT_WAIT`, since
  `EVENT_WAIT` locks the VM too.
- The rules compile as banked code: `ABL_FN` expands to `BANKED` on the Game Boy
  and to nothing on the host. Bank 0 was over budget with the rules as fixed
  code, so keep new code out of bank 0 and watch the build for
  `ROM_CAPACITY_EXCEEDED`.
- Glyph tile ids are read from the play background's own tilemap at the atlas
  position (`ATLAS_X`, `ATLAS_Y`). Nothing hard-codes VRAM ids.
- The play background is 32 tiles wide, but the field never scrolls: the scene
  sets its scroll bounds to zero and hides sprites.
- Music and sound: `EVENT_MUSIC_PLAY` on each scene. The sound effects are
  `EVENT_SOUND_PLAY_EFFECT` with the ids in `assets/sounds/*.wav.gbsres`.

## Commands

From the project root (see the baseline for the CLI path):

```sh
mkdir -p build && cc -std=c99 -Wall -Wextra -Werror -Iplugins/abetris/engine/include \
  tests/test_logic.c plugins/abetris/engine/src/abetris_logic.c -o build/test_logic
build/test_logic

PY="/Users/abe/Library/Application Support/modretro-chromatic/toolchain/.local/pyboy-venv/bin/python"
"$PY" tools/make_art.py
python3 tools/make_sfx.py
```

Music is regenerated with `tools/make_music.py` and the `uge-builder` image
(commands in `docs/VERIFYING.md`).

On this Mac, the MCP `rom_build` tool reports compiler diagnostics. The CLI
reports only the exit status, so a failed build looks like
`buildTask process terminated with error: 1`.
