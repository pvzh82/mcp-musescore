"""
Rhythm & Tempo tools — tempo markings, dynamics, and expression text.

These tools add notation elements that affect performance interpretation
but do not change the pitch content of the score.
"""

from typing import Optional
from mcp.server.fastmcp import FastMCP
from src.client import MuseScoreClient


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

# Dynamic marks in order of intensity
DYNAMICS = {
    "pppp": "pppp",
    "ppp":  "ppp",
    "pp":   "pp",
    "p":    "p",
    "mp":   "mp",
    "mf":   "mf",
    "f":    "f",
    "ff":   "ff",
    "fff":  "fff",
    "ffff": "ffff",
    "sfz":  "sfz",   # Sforzando
    "sfp":  "sfp",   # Sforzando-piano
    "fp":   "fp",    # Forte-piano
    "rf":   "rf",    # Rinforzando
    "rfz":  "rfz",   # Rinforzando sforzando
    "fz":   "fz",    # Forzando
}

# Common Italian tempo terms
TEMPO_TERMS = {
    "larghissimo":  16,
    "grave":        40,
    "largo":        50,
    "larghetto":    60,
    "adagio":       66,
    "adagietto":    72,
    "andante":      76,
    "andantino":    80,
    "moderato":     96,
    "allegretto":   108,
    "allegro":      120,
    "vivace":       140,
    "presto":       168,
    "prestissimo":  200,
}

# Text direction types
TEXT_DIRECTIONS = {
    "rit":       "rit.",
    "ritard":    "ritard.",
    "ritardando":"ritardando",
    "rall":      "rall.",
    "rallentando":"rallentando",
    "accel":     "accel.",
    "accelerando":"accelerando",
    "a_tempo":   "a tempo",
    "poco_a_poco":"poco a poco",
    "cresc":     "cresc.",
    "crescendo": "crescendo",
    "dim":       "dim.",
    "diminuendo":"diminuendo",
    "decresc":   "decresc.",
    "decrescendo":"decrescendo",
    "sempre":    "sempre",
    "subito":    "subito",
}


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

def setup_rhythm_tools(mcp: FastMCP, client: MuseScoreClient) -> None:

    def _guard() -> Optional[str]:
        if not client.is_connected():
            return "Not connected to MuseScore. Call connect_to_musescore() first."
        return None

    # ── Tempo ─────────────────────────────────────────────────────────────────

    @mcp.tool()
    async def add_tempo_marking(
        bpm: int,
        text: Optional[str] = None,
    ) -> str:
        """
        Add a tempo marking at the current cursor position.

        Args:
            bpm:  Beats per minute (e.g. 120 for Allegro).
                  Common values: Larghissimo=16, Grave=40, Largo=50,
                  Adagio=66, Andante=76, Moderato=96, Allegro=120,
                  Vivace=140, Presto=168, Prestissimo=200.
            text: Optional display text, e.g. "Allegro", "♩ = 120".
                  If omitted, only the metronome number is shown.

        Examples:
            add_tempo_marking(120, "Allegro")
            add_tempo_marking(66,  "Adagio")
            add_tempo_marking(76)
        """
        if err := _guard(): return err

        if bpm < 1 or bpm > 400:
            return f"BPM must be between 1 and 400 (got {bpm})."

        return await client.send_command({
            "action": "addTempoMarking",
            "params": {
                "bpm":  bpm,
                "text": text or f"♩ = {bpm}",
            },
        })

    @mcp.tool()
    async def add_tempo_by_name(tempo_name: str) -> str:
        """
        Add a standard Italian tempo marking by name.

        Args:
            tempo_name: Italian tempo term (case-insensitive).
                        Options: larghissimo, grave, largo, larghetto,
                        adagio, adagietto, andante, andantino, moderato,
                        allegretto, allegro, vivace, presto, prestissimo.

        Examples:
            add_tempo_by_name("andante")   # ♩ = 76
            add_tempo_by_name("Allegro")   # ♩ = 120
        """
        if err := _guard(): return err

        key = tempo_name.lower()
        if key not in TEMPO_TERMS:
            available = ", ".join(sorted(TEMPO_TERMS.keys()))
            return f"Unknown tempo '{tempo_name}'. Available: {available}"

        bpm = TEMPO_TERMS[key]
        display = tempo_name.capitalize()

        return await client.send_command({
            "action": "addTempoMarking",
            "params": {"bpm": bpm, "text": display},
        })

    # ── Dynamics ──────────────────────────────────────────────────────────────

    @mcp.tool()
    async def add_dynamic(dynamic: str) -> str:
        """
        Add a dynamic mark at the current cursor position.

        Args:
            dynamic: Dynamic symbol (case-insensitive).
                     Options: pppp, ppp, pp, p, mp, mf, f, ff, fff, ffff,
                              sfz, sfp, fp, rf, rfz, fz.

        Examples:
            add_dynamic("mf")    # mezzo forte
            add_dynamic("pp")    # pianissimo
            add_dynamic("sfz")   # sforzando
        """
        if err := _guard(): return err

        key = dynamic.lower()
        if key not in DYNAMICS:
            available = ", ".join(sorted(DYNAMICS.keys()))
            return f"Unknown dynamic '{dynamic}'. Available: {available}"

        return await client.send_command({
            "action": "addDynamic",
            "params": {"dynamic": DYNAMICS[key]},
        })

    # ── Text directions ───────────────────────────────────────────────────────

    @mcp.tool()
    async def add_text_direction(direction: str) -> str:
        """
        Add an expression / text direction above the staff at the cursor.

        These are non-dynamic tempo modification instructions, such as
        ritardando, accelerando, or crescendo hairpin text.

        Args:
            direction: Direction key (case-insensitive).
                       Options: rit, ritard, ritardando, rall, rallentando,
                                accel, accelerando, a_tempo, poco_a_poco,
                                cresc, crescendo, dim, diminuendo,
                                decresc, decrescendo, sempre, subito.

        Examples:
            add_text_direction("rit")       → adds "rit."
            add_text_direction("a_tempo")   → adds "a tempo"
            add_text_direction("cresc")     → adds "cresc."
        """
        if err := _guard(): return err

        key = direction.lower()
        if key not in TEXT_DIRECTIONS:
            available = ", ".join(sorted(TEXT_DIRECTIONS.keys()))
            return f"Unknown direction '{direction}'. Available: {available}"

        text = TEXT_DIRECTIONS[key]
        return await client.send_command({
            "action": "addTextDirection",
            "params": {"text": text},
        })

    # ── Reference ─────────────────────────────────────────────────────────────

    @mcp.tool()
    async def get_tempo_reference() -> str:
        """Return the standard Italian tempo terms with their BPM values."""
        lines = ["Tempo reference (name → BPM):"]
        for term, bpm in sorted(TEMPO_TERMS.items(), key=lambda x: x[1]):
            lines.append(f"  {term:<16} ♩ = {bpm}")
        return "\n".join(lines)
