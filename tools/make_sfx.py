#!/usr/bin/env python3
"""Generate the Abetris sound effects: unsigned 8-bit mono 8000 Hz WAVs plus
their GB Studio sidecars, written to assets/sounds/.

    stem          plays when                     length  sound
    sfx_rotate    a piece rotates                 56 ms  light 25% pulse blip, B5 flicking up to E6
    sfx_lock      a piece locks                   80 ms  soft triangle thud falling E5 -> E3, faint noise click
    sfx_line      1-3 lines clear                352 ms  bright square sweep E4 -> E6 that flutters, rings on E6
    sfx_abetris   4 lines at once ("ABETRIS!")  1100 ms  saw fanfare Am-F-G-Am, top line E-F-G-A, ending on
                                                         a shimmering A/E open fifth
    sfx_levelup   the level goes up              512 ms  square arpeggio rolling up A minor, A4 to E6
    sfx_gameover  the game ends                 1440 ms  two falling sighs (E-D, C-B), then A4 sagging to E4
    sfx_pause     pause and resume               128 ms  two-note blip, E6 then B5
    sfx_start     Start on the title screen      400 ms  E5-A5 pickup into a ringing, chorused E6

Pitched material is A-minor diatonic without G#, so it sits over the
Korobeiniki arrangement. All phrases are original.

What GB Studio 4.3.2 does with a WAV, and how this script allows for it:

* compileWav.ts keeps 8000-8192 Hz files as they are, turns each 8-bit sample
  into a 4-bit wave sample with ``>> 4`` and drops any tail that does not fill
  a 32-sample block. Every byte written here is ``level * 16`` for a 4-bit
  level (silence = level 8 = byte 128), so that step loses nothing and the WAV
  is exactly what the wave channel plays; every length is whole blocks. Each
  effect is normalised to levels 1-15 (bytes 16-240), the widest swing that is
  symmetric around silence. Pulses are DC-free, so a 25% pulse swings less
  below silence than above it (bytes 96-240).
* sfx_player.c plays one block per 256 Hz timer tick with the wave channel at
  8192 samples/s, so hardware runs an 8000 Hz file 2.4% fast. Pitches are
  synthesised 8000/8192 low so they land on concert pitch (A4 = 440 Hz) with
  the music on the device; on-device lengths are 2.3% shorter than listed.
  Set DEVICE_RATE = SAMPLE_RATE to write nominal pitches instead.
* The player retriggers the channel every block and lets the last block
  repeat until the length counter stops it, so every effect starts on silence
  and ends with a fully silent block.

Waveforms are box-filtered (each sample is the mean of the ideal wave over
that sample) to keep 8 kHz aliasing down. Noise is a Game Boy style 15-bit
LFSR with a fixed seed, so the output is byte-identical on every run.

Usage (stdlib only):

    python3 tools/make_sfx.py
"""
from __future__ import annotations

import json
import math
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOUNDS = ROOT / "assets" / "sounds"

SAMPLE_RATE = 8000  # file rate (project baseline)
DEVICE_RATE = 8192  # sfx_player.c: one 32-sample block per 1/256 s
TUNE = SAMPLE_RATE / DEVICE_RATE
BLOCK = 32  # samples per wave-RAM load
SILENCE = 8  # 4-bit level of silence (byte 128)
SWING = 7  # usable levels either side of silence: 1..15
NOISE_SEED = 0x2B5D  # any non-zero 15-bit LFSR state

SEMITONE = {"C": -9, "D": -7, "E": -5, "F": -4, "G": -2, "A": 0, "B": 2}


def hz(pitch: str | float) -> float:
    """'A4', 'C#5', 'Bb3' -> equal-tempered Hz (A4 = 440); numbers pass through."""
    if not isinstance(pitch, str):
        return float(pitch)
    semis = SEMITONE[pitch[0]] + pitch.count("#") - pitch.count("b")
    octave = int(pitch.lstrip("ABCDEFG#b"))
    return 440.0 * 2.0 ** ((semis + 12 * (octave - 4)) / 12)


def cycle_integral(shape: str, x: float, duty: float) -> float:
    """Integral over [0, x) of one zero-mean cycle of the wave, x in [0, 1)."""
    if shape == "pulse":  # high for `duty` of the cycle; levels keep the mean at 0
        high, low = 2.0 * (1.0 - duty), -2.0 * duty
        return x * high if x < duty else duty * high + (x - duty) * low
    if shape == "saw":  # +1 falling to -1
        return x - x * x
    if shape == "triangle":  # 0 up to +1, down to -1, back to 0
        if x < 0.25:
            return 2.0 * x * x
        if x < 0.75:
            return 2.0 * x - 2.0 * x * x - 0.25
        return 2.0 * (1.0 - x) ** 2
    raise ValueError(f"unknown wave shape {shape!r}")


def box_sample(shape: str, phase: float, step: float, duty: float) -> float:
    """Mean of the wave over [phase, phase + step): one anti-aliased sample."""
    start = cycle_integral(shape, phase % 1.0, duty)
    end = cycle_integral(shape, (phase + step) % 1.0, duty)
    return (end - start) / step  # whole cycles integrate to zero


class Lfsr:
    """Game Boy noise: 15-bit LFSR, taps on bits 0 and 1."""

    def __init__(self) -> None:
        self.state = NOISE_SEED

    def clock(self) -> None:
        bit = (self.state ^ (self.state >> 1)) & 1
        self.state = (self.state >> 1) | (bit << 14)

    def value(self) -> float:
        return -1.0 if self.state & 1 else 1.0


def ms_to_samples(ms: float) -> int:
    return round(ms * SAMPLE_RATE / 1000)


def tone(
    buf: list[float],
    at: float,
    length: float,
    pitch: str | float,
    *,
    shape: str = "pulse",
    duty: float = 0.5,
    amp: float = 1.0,
    to: str | float | None = None,
    glide: float | None = None,
    bend_at: float = 0.0,
    curve: str = "exp",
    attack: float = 2.0,
    hold: float = 0.0,
    decay: float | None = None,
    release: float = 4.0,
    vibrato: tuple[float, float, float] | None = None,
    tremolo: tuple[float, float, float] | None = None,
    arp: tuple[int, ...] = (0,),
    arp_hz: float = 64.0,
    cents: float = 0.0,
) -> None:
    """Mix one note into buf. `at` is ms from the effect start; other times
    are ms from the note start.

    shape    "pulse" (duty = high fraction), "saw", "triangle", or "noise"
             (pitch is then the LFSR clock in Hz)
    to       glide target. curve "exp" moves at a constant semitone rate over
             `glide` ms (default: rest of the note) starting at `bend_at`;
             "drop" approaches the target with time constant `glide` ms
    attack   linear rise, then `hold` ms at full level, then exponential decay
             with time constant `decay` ms (None = sustain), and finally a
             `release` ms linear fade that ends exactly on zero
    vibrato  (rate Hz, depth semitones, delay ms)
    tremolo  (rate Hz, depth 0-1, fade ms): amplitude flutter that fades out
    arp      semitone offsets stepped through at arp_hz steps per second
    """
    start, count = ms_to_samples(at), ms_to_samples(length)
    if start + count > len(buf) - BLOCK:
        raise ValueError("note runs into the final silent block")
    f0 = hz(pitch)
    f1 = hz(to) if to is not None else f0
    glide = length - bend_at if glide is None else glide
    attack_n = max(1, ms_to_samples(attack))
    hold_n = ms_to_samples(hold)
    release_n = max(1, ms_to_samples(release))
    decay_n = None if decay is None else decay * SAMPLE_RATE / 1000
    lfsr = Lfsr() if shape == "noise" else None
    phase = 0.0

    for i in range(count):
        t = i * 1000.0 / SAMPLE_RATE
        freq = f0
        if f1 != f0 and t > bend_at:
            if curve == "drop":
                freq = f1 * (f0 / f1) ** math.exp(-(t - bend_at) / glide)
            else:
                freq = f0 * (f1 / f0) ** min(1.0, (t - bend_at) / glide)
        semis = arp[int(t * arp_hz / 1000) % len(arp)] + cents / 100
        if vibrato and t > vibrato[2]:
            rate, depth, delay = vibrato
            fade_in = min(1.0, (t - delay) / 60.0)
            semis += depth * fade_in * math.sin(2 * math.pi * rate * (t - delay) / 1000)
        freq *= 2.0 ** (semis / 12)

        if lfsr is not None:
            phase += freq / SAMPLE_RATE
            while phase >= 1.0:
                lfsr.clock()
                phase -= 1.0
            value = lfsr.value()
        else:
            step = freq * TUNE / SAMPLE_RATE
            value = box_sample(shape, phase, step, duty)
            phase += step

        if i < attack_n:
            env = i / attack_n
        elif decay_n is not None and i >= attack_n + hold_n:
            env = math.exp(-(i - attack_n - hold_n) / decay_n)
        else:
            env = 1.0
        if tremolo and t < tremolo[2]:
            rate, depth, fade = tremolo
            dip = 0.5 - 0.5 * math.cos(2 * math.pi * rate * t / 1000)
            env *= 1.0 - depth * (1.0 - t / fade) * dip
        left = count - 1 - i
        if left < release_n:
            env *= left / release_n
        buf[start + i] += amp * env * value


EFFECTS: list[tuple[str, str, str, int, object]] = []


def effect(stem: str, name: str, sound_id: str, length_ms: int):
    def register(build):
        EFFECTS.append((stem, name, sound_id, length_ms, build))
        return build

    return register


@effect("sfx_rotate", "Rotate", "7d2e9c41-5a3b-4c8d-9e1f-0a6b2c3d4e01", 56)
def rotate(buf: list[float]) -> None:
    # very frequent, so thin and short: flicks up a fourth and is gone
    tone(buf, 0, 52, "B5", to="E6", glide=12, duty=0.25, attack=1, hold=8, decay=14, release=8)


@effect("sfx_lock", "Lock", "7d2e9c41-5a3b-4c8d-9e1f-0a6b2c3d4e02", 80)
def lock(buf: list[float]) -> None:
    # very frequent, so soft: a triangle whose pitch drops fast (the knock)
    # and settles low, with a few milliseconds of noise for the click
    tone(buf, 0, 76, "E5", to="E3", curve="drop", glide=9, shape="triangle",
         attack=0.5, decay=24, release=12)
    tone(buf, 0, 6, 3000, shape="noise", amp=0.35, attack=0.25, decay=1.5, release=2)


@effect("sfx_line", "Line Clear", "7d2e9c41-5a3b-4c8d-9e1f-0a6b2c3d4e03", 352)
def line(buf: list[float]) -> None:
    # two octaves up in a fifth of a second, fluttering on the way, then rings
    tone(buf, 0, 348, "E4", to="E6", glide=192, attack=2, hold=220, decay=36, release=24,
         tremolo=(32, 0.4, 192))


@effect("sfx_abetris", "Abetris", "7d2e9c41-5a3b-4c8d-9e1f-0a6b2c3d4e04", 1100)
def abetris(buf: list[float]) -> None:
    # i - VI - VII - i as rising saw arpeggios ("ta-ta-taa" each) whose top
    # notes climb E5 F5 G5 to A5, which rings as a shimmering A/E open fifth
    pluck = dict(shape="saw", decay=120, release=6)
    for at, chord in ((0, ("A4", "C5", "E5")), (192, ("A4", "C5", "F5")), (384, ("B4", "D5", "G5"))):
        for k, note in enumerate(chord):
            tone(buf, at + 48 * k, 96 if k == 2 else 48, note, **pluck)
    tone(buf, 576, 48, "C5", **pluck)
    tone(buf, 624, 48, "E5", **pluck)
    tone(buf, 672, 424, "A5", arp=(0, 7), amp=0.75, hold=60, decay=220, release=60)


@effect("sfx_levelup", "Level Up", "7d2e9c41-5a3b-4c8d-9e1f-0a6b2c3d4e05", 512)
def levelup(buf: list[float]) -> None:
    # A-minor triads rolling upward, each a chord tone higher than the last
    notes = ("A4", "C5", "E5", "C5", "E5", "A5", "E5", "A5", "C6", "A5", "C6")
    for k, note in enumerate(notes):
        tone(buf, 36 * k, 36, note, attack=1, decay=45, release=4)
    tone(buf, 396, 112, "E6", attack=1, hold=20, decay=40, release=24)


@effect("sfx_gameover", "Game Over", "7d2e9c41-5a3b-4c8d-9e1f-0a6b2c3d4e06", 1440)
def gameover(buf: list[float]) -> None:
    # two falling sighs down the scale, then the tonic sags away a fourth
    sigh = dict(vibrato=(5.5, 0.18, 90), decay=500, release=18)
    tone(buf, 0, 120, "E5", amp=0.85, release=14)
    tone(buf, 120, 240, "D5", **sigh)
    tone(buf, 360, 120, "C5", amp=0.85, release=14)
    tone(buf, 480, 240, "B4", **sigh)
    tone(buf, 720, 716, "A4", to="E4", bend_at=300, glide=380, vibrato=(5, 0.25, 140),
         decay=900, release=140)


@effect("sfx_pause", "Pause", "7d2e9c41-5a3b-4c8d-9e1f-0a6b2c3d4e07", 128)
def pause(buf: list[float]) -> None:
    # neutral "bip-bop", the same for pausing and resuming
    tone(buf, 0, 56, "E6", attack=1, hold=16, decay=24, release=6)
    tone(buf, 60, 60, "B5", attack=1, hold=16, decay=24, release=6)


@effect("sfx_start", "Start", "7d2e9c41-5a3b-4c8d-9e1f-0a6b2c3d4e08", 400)
def start(buf: list[float]) -> None:
    # E5-A5 pickup into a ringing E6; a faint, slightly sharp second E6 beats
    # slowly against it so the ring shimmers like a chime (kept faint so the
    # beat only dips the ring and never gaps it)
    tone(buf, 0, 48, "E5", attack=1, decay=60, release=4)
    tone(buf, 48, 48, "A5", attack=1, decay=60, release=4)
    for cents, amp in ((0, 0.8), (6, 0.2)):
        tone(buf, 96, 300, "E6", cents=cents, amp=amp, attack=1, decay=110, release=30)


def render(length_ms: int, build) -> bytes:
    count = ms_to_samples(length_ms)
    if count % BLOCK:
        raise ValueError(f"{length_ms} ms is not a whole number of {BLOCK}-sample blocks")
    buf = [0.0] * count
    build(buf)
    peak = max(abs(x) for x in buf)
    levels = [SILENCE + math.floor(SWING * x / peak + 0.5) for x in buf]
    assert 1 <= min(levels) and max(levels) <= 15
    assert levels[0] == SILENCE and set(levels[-BLOCK:]) == {SILENCE}
    return bytes(level * 16 for level in levels)


def sidecar(stem: str, name: str, sound_id: str) -> str:
    # same keys, order and formatting GB Studio writes (no trailing newline)
    return json.dumps(
        {
            "_resourceType": "sound",
            "id": sound_id,
            "name": name,
            "symbol": f"sound_{stem}",
            "type": "wav",
            "filename": f"{stem}.wav",
        },
        indent=2,
    )


def main() -> None:
    SOUNDS.mkdir(parents=True, exist_ok=True)
    for stem, name, sound_id, length_ms, build in EFFECTS:
        data = render(length_ms, build)
        with wave.open(str(SOUNDS / f"{stem}.wav"), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(1)
            w.setframerate(SAMPLE_RATE)
            w.writeframes(data)
        (SOUNDS / f"{stem}.wav.gbsres").write_bytes(sidecar(stem, name, sound_id).encode())
        print(f"{stem:<13} {length_ms:>5} ms {len(data):>6} frames  bytes {min(data):>3}-{max(data)}")


if __name__ == "__main__":
    main()
