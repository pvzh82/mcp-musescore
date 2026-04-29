# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.2.0] — 2025-01 — Export, Notation, Analysis, Rhythm

### Added

#### `src/tools/export.py` — Headless export (no GUI required)
- `get_musescore_binary_path()` — detect the MuseScore executable
- `export_score_to_pdf(score_path, output_path?)` — export .mscz → PDF
- `export_score_to_png(score_path, output_dir?, dpi?)` — export per-page PNGs
- `export_score_to_mp3(score_path, output_path?)` — export audio
- `batch_export_scores(input_dir, output_dir, format?)` — bulk export of exam PDFs

#### `src/tools/notation.py` — Score notation elements
- `set_clef(clef_type)` — change clef (treble, bass, alto, tenor, …)
- `list_clef_types()` — reference of all supported clefs
- `set_key_signature(key)` — change key signature
- `list_key_signatures()` — reference of all key signatures with accidental counts
- `get_note_at_cursor()` — detailed note/chord info at cursor
- `read_measures(start, end)` — read score content as structured data
- `add_accidental(type)` — force accidental on current note

#### `src/tools/analysis.py` — Music theory engine (pure Python)
- `analyze_interval(pitch1, pitch2)` — compute and name intervals
- `get_interval_name(semitones)` — look up interval by semitone count
- `get_interval_reference()` — full interval table
- `identify_chord(pitches)` — identify chord name from MIDI pitches
- `get_chord_reference()` — all supported chord patterns
- `get_roman_numeral(chord, key)` — harmonic function analysis
- `detect_scale(pitches)` — best-match scale detection
- `midi_to_note_name(pitch, prefer_flats?)` — MIDI → note name + Hz
- `note_name_to_midi(note_name)` — note name → MIDI

#### `src/tools/rhythm.py` — Tempo and expression markings
- `add_tempo_marking(bpm, text?)` — add metronome mark
- `add_tempo_by_name(tempo_name)` — add standard Italian tempo (Allegro, Adagio, …)
- `add_dynamic(dynamic)` — add dynamic mark (pp, mf, f, sfz, …)
- `add_text_direction(direction)` — add rit., accel., a tempo, cresc., …
- `get_tempo_reference()` — Italian tempo terms with BPM values

### Changed
- `src/client/websocket_client.py` — rewritten with better error handling and timeout
- `src/types/action_types.py` — added constants for all new actions
- `src/tools/__init__.py` — exports all setup functions including new ones
- `server.py` — registers all new tool groups; separates WS vs standalone tools
- `requirements.txt` — unchanged (no new Python dependencies)

---

## [1.1.0] — 2024-12 — Chord Support

### Added

#### `src/tools/chords.py`
- `add_chord(pitches, duration, advance?)` — add simultaneous notes by MIDI pitch
- `add_chord_by_name(chord_name, duration, root_octave?, advance?)` — add chord by name
- `add_chord_symbol(text)` — add visual chord symbol above staff
- `add_chord_with_symbol(chord_name, duration, …)` — notes + symbol in one call
- `list_chord_types()` — reference of all 30+ supported chord suffixes

#### `musescore-mcp-websocket.qml` patch
- `addChord` action handler
- `addChordSymbol` action handler (HARMONY element)

---

## [1.0.0] — 2024-11 — Initial Release (upstream ghchen99/mcp-musescore)

### Added
- WebSocket plugin for MuseScore 3.x / 4.x
- `connect_to_musescore` / `ping_musescore`
- Navigation: `get_cursor_info`, `go_to_measure`, `go_to_beginning_of_score`,
  `go_to_final_measure`, `next_element`, `prev_element`, `next_staff`, `prev_staff`,
  `select_current_measure`, `get_score`
- Notes: `add_note`, `add_rest`, `add_tuplet`
- Measures: `insert_measure`, `append_measure`, `delete_selection`, `undo`
- Text: `add_lyrics`, `add_lyrics_to_current_note`, `set_title`
- Staff: `add_instrument`, `set_instrument_sound`, `set_staff_mute`
- Time: `set_time_signature`
- Batch: `process_sequence`
