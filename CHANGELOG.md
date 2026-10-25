# Changelog

## 0.4.0 (2026-10-25)

Deutsch: siehe unten.

### New

- **Simpler tool set:** the MCP server has 16 tools. New: `find_sounds`, `set_track`, `edit_notes`, `create_track`, copy of arrangement clips (`copy_clip` in `edit_arrangement`).
- **`plan_song` complexity:** `rich` (default: answer voice, lead and bass layers, noise sweeps, downlifters, short risers, snare rolls, ghost notes, varying section lengths, a lead that changes every 8 bars) or `simple`. Optional `tempo`. The preview names tempo and key, and says when the Set's tempo or key will change.
- **Bake device:** choose **Simple** or **Rich** on the Bake page; loops and reference have their own row.
- **`compose`** follows the song's chords track (chords-aware bass and melody).
- **Chat confirmation:** with `MIDIBAKERY_CONFIRM=chat` the MCP server never shows a dialog; replacements and deletions come back as a preview that Claude confirms with you in the chat.
- **Honest undo:** `apply_plan` reports how many undo steps a song took, the track count to undo down to and the key and tempo from before. New tracks go behind existing ones.
- **Installation guide** rewritten (English and German): step by step for macOS and Windows, Control Surface, devices, API key, MCP server, troubleshooting, update, uninstall.

### Changed

- MidiBakery is free: all licence, trial and key code and UI are removed. The update service stays.
- Repository: `github.com/markus-fischbacher/MidiBakery`.

### Notes

- The installers are not signed or notarized yet (macOS: **Open Anyway**, Windows: **Run anyway**).

### Deutsch

- Neu: 16 MCP-Tools (u. a. `find_sounds`, `set_track`, `edit_notes`, `create_track`, Clips kopieren), `plan_song` mit Komplexität `rich`/`simple` und `tempo`, Bake-Device mit Simple/Rich, chords-bewusstes `compose`, Chat-Bestätigung mit `MIDIBAKERY_CONFIRM=chat`, ehrliche Undo-Angaben, neu geschriebene Installationsanleitung.
- Geändert: MidiBakery ist kostenlos; der gesamte Lizenzcode ist entfernt.
- Hinweis: Die Installer sind noch nicht signiert (macOS: „Dennoch öffnen“, Windows: „Trotzdem ausführen“).

## 0.3.0

Last release before the simplification to 16 tools; see the git history (`v0.3.0`).
