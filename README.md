# Abetris

[![GB Studio 4.3.2](https://img.shields.io/badge/GB%20Studio-4.3.2-2b6cb0)](https://www.gbstudio.dev)
[![ModRetro Chromatic GBC](https://img.shields.io/badge/ModRetro%20Chromatic-GBC%20MBC5-6b46c1)](docs/GBSTUDIO-BASELINE.md)
[![Version 0.1.0](https://img.shields.io/badge/version-0.1.0-2f855a)](docs/CHANGELOG.md)
[![Semantic Versioning 2.0.0](https://img.shields.io/badge/semver-2.0.0-blue)](https://semver.org)
[![Conventional Commits](https://img.shields.io/badge/commits-conventional-fe5196)](https://www.conventionalcommits.org)
[![Status: in development](https://img.shields.io/badge/status-in%20development-dd6b20)](docs/GAME-DESIGN.md)

A Tetris game for the ModRetro Chromatic, built as a native GB Studio 4.3.2
project. The playfield is the 10-column ASCII well from the original terminal
Tetris: `[]` blocks, `<!` `!>` walls, and a `<!====!>` floor.

Four lines at once is an **ABETRIS**.

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

# ROM
node "$CLI" make:rom project.gbsproj build/project.gb
```

What each check proves, and what a good build looks like, is in
[`docs/VERIFYING.md`](docs/VERIFYING.md).

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
| [`AGENTS.md`](AGENTS.md) | Rules for working in this repo, and the engine notes |
| [`docs/GAME-DESIGN.md`](docs/GAME-DESIGN.md) | Rules, controls, levels, scoring, sound |
| [`docs/VERIFYING.md`](docs/VERIFYING.md) | How to check a build and the gameplay |
| [`docs/GBSTUDIO-BASELINE.md`](docs/GBSTUDIO-BASELINE.md) | Toolchain, MCP workflow, engine traps |
| [`docs/CHANGELOG.md`](docs/CHANGELOG.md) | What changed in each version |
| [`docs/abes-ascii-tetris.md`](docs/abes-ascii-tetris.md) | The original brief |
| [`docs/image.png`](docs/image.png) | The reference picture |

## Versioning and commits

- Versions follow [semantic versioning](https://semver.org). `VERSION` is the
  source of truth; patch bumps unless a minor or major change is agreed.
- Commit subjects are one line in [conventional commit](https://www.conventionalcommits.org)
  form, with no body.
