"""Cursor and navigation tools for MuseScore MCP."""

from ..client import MuseScoreClient


def setup_navigation_tools(mcp, client: MuseScoreClient):
    """Setup cursor and navigation tools."""
    
    async def _run_and_convert(action: str, params=None):
        res = await client.send_command(action, params)
        if res.get("success") and "currentSelection" in res:
            from ..utils.lilypond_converter import json_to_lilypond
            sel = res["currentSelection"]
            lily_str = json_to_lilypond(sel)
            
            meta = []
            score_info = res.get("currentScore", {})
            if not isinstance(score_info, dict):
                score_info = {}
                
            if "startTick" in sel:
                tick = sel["startTick"]
                # Default math fallback
                measure_num = (tick // 1920) + 1
                beat_num = ((tick % 1920) // 480) + 1
                
                if "measures" in score_info:
                    measures = score_info["measures"]
                    # Sort and find
                    measures = sorted(measures, key=lambda m: m.get("startTick", 0))
                    current_m = measures[0] if measures else {}
                    for i, m in enumerate(measures):
                        if m.get("startTick", 0) > tick:
                            break
                        current_m = m
                    measure_num = current_m.get("measure", measure_num)
                    m_start = current_m.get("startTick", 0)
                    beat_num = (max(0, tick - m_start) // 480) + 1

                meta.append(f"Mesure: {measure_num}")
                meta.append(f"Temps: {beat_num}")
                
            if "startStaff" in sel:
                start_s = sel["startStaff"]
                end_s = sel.get("endStaff", start_s)
                staff_name = f"{start_s}-{end_s}" if start_s != end_s else str(start_s)
                
                if "staves" in score_info:
                    staves = score_info["staves"]
                    if 0 <= start_s < len(staves):
                        st_info = staves[start_s]
                        name = st_info.get("shortName") or st_info.get("name")
                        if name:
                            staff_name = name
                            
                meta.append(f"Portée: {staff_name}")
            
            if "title" in score_info and score_info["title"]:
                meta.append(f"Titre: {score_info['title']}")
            if "numMeasures" in score_info:
                meta.append(f"Total Mesures: {score_info['numMeasures']}")
            
            meta_str = ", ".join(meta) if meta else "Aucune métadonnée"
            return f"[Métadonnées] {meta_str}\n[Partition]\n{lily_str}"
        return res
        return res

    @mcp.tool()
    async def get_cursor_info():
        """Get information about the current cursor position."""
        return await _run_and_convert("getCursorInfo")

    @mcp.tool()
    async def go_to_measure(measure: int):
        """Navigate to a specific measure."""
        return await _run_and_convert("goToMeasure", {"measure": measure})

    @mcp.tool()
    async def go_to_final_measure():
        """Navigate to the final measure of the score."""
        return await _run_and_convert("goToFinalMeasure")

    @mcp.tool()
    async def go_to_beginning_of_score():
        """Navigate to the beginning of the score."""
        return await _run_and_convert("goToBeginningOfScore")

    @mcp.tool()
    async def next_element():
        """Move cursor to the next element."""
        return await _run_and_convert("nextElement")

    @mcp.tool()
    async def prev_element():
        """Move cursor to the previous element."""
        return await _run_and_convert("prevElement")

    @mcp.tool()
    async def next_staff():
        """Move cursor to the next staff."""
        return await _run_and_convert("nextStaff")

    @mcp.tool()
    async def prev_staff():
        """Move cursor to the previous staff."""
        return await _run_and_convert("prevStaff")

    @mcp.tool()
    async def select_current_measure():
        """Select the current measure."""
        return await _run_and_convert("selectCurrentMeasure")
        
    @mcp.tool()
    async def select_custom_range(start_tick: int, end_tick: int, start_staff: int, end_staff: int):
        """
        Select a custom range of ticks across staves.
        This provides high surgical precision for retrieving continuous phrasing that spans measure bounds.
        """
        params = {
            "startTick": start_tick,
            "endTick": end_tick,
            "startStaff": start_staff,
            "endStaff": end_staff
        }
        return await _run_and_convert("selectCustomRange", params)