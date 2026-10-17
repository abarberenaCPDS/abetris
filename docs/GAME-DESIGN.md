# Abetris — game design

The rules and the decisions behind them. The original brief is kept in
[`abes-ascii-tetris.md`](abes-ascii-tetris.md), with the reference picture
[`image.png`](image.png).

## Screens

- **Title** (`project/scenes/title`, LOGO scene, start scene): the "ABETRIS"
  logo built from `[]` blocks, `PRESS START`, Korobeiniki loops, Start plays a
  chime and goes to play.
- **Play** (`project/scenes/play`, scene type `ABETRIS`): the ASCII well on the
  left (10 columns), the side panel on the right with SCORE, LEVEL, LINES and
  NEXT.
- **Game over**: `GAME OVER` over the stack. Start returns to the title.

## Controls

| Button | Action |
| --- | --- |
| Left / Right | Move. Auto-repeats after 12 frames, then every 4 frames |
| Down | Soft drop: 2 frames per row, +1 point per row |
| A | Rotate clockwise |
| B | Rotate counter-clockwise |
| Start | Pause / resume (ignored for the first 30 frames of a game) |
| Start (game over) | Back to the title |

No hard drop and no ghost piece, by choice.

## Pieces

- Classic seven: I, O, T, S, Z, J, L. The brief said "z, t, L, I and square";
  the choice was made for the classic seven.
- Random order from a 7-bag: each run of seven spawns contains every piece once.
- Spawn: top centre (columns 3–6, or 4–5 for O).
- Rotation is about each piece's own centre. O never turns.
- Wall kicks are tried in this order: stay, left, right, up, up-left, up-right,
  left two, right two. A rotation that fits nowhere does nothing.

## Locking and clearing

- A grounded piece locks after 24 frames. Moves and rotations while grounded
  restart that timer, up to 12 times, so a piece cannot be stalled forever.
- A completed row blinks for 24 frames, then is removed and the rows above fall.
- Four rows at once is an **ABETRIS**: the message shows for 2.5 s with its own
  sound.

## Levels and speed

| Level | Lines to reach | Frames per row (fall speed) |
| --- | --- | --- |
| 0 | 0 | 48 (easy) |
| 1 | 10 | 32 |
| 2 | 20 | 20 |
| 3 | 30 | 12 (fastest, the top level) |

The level stays at 3 after 30 lines. Lines keep counting.

## Score

- Line clear: 40 (1), 100 (2), 300 (3), 1200 (four rows, ABETRIS), each
  multiplied by (level + 1).
- Soft drop: 1 point per row.
- Caps: score 999999, lines 999.

## Look

- Green terminal for now (palette `abetris-green`, four shades of green on black).
- Later phase: coloured pieces. The board stores each cell's piece kind, so
  colour can be added without changing the rules.
- Glyphs: `[]` for a block, ` .` for an empty cell, `<!` `!>` for the walls,
  `<!====!>` and `\/\/\/` for the floor. Each one is one 8×8 tile.

## Sound

- Music: one looping track, `korobeiniki.uge`. It is an original arrangement of
  the public-domain folk melody, not a copy of any game's arrangement.
- Sound effects: eight WAVs (rotate, lock, line, ABETRIS, level up, game over,
  pause, start). Their pitches are tuned for the hardware's 8192 samples/s
  playback. See [VERIFYING.md](VERIFYING.md#3-sound).
- How it's wired: the C code can't start a sound directly. It writes a request
  number into the script variable `var_sfx_request`. A thread that the play scene
  starts (`EVENT_THREAD_START` around an `EVENT_LOOP`) reads that variable every
  frame, plays the matching sound and resets it. The same loop watches
  `var_goto_title` for the return to the title.

## Why a plugin, not events

Tetris needs a board, collision, rotation and a per-frame state machine. None
of that is expressible with GB Studio's visual events. So the rules and drawing
live in an engine plugin (`plugins/abetris/engine`) that adds the `ABETRIS`
scene type. Scenes, music, sound, palettes and the title stay as normal GB Studio
resources, so they can still be edited in the GUI.
