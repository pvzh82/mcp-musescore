"""
Export tools — convert .mscz scores to PDF, PNG or other formats
using the MuseScore executable in headless (batch) mode.

No WebSocket connection is required; these tools invoke the MuseScore
binary directly as a subprocess.  They are therefore usable even when
the MuseScore GUI plugin is not running.

MuseScore CLI reference:
  mscore -o output.pdf input.mscz
  mscore -o output.png input.mscz   (one PNG per page: output-1.png, …)
"""

import asyncio
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# MuseScore binary detection
# ---------------------------------------------------------------------------

_CANDIDATE_PATHS = [
    # Linux
    "mscore",
    "musescore",
    "musescore4",
    "musescore3",
    "/usr/bin/mscore",
    "/usr/bin/musescore4",
    # macOS
    "/Applications/MuseScore 4.app/Contents/MacOS/mscore",
    "/Applications/MuseScore 3.app/Contents/MacOS/mscore",
    # Windows (forward slashes work fine for shutil.which)
    r"C:\Program Files\MuseScore 4\bin\MuseScore4.exe",
    r"C:\Program Files\MuseScore 3\bin\MuseScore3.exe",
]


def _find_musescore_binary() -> Optional[str]:
    """Return the first MuseScore executable found on the system."""
    for candidate in _CANDIDATE_PATHS:
        path = shutil.which(candidate) or (candidate if os.path.isfile(candidate) else None)
        if path:
            return path
    return None


MUSESCORE_BIN: Optional[str] = _find_musescore_binary()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _run_headless(args: list[str], timeout: int = 60) -> tuple[int, str, str]:
    """
    Run MuseScore headless and return (returncode, stdout, stderr).
    Uses asyncio subprocess so the MCP event loop is not blocked.
    """
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return -1, "", f"MuseScore process timed out after {timeout}s."

    return proc.returncode, stdout_b.decode(errors="replace"), stderr_b.decode(errors="replace")


def _validate_score_path(score_path: str) -> tuple[Optional[Path], Optional[str]]:
    """Return (resolved Path, None) or (None, error_message)."""
    p = Path(score_path).expanduser().resolve()
    if not p.exists():
        return None, f"Score file not found: {p}"
    if p.suffix.lower() not in {".mscz", ".mscx", ".xml", ".musicxml"}:
        return None, f"Unsupported score format '{p.suffix}'. Use .mscz or .mscx."
    return p, None


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------

def setup_export_tools(mcp: FastMCP, _client=None) -> None:
    """Register export tools.  No WebSocket client needed."""

    @mcp.tool()
    async def get_musescore_binary_path() -> str:
        """
        Return the path of the MuseScore executable found on this system.

        Useful for diagnosing why exports might fail.
        """
        if MUSESCORE_BIN:
            return f"MuseScore binary: {MUSESCORE_BIN}"
        return (
            "MuseScore binary not found. "
            "Install MuseScore and make sure it is on your PATH, "
            "or set the MUSESCORE_BIN environment variable."
        )

    @mcp.tool()
    async def export_score_to_pdf(
        score_path: str,
        output_path: Optional[str] = None,
    ) -> str:
        """
        Export a MuseScore file (.mscz) to PDF using headless mode.

        This does NOT require the MuseScore GUI to be open.

        Args:
            score_path:  Absolute or relative path to the .mscz file.
                         Example: "/home/user/scores/exam.mscz"
            output_path: Where to write the PDF.  If omitted, the PDF is
                         saved next to the source file with the same stem.
                         Example: "/home/user/exports/exam.pdf"

        Returns:
            Path of the generated PDF on success, or an error message.
        """
        binary = os.environ.get("MUSESCORE_BIN", MUSESCORE_BIN)
        if not binary:
            return (
                "MuseScore binary not found. "
                "Install MuseScore or set the MUSESCORE_BIN environment variable."
            )

        score_p, err = _validate_score_path(score_path)
        if err:
            return err

        if output_path:
            out_p = Path(output_path).expanduser().resolve()
        else:
            out_p = score_p.with_suffix(".pdf")

        out_p.parent.mkdir(parents=True, exist_ok=True)

        returncode, _, stderr = await _run_headless(
            [binary, "--export-to", str(out_p), str(score_p)]
        )

        if returncode == 0 and out_p.exists():
            size_kb = out_p.stat().st_size // 1024
            return f"PDF exported successfully: {out_p}  ({size_kb} KB)"
        else:
            return (
                f"Export failed (exit code {returncode}).\n"
                f"MuseScore stderr: {stderr.strip() or '(none)'}"
            )

    @mcp.tool()
    async def export_score_to_png(
        score_path: str,
        output_dir: Optional[str] = None,
        dpi: int = 150,
    ) -> str:
        """
        Export each page of a score as a separate PNG image.

        MuseScore names the files <stem>-1.png, <stem>-2.png, etc.

        Args:
            score_path:  Path to the .mscz file.
            output_dir:  Directory where PNGs will be saved.
                         Defaults to the same directory as the score.
            dpi:         Resolution in dots per inch (default 150).
                         Use 300 for print quality.

        Returns:
            List of generated PNG paths on success, or an error message.
        """
        binary = os.environ.get("MUSESCORE_BIN", MUSESCORE_BIN)
        if not binary:
            return "MuseScore binary not found."

        score_p, err = _validate_score_path(score_path)
        if err:
            return err

        out_dir = Path(output_dir).expanduser().resolve() if output_dir else score_p.parent
        out_dir.mkdir(parents=True, exist_ok=True)

        out_stem = out_dir / score_p.stem
        # MuseScore appends "-1.png", "-2.png", etc.
        out_png_pattern = str(out_stem) + ".png"

        returncode, _, stderr = await _run_headless(
            [binary, "--export-to", out_png_pattern,
             "--export-pdf-dpi", str(dpi), str(score_p)]
        )

        if returncode != 0:
            return (
                f"Export failed (exit code {returncode}).\n"
                f"MuseScore stderr: {stderr.strip() or '(none)'}"
            )

        # Collect the generated files
        generated = sorted(out_dir.glob(f"{score_p.stem}*.png"))
        if not generated:
            return "Export command succeeded but no PNG files were found."

        paths = "\n".join(f"  {p}" for p in generated)
        return f"Exported {len(generated)} page(s):\n{paths}"

    @mcp.tool()
    async def export_score_to_mp3(
        score_path: str,
        output_path: Optional[str] = None,
    ) -> str:
        """
        Export a score to MP3 audio using MuseScore's built-in soundfont.

        Args:
            score_path:  Path to the .mscz file.
            output_path: Destination .mp3 path.  Defaults to same dir as score.

        Returns:
            Path of generated MP3, or an error message.
        """
        binary = os.environ.get("MUSESCORE_BIN", MUSESCORE_BIN)
        if not binary:
            return "MuseScore binary not found."

        score_p, err = _validate_score_path(score_path)
        if err:
            return err

        if output_path:
            out_p = Path(output_path).expanduser().resolve()
        else:
            out_p = score_p.with_suffix(".mp3")

        out_p.parent.mkdir(parents=True, exist_ok=True)

        returncode, _, stderr = await _run_headless(
            [binary, "--export-to", str(out_p), str(score_p)]
        )

        if returncode == 0 and out_p.exists():
            size_kb = out_p.stat().st_size // 1024
            return f"MP3 exported: {out_p}  ({size_kb} KB)"
        else:
            return (
                f"Export failed (exit code {returncode}).\n"
                f"MuseScore stderr: {stderr.strip() or '(none)'}"
            )

    @mcp.tool()
    async def batch_export_scores(
        input_dir: str,
        output_dir: str,
        format: str = "pdf",
    ) -> str:
        """
        Export all .mscz files in a directory to the specified format.

        Ideal for generating a batch of exam PDFs in one call.

        Args:
            input_dir:  Directory containing .mscz files.
            output_dir: Directory where exports will be saved.
            format:     Output format: "pdf", "png", or "mp3" (default "pdf").

        Returns:
            Summary of exported files or errors encountered.
        """
        binary = os.environ.get("MUSESCORE_BIN", MUSESCORE_BIN)
        if not binary:
            return "MuseScore binary not found."

        in_dir = Path(input_dir).expanduser().resolve()
        out_dir = Path(output_dir).expanduser().resolve()

        if not in_dir.is_dir():
            return f"Input directory not found: {in_dir}"
        out_dir.mkdir(parents=True, exist_ok=True)

        if format not in {"pdf", "png", "mp3"}:
            return f"Unsupported format '{format}'. Choose pdf, png, or mp3."

        scores = sorted(in_dir.glob("*.mscz"))
        if not scores:
            return f"No .mscz files found in {in_dir}"

        results = []
        for score_p in scores:
            out_p = out_dir / score_p.with_suffix(f".{format}").name
            returncode, _, stderr = await _run_headless(
                [binary, "--export-to", str(out_p), str(score_p)]
            )
            if returncode == 0 and out_p.exists():
                results.append(f"  ✓ {score_p.name} → {out_p.name}")
            else:
                snippet = stderr.strip()[:120] if stderr.strip() else "unknown error"
                results.append(f"  ✗ {score_p.name}  ERROR: {snippet}")

        summary = f"Batch export ({format.upper()}) — {len(scores)} file(s):\n"
        return summary + "\n".join(results)
