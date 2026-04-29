"""
Analysis tools — music theory computations that run entirely in Python.

These tools do NOT require a WebSocket connection because they operate
on data already known to the model (MIDI pitches, note names, etc.).
They are pure music-theory engines designed to help Claude reason about
scores produced with the other tools.

Primary use-case: automated generation of Liceu harmony exam exercises
(interval identification, chord labelling, roman-numeral analysis).
"""

from typing import List, Optional
from mcp.server.fastmcp import FastMCP


# ---------------------------------------------------------------------------
# Core music theory tables
# ---------------------------------------------------------------------------

# Pitch class → note name (using sharps by default)
_PC_TO_NAME_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_PC_TO_NAME_FLAT  = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]

# Note name → pitch class
_NAME_TO_PC = {
    "C":0,"C#":1,"Db":1,"D":2,"D#":3,"Eb":3,
    "E":4,"F":5,"F#":6,"Gb":6,"G":7,"G#":8,
    "Ab":8,"A":9,"A#":10,"Bb":10,"B":11,
}

# Interval quality / name by semitone distance (within one octave)
_INTERVAL_NAMES = {
    0:  ("P1",  "Unison"),
    1:  ("m2",  "Minor 2nd"),
    2:  ("M2",  "Major 2nd"),
    3:  ("m3",  "Minor 3rd"),
    4:  ("M3",  "Major 3rd"),
    5:  ("P4",  "Perfect 4th"),
    6:  ("A4",  "Augmented 4th / Diminished 5th (Tritone)"),
    7:  ("P5",  "Perfect 5th"),
    8:  ("m6",  "Minor 6th"),
    9:  ("M6",  "Major 6th"),
    10: ("m7",  "Minor 7th"),
    11: ("M7",  "Major 7th"),
    12: ("P8",  "Octave"),
    13: ("m9",  "Minor 9th"),
    14: ("M9",  "Major 9th"),
    15: ("A9",  "Augmented 9th"),
    17: ("P11", "Perfect 11th"),
    18: ("A11", "Augmented 11th"),
    21: ("M13", "Major 13th"),
}

# Chord types: semitone intervals → (chord suffix, full name)
# Sorted from most specific (longer) to least specific for best matching
_CHORD_PATTERNS: list[tuple[tuple[int,...], str, str]] = [
    # 7th chords + extensions (check before triads)
    ((0,4,7,11,14),   "maj9",  "Major 9th"),
    ((0,3,7,10,14),   "m9",    "Minor 9th"),
    ((0,4,7,10,14),   "9",     "Dominant 9th"),
    ((0,4,7,11),      "maj7",  "Major 7th"),
    ((0,3,7,11),      "mM7",   "Minor-Major 7th"),
    ((0,4,7,10),      "7",     "Dominant 7th"),
    ((0,3,7,10),      "m7",    "Minor 7th"),
    ((0,3,6,10),      "m7b5",  "Half-Diminished 7th"),
    ((0,3,6,9),       "dim7",  "Diminished 7th"),
    ((0,4,8,10),      "+7",    "Augmented 7th"),
    ((0,4,8,11),      "+M7",   "Augmented Major 7th"),
    # Add-chords
    ((0,4,7,14),      "add9",  "Add 9"),
    ((0,3,7,14),      "madd9", "Minor Add 9"),
    ((0,4,7,9),       "6",     "Major 6th"),
    ((0,3,7,9),       "m6",    "Minor 6th"),
    # Triads
    ((0,4,7),         "",      "Major"),
    ((0,3,7),         "m",     "Minor"),
    ((0,3,6),         "dim",   "Diminished"),
    ((0,4,8),         "+",     "Augmented"),
    # Suspended
    ((0,5,7),         "sus4",  "Suspended 4th"),
    ((0,2,7),         "sus2",  "Suspended 2nd"),
    # Dyads / power chords
    ((0,7),           "5",     "Power chord"),
]

# Key scale degrees (major scale)
_MAJOR_SCALE_SEMITONES = [0, 2, 4, 5, 7, 9, 11]

# Roman numeral labels (0-based scale degree → roman numeral)
_ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII"]


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------

def _pitch_to_name(midi: int, prefer_flats: bool = False) -> str:
    """Convert a MIDI pitch to a note name with octave, e.g. 60 → 'C4'."""
    names = _PC_TO_NAME_FLAT if prefer_flats else _PC_TO_NAME_SHARP
    pc = midi % 12
    octave = (midi // 12) - 1
    return f"{names[pc]}{octave}"


def _normalise_intervals(pitches: list[int]) -> tuple[int, ...]:
    """
    Given a list of MIDI pitches, return the sorted set of unique
    semitone intervals relative to the lowest pitch, reduced to ≤ 1 octave.
    """
    if not pitches:
        return ()
    root = min(pitches)
    intervals = sorted({(p - root) % 12 for p in pitches})
    return tuple(intervals)


def _identify_chord(pitches: list[int]) -> tuple[str, str, str]:
    """
    Identify a chord from a list of MIDI pitches.

    Returns: (root_name, suffix, full_name)
    """
    if not pitches:
        return ("?", "?", "Unknown (no pitches)")

    # Try every pitch as potential root
    best: tuple[str, str, str] | None = None

    for root_midi in sorted(set(pitches)):
        shifted = sorted({(p - root_midi) % 12 for p in pitches})
        pattern = tuple(shifted)

        for chord_pattern, suffix, name in _CHORD_PATTERNS:
            if pattern == chord_pattern:
                root_name = _PC_TO_NAME_SHARP[root_midi % 12]
                best = (root_name, suffix, name)
                break
        if best is not None:
            break

    if best is None:
        root_name = _PC_TO_NAME_SHARP[min(pitches) % 12]
        intervals_str = str(_normalise_intervals(pitches))
        return (root_name, "?", f"Unknown chord — intervals: {intervals_str}")

    return best


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

def setup_analysis_tools(mcp: FastMCP, _client=None) -> None:
    """Register analysis tools.  No WebSocket client required."""

    # ── Intervals ─────────────────────────────────────────────────────────────

    @mcp.tool()
    async def analyze_interval(pitch1: int, pitch2: int) -> str:
        """
        Compute the interval between two MIDI pitches.

        Returns the abbreviated name (e.g. "M3"), the full name
        ("Major 3rd"), the semitone distance, and whether the interval
        is ascending or descending.

        Args:
            pitch1: Lower or first MIDI pitch (e.g. 60 = C4).
            pitch2: Upper or second MIDI pitch (e.g. 64 = E4).

        Examples:
            analyze_interval(60, 64)  → "M3 — Major 3rd (ascending, 4 semitones)"
            analyze_interval(60, 55)  → "P4 — Perfect 4th (descending, 5 semitones)"
        """
        semitones = abs(pitch2 - pitch1)
        direction = "ascending" if pitch2 >= pitch1 else "descending"
        compound = ""

        if semitones > 12:
            octaves = semitones // 12
            remainder = semitones % 12
            compound = f"  [{octaves} octave(s) + "
            if remainder in _INTERVAL_NAMES:
                short, long_ = _INTERVAL_NAMES[remainder]
                compound += f"{short} / {long_}]"
            else:
                compound += f"{remainder} semitones]"

        if semitones in _INTERVAL_NAMES:
            short, long_ = _INTERVAL_NAMES[semitones]
        else:
            short = f"{semitones}st"
            long_ = f"{semitones} semitones"

        n1 = _pitch_to_name(pitch1)
        n2 = _pitch_to_name(pitch2)

        return (
            f"{short} — {long_}\n"
            f"  Notes:     {n1} → {n2}\n"
            f"  Direction: {direction}\n"
            f"  Semitones: {semitones}"
            f"{compound}"
        )

    @mcp.tool()
    async def get_interval_name(semitones: int) -> str:
        """
        Return the interval name for a given number of semitones.

        Args:
            semitones: Number of semitones (0–21+).

        Example:
            get_interval_name(7)  → "P5 — Perfect 5th"
        """
        if semitones in _INTERVAL_NAMES:
            short, long_ = _INTERVAL_NAMES[semitones]
            return f"{short} — {long_}  ({semitones} semitones)"
        # Compound intervals
        octaves = semitones // 12
        rem = semitones % 12
        base = _INTERVAL_NAMES.get(rem, (f"{rem}st", f"{rem} semitones above octave"))
        return f"Compound: {octaves} octave(s) + {base[0]} ({base[1]})  [{semitones} semitones]"

    @mcp.tool()
    async def get_interval_reference() -> str:
        """Return a reference table of all simple intervals (unison through 13th)."""
        lines = ["Interval reference (semitones → symbol — name):"]
        for st in range(22):
            if st in _INTERVAL_NAMES:
                short, long_ = _INTERVAL_NAMES[st]
                lines.append(f"  {st:>2} semitones  {short:<5} {long_}")
        return "\n".join(lines)

    # ── Chord identification ───────────────────────────────────────────────────

    @mcp.tool()
    async def identify_chord(pitches: List[int]) -> str:
        """
        Identify a chord from a list of MIDI pitches.

        Works for triads, seventh chords, added-note chords, and power chords.
        Does not require the score to be open.

        Args:
            pitches: List of MIDI note numbers, e.g. [60, 64, 67] = C major.

        Returns:
            Chord name, root, quality, and the note names in the chord.

        Examples:
            identify_chord([60, 64, 67])         → "C  (Major)"
            identify_chord([57, 60, 64, 67])      → "Am7  (Minor 7th)"
            identify_chord([55, 59, 62, 65])      → "G7  (Dominant 7th)"
            identify_chord([60, 64, 67, 71, 74])  → "Cmaj9  (Major 9th)"
        """
        if not pitches:
            return "No pitches provided."

        root, suffix, quality = _identify_chord(pitches)
        note_names = [_pitch_to_name(p) for p in sorted(pitches)]

        return (
            f"Chord:   {root}{suffix}  ({quality})\n"
            f"Root:    {root}\n"
            f"Quality: {quality}\n"
            f"Notes:   {', '.join(note_names)}"
        )

    @mcp.tool()
    async def get_chord_reference() -> str:
        """Return a reference table of all supported chord patterns."""
        lines = ["Chord reference (intervals from root → symbol — name):"]
        for pattern, suffix, name in _CHORD_PATTERNS:
            intervals_str = ", ".join(str(i) for i in pattern)
            lines.append(f"  [{intervals_str}]  →  X{suffix:<8}  {name}")
        return "\n".join(lines)

    # ── Roman numeral / harmonic function ─────────────────────────────────────

    @mcp.tool()
    async def get_roman_numeral(chord_name: str, key: str) -> str:
        """
        Return the Roman-numeral function of a chord within a major key.

        Args:
            chord_name: Chord root + optional quality, e.g. "G7", "Am", "Bdim".
            key:        Root of the major key, e.g. "C", "G", "Bb".

        Examples:
            get_roman_numeral("G7", "C")   → "V7  (Dominant 7th)"
            get_roman_numeral("Am",  "C")  → "vi  (Minor triad)"
            get_roman_numeral("F",   "C")  → "IV  (Major triad)"
        """
        # Identify root from chord_name
        root_name: str | None = None
        for candidate in ["C#","Db","D#","Eb","F#","Gb","G#","Ab","A#","Bb","C","D","E","F","G","A","B"]:
            if chord_name.startswith(candidate):
                root_name = candidate
                break
        if root_name is None:
            return f"Cannot parse root from chord name '{chord_name}'."

        suffix = chord_name[len(root_name):]

        if key not in _NAME_TO_PC:
            return f"Unknown key '{key}'. Use a note name like C, G, Bb, F#, etc."

        key_pc  = _NAME_TO_PC[key]
        root_pc = _NAME_TO_PC.get(root_name)
        if root_pc is None:
            return f"Unknown root '{root_name}'."

        degree_semitones = (root_pc - key_pc) % 12

        # Find which scale degree
        if degree_semitones in _MAJOR_SCALE_SEMITONES:
            idx = _MAJOR_SCALE_SEMITONES.index(degree_semitones)
            numeral = _ROMAN[idx]
            # Quality determines case
            is_minor = suffix.startswith(("m", "dim", "ø", "°"))
            if is_minor:
                numeral = numeral.lower()
        else:
            # Chromatic / secondary dominant
            numeral = f"#{_ROMAN[degree_semitones // 2]}" if degree_semitones % 2 else _ROMAN[degree_semitones // 2]

        quality_map = {
            "": "Major triad", "m": "Minor triad", "dim": "Diminished triad",
            "+": "Augmented triad", "7": "Dominant 7th", "maj7": "Major 7th",
            "m7": "Minor 7th", "dim7": "Diminished 7th", "m7b5": "Half-diminished",
        }
        quality = quality_map.get(suffix, suffix or "Major triad")

        return f"{numeral}{suffix}  in {key} major  —  {quality}"

    # ── Scale detection ───────────────────────────────────────────────────────

    @mcp.tool()
    async def detect_scale(pitches: List[int]) -> str:
        """
        Detect the most likely scale from a collection of MIDI pitches.

        Compares the pitch-class content against all 12 transpositions of
        common scales and ranks matches.

        Args:
            pitches: List of MIDI pitches from a melody or passage.

        Returns:
            Ranked list of matching scales (best match first).
        """
        if not pitches:
            return "No pitches provided."

        input_pcs = {p % 12 for p in pitches}

        scales = {
            "Major (Ionian)":    [0,2,4,5,7,9,11],
            "Natural Minor":     [0,2,3,5,7,8,10],
            "Harmonic Minor":    [0,2,3,5,7,8,11],
            "Melodic Minor":     [0,2,3,5,7,9,11],
            "Dorian":            [0,2,3,5,7,9,10],
            "Phrygian":          [0,1,3,5,7,8,10],
            "Lydian":            [0,2,4,6,7,9,11],
            "Mixolydian":        [0,2,4,5,7,9,10],
            "Locrian":           [0,1,3,5,6,8,10],
            "Blues":             [0,3,5,6,7,10],
            "Pentatonic Major":  [0,2,4,7,9],
            "Pentatonic Minor":  [0,3,5,7,10],
            "Whole Tone":        [0,2,4,6,8,10],
            "Diminished (HW)":   [0,1,3,4,6,7,9,10],
        }

        note_names = _PC_TO_NAME_SHARP

        matches = []
        for scale_name, intervals in scales.items():
            for root_pc in range(12):
                scale_pcs = {(root_pc + i) % 12 for i in intervals}
                if input_pcs.issubset(scale_pcs):
                    coverage = len(input_pcs) / len(scale_pcs)
                    matches.append((coverage, note_names[root_pc], scale_name))

        if not matches:
            return "No standard scale matches all the given pitches."

        matches.sort(reverse=True, key=lambda x: x[0])
        lines = [f"Scale detection — input pitch classes: {sorted(input_pcs)}\n"]
        lines.append("Best matches:")
        for coverage, root, name in matches[:8]:
            lines.append(f"  {root} {name:<22}  (covers {coverage*100:.0f}% of scale)")

        return "\n".join(lines)

    # ── Pitch utilities ────────────────────────────────────────────────────────

    @mcp.tool()
    async def midi_to_note_name(pitch: int, prefer_flats: bool = False) -> str:
        """
        Convert a MIDI pitch number to a human-readable note name.

        Args:
            pitch:        MIDI pitch (0–127).  Middle C = 60.
            prefer_flats: If True, use flat names (Bb, Eb) instead of
                          sharp names (A#, D#).

        Examples:
            midi_to_note_name(60)           → "C4"
            midi_to_note_name(70, True)     → "Bb4"
            midi_to_note_name(69)           → "A4  (440 Hz)"
        """
        if not 0 <= pitch <= 127:
            return f"Invalid MIDI pitch {pitch}. Must be 0–127."
        name = _pitch_to_name(pitch, prefer_flats)
        freq = 440.0 * (2 ** ((pitch - 69) / 12))
        return f"{name}  ({freq:.2f} Hz)"

    @mcp.tool()
    async def note_name_to_midi(note_name: str) -> str:
        """
        Convert a note name with octave to its MIDI pitch number.

        Args:
            note_name: Note name + octave, e.g. "C4", "A4", "F#3", "Bb5".

        Examples:
            note_name_to_midi("C4")   → 60
            note_name_to_midi("A4")   → 69
            note_name_to_midi("Bb3")  → 58
        """
        # Strip octave number
        for i in range(len(note_name) - 1, -1, -1):
            if note_name[i].lstrip("-").isdigit():
                octave_str = note_name[i:]
                root = note_name[:i]
                break
        else:
            return f"Cannot parse octave from '{note_name}'. Use format like 'C4' or 'F#3'."

        if root not in _NAME_TO_PC:
            return f"Unknown note name '{root}'."
        try:
            octave = int(octave_str)
        except ValueError:
            return f"Cannot parse octave '{octave_str}' as an integer."

        midi = 12 * (octave + 1) + _NAME_TO_PC[root]
        if not 0 <= midi <= 127:
            return f"Resulting MIDI pitch {midi} is out of range (0–127)."
        return f"{note_name}  →  MIDI {midi}"
