import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("LilyPondConverter")

def midi_to_lilypond_pitch(midi_pitch: int, tpc: Optional[int] = None) -> str:
    """
    Convert a MIDI pitch to LilyPond pitch syntax.
    If TPC (Tonal Pitch Class) is provided, uses it to determine enharmonic spelling (flats vs sharps).
    Example: 60 -> c', 67 -> g', 74 -> d''
    """
    try:
        # Fallback names if no TPC provided
        pitch_names = ['c', 'cis', 'd', 'dis', 'e', 'f', 'fis', 'g', 'gis', 'a', 'ais', 'b']
        
        if tpc is not None:
            # MuseScore TPC map (circle of fifths where 14 = C, 15 = G)
            tpc_map = {
                6: 'fes', 7: 'ces', 8: 'ges', 9: 'des', 10: 'as', 11: 'es', 12: 'bes', 13: 'f',
                14: 'c', 15: 'g', 16: 'd', 17: 'a', 18: 'e', 19: 'b', 20: 'fis',
                21: 'cis', 22: 'gis', 23: 'dis', 24: 'ais', 25: 'eis', 26: 'bis',
                27: 'fisis', 28: 'cisis', 29: 'gisis', 30: 'disis', 31: 'aisis', 32: 'eisis', 33: 'bisis',
                -1: 'feses', 0: 'ceses', 1: 'geses', 2: 'deses', 3: 'ases', 4: 'eses', 5: 'beses'
            }
            base_note = tpc_map.get(tpc, pitch_names[midi_pitch % 12])
        else:
            base_note = pitch_names[midi_pitch % 12]
            
        octave = (midi_pitch // 12) - 1
        
        # Mapping MIDI octaves to LilyPond octaves (C4 = MIDI 60 = c')
        if octave == 4:
            octave_mark = "'"
        elif octave == 5:
            octave_mark = "''"
        elif octave == 6:
            octave_mark = "'''"
        elif octave == 7:
            octave_mark = "''''"
        elif octave == 3:
            octave_mark = ""
        elif octave == 2:
            octave_mark = ","
        elif octave == 1:
            octave_mark = ",,"
        elif octave == 0:
            octave_mark = ",,,"
        else:
            octave_mark = ""  # Fallback for out-of-bounds
            
        return f"{base_note}{octave_mark}"
    except Exception as e:
        logger.error(f"Error converting MIDI pitch {midi_pitch}: {e}")
        return "c'"  # Safe fallback

def ticks_to_lilypond_duration(ticks: int) -> str:
    """
    Convert MuseScore ticks to LilyPond rhythmic duration.
    MuseScore defines a quarter note as 480 ticks.
    """
    try:
        mapping = {
            1920: "1",    # Whole note
            1440: "2.",   # Dotted half note
            960: "2",     # Half note
            720: "4.",    # Dotted quarter note
            480: "4",     # Quarter note
            360: "8.",    # Dotted eighth note
            320: "2*2/3", # Half triplet
            240: "8",     # Eighth note
            180: "16.",   # Dotted 16th note
            160: "4*2/3", # Quarter triplet
            120: "16",    # 16th note
            80: "8*2/3",  # Eighth triplet
            60: "32",     # 32nd note
            30: "64"      # 64th note
        }
        return mapping.get(ticks, "4")  # Default to quarter note if not mapped
    except Exception as e:
        logger.error(f"Error converting ticks {ticks}: {e}")
        return "4"

def process_element(element: Dict[str, Any]) -> str:
    """
    Process a single JSON element dictionary into LilyPond syntax.
    Handles 'Chord' (with notes) and 'Rest'.
    """
    try:
        elem_name = element.get("name", "")
        duration_ticks = element.get("durationTicks", 480)
        lily_duration = ticks_to_lilypond_duration(duration_ticks)

        if elem_name == "Rest":
            return f"r{lily_duration}"
        
        elif elem_name == "Chord":
            notes = element.get("notes", [])
            if not notes:
                return f"r{lily_duration}"
            
            lily_notes = []
            for note in notes:
                pitch = note.get("pitchMidi")
                tpc = note.get("tpc")
                if pitch is not None:
                    lily_notes.append(midi_to_lilypond_pitch(pitch, tpc))
            
            if not lily_notes:
                return f"r{lily_duration}"
            elif len(lily_notes) == 1:
                return f"{lily_notes[0]}{lily_duration}"
            else:
                joined_notes = " ".join(lily_notes)
                return f"<{joined_notes}>{lily_duration}"
        else:
            return ""  # Ignore other elements without crashing
    except Exception as e:
        logger.error(f"Error parsing element: {e}")
        return ""

def json_to_lilypond(score_data: Dict[str, Any]) -> str:
    """
    Convert a JSON response representing a MuseScore measure/score into an absolute LilyPond tree.
    Assembles code into structured staffs and voices using concurrent compilation.
    """
    try:
        # Handle 'currentSelection' raw input format
        if "startStaff" in score_data and "elements" in score_data and isinstance(score_data["elements"], list):
            staff_idx = score_data.get("startStaff", 0)
            staff_name = f"staff{staff_idx}"
            staff_names = [staff_name]
            elements_by_staff = {staff_name: score_data["elements"]}
        else:
            # Handle 'getScore' or standard wrapped output
            staves_info = score_data.get("staves", [])
            staff_names = [st.get("name") for st in staves_info if st.get("visible", True)]
            
            measure = score_data.get("measure", {})
            if not measure:
                measures = score_data.get("measures", [])
                if measures:
                    measure = measures[0]  # Take only the first measure for demonstration
                    
            elements_by_staff = measure.get("elements", {})
            
            if not staff_names:
                staff_names = list(elements_by_staff.keys())

        lily_parts = ["<<"]
        
        for staff in staff_names:
            staff_elements = elements_by_staff.get(staff, [])
            if not staff_elements:
                continue
                
            lily_parts.append("  \\new Staff {")
            lily_parts.append("    <<")
            
            # Group elements by voice (default to voice 1 if unspecified)
            voices: Dict[int, List[Dict[str, Any]]] = {}
            for elem in staff_elements:
                # MuseScore voices are 0-indexed (0 to 3) from our QML plugin
                v = elem.get("voice", 0)
                mapped_v = v + 1
                if mapped_v not in voices:
                    voices[mapped_v] = []
                voices[mapped_v].append(elem)
                
            voice_strings = []
            voice_commands = {1: "\\voiceOne", 2: "\\voiceTwo", 3: "\\voiceThree", 4: "\\voiceFour"}
            
            for v_idx in sorted(voices.keys()):
                v_elems = voices[v_idx]
                formatted_elems = [process_element(e) for e in v_elems]
                formatted_elems = [e for e in formatted_elems if e]
                
                cmd = voice_commands.get(v_idx, "\\voiceOne")
                voice_str = f"{cmd} " + " ".join(formatted_elems)
                voice_strings.append(f"      \\new Voice {{ {voice_str} }}")
            
            # Use LilyPond's double backslash separator for multiple concurrent voices
            voices_combined = " \\\\\n".join(voice_strings)
            lily_parts.append(voices_combined)
            
            lily_parts.append("    >>")
            lily_parts.append("  }")
            
        lily_parts.append(">>")
        
        return "\n".join(lily_parts)
        
    except Exception as e:
        logger.error(f"Failed to convert JSON to LilyPond: {e}")
        return "<< >>"
