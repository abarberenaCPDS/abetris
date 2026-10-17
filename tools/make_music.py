#!/usr/bin/env python3
"""Compose "Korobeiniki" (trad., arr. abetris) for uge_gen -> GB Studio 4.3.2.

Title + gameplay loop for Abetris. The melody is the 19th-century Russian folk
song (public domain). Everything around it -- bass lines, the A' descant, the
B section, the balalaika strums and the drums -- is an original arrangement
written for this game. Nothing is transcribed from the 1989 Game Boy "Type A"
or any NES Tetris arrangement, and B is built from folk-melody motifs, not the
Tetris half-note bridge (an assertion below guards against that contour).

Grid: 1 row = 16th note, 16 rows = 1 bar, one 64-row pattern = 4 bars = one
order. A minor, 4/4.

  orders bars   section  ch0 duty1           ch1 duty2               ch2 wave bass       ch3 noise
  0-1    1-8    A        melody (25%)        tacet                   roots on 1 + 3      kick 1+3, off-beat hat
  2-3    9-16   A'       melody (25%)        descant above (50%)     walking quarters    + snare 2+4
  4-5    17-24  B1       calls in C (50%)    answers (25%), pads     falling half notes  half-time
  6-7    25-32  B2       motif swapped every bar, then every half    oom-pah, Alberti,   16th hats,
                         bar, then both voices in thirds up the E7   E pedal             snare roll
  8-9    33-40  A''      melody 8va (50%)    arpeggio strums         arpeggio eighths    full groove, crash
  10     41-44  tag      pickup back into A  strums Am Dm E E7       oom-pah             light, pickup fill

Harmony, A sections (per half bar): Am-E | Am | E-E7 | Am-A7 | Dm | C-Am |
E-E7 | Am.  B1: C | G/B | Am | Em/G | F | C/E | Dm | E (relative major, calls
rework the head motif in C, answers bring back the original motifs).
B2: Am | Dm | G | C | F | Dm | E | E7 (circle of fifths, builds into A'').

Channel map: 0 = duty1 lead, 1 = duty2 harmony/counter-line (duty1 and duty2
share one 15-slot bank), 2 = wave bass (never the melody: GB Studio WAV sound
effects borrow this channel), 3 = noise drums. Instruments are uge_gen's
hUGETracker defaults: duty 1/2/3 = 12.5/25/50 % steady volume, duty 6 = 25 %
"plink" (fast decay); wave 12 plays the custom soft saw stored in waves[11];
noise 1 with a per-hit Cxy envelope. The lead always uses its instrument's
steady volume 15 and stays below C7.

Effects: Cxy (x = envelope, y = volume), Exy note cut (each note is cut a
couple of ticks before it ends, so repeated notes re-attack and nothing hangs
over a section boundary) and 0xy arpeggio on the strums. No Fxx, Bxx or Dxx:
the song loops by running off the end of the order list, and the tag's E7
pickup resolves into the first bar.

Tempo: ticks_per_row = 6. GB Studio ticks hUGEDriver at 64 Hz, so one row is
6/64 s = 93.75 ms = a 16th at 160 BPM. Loop = 11 orders * 64 rows * 6 ticks
/ 64 Hz = 66.0 s (about 70 s / 150 BPM in hUGETracker, which ticks at ~60 Hz).

Pitch: names follow hUGETracker (C3 = code 0). On the duty channels a name
sounds one octave below scientific pitch (A5 = 440 Hz); the wave channel
sounds one octave lower again (wave A4 = 110 Hz).

Usage: python3 tools/make_music.py   (writes assets/music/korobeiniki.json)
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "music", "korobeiniki.json")

TICKS = 6           # ticks per row
DRIVER_HZ = 64      # GB Studio calls hUGEDriver 64 times per second
BAR = 16            # rows per bar (1 row = 16th note)
PAT = 64            # rows per pattern

SQ12, SQ25, SQ50, PLINK25 = 1, 2, 3, 6   # duty bank (shared by ch0 + ch1)
BASS = 12                                # wave slot 12 -> waves[11]
NOISE = 1
ARP, VOL, CUT = 0x0, 0xC, 0xE            # effect codes

# Bass timbre: sin t + sin 2t / 2 + sin 3t / 4 scaled to 0..15. Rounder than
# the stock saw/square, but the 2nd/3rd harmonics keep an 82-165 Hz bass
# audible on small speakers.
SOFT_SAW = [8, 10, 13, 14, 15, 15, 14, 13, 12, 11, 10, 10, 10, 9, 9, 8,
            8, 7, 6, 6, 5, 5, 5, 4, 3, 2, 1, 0, 0, 1, 2, 5]

COMMENT = ("Russian folk song (public-domain melody); original Game Boy "
           "arrangement for Abetris: A, A' descant, B call/answer in C, "
           "A'' 8va + strums, tag. 160 BPM at 64 Hz, 11 orders = 66 s loop.")

SEMI = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def code(n):
    """hUGE note name ("G#4") -> 0..71 (C3 = 0), same rule as validate.py."""
    acc = n[1:-1]
    c = (int(n[-1]) - 3) * 12 + SEMI[n[0]] + acc.count("#") - acc.count("b")
    assert 0 <= c <= 71, n
    return c


def name(c):
    return NAMES[c % 12] + str(c // 12 + 3)


def octave_up(score):
    out = []
    for tok in score.split():
        n, d = tok.split(":")
        out.append(tok if n == "-" else f"{name(code(n) + 12)}:{d}")
    return " ".join(out)


class Song:
    """Absolute-row timeline per channel, cut into 64-row patterns at the end."""

    def __init__(self, title, artist, comment, bars):
        self.d = {"name": title, "artist": artist, "comment": comment,
                  "ticks_per_row": TICKS, "waves": {"11": SOFT_SAW},
                  "orders": [[], [], [], []], "patterns": {}}
        self.rows = bars * BAR
        self.cells = [{} for _ in range(4)]

    def put(self, ch, row, note, inst, fx=None, fxp=0):
        """One cell. Two events on the same channel + row is a score bug.
        fx=None omits the effect keys; fx=0 with fxp != 0 is an arpeggio."""
        assert 0 <= row < self.rows and row not in self.cells[ch], (ch, row)
        e = {"row": row % PAT, "note": note, "inst": inst}
        if fx is not None:
            e["fx"], e["fxp"] = fx, fxp
        self.cells[ch][row] = e
        return e

    def finish(self):
        """Split into patterns; identical patterns on a channel share a key.
        Keys are ch*100+n, so each key lives in exactly one channel's orders."""
        for ch in range(4):
            keys = {}
            for start in range(0, self.rows, PAT):
                evts = [self.cells[ch][r] for r in sorted(self.cells[ch])
                        if start <= r < start + PAT]
                sig = json.dumps(evts)
                if sig not in keys:
                    keys[sig] = ch * 100 + len(keys)
                    self.d["patterns"][str(keys[sig])] = evts
                self.d["orders"][ch].append(keys[sig])
        n = len(self.d["orders"][0])
        assert all(len(o) == n for o in self.d["orders"]), "ragged orders"
        owner = {}
        for ch, seq in enumerate(self.d["orders"]):
            for k in seq:
                assert owner.setdefault(k, ch) == ch, f"key {k} shared"
        return self.d, n * PAT * TICKS / DRIVER_HZ


def play(s, ch, bar, score, inst, vol=None, env=0, gap=2):
    """Monophonic line from absolute `bar`. Tokens are "E5:4" (note:rows) or
    "-:4" (rest). vol adds Cxy on each note (x = envelope pace, 0 = steady;
    y = volume). Every note is cut `gap` ticks before it ends (Exy on its last
    row) so repeated pitches re-attack (at least 3 ticks of air) and nothing
    rings over into the next section. Returns the row after the line."""
    toks = [(None if n == "-" else n, int(d))
            for n, d in (t.split(":") for t in score.split())]
    row = bar * BAR
    for i, (n, d) in enumerate(toks):
        if n is not None:
            if vol is None:
                e = s.put(ch, row, n, inst)
            else:
                e = s.put(ch, row, n, inst, VOL, env << 4 | vol)
            nxt = toks[i + 1][0] if i + 1 < len(toks) else None
            sound = d * TICKS - (max(gap, 3) if nxt == n else gap)
            assert sound > 0, (ch, row, n)
            crow, tick = row + sound // TICKS, sound % TICKS
            if crow > row:
                s.put(ch, crow, None, 0, CUT, tick)
            else:                       # one-row note: cut inside its own cell
                assert "fx" not in e, (ch, row, n)
                e["fx"], e["fxp"] = CUT, tick
        row += d
    return row


# Strums: chord -> (base note, 0xy). The driver cycles base+y, base+x, base
# every tick, so each pluck sounds like a quick three-string strum.
STRUM = {"Am": ("A4", 0x73), "E": ("G#4", 0x83), "E7": ("G#4", 0x63),
         "E-": ("G#4", 0x88),   # G#4 + E5 only: no B4 under a passing C6
         "A7": ("A4", 0xA4), "Dm": ("A4", 0x85), "C": ("G4", 0x95)}


def strum(s, bar, chords, offs=(2, 6, 10, 14)):
    """Balalaika 'pah' on duty2: plink plucks on the off-eighths, each a
    2-row arpeggio. `chords` gives one chord per half bar, or one per pluck.
    The plink envelope (15 -> 0 in 15 ticks) ends the note, no cut needed."""
    for i, off in enumerate(offs):
        c = chords[i] if len(chords) == len(offs) > 2 else chords[off // 8]
        base, xy = STRUM[c]
        r = bar * BAR + off
        s.put(1, r, base, PLINK25, ARP, xy)
        s.put(1, r + 1, None, 0, ARP, xy)


# Drum kit: symbol -> (noise note, Cxy). Every hit carries its own decaying
# envelope (the default noise instrument is a steady hiss).
KIT = {
    "K": ("E5", 0x1D),   # kick: low noise, vol 13, fast decay
    "k": ("E5", 0x1A),   # soft kick (syncopation)
    "S": ("A6", 0x2B),   # snare: vol 11, pace 2
    "s": ("A6", 0x17),   # ghost / pickup snare
    "R": ("A6", 0x1D),   # roll accent
    "H": ("C8", 0x15),   # closed hat
    "h": ("C8", 0x12),   # ghost hat
    "O": ("A7", 0x36),   # open hat
    "X": ("E7", 0x5A),   # crash
}
LIGHT = "K.H...H.K.H...H."
LIGHT_FILL = "K.H...H.K.H.s.ss"
GROOVE = "K.H.S.H.K.H.S.H."
GROOVE_FILL = "K.H.S.H.K.H.SsSS"
HALF = "K.h.H.h.S.h.H.h."
HALF_FILL = "K.h.H.h.S.h.ssSS"
SIXTEENTHS = "KhHhShHhKhHhShHh"
DRIVE = "KhHhShHhKhKhShSS"
ROLL = "s.s.s.s.sSsSSSRR"
FULL = "K.H.S.HhK.k.S.Hh"
FULL_CRASH = "X...S.HhK.k.S.Hh"
FULL_FILL = "K.H.S.HhK.k.SsSS"
FULL_OPEN = "K.H.S.HhK.k.S.O."


def drums(s, bar, grids):
    for i, grid in enumerate(grids):
        assert len(grid) == BAR, grid
        for r, c in enumerate(grid):
            if c != ".":
                n, env = KIT[c]
                s.put(3, (bar + i) * BAR + r, n, NOISE, VOL, env)


# ------------------------------------------------- the folk melody (PD) ---
MELODY = [
    "E5:4 B4:2 C5:2 D5:4 C5:2 B4:2",    # 1  Am - E
    "A4:4 A4:2 C5:2 E5:4 D5:2 C5:2",    # 2  Am
    "B4:6 C5:2 D5:4 E5:4",              # 3  E - E7
    "C5:4 A4:4 A4:4 -:4",               # 4  Am - A7
    "D5:6 F5:2 A5:4 G5:2 F5:2",         # 5  Dm
    "E5:6 C5:2 E5:4 D5:2 C5:2",         # 6  C - Am
    "B4:4 B4:2 C5:2 D5:4 E5:4",         # 7  E - E7
    "C5:4 A4:4 A4:4 -:4",               # 8  Am
]
# A-section harmony per half bar, as strummed in A''. Bars 3 and 7 give one
# chord per pluck so the E chord loses its B4 under the tune's passing C6.
A3_STRUMS = [("Am", "E"), ("Am", "Am"), ("E", "E-", "E7", "E7"), ("Am", "A7"),
             ("Dm", "Dm"), ("C", "Am"), ("E", "E-", "E7", "E7"), ("Am", "Am")]

# ------------------------------------------------------- arrangement ---
# A: bass on beats 1 + 3 only; C#5 pickup turns bar 4 into A7 -> Dm.
BASS_LIGHT = ["A4:4 -:4 E4:4 -:4", "A4:4 -:4 E4:4 -:4",
              "E4:4 -:4 B4:4 -:4", "A4:4 -:4 A4:4 C#5:4",
              "D5:4 -:4 A4:4 -:4", "C5:4 -:4 A4:4 -:4",
              "E4:4 -:4 G#4:4 -:4", "A4:4 -:4 E4:4 G#4:4"]

# A': soft descant above the tune (falls D6 C6 B5 A5 over the second phrase).
DESCANT = ["A5:8 G#5:8", "A5:8 C6:8", "G#5:8 B5:8", "A5:8 C#6:8",
           "D6:8 F6:8", "E6:8 C6:8", "G#5:8 B5:8", "A5:12 B5:4"]
# Walking quarters with Phrygian F-E and chromatic C#-D approaches.
BASS_WALK = ["A4:4 E5:4 E4:4 G#4:4", "A4:4 E5:4 A4:4 F4:4",
             "E4:4 G#4:4 D5:4 B4:4", "A4:4 E5:4 A4:4 C#5:4",
             "D5:4 A4:4 D5:4 B4:4", "C5:4 G4:4 A4:4 F4:4",
             "E4:4 G#4:4 B4:4 D5:4", "A4:4 E5:4 A4:4 G4:2 B4:2"]

# B1: call (duty1) and answer (duty2) every two bars; the idle voice pads.
# Calls turn the head motif (drop a fourth, climb back by step) into C major;
# the answers bring back the original bar-1 and bar-5 motifs in minor.
B1_CALLS = {0: "C6:6 G5:2 A5:2 B5:2 C6:4", 1: "B5:6 A5:2 G5:8",
            4: "A5:6 E5:2 F5:2 G5:2 A5:4", 5: "G5:6 F5:2 E5:8"}
B1_ANSWERS = {2: "E5:6 B4:2 C5:2 D5:2 E5:4", 3: "D5:6 C5:2 B4:8",
              6: "D5:6 F5:2 A5:4 G5:2 F5:2", 7: "E5:6 D5:2 B4:4 G#4:4"}
B1_PADS_HI = {2: "A5:8 C6:8", 3: "G5:8 B5:8", 6: "A5:8 D6:8", 7: "B5:8 G#5:8"}
B1_PADS_LO = {0: "C5:8 E5:8", 1: "D5:8 B4:8", 4: "C5:8 A4:8", 5: "C5:8 G4:8"}
B1_BASS = ["C5:8 G4:8", "B4:8 G4:8", "A4:8 E4:8", "G4:8 E4:8",
           "A4:8 F4:8", "C5:8 G4:8", "D5:8 A4:8", "E4:8 B4:4 G#4:4"]

# B2: the repeated-note motif (A A C E) climbs the circle of fifths with the
# voices swapping each bar, then the head motif cascades down in half-bar
# hand-offs, then both voices rise in thirds through E7 into A''.
B2_CALLS = {0: "A5:4 A5:2 C6:2 E6:4 D6:2 C6:2", 2: "G5:4 G5:2 B5:2 D6:4 C6:2 B5:2"}
B2_ANSWERS = {1: "D5:4 D5:2 F5:2 A5:4 G5:2 F5:2", 3: "C5:4 C5:2 E5:2 G5:4 F5:2 E5:2"}
B2_PADS_HI = {1: "D6:8 F6:8", 3: "E6:8 C6:8"}
B2_PADS_LO = {0: "E5:8 C5:8", 2: "B4:8 D5:8"}
B2_CASCADE = ("C6:4 G5:2 A5:2 -:8 F5:4 C5:2 D5:2 -:8",
              "-:8 A5:4 E5:2 F5:2 -:8 D5:4 A4:2 B4:2")
B2_THIRDS = ("G#5:6 A5:2 B5:4 C6:4 B5:4 G#5:2 A5:2 B5:2 C6:2 D6:4",
             "E5:6 F5:2 G#5:4 A5:4 G#5:4 E5:2 F5:2 G#5:2 A5:2 B5:4")
B2_BASS_Q = ["A4:4 E5:4 A4:4 E5:4", "D5:4 A4:4 D5:4 A4:4",
             "G4:4 D5:4 G4:4 D5:4", "C5:4 G4:4 C5:4 G4:4"]
B2_BASS_E = ["F4:2 C5:2 A4:2 C5:2 F4:2 C5:2 A4:2 C5:2",
             "D5:2 A4:2 F4:2 A4:2 D5:2 A4:2 F4:2 B4:2",
             "E4:2 E4:2 E4:2 E4:2 E4:2 E4:2 E4:2 E4:2",
             "E4:2 E4:2 E4:2 E4:2 E5:2 E5:2 E5:2 E5:2"]

# A'': bass echoes the tune's repeated-note arpeggio, two per bar.
BASS_ARP = ["A4:2 A4:2 E5:2 C5:2 E4:2 E4:2 G#4:2 B4:2",
            "A4:2 A4:2 C5:2 E5:2 E5:2 E5:2 C5:2 A4:2",
            "E4:2 E4:2 B4:2 G#4:2 D5:2 D5:2 B4:2 G#4:2",
            "A4:2 A4:2 C5:2 E5:2 A4:2 A4:2 C#5:2 E5:2",
            "D5:2 D5:2 F5:2 A5:2 A5:2 A5:2 F5:2 D5:2",
            "C5:2 C5:2 E5:2 G5:2 A4:2 A4:2 C5:2 E5:2",
            "E4:2 E4:2 B4:2 G#4:2 D5:2 D5:2 B4:2 G#4:2",
            "A4:2 A4:2 C5:2 E5:2 A4:4 -:4"]

# Tag: band vamps i-iv-V-V7, lead re-enters with a pickup that lands on the
# melody's first E5 when the order list wraps.
TAG_LEAD = "-:8 E5:4 D5:4 B4:6 C5:2 D5:8"          # from tag bar 3
TAG_CHORDS = ["Am", "Dm", "E", "E7"]
TAG_BASS = ["A4:4 E5:4 A4:4 E5:4", "D5:4 A4:4 D5:4 A4:4",
            "E4:4 B4:4 E4:4 B4:4", "E4:4 G#4:4 B4:4 D5:4"]

TETRIS_BRIDGE = [4, 0, 2, 11, 0, 9, 8, 11]   # E C D B C A G# B (pitch classes)


def build():
    s = Song("Korobeiniki", "trad., arr. abetris", COMMENT, bars=44)
    A, A2, B1, B2, A3, TAG = 0, 8, 16, 24, 32, 40     # first bar of each section
    melody = " ".join(MELODY)
    pad = {"vol": 6, "env": 7}        # 12.5 % pad notes that fade out
    answer = {"vol": 12}              # duty2 answers, steady and a bit below lead

    # A (orders 0-1): melody, light bass, kick + off-beat hats; duty2 tacet.
    play(s, 0, A, melody, SQ25)
    play(s, 2, A, " ".join(BASS_LIGHT), BASS, gap=9)
    drums(s, A, [LIGHT] * 7 + [LIGHT_FILL])

    # A' (2-3): + descant above on duty2, walking bass, backbeat snare.
    play(s, 0, A2, melody, SQ25)
    play(s, 1, A2, " ".join(DESCANT), SQ50, vol=7, env=7)
    play(s, 2, A2, " ".join(BASS_WALK), BASS, gap=6)
    drums(s, A2, [GROOVE] * 7 + [GROOVE_FILL])

    # B1 (4-5): relative-major call and answer over a falling half-note bass.
    for b, sc in B1_CALLS.items():
        play(s, 0, B1 + b, sc, SQ50)
    for b, sc in B1_ANSWERS.items():
        play(s, 1, B1 + b, sc, SQ25, **answer)
    for b, sc in B1_PADS_HI.items():
        play(s, 0, B1 + b, sc, SQ12, **pad)
    for b, sc in B1_PADS_LO.items():
        play(s, 1, B1 + b, sc, SQ12, **pad)
    play(s, 2, B1, " ".join(B1_BASS), BASS, gap=6)
    drums(s, B1, [HALF] * 7 + [HALF_FILL])

    # B2 (6-7): exchanges tighten (1 bar -> half bar -> together), drums build.
    for b, sc in B2_CALLS.items():
        play(s, 0, B2 + b, sc, SQ50)
    for b, sc in B2_ANSWERS.items():
        play(s, 1, B2 + b, sc, SQ25, **answer)
    for b, sc in B2_PADS_HI.items():
        play(s, 0, B2 + b, sc, SQ12, **pad)
    for b, sc in B2_PADS_LO.items():
        play(s, 1, B2 + b, sc, SQ12, **pad)
    play(s, 0, B2 + 4, B2_CASCADE[0], SQ50)
    play(s, 1, B2 + 4, B2_CASCADE[1], SQ25, **answer)
    play(s, 0, B2 + 6, B2_THIRDS[0], SQ50)
    play(s, 1, B2 + 6, B2_THIRDS[1], SQ25, **answer)
    play(s, 2, B2, " ".join(B2_BASS_Q), BASS, gap=6)
    play(s, 2, B2 + 4, " ".join(B2_BASS_E), BASS, gap=3)
    drums(s, B2, [GROOVE] * 4 + [SIXTEENTHS] * 2 + [DRIVE, ROLL])

    # A'' (8-9): melody an octave up, strums, arpeggio bass, full groove.
    play(s, 0, A3, octave_up(melody), SQ50)
    for i, chords in enumerate(A3_STRUMS):
        strum(s, A3 + i, chords)
    play(s, 2, A3, " ".join(BASS_ARP), BASS, gap=3)
    drums(s, A3, [FULL_CRASH, FULL, FULL, FULL_FILL,
                  FULL, FULL, FULL, FULL_OPEN])

    # Tag (10): vamp, then the pickup that wraps into bar 1.
    play(s, 0, TAG + 2, TAG_LEAD, SQ25)
    for i, c in enumerate(TAG_CHORDS):    # last bar: room for the pickup
        strum(s, TAG + i, (c, c), (2, 10) if i == 3 else (2, 6, 10, 14))
    play(s, 2, TAG, " ".join(TAG_BASS), BASS, gap=6)
    drums(s, TAG, [LIGHT] * 3 + [LIGHT_FILL])

    check(s)
    return s.finish()


def check(s):
    """Arrangement guards that validate.py cannot know about."""
    notes = [[code(e["note"]) for _, e in sorted(c.items()) if e["note"]]
             for c in s.cells]
    assert max(notes[0]) < code("C7"), "lead must stay below C7"
    assert max(notes[2]) <= code("A5"), "wave channel carries bass only"
    for ch, seq in enumerate(notes):
        pcs = [n % 12 for n in seq]
        for i in range(len(pcs) - len(TETRIS_BRIDGE) + 1):
            assert pcs[i:i + len(TETRIS_BRIDGE)] != TETRIS_BRIDGE, \
                f"ch{ch}: Tetris bridge contour"
    for e in s.cells[3].values():      # every drum hit decays by itself
        env = e["fxp"] >> 4
        assert e["fx"] == VOL and 1 <= env <= 7 and e["fxp"] & 15, e


def main():
    song, secs = build()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(song, f)
    nev = sum(len(v) for v in song["patterns"].values())
    print(f"{OUT}: {len(song['patterns'])} patterns, {nev} events, "
          f"orders {[len(c) for c in song['orders']]}, "
          f"ticks={song['ticks_per_row']}, {secs:.1f}s loop at {DRIVER_HZ} Hz "
          f"({60 * DRIVER_HZ / (4 * TICKS):.0f} BPM)")


if __name__ == "__main__":
    main()
