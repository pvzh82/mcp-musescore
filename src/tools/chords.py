"""
Chord tools for the MuseScore MCP server.

Provides three levels of abstraction:
  1. add_chord()             – raw MIDI pitches
  2. add_chord_by_name()     – chord name string ("Cmaj7", "Am", "G7", …)
  3. add_chord_symbol()      – text harmony symbol above the staff
  4. add_chord_with_symbol() – notes + symbol in one call
"""

from typing import List, Dict
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Music theory helpers
# ---------------------------------------------------------------------------

# Semitone offsets from the root for each chord quality
CHORD_TYPES: Dict[str, List[int]] = {
    # Triads
    "major":            [0, 4, 7],
    "minor":            [0, 3, 7],
    "diminished":       [0, 3, 6],
    "augmented":        [0, 4, 8],
    # Suspended
    "sus2":             [0, 2, 7],
    "sus4":             [0, 5, 7],
    # 6th chords
    "major6":           [0, 4, 7, 9],
    "minor6":           [0, 3, 7, 9],
    # 7th chords
    "major7":           [0, 4, 7, 11],
    "dominant7":        [0, 4, 7, 10],
    "minor7":           [0, 3, 7, 10],
    "minormajor7":      [0, 3, 7, 11],
    "half-diminished7": [0, 3, 6, 10],
    "diminished7":      [0, 3, 6, 9],
    "augmented7":       [0, 4, 8, 10],
    "augmentedmajor7":  [0, 4, 8, 11],
    # Add chords
    "add9":             [0, 4, 7, 14],
    "minoradd9":        [0, 3, 7, 14],
    # 9th chords
    "dominant9":        [0, 4, 7, 10, 14],
    "major9":           [0, 4, 7, 11, 14],
    "minor9":           [0, 3, 7, 10, 14],
    # 11th chords
    "dominant11":       [0, 4, 7, 10, 14, 17],
    "minor11":          [0, 3, 7, 10, 14, 17],
    # 13th chords
    "dominant13":       [0, 4, 7, 10, 14, 17, 21],
}

# Aliases: string suffix → canonical chord type key
_SUFFIX_MAP: Dict[str, str] = {
    "":          "major",
    "M":         "major",
    "maj":       "major",
    "m":         "minor",
    "min":       "minor",
    "dim":       "diminished",
    "°":         "diminished",
    "aug":       "augmented",
    "+":         "augmented",
    "sus2":      "sus2",
    "sus4":      "sus4",
    "sus":       "sus4",
    "6":         "major6",
    "m6":        "minor6",
    "min6":      "minor6",
    "maj7":      "major7",
    "M7":        "major7",
    "7":         "dominant7",
    "dom7":      "dominant7",
    "m7":        "minor7",
    "min7":      "minor7",
    "mM7":       "minormajor7",
    "minMaj7":   "minormajor7",
    "m7b5":      "half-diminished7",
    "ø":         "half-diminished7",
    "ø7":        "half-diminished7",
    "dim7":      "diminished7",
    "°7":        "diminished7",
    "aug7":      "augmented7",
    "+7":        "augmented7",
    "augM7":     "augmentedmajor7",
    "+M7":       "augmentedmajor7",
    "add9":      "add9",
    "madd9":     "minoradd9",
    "9":         "dominant9",
    "maj9":      "major9",
    "m9":        "minor9",
    "min9":      "minor9",
    "11":        "dominant11",
    "m11":       "minor11",
    "13":        "dominant13",
}

# Chromatic note name → semitone (0–11)
_NOTE_TO_PC: Dict[str, int] = {
    "C": 0,  "C#": 1, "Db": 1,
    "D": 2,  "D#": 3, "Eb": 3,
    "E": 4,
    "F": 5,  "F#": 6, "Gb": 6,
    "G": 7,  "G#": 8, "Ab": 8,
    "A": 9,  "A#": 10, "Bb": 10,
    "B": 11,
}


def chord_name_to_pitches(chord_name: str, root_octave: int = 4) -> List[int]:
    """
    Convert a chord name string to a list of MIDI pitches.

    Examples
    --------
    chord_name_to_pitches("C")       → [60, 64, 67]   (C major triad)
    chord_name_to_pitches("Am")      → [57, 60, 64]   (A minor triad)
    chord_name_to_pitches("G7")      → [67, 71, 74, 77]
    chord_name_to_pitches("Cmaj7")   → [60, 64, 67, 71]
    chord_name_to_pitches("F#m7")    → [54, 57, 61, 64]
    chord_name_to_pitches("Bbdim7")  → [58, 61, 64, 67]
    """
    # --- 1. Extract root note (1 or 2 chars) ---
    root_name: str | None = None
    for candidate in ["C#", "Db", "D#", "Eb", "F#", "Gb", "G#", "Ab", "A#", "Bb",
                       "C", "D", "E", "F", "G", "A", "B"]:
        if chord_name.startswith(candidate):
            root_name = candidate
            break
    if root_name is None:
        raise ValueError(f"Cannot identify root note in chord name: '{chord_name}'")

    suffix = chord_name[len(root_name):]

    # --- 2. Identify chord type ---
    chord_type = _SUFFIX_MAP.get(suffix)
    if chord_type is None:
        # Try case-insensitive lookup
        for key, val in _SUFFIX_MAP.items():
            if key.lower() == suffix.lower():
                chord_type = val
                break
    if chord_type is None:
        raise ValueError(
            f"Unknown chord quality '{suffix}' in '{chord_name}'. "
            f"Supported suffixes: {sorted(_SUFFIX_MAP.keys())}"
        )

    # --- 3. Build MIDI pitches ---
    root_midi = 12 * (root_octave + 1) + _NOTE_TO_PC[root_name]
    offsets = CHORD_TYPES[chord_type]
    return [root_midi + offset for offset in offsets]


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------

def setup_chord_tools(mcp: FastMCP, client) -> None:
    """Register chord-related MCP tools onto the FastMCP instance."""

    @mcp.tool()
    async def add_chord(
        pitches: List[int],
        duration: Dict,
        advance_cursor_after_action: bool = True,
    ) -> str:
        """
        Add a chord (multiple simultaneous notes) at the current cursor position.

        Parameters
        ----------
        pitches : list[int]
            MIDI pitch numbers, e.g. [60, 64, 67] for a C-major triad.
            Middle C = 60.  Common values:
              C major  → [60, 64, 67]
              A minor  → [57, 60, 64]
              G7       → [55, 59, 62, 65]
        duration : dict
            {"numerator": int, "denominator": int}
            Examples: whole={"numerator":1,"denominator":1},
                      half={"numerator":1,"denominator":2},
                      quarter={"numerator":1,"denominator":4}
        advance_cursor_after_action : bool
            Move to the next beat after inserting the chord (default True).
        """
        if not client.is_connected():
            return "Not connected to MuseScore. Call connect_to_musescore() first."

        result = await client.send_command({
            "action": "addChord",
            "params": {
                "pitches": pitches,
                "duration": duration,
                "advanceCursorAfterAction": advance_cursor_after_action,
            },
        })
        return result

    @mcp.tool()
    async def add_chord_by_name(
        chord_name: str,
        duration: Dict,
        root_octave: int = 4,
        advance_cursor_after_action: bool = True,
    ) -> str:
        """
        Add a chord by name at the current cursor position.

        The chord name is parsed into MIDI pitches automatically.

        Parameters
        ----------
        chord_name : str
            Standard chord name, e.g.:
              "C"      → C major triad
              "Am"     → A minor triad
              "G7"     → G dominant 7th
              "Cmaj7"  → C major 7th
              "Dm7"    → D minor 7th
              "F#m7b5" → F# half-diminished
              "Bbdim"  → Bb diminished
              "Esus4"  → E suspended 4th
              "Dadd9"  → D add9
              "Ab9"    → Ab dominant 9th
        duration : dict
            {"numerator": int, "denominator": int}
        root_octave : int
            Octave for the root note (default 4 = middle C octave).
            Increase to 5 for a higher voicing, decrease to 3 for bass.
        advance_cursor_after_action : bool
            Move to the next beat after inserting (default True).

        Supported chord suffixes
        ------------------------
        (none)/M/maj   major triad
        m/min          minor triad
        dim/°          diminished triad
        aug/+          augmented triad
        sus2/sus4/sus  suspended
        6/m6           sixth chords
        maj7/M7        major 7th
        7/dom7         dominant 7th
        m7/min7        minor 7th
        mM7            minor-major 7th
        m7b5/ø         half-diminished 7th
        dim7/°7        diminished 7th
        add9/madd9     add9 chords
        9/maj9/m9      ninth chords
        11/m11         eleventh chords
        13             thirteenth chord
        """
        if not client.is_connected():
            return "Not connected to MuseScore. Call connect_to_musescore() first."

        try:
            pitches = chord_name_to_pitches(chord_name, root_octave)
        except ValueError as exc:
            return f"Error parsing chord '{chord_name}': {exc}"

        result = await client.send_command({
            "action": "addChord",
            "params": {
                "pitches": pitches,
                "duration": duration,
                "advanceCursorAfterAction": advance_cursor_after_action,
            },
        })
        return f"Added {chord_name} (MIDI {pitches}): {result}"

    @mcp.tool()
    async def add_chord_symbol(text: str) -> str:
        """
        Add a chord symbol (harmony text) above the staff at the current cursor
        position.  This places a *visual* text label only — it does not add
        sounding notes.  Use add_chord() or add_chord_by_name() for actual notes.

        Parameters
        ----------
        text : str
            Chord symbol, e.g. "C", "Am", "G7", "Cmaj7", "F#m7b5"
        """
        if not client.is_connected():
            return "Not connected to MuseScore. Call connect_to_musescore() first."

        result = await client.send_command({
            "action": "addChordSymbol",
            "params": {"text": text},
        })
        return result

    @mcp.tool()
    async def add_chord_with_symbol(
        chord_name: str,
        duration: Dict,
        root_octave: int = 4,
        advance_cursor_after_action: bool = True,
    ) -> str:
        """
        Convenience tool: adds both the chord *notes* and the chord *symbol text*
        at the current cursor position in a single call.

        Parameters
        ----------
        chord_name : str
            Standard chord name used for both pitch generation and symbol text.
            Same syntax as add_chord_by_name().
        duration : dict
            {"numerator": int, "denominator": int}
        root_octave : int
            Octave for the root note (default 4).
        advance_cursor_after_action : bool
            Move to the next beat after inserting (default True).
        """
        if not client.is_connected():
            return "Not connected to MuseScore. Call connect_to_musescore() first."

        try:
            pitches = chord_name_to_pitches(chord_name, root_octave)
        except ValueError as exc:
            return f"Error parsing chord '{chord_name}': {exc}"

        # 1. Add notes (cursor stays put so we can attach the symbol)
        chord_result = await client.send_command({
            "action": "addChord",
            "params": {
                "pitches": pitches,
                "duration": duration,
                "advanceCursorAfterAction": False,
            },
        })

        # 2. Add chord symbol text at the same position
        symbol_result = await client.send_command({
            "action": "addChordSymbol",
            "params": {"text": chord_name},
        })

        # 3. Advance cursor if requested
        if advance_cursor_after_action:
            await client.send_command({"action": "nextElement", "params": {}})

        return (
            f"Added {chord_name} chord with symbol "
            f"(MIDI {pitches}) — notes: {chord_result} | symbol: {symbol_result}"
        )

    @mcp.tool()
    async def list_chord_types() -> str:
        """
        Return a reference list of all supported chord name suffixes and their
        interval content.  Useful for the AI to know which chord qualities are
        available when composing.
        """
        lines = ["Supported chord types (suffix → intervals from root):"]
        for suffix, canonical in sorted(_SUFFIX_MAP.items()):
            offsets = CHORD_TYPES[canonical]
            lines.append(f"  '{suffix}' ({canonical}): {offsets}")
        return "\n".join(lines)
