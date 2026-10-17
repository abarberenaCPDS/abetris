# Abetris

[![GB Studio 4.3.2](https://img.shields.io/badge/GB%20Studio-4.3.2-2b6cb0)](https://www.gbstudio.dev)
[![ModRetro Chromatic GBC](https://img.shields.io/badge/ModRetro%20Chromatic-GBC%20MBC5-6b46c1)](docs/GBSTUDIO-BASELINE.md)
[![Version 0.1.0](https://img.shields.io/badge/version-0.1.0-2f855a)](docs/CHANGELOG.md)
[![Semantic Versioning 2.0.0](https://img.shields.io/badge/semver-2.0.0-blue)](https://semver.org)
[![Conventional Commits](https://img.shields.io/badge/commits-conventional-fe5196)](https://www.conventionalcommits.org)
[![Status: playable](https://img.shields.io/badge/status-playable-brightgreen)](docs/GAME-DESIGN.md)
[![Rule tests: 256 checks](https://img.shields.io/badge/rule%20tests-256%20checks-brightgreen)](docs/VERIFYING.md#1-rule-tests-host-no-toolchain)
[![Hardware: flashed, boot check pending](https://img.shields.io/badge/hardware-flashed%20%28boot%20check%20pending%29-yellow)](docs/VERIFYING.md#7-hardware)

A Tetris game for the ModRetro Chromatic, built as a native GB Studio 4.3.2
project. The playfield is the 10-column ASCII well from the original terminal
Tetris: `[]` blocks, `<!` `!>` walls, and a `<!====!>` floor.

Four lines at once is an **ABETRIS**.

**Status:** 0.1.0 is playable in the emulator and was flashed to a ModRetro
Chromatic (the vendor tool reported success). The on-device boot check is still
pending. See [VERIFYING.md](docs/VERIFYING.md#7-hardware).

## Tribute

Abetris is inspired by **Tetris**, created by **Alexey Pajitnov** in Moscow.
This game is a tribute to him, and its `[]` playfield follows the look of the
original ASCII version.

## Controls

| Button | Action |
| --- | --- |
| Left / Right | Move the piece |
| Down | Soft drop |
| A | Rotate clockwise |
| B | Rotate counter-clockwise |
| Start | Pause / resume; on game over, back to the title |

On the title screen, Start begins a game.

## Levels

Four levels. The piece falls faster at each one, and the level goes up every 10
lines. Level 0 starts easy, with the piece dropping from the top centre.

| Level | Lines | Frames per row |
| --- | --- | --- |
| 0 | 0–9 | 48 |
| 1 | 10–19 | 32 |
| 2 | 20–29 | 20 |
| 3 | 30+ | 12 |

Full rules, scoring and sound are in [`docs/GAME-DESIGN.md`](docs/GAME-DESIGN.md).

## Build and test

Run from the project root. The toolchain paths are in
[`docs/GBSTUDIO-BASELINE.md`](docs/GBSTUDIO-BASELINE.md).

```sh
# rule tests (no toolchain needed)
mkdir -p build && cc -std=c99 -Wall -Wextra -Werror -Iplugins/abetris/engine/include \
  tests/test_logic.c plugins/abetris/engine/src/abetris_logic.c -o build/test_logic
build/test_logic
```

Build the ROM with the MCP `rom_build` tool, which reports compiler diagnostics,
or with the CLI in [`docs/GBSTUDIO-BASELINE.md`](docs/GBSTUDIO-BASELINE.md).
What each check proves, and what a good build looks like, is in
[`docs/VERIFYING.md`](docs/VERIFYING.md).

## Hardware

- **Stream:** `play` runs the ROM on a Chromatic for a set time. It doesn't write
  the cartridge, and the host can't send button presses.
- **Flash:** `flash` overwrites the cartridge's game data and saves, with no
  backup. The first flash on each device needs the owner's explicit acceptance
  of that.
- **0.1.0:** streamed for 60 seconds and flashed to Chromatic player 1 on
  2026-10-17. The vendor tool reported success. The on-device checks are still to
  do; see [`docs/VERIFYING.md`](docs/VERIFYING.md#7-hardware).

## Project layout

```
project.gbsproj       GB Studio project (metadata only)
project/              settings, scenes (title, play), palettes, variables
assets/               backgrounds, font, sprite, music, sounds (+ .gbsres)
plugins/abetris/      engine plugin: the ABETRIS scene type (rules + drawing)
tools/                generators for art, sound and music
tests/                host tests for the rules
docs/                 design, verification, toolchain baseline, changelog
VERSION               semantic version, 0.1.0
```

## Documentation

| Doc | For |
| --- | --- |
| [`AGENTS.md`](AGENTS.md) | Rules for working in this repo, hardware consent, and the engine notes |
| [`docs/GAME-DESIGN.md`](docs/GAME-DESIGN.md) | Rules, controls, levels, scoring, sound |
| [`docs/VERIFYING.md`](docs/VERIFYING.md) | How to check a build, the gameplay, and the hardware |
| [`docs/GBSTUDIO-BASELINE.md`](docs/GBSTUDIO-BASELINE.md) | Toolchain, MCP workflow, engine traps |
| [`docs/CHANGELOG.md`](docs/CHANGELOG.md) | What changed in each version, and the known limits |
| [`docs/abes-ascii-tetris.md`](docs/abes-ascii-tetris.md) | The original brief |
| [`docs/image.png`](docs/image.png) | The reference picture |

## Versioning and commits

- Versions follow [semantic versioning](https://semver.org). `VERSION` is the
  source of truth; patch bumps unless a minor or major change is agreed.
- Commit subjects are one line in [conventional commit](https://www.conventionalcommits.org)
  form, with no body.
