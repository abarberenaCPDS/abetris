# Changelog

Semantic versioning. Patch bumps unless the owner asks otherwise. The version
lives in `VERSION` and the on-screen tag is generated from it.

## 0.1.0 - 2026-10-16

- Title screen: "ABETRIS" in `[]` blocks, PRESS START, looping Korobeiniki
  arrangement and a start chime.
- Play field: 10-column ASCII well with `<!` `!>` walls and `<!====!>` floor.
- Classic seven pieces from a 7-bag, spawning top centre.
- A rotates clockwise, B counter-clockwise, with wall kicks.
- Left/Right with auto-repeat, Down soft drop, Start pause.
- Next-piece panel; SCORE, LEVEL and LINES in the side panel.
- Four levels with falling speeds 48, 32, 20 and 12 frames per row.
- ABETRIS: four rows at once shows the message and plays its own sound.
- Eight sound effects.
- Host tests for the rules (`tests/test_logic.c`).
