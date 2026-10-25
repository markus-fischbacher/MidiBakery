# MidiBakery als MCP-Server

Der **MCP-Server** bringt MidiBakery in **Claude Desktop**, **Claude Code** oder jede andere MCP-App. Du sprichst mit Claude in dessen eigenem Fenster statt im Chat-Device; Claude nutzt dieselben 16 Werkzeuge, um dein Live Set zu lesen und darin Songs zu bauen.

English version: [MCP_SERVER.md](MCP_SERVER.md) · Zurück zum [Benutzerhandbuch](BENUTZERHANDBUCH.md)

## Einrichten

**Voraussetzungen:** MidiBakery ist installiert, Live läuft und die Control Surface **MidiBakery** ist an ([Benutzerhandbuch, Kapitel 3](BENUTZERHANDBUCH.md#3-in-live-einrichten)). Das Chat-Device brauchst du nicht.

Der Server ist der Befehl `midibakery mcp` (stdio). **Claude Code:**

```bash
claude mcp add midibakery -- "$HOME/Library/Application Support/MidiBakery/runtime/<version>/midibakery" mcp
```

Unter Windows liegt das Programm in `%LOCALAPPDATA%\Programs\MidiBakery\runtime\<version>\`. Aus einem Checkout des Repositorys: `claude mcp add midibakery -- uv --directory <pfad> run midibakery mcp`.

**Claude Desktop:** **Einstellungen > Entwickler > Konfiguration bearbeiten** (`claude_desktop_config.json`), danach Claude Desktop neu starten:

```json
{
  "mcpServers": {
    "midibakery": {
      "command": "/Users/<du>/Library/Application Support/MidiBakery/runtime/<version>/midibakery",
      "args": ["mcp"]
    }
  }
}
```

Der Pfad enthält die Version: nach einem Update anpassen. Für Apps ohne stdio stellt `midibakery mcp --http` den Server auf `127.0.0.1:8765` bereit (`--port` ändert ihn).

**Testen:** „Was ist in meinem Live Set?“ Claude ruft `get_session` auf. Klappt das nicht, hilft `midibakery ping`.

## Sicherheit

- Jede Änderung ist ein Schritt in Lives Undo-Liste; Claude kann selbst `undo` aufrufen.
- `plan_song` ändert **nichts**, bis `apply_plan` kommt. Ein Song überschreibt nie bestehende Arrangement-Clips.
- Vor dem Löschen eines Clips oder dem Ersetzen von Noten fragt MidiBakery nach (Apps ohne Rückfragen bekommen stattdessen eine `plan_id` und müssen dich im Chat fragen, bevor `apply_plan` kommt). Abgelehnt: `CANCELLED`. Kommt `CANCELLED`, ohne dass du abgelehnt hast (die App zeigt keine Rückfrage), setze für den Server die Umgebungsvariable `MIDIBAKERY_CONFIRM=chat` (`claude mcp add -e MIDIBAKERY_CONFIRM=chat …`): Dann erscheint nie ein Dialog, und jedes Ersetzen oder Löschen kommt als Vorschau mit `plan_id` zurück, die Claude im Chat mit dir bestätigen muss, bevor `apply_plan` kommt.
- Der Server spricht nur mit Live. Die App, in der du bist, sieht, was die Werkzeuge zurückgeben: Spur- und Clipnamen, Noten, Tempo.

## Die 16 Werkzeuge

Spuren, Slots und Arrangement-Clips zählen ab **0** (Spur 1 in Live = `track 0`). Zeit in Schlägen; Tonhöhe 60 = C3. Clip-Werkzeuge nehmen `slot` (Session) **oder** `arrangement_clip` (Arrangement: Index oder **Name**, z. B. „Drop Bass“).

| Werkzeug | Art | Was es tut |
|---|---|---|
| `get_session` | lesen | Tempo, Taktart, Tonart, Transport und alle Spuren mit Devices und Clips. |
| `get_clip` | lesen | Eigenschaften eines Clips und bei MIDI-Clips alle Noten. |
| `get_arrangement` | lesen | Arrangement-Clips pro Spur, Locators, Songlänge. |
| `get_reference` | lesen | Referenzen aus dem Reference Analyzer und vom Set Importer importierte Live Sets: Abschnitte, Tonart, Tempo, mit `name` auch die Spuren pro Takt. |
| `plan_song` | lesen | Plant einen **ganzen Song**: `genre` (`house`, `melodic_techno`, `peak_time_techno`, `drum_and_bass`, `trap`), `length` (`radio`/`standard`/`extended`), `key` (z. B. `A minor`; wird in Live gesetzt), `progression`, `reference` (ein analysierter Song oder ein importiertes Set), `loops_from` (`{"bass": "<Set>"}`; Rollen drums, bass, lead, chords), `my_loops` (der Seed zieht Loops aus den importierten Sets), `seed`. Das Tempo folgt Genre oder Referenz; Rollen, die einem Set fehlen, kommen aus dem Genre. Liefert eine Vorschau und eine `plan_id`. |
| `apply_plan` | **fragt nach** (beim Ersetzen) | Schreibt einen Plan nach Live. `CONFLICT`, wenn sich ein Ziel seit dem Planen geändert hat. Pläne bleiben im Speicher (die letzten 32). |
| `compose` | **fragt nach** (beim Ersetzen) | **Eine Stimme** als MIDI-Clip in der Tonart des Sets: `kind` drums, bass, chords oder melody; `bars`, `seed`, `style`, `pattern`, `density`, `swing`, `progression`, `chords_from`, `follow_kick`, `if_exists`, `preview`. Mit `arrangement_clip` schreibt es diesen Clip neu. |
| `edit_arrangement` | schreiben | MIDI-Clips anlegen, Session-Clips kopieren, Arrangement-Clips **kopieren (`copy_clip`), verschieben, tauschen, löschen**, Locators setzen oder löschen (Transport gestoppt). Ein Undo-Schritt; ein Clip landet nie auf einem anderen. |
| `find_sounds` | lesen | Durchsucht den Live-Browser nach Namen (`query`, `category`, `limit`): Instrumente, Presets, Kits, jeweils mit `path`. |
| `set_track` | schreiben | Spur umbenennen (`name`) und/oder einen `sound` aus `find_sounds` laden. Kein Mixing: Lautstärke und Pan bleiben. |
| `edit_notes` | schreiben | Einen MIDI-Clip an Ort und Stelle ändern: Noten `add`, `remove` per `note_id` (aus `get_clip`), `transpose` in Halbtönen (optional `from_time`/`to_time`). |
| `create_track` | schreiben | MIDI- oder Audiospur anlegen (`kind`, `index` für die Position, `name`); Standard: am Ende. Danach kann `compose` hineinschreiben. |
| `delete_clip` | **fragt nach** | Einen Clip löschen (Session per `slot`, Arrangement per `arrangement_clip`). |
| `set_song` | schreiben | Tempo, Taktart, Tonart (`root_note`, `scale_name`, `scale_mode`), Metronom, Loop. |
| `transport` | schreiben | Abspielen, stoppen, fortsetzen, alle Clips stoppen, Arrangement-Aufnahme umschalten. |
| `undo` | schreiben | Rückgängig oder wiederholen in Live. |

## Für Entwickler

Der Server ist `midibakery.mcp.server.build_server`; die Live-Operationen liegen in `midibakery.catalog` und erreichen das Remote Script über die Bridge. Der Agent des Chat-Devices nutzt dieselben Werkzeuge. Mehr in [ARCHITECTURE.md](../ARCHITECTURE.md).
