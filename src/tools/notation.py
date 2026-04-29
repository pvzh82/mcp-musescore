"""
Notation tools — read and write score notation elements:
clef, key signature, accidentals, and detailed note inspection.

These tools rely on the WebSocket plugin for write operations and for
reading data that is only available inside the live MuseScore process.
"""

from typing import Optional
from mcp.server.fastmcp import FastMCP
from src.client import MuseScoreClient


# ---------------------------------------------------------------------------
# Reference data (pure Python — no WebSocket needed)
# ---------------------------------------------------------------------------

# Clef names as accepted by the MuseScore plugin API
CLEF_TYPES = {
    "treble":       "TREBLE",          # Standard G clef (line 2)
    "treble8vb":    "TREBLE8_VB",      # Treble clef 8va bassa (guitar, tenor voice)
    "treble8va":    "TREBLE8_VA",      # Treble clef 8va alta
    "bass":         "BASS",            # Standard F clef (line 4)
    "bass8vb":      "BASS8_VB",        # Bass clef 8va bassa (contrabass)
    "alto":         "ALTO",            # C clef on line 3 (viola)
    "tenor":        "TENOR",           # C clef on line 4 (cello upper range)
    "soprano":      "SOPRANO",         # C clef on line 1
    "mezzo_soprano":"MEZZO_SOPRANO",   # C clef on line 2
    "baritone_c":   "BARITONE_C",      # C clef on line 5
    "baritone_f":   "BARITONE_F",      # F clef on line 3
    "percussion":   "PERCUSSION",
    "tab":          "TAB",             # Guitar tablature
    "tab_small":    "TAB_SMALL",
}

# Key signatures: sharps (+) and flats (-) as semitone pitch classes of key roots
KEY_SIGNATURES = {
    "C":  0,   # 0 sharps/flats
    "G":  1,   # 1 sharp
    "D":  2,   # 2 sharps
    "A":  3,   # 3 sharps
    "E":  4,   # 4 sharps
    "B":  5,   # 5 sharps
    "F#": 6,   # 6 sharps
    "C#": 7,   # 7 sharps
    "F": -1,   # 1 flat
    "Bb": -2,  # 2 flats
    "Eb": -3,  # 3 flats
    "Ab": -4,  # 4 flats
    "Db": -5,  # 5 flats
    "Gb": -6,  # 6 flats
    "Cb": -7,  # 7 flats
}

# Accidental type strings accepted by the plugin
ACCIDENTAL_TYPES = {
    "sharp":         "SHARP",
    "flat":          "FLAT",
    "natural":       "NATURAL",
    "double_sharp":  "SHARP2",
    "double_flat":   "FLAT2",
    "sharp_flat":    "SHARP_SLASH",   # Quarter-tone sharp
    "flat_arrow":    "FLAT_ARROW_UP", # Quarter-tone flat
}


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

def setup_notation_tools(mcp: FastMCP, client: MuseScoreClient) -> None:

    def _guard() -> Optional[str]:
        if not client.is_connected():
            return "Not connected to MuseScore. Call connect_to_musescore() first."
        return None

    # ── Clef ─────────────────────────────────────────────────────────────────

    @mcp.tool()
    async def set_clef(clef_type: str) -> str:
        """
        Change the clef at the current cursor position.

        Args:
            clef_type: One of the supported clef names (case-insensitive):
                       treble, treble8vb, treble8va, bass, bass8vb,
                       alto, tenor, soprano, mezzo_soprano,
                       baritone_c, baritone_f, percussion, tab.

        Example:
            set_clef("bass")   # Switch to bass clef
            set_clef("alto")   # Switch to alto clef (for viola)
        """
        if err := _guard(): return err

        key = clef_type.lower().replace(" ", "_")
        if key not in CLEF_TYPES:
            available = ", ".join(sorted(CLEF_TYPES.keys()))
            return f"Unknown clef '{clef_type}'. Available: {available}"

        return await client.send_command({
            "action": "setClef",
            "params": {"clefType": CLEF_TYPES[key]},
        })

    @mcp.tool()
    async def list_clef_types() -> str:
        """Return all supported clef type names and their MuseScore identifiers."""
        lines = ["Supported clefs (use the left-hand name in set_clef):"]
        for name, ms_id in sorted(CLEF_TYPES.items()):
            lines.append(f"  {name:<18} → {ms_id}")
        return "\n".join(lines)

    # ── Key signature ─────────────────────────────────────────────────────────

    @mcp.tool()
    async def set_key_signature(key: str) -> str:
        """
        Set the key signature at the current cursor position.

        Args:
            key: Root note of the key (major implied), e.g. "C", "G", "F",
                 "Bb", "D", "Eb", "A", "Ab", "E", "Db", "B", "Gb",
                 "F#", "C#", "Cb".

        Example:
            set_key_signature("G")   # 1 sharp (G major / E minor)
            set_key_signature("Bb")  # 2 flats  (Bb major / G minor)
        """
        if err := _guard(): return err

        if key not in KEY_SIGNATURES:
            available = ", ".join(sorted(KEY_SIGNATURES.keys()))
            return f"Unknown key '{key}'. Supported: {available}"

        accidentals = KEY_SIGNATURES[key]
        return await client.send_command({
            "action": "setKeySignature",
            "params": {"key": key, "accidentals": accidentals},
        })

    @mcp.tool()
    async def list_key_signatures() -> str:
        """Return all supported key signatures with their accidental counts."""
        sharps = [(k, v) for k, v in KEY_SIGNATURES.items() if v >= 0]
        flats  = [(k, v) for k, v in KEY_SIGNATURES.items() if v < 0]

        sharps.sort(key=lambda x: x[1])
        flats.sort(key=lambda x: x[1])

        lines = ["Key signatures — sharps:"]
        for k, v in sharps:
            lines.append(f"  {k:<4} ({v} sharp{'s' if v != 1 else ''})")

        lines.append("\nKey signatures — flats:")
        for k, v in flats:
            lines.append(f"  {k:<4} ({abs(v)} flat{'s' if abs(v) != 1 else ''})")

        return "\n".join(lines)

    # ── Note inspection ───────────────────────────────────────────────────────

    @mcp.tool()
    async def get_note_at_cursor() -> str:
        """
        Return detailed information about the note or chord at the cursor.

        Response includes: MIDI pitch(es), note name(s), octave, duration,
        accidentals, voice, beam group, and any attached dynamics or lyrics.
        """
        if err := _guard(): return err
        return await client.send_command({"action": "getNoteAtCursor", "params": {}})

    @mcp.tool()
    async def read_measures(start_measure: int, end_measure: int) -> str:
        """
        Read all notes and rests from a range of measures as structured data.

        Returns a JSON-serialisable list of events per beat, useful for
        analysis or for feeding into the Analysis tools below.

        Args:
            start_measure: First measure to read (1-based, inclusive).
            end_measure:   Last measure to read (1-based, inclusive).

        Example:
            read_measures(1, 4)  # Read the first 4 measures
        """
        if err := _guard(): return err

        if start_measure < 1:
            return "start_measure must be ≥ 1."
        if end_measure < start_measure:
            return "end_measure must be ≥ start_measure."

        return await client.send_command({
            "action": "readMeasures",
            "params": {
                "startMeasure": start_measure,
                "endMeasure":   end_measure,
            },
        })

    # ── Accidentals ───────────────────────────────────────────────────────────

    @mcp.tool()
    async def add_accidental(accidental_type: str) -> str:
        """
        Add or force an accidental on the note at the current cursor.

        This overrides the key-signature default (e.g. force a natural sign
        or add a cautionary accidental).

        Args:
            accidental_type: One of: sharp, flat, natural, double_sharp,
                             double_flat, sharp_flat, flat_arrow.
        """
        if err := _guard(): return err

        key = accidental_type.lower()
        if key not in ACCIDENTAL_TYPES:
            available = ", ".join(sorted(ACCIDENTAL_TYPES.keys()))
            return f"Unknown accidental '{accidental_type}'. Available: {available}"

        return await client.send_command({
            "action": "addAccidental",
            "params": {"accidentalType": ACCIDENTAL_TYPES[key]},
        })
