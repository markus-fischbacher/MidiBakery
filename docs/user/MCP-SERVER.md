# MidiBakery als MCP-Server

Mit dem **MCP-Server** steuerst du Ableton Live aus **Claude Desktop**, **Claude Code** oder jedem anderen MCP-fähigen Programm. Du brauchst dafür das Chat-Gerät nicht: Du sprichst mit Claude in dessen eigenem Fenster, und Claude benutzt die MidiBakery-Werkzeuge, um dein Live-Set zu lesen und zu verändern.

English version: [MCP_SERVER.md](MCP_SERVER.md) · Zurück zum [Benutzerhandbuch](BENUTZERHANDBUCH.md)

**Inhalt**

- Teil A: [Kurz erklärt](#teil-a-kurz-erklärt) – was das ist, einrichten, was du sagen kannst
- Teil B: [Referenz aller 39 Werkzeuge](#teil-b-referenz-aller-38-werkzeuge)

---

## Teil A: Kurz erklärt

### Chat-Gerät oder MCP-Server?

MidiBakery hat zwei Wege zur selben Fähigkeit:

| | Chat-Gerät in Live | MCP-Server |
|---|---|---|
| Wo du schreibst | in Live, im Gerät **MidiBakery Chat** | in Claude Desktop oder Claude Code |
| Welche KI | Claude (eigener API-Schlüssel), LM Studio, Ollama | die KI des Programms, in dem du bist (z. B. dein Claude-Abo) |
| Werkzeuge | dieselben 38 | dieselben 38 |
| Vorschau-Karten | im Chat-Gerät, mit **Apply** | als Piano Roll im Programm (wenn es „MCP Apps“ kann), sonst als Text |
| Für wen | Einsteiger, alles in Live | wer ohnehin mit Claude arbeitet, oder die Programmierung mag |

Beide benutzen dieselbe Verbindung zu Live (das Remote Script). Der MCP-Server braucht also **das Remote Script in Live** ([Handbuch, Kapitel 4](BENUTZERHANDBUCH.md#4-in-live-einrichten)), aber keinen API-Schlüssel von MidiBakery und das Chat-Gerät nicht.

### Einrichten

**Voraussetzungen:** MidiBakery ist installiert ([Kapitel 3](BENUTZERHANDBUCH.md#3-installieren-und-aktualisieren)), Live läuft und das Remote Script **MidiBakery** ist als Control Surface eingeschaltet.

Der Server ist der Befehl `midibakery mcp`. Programme starten ihn selbst und sprechen mit ihm über die Standardeingabe (stdio). Du gibst ihnen nur den Befehl.

**Claude Code** (Terminal), aus dem installierten Programm:

```bash
claude mcp add midibakery -- "$HOME/Library/Application Support/MidiBakery/runtime/<Version>/midibakery" mcp
```

(`<Version>` ist die installierte Version, z. B. `0.3.0`; unter Windows liegt das Programm in `%LOCALAPPDATA%\Programs\MidiBakery\runtime\<Version>\`.) Wer das Repository selbst ausgecheckt hat:

```bash
claude mcp add midibakery -- uv --directory <Pfad zum Repository> run midibakery mcp
```

**Claude Desktop:** Öffne **Einstellungen > Entwickler > Konfiguration bearbeiten**. Die Datei heißt `claude_desktop_config.json` (macOS: `~/Library/Application Support/Claude/`, Windows: `%APPDATA%\Claude\`). Füge hinzu:

```json
{
  "mcpServers": {
    "midibakery": {
      "command": "/Users/<du>/Library/Application Support/MidiBakery/runtime/<Version>/midibakery",
      "args": ["mcp"]
    }
  }
}
```

Beende Claude Desktop vollständig und starte es neu. Dann zeigt das Werkzeug-Symbol im Chat „midibakery“ mit 39 Werkzeugen.

**Hinweis zu Updates:** Das installierte Programm liegt in einem Ordner mit der Versionsnummer. Nach einem MidiBakery-Update zeigt der Pfad auf die neue Version: passe ihn an (Claude Code: `claude mcp remove midibakery`, dann neu hinzufügen).

**Als Netzwerkdienst** (für Programme, die kein stdio können): `midibakery mcp --http` bietet den Server auf `127.0.0.1:8765` an (`--port` ändert das). Er ist nur von deinem Rechner aus erreichbar.

**Testen:** Schreibe in Claude: „Was ist in meinem Live-Set?“ Claude ruft `get_session` auf und beschreibt dein Set. Klappt das nicht: Läuft Live? Ist das Remote Script an? Im Terminal prüft `midibakery ping` die Verbindung.

### Was du sagen kannst

Alle Beispiele aus dem [Handbuch (Kapitel 7)](BENUTZERHANDBUCH.md#7-beispiele-was-du-fragen-kannst) funktionieren genauso. Ein paar typische Gespräche:

- **Überblick:** „Schau dir mein Live-Set an und sag mir, was fehlt.“ (Claude liest Spuren, Clips und Geräte.)
- **Teile:** „Schreibe vier Takte Techno-Drums auf Spur 1 und eine Basslinie, die der Kick folgt.“
- **Vorschau zuerst:** „Plane Bass, Akkorde und Melodie für Spur 2 bis 4 und zeig mir erst die Vorschau.“ Die Vorschau erscheint als Piano Roll (vorher/nachher). **Wenn du zustimmst, schreibt Claude sie mit `apply_plan`.**
- **Ganzer Song:** „Baue einen Melodic-Techno-Track, standard-lang, ab Takt 1.“
- **Bearbeiten:** „Transponiere ‚Drop Bass‘ eine Oktave tiefer, nur die zweite Hälfte.“
- **Mixen:** „Leg einen Hall-Return an und schick die Melodie mit -12 dB hinein.“
- **Referenz:** „Nimm den Referenzsong ‚…‘, den ich analysiert habe, als Vorlage für den Aufbau.“

Der Unterschied zum Chat-Gerät: Claude Desktop und Claude Code können **mehr** als MidiBakery (Dateien lesen, Texte schreiben, im Web suchen). Du kannst zum Beispiel sagen: „Lies die Akkorde aus dieser Textdatei und schreib sie als Clip.“

### Sicherheit: Was passiert, bevor etwas gelöscht wird?

- **Undo:** Jede Änderung ist ein Schritt in Lives Rückgängig-Liste (⌘Z / Strg+Z). Das Werkzeug `undo` kann Claude selbst aufrufen.
- **Nachfrage:** Beim **Löschen von Spuren oder Clips** und beim **Ersetzen vorhandener Noten** (`compose`, `transform_notes`, `apply_plan`) fragt MidiBakery vorher nach. Ein Song-Plan überschreibt nie vorhandene Arrangement-Clips. Programme, die Rückfragen können (die meisten), zeigen dir eine Bestätigung. Lehnst du ab, bleibt alles, wie es ist, und Claude erfährt `CANCELLED`.
- **Programme ohne Rückfrage-Funktion** werden nicht gefragt. Dort schützen nur Undo und der Hinweis „destruktiv“, den manche Programme selbst anzeigen. Prüfe in so einem Programm, was Claude vorhat.
- **Vorschau vor Änderung:** Ganze Songs (`plan_song`) und Pläne (`plan_changes`) ändern **nichts**, bevor `apply_plan` aufgerufen wird.
- **Alles bleibt auf deinem Rechner,** was MidiBakery selbst betrifft: Der Server spricht nur mit Live. Claude (das Programm, in dem du bist) bekommt natürlich zu sehen, was die Werkzeuge zurückgeben: Spur- und Clipnamen, Noten, Tempo.

---

## Teil B: Referenz aller 39 Werkzeuge

Konventionen, die Claude kennt (siehe die Anweisungen, die der Server mitschickt):

- **Zählweise:** Spuren, Slots, Geräte und Szenen sind **nullbasiert** (Spur 1 in Live = `track 0`). Beim Anlegen oder Löschen verschieben sich die Nummern.
- **Zeit** in Zählzeiten (Viertel); Takt *n* beginnt bei Zählzeit (n-1) × Zählzeiten pro Takt. **Tonhöhe** 60 = C3. Tonart: `root_note` 0 = C bis 11 = H.
- **Session oder Arrangement:** Clip-Werkzeuge nehmen `slot` (Session) **oder** `arrangement_clip` (Arrangement: Index in Zeitreihenfolge oder **Name**, z. B. „Groove Bass“), nie beides.
- **Lautstärke und Sends** in dB, wie Live sie anzeigt.
- **Racks:** Geräte in Racks mit `chain_path` [Kette, Gerät, …]. Return-Spuren mit `return_track` statt `track`.

Die Spalte **Art** zeigt: **lesen** (ändert nichts), **schreiben**, **fragt nach** (Rückfrage vor dem Ändern bei Programmen, die das können).

### Lesen und Überblick

| Werkzeug | Art | Was es tut |
|---|---|---|
| `get_session` | lesen | Song-Einstellungen (Tempo, Takt, Tonart, Transport) und alle Spuren mit Geräten und Clips. **Der erste Aufruf jeder Sitzung.** |
| `get_clip` | lesen | Eigenschaften eines Clips und bei MIDI-Clips **alle Noten** mit `note_id`, Wahrscheinlichkeit und Velocity-Abweichung. Parameter: `track`, `slot` oder `arrangement_clip`. |
| `get_arrangement` | lesen | Arrangement-Clips je Spur (Start, Ende), Locators, Songlänge. Optional `track`. |
| `get_reference` | lesen | Analysierte Referenzsongs des Reference Analyzers: Abschnitte, Tonart, Tempo, mit `name` auch die Bahnen je Takt (Kick, Tiefen, Mitten, Höhen, Energie). Ohne `name`: alle, neueste zuerst. |
| `get_mixer` | lesen | Lautstärke, Pan, Sends, Mute/Solo, Crossfader und Routing von Spuren, Returns und Master. `options` listet die gültigen Routing-Namen. |
| `get_device_parameters` | lesen | Parameter eines Geräts mit Bereichen und angezeigten Werten. |
| `get_rack` | lesen | Ketten (Geräte, Mixer, Drum-Pad-Note) und Macros eines Racks. |
| `get_drum_pads` | lesen | Belegte Pads eines Drum Racks mit Note und Name. |
| `find_browser_items` | lesen | Sucht Presets, Kits und Geräte im Live-Browser nach Namen (`query`, `category`, `limit`, `loadable_only`). |

### Song und Wiedergabe

| Werkzeug | Art | Was es tut |
|---|---|---|
| `set_song` | schreiben | Tempo, Takt (`signature_numerator`/`signature_denominator`), Tonart (`root_note`, `scale_name`, `scale_mode`), Metronom, Loop (`loop`, `loop_start`, `loop_length`). |
| `transport` | schreiben | `action`: Play, Stop, Continue, alle Session-Clips stoppen oder Arrangement-Aufnahme umschalten; `from_beat` als Startpunkt. |
| `launch_clip` | schreiben | Session-Clip starten oder stoppen. |
| `create_scene` / `fire_scene` | schreiben | Szene anlegen (`index`, `name`) / Szene starten. |
| `undo` | schreiben | Rückgängig oder Wiederholen in Live (`action`). |

### Spuren und Clips

| Werkzeug | Art | Was es tut |
|---|---|---|
| `create_track` | schreiben | MIDI- oder Audiospur anlegen (`kind`, `index`, `name`). |
| `update_track` | schreiben | Umbenennen, umfärben (`color_index`), Mute, Solo, Arm, Lautstärke, Pan. |
| `delete_track` | **fragt nach** | Spur samt Clips löschen. |
| `create_clip` | schreiben | Leeren MIDI-Clip in einen Session-Slot legen (`length`, `name`). |
| `update_clip` | schreiben | Clip umbenennen, umfärben, Loop (`looping`, `loop_start`, `loop_end`). |
| `delete_clip` | **fragt nach** | Einen Clip löschen (Session per `slot`, Arrangement per `arrangement_clip`). |
| `edit_notes` | schreiben (als „destruktiv“ markiert, ohne Rückfrage) | Noten **als Diff** hinzufügen (`add`), ändern (`modify`) oder entfernen (`remove`) nach `note_id`. Unberührte Noten behalten Daten und Ids. |
| `write_clip_envelope` | schreiben | Clip-Automation (Punkte oder Formen) auf einen bestehenden Clip schreiben; Geräteparameter und Spurmixer (Lautstärke, Pan, Sends). `clear`, `replace_envelopes`. |
| `edit_arrangement` | schreiben | Im Arrangement: MIDI-Clips mit Noten anlegen, Session-Clips kopieren, Clips **verschieben, tauschen, löschen**, Locators setzen oder löschen. Clip-Aktionen zuerst (ein Undo-Schritt), dann Locators (Transport muss stehen). Ein Clip landet nie auf einem anderen. Take Lanes: `compose_takes`. |

### Mixer, Geräte, Klänge

| Werkzeug | Art | Was es tut |
|---|---|---|
| `update_mixer` | schreiben | Lautstärke (`volume` normalisiert oder `volume_db`), Pan, Sends, Mute, Solo, Crossfader, Routing (`input_routing`, `input_channel`, `output_routing`, `output_channel`). Für Spuren, Returns und Master. |
| `create_return_track` | schreiben | Return-Spur anlegen, optional mit einem Live-Gerät (`device`). |
| `insert_device` | schreiben | Natives Live-Gerät einfügen (`name`, `index`), auf einer Spur, einem Return (`return_track`) oder dem Master (`master`). |
| `load_browser_item` | schreiben | Browser-Eintrag auf eine Spur laden (`path`); ein Instrument oder Kit ersetzt das vorhandene Instrument. |
| `set_device_parameter` | schreiben | Einen Geräteparameter setzen (`parameter`, `value` oder `display`). |
| `update_rack` | schreiben | Macros setzen, Ketten ändern oder eine Kette hinzufügen. |
| `run_batch` | **fragt nach**, wenn ein Löschen enthalten ist | Mehrere Operationen **atomar in einem Undo-Schritt** (`ops`, `label`). |

### Komponieren und Bearbeiten

| Werkzeug | Art | Was es tut |
|---|---|---|
| `compose` | **fragt nach** (beim Ersetzen) | **Ein Teil** als neuer MIDI-Clip in Tonart und Takt des Sets. `kind`: `drums` (Muster auf den Pads des Drum Racks), `bass` (folgt den Akkorden, rastet auf die Kick ein oder weicht ihr aus), `chords` (stimmgeführt), `melody` (Motive A A' A B). Wichtige Felder: `bars`, `seed`, `style`, `density`, `swing`, `progression`, `chords_from`, `follow_kick`, `if_exists` (`error`, `replace`, `merge`), `preview`. Details in [Kapitel 8 des Handbuchs](BENUTZERHANDBUCH.md#8-teile-und-ganze-songs-komponieren). |
| `transform_notes` | **fragt nach** (beim Ersetzen) | Bearbeitet einen Clip **als Diff**: `humanize`, `quantize`, `invert` (diatonisch), `arpeggiate`, `variation`, `transpose` (`semitones` chromatisch **oder** `steps` in der Tonart). Nur ein Teil: `half` (`first`/`second`) oder `from_bar`/`to_bar` (Takte **des Clips**), oder `note_ids`. `preview` zeigt vorher, was passiert. |
| `plan_changes` | lesen | Plant mehrere Schritte (Drums, Bass, Akkorde, Melodie, Transform) **ohne etwas zu ändern**. Spätere Schritte sehen frühere (der Bass kann der geplanten Kick folgen; Akkorde werden geteilt). Liefert eine Vorschau und eine `plan_id`. |
| `plan_song` | lesen | Plant einen **ganzen Song** nach Genre (`house`, `melodic_techno`, `peak_time_techno`, `drum_and_bass`, `trap`): Abschnitte, Locators, Spuren (fehlende werden angelegt), optional Mix, Automation, Sidechain, FX. Felder: `length` (`radio`/`standard`/`extended`) oder `minutes`, `start_bar`, `roles`, `clips`, `create_missing`, `sounds`, `mix`, `fx`, `sidechain`, `progression`, `set_tempo`, `reference`, `seed`. Liefert Vorschau und `plan_id`; **bis `apply_plan` ändert sich nichts**. |
| `measure_master` | lesen | Liest die **Lautheit des Masters** vom Gerät MidiBakery Loudness Meter (letztes Gerät auf dem Master): Momentary, Short-term und Integrated LUFS (BS.1770), Sample-Peak, gemessene Sekunden, ob Live gerade spielt. `reset=true` startet Integrated und Peak neu. Ohne das Gerät: Fehler mit dem Hinweis, wo es im Browser liegt. |
| `plan_master` | lesen | Plant eine **Master-Kette** (EQ Eight mit Low Cut, Glue Compressor, Limiter mit -1 dB True Peak) mit den Werten des Genres (`genre`, optional; `ceiling_db`). Ein Startpunkt: Sie hört nichts und macht nicht lauter. Liefert Vorschau und `plan_id`; `apply_plan` schreibt sie in zwei Undo-Schritten. Ein Master mit Limiter, EQ Eight oder Glue Compressor bleibt unberührt. |
| `apply_plan` | **fragt nach** (beim Ersetzen von Noten) | Schreibt einen Plan als **einen Undo-Schritt** nach Live. Schlägt mit `CONFLICT` fehl, wenn sich ein Ziel-Clip seit der Planung geändert hat; dann neu planen. |
| `compose_takes` | schreiben | Mehrere **Varianten** eines Teils (`kind`: Hook, Melodie, Bass, Akkorde, Drums; `count`) über denselben Akkorden, jede auf einer **Take Lane** im Arrangement (Live 12.2+), zum Comping in Live. Ein Undo-Schritt. |

### Vorschau (Piano Roll)

`compose` und `transform_notes` zeigen mit `preview=true` die Änderung, ohne zu schreiben; `plan_changes` und `plan_song` tun das immer. In Programmen, die **MCP Apps** verstehen, erscheint dazu ein kleines **Piano Roll** (vorher/nachher, Ressource `ui://midibakery/piano-roll.html`). In anderen gibt es eine Textzusammenfassung. Geschrieben wird erst mit `apply_plan`.

### Fehler, die du sehen kannst

| Meldung | Bedeutung |
|---|---|
| `CANCELLED` | Du hast die Rückfrage abgelehnt; nichts wurde geändert. |
| `CONFLICT` | Ein Ziel hat sich seit der Vorschau geändert, oder ein Clip würde auf einen anderen fallen. Neu planen. |
| Verbindung zu Live | Live läuft nicht oder das Remote Script ist aus ([Probleme lösen](BENUTZERHANDBUCH.md#14-probleme-lösen)). |
| Eingabe abgelehnt | Eine Angabe passt nicht (z. B. `slot` **und** `arrangement_clip`, `to_bar` vor `from_bar`, Akkordbereich unter einer Oktave). Die Meldung sagt, was zu ändern ist; Claude korrigiert das meist selbst. |

### Für Entwickler

- Befehle: `midibakery mcp` (stdio), `midibakery mcp --http [--port 8765]`.
- Der Server ist `midibakery.mcp.server.build_server`; die Operationen an Live stehen im Katalog `midibakery.catalog` und werden über die Brücke (Port 47681, Token in `bridge.json`) an das Remote Script gegeben. Mehr in [ARCHITEKTUR.md](../ARCHITEKTUR.md).
- Dieselben Werkzeuge nutzt der Chat-Agent (`midibakery chat` im Terminal, oder das Chat-Gerät); sie sind **nicht** doppelt gepflegt.
