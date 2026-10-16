# MidiBakery – Konzept: KI-Steuerung & Komposition für Ableton Live 12 Suite

MidiBakery ist ein Tool von Klirrwerk.

## Context

`ableton-mcp` (Fork jpoindexter) zeigt die Idee: Ein LLM steuert Ableton Live über einen MCP-Server und ein Remote Script. Die Umsetzung ist für ein Produkt aber nicht tragfähig:
- LOM-Lesezugriffe laufen außerhalb von Lives Main-Thread.
- Es gibt kein Message-Framing; Fehler werden als `success` gemeldet.
- Drei Tool-Listen werden von Hand gepflegt (MCP, REST, M4L), das Ausführungsmodul im M4L-Gerät ist ein Stub.
- Die alte Notes-API zerstört Note-IDs und Undo-Schritte.
- Es gibt keine Events, die „KI-Helfer“ sind bloße Zufallsgeneratoren.

MidiBakery übernimmt nur die Idee und baut sie neu: als **kommerzielles Produkt**, in **Python**, für **Claude via MCP, Chat direkt in Live und lokale LLMs (Ollama)**, mit Schwerpunkt **Komposition/MIDI und Session-Fernsteuerung**.

Ausgangslage auf deinem Rechner: Live **12.4.6 Suite** (Python 3.11 im Remote-Script-Host, `ableton.v3` vorhanden) und Max **9.2.0**.

Wichtige Erkenntnisse aus der Recherche:
- **Live 12 LOM:**
  - `Song.scale_name`, `scale_mode`, `scale_intervals` und `root_note`, dazu `tuning_system`
  - `Track.create_midi_clip` (12.1.10)
  - Take Lanes über die API (12.2)
  - Clip-Automation im Arrangement: Live legt Hüllkurven nur auf Session-Clips an. Ein `add_clip` mit `envelopes` entsteht deshalb in einem freien Slot und wird ins Arrangement kopiert. Die Werte sind absolut (in Live 12.4.6 gemessen).
  - `Track.insert_device` / `RackDevice.insert_chain` / `DrumChain.in_note` (12.3): native Devices lassen sich ohne Browser einfügen
  - `SimplerDevice.replace_sample` (12.4)
  - `Application.browser.load_item`: lädt Kits und Presets wie ein Doppelklick auf die gewählte Spur. Ein Instrument oder Kit ersetzt das Instrument, ein Effekt wird angehängt, und jeder Load ist ein eigener Undo-Schritt. In Live 12.4.6 stürzte Live ab, wenn ein frisch geladenes Rack sofort wieder ersetzt wurde. `browser.load` wartet deshalb, bis die Kette stabil ist, und lässt mindestens 1 s zwischen zwei Loads. `plan_song` lädt auf neue Spuren das Kit und die Presets des Genres aus der Core Library und legt die Drum-Noten auf die Pads des Kits.
  - `Song.create_return_track` schließt in Live 12.4.6 den offenen Undo-Schritt: Was ein Batch nach dem letzten neuen Return ändert, ist ein zweiter Schritt. `plan_song` zählt das beim Zurückrollen mit.
  - Notes-API mit IDs (`get_notes_extended`, `add_new_notes`, `apply_note_modifications`), dazu Probability und Velocity Deviation
- **Max 9.1+:**
  - Node for Max nutzt Node 22; die Objekte `v8` und `v8ui` laufen auf ES6+.
  - MIDI Tools (`live.miditool.in/out`, Generator/Transformation) bekommen Kontext mit Scale, Grid und Seed.
  - Node selbst hat keinen direkten Zugriff auf die Live API, das geht nur über `v8`.
- **Ableton Extensions SDK** (JS/TS, Beta seit 12.4.5): ein offizieller neuer Weg. Die Doku ist nur mit Beta-Anmeldung zugänglich, deshalb wird er hier als zukünftiger Adapter vorgesehen und nicht als Basis.
- **MCP-Spec 2026-07-28:**
  - Das Protokoll ist zustandslos; es gibt `server/discover` und `subscriptions/listen`.
  - Statt Elicitation gibt es `input_required`; lange Jobs laufen über die Tasks-Extension.
  - Sampling, Roots und Logging sind deprecated.
  - MCP Apps (`ui://`) erlauben eigene UIs, etwa eine Piano-Roll-Vorschau.
  - Python-SDK v2 heißt `MCPServer` (früher `FastMCP`).
- **Tool-Anzahl:** Bei mehr als 30–50 Tools sinkt die Trefferquote. Besser sind wenige grobe Tools, Ressourcen und Plan/Apply.
- **Wettbewerb:**
  - Producer Pal (M4L, GPL, kostenlos)
  - ulm0/ableton-live-mcp (Extensions SDK)
  - AbletonOSC-Derivate
  - SMYLZ Producer (kommerziell, bei dir installiert)
  - Anthropics offizieller Ableton-Connector liefert nur Doku und steuert Live nicht.
  - **Differenzierung:** musikalisch intelligente Kompositions-Engine, sauberes Undo/Diff-Verhalten, MIDI Tools direkt im Clip-View, lokal und offline nutzbar.

## Umsetzungsvarianten (Überblick)

| | A: Remote Script + Python-Core + M4L-Frontends (**empfohlen**) | B: Extensions SDK (TS) | C: Reines M4L (Node + v8) |
|---|---|---|---|
| Sprache | Python (Core), Python 3.11 (Bridge), JS nur für die UI | TypeScript | JavaScript |
| LOM-Abdeckung | vollständig, inkl. Listener | laut Ableton breit, Details unklar (Beta) | vollständig über `v8`, Bridge zu Node nötig |
| Persistenz/Headless | läuft dauerhaft, ohne UI | Ausführungsmodell unklar | nur, solange das Gerät im Set liegt |
| Komposition in Python (music21, numpy …) | ja | nein | nein |
| Kommerzielle Risiken | gering, etablierter Weg | Beta, SDK-Lizenzbedingungen unklar | gering, aber Producer Pal ist starker Gratis-Konkurrent |

**Empfehlung A.** Die Bridge bekommt eine eigene Schnittstelle (`LiveBackend`), damit sich B später als zweiter Adapter ergänzen lässt.

## Empfohlene Architektur (Variante A)

```
Claude Desktop/Code ─MCP (stdio | Streamable HTTP)─┐
Ollama / Anthropic API ◄── Agent-Loop ─────────────┤
M4L Chat-Device (v8ui + Node) ─WebSocket───────────┤
M4L MIDI Tools (Generator/Transform) ─WebSocket────┤
                                                    ▼
                        midibakery-core (Python 3.12+, uv)
                         ├─ catalog/  Single Source of Truth (Pydantic-Schemas aller Ops)
                         ├─ bridge/   async Client, NDJSON + Request-IDs, Events
                         ├─ compose/  Musik-Engine (Theorie, Generatoren, Transformationen)
                         ├─ agent/    Provider-Abstraktion (Anthropic, Ollama), Tool-Loop
                         ├─ mcp/      MCP-Server (Spec 2026-07-28, Python-SDK v2)
                         └─ api/      lokaler HTTP/WebSocket-Server für M4L
                                                    │ TCP 127.0.0.1, Token-Auth, NDJSON
                                                    ▼
                  MidiBakery Remote Script (ableton.v3, keine Fremd-Dependencies)
                         ├─ Op-Registry (Decorator, Schema-validiert)
                         ├─ MainThreadExecutor (Queue → schedule_message)
                         ├─ Listener → Event-Stream
                         └─ Undo-Klammer (begin/end_undo_step)
```

### Leitprinzip: „dumme Bridge, schlaue Core“
- **Remote Script:**
  - So klein wie möglich, nur Standardbibliothek; es läuft in Lives Python 3.11.
  - Es führt atomare LOM-Ops aus, validiert sie und meldet strukturierte Fehler (`code`, `message`, `details`).
  - **Alle** LOM-Zugriffe laufen auf dem Main-Thread: Socket-Thread → Queue → `schedule_message(0, drain)`.
  - Ergebnisse gehen per Future mit Request-ID zurück; ein Timeout bricht die Op ab, statt sie still nachzuholen.
- **Batch-Op:** Mehrere Ops laufen in **einem** Main-Thread-Tick und als **ein** Undo-Schritt.
- **Framing:** NDJSON mit `{"id","op","params"}` und `{"id","ok","result"|"error"}`, dazu Events als `{"event","data"}`.
- **Sicherheit:** Die Bridge bindet nur an Loopback. Beim Start erzeugt sie ein Token und legt es in `~/Library/Application Support/MidiBakery/` ab; die Core liest es von dort.

### Single Source of Truth: `catalog/`
- Jede Op wird einmal definiert: Name, Pydantic-Parameter, Ergebnis-Schema, `read_only` / `destructive`, Timeout-Klasse und Kategorie.
- Daraus wird erzeugt:
  1. das Op-Manifest der Remote-Script-Registry (JSON, gegen das die Bridge validiert)
  2. MCP-Tools inkl. `outputSchema` und Annotations
  3. Tool-Definitionen für Ollama und die Anthropic API
  4. die TypeScript-Typen für die M4L-Clients
- Ein CI-Check stellt sicher, dass Bridge-Registry und Katalog übereinstimmen.

### Tool-Design für LLMs (~25–35 Tools statt 200)
- **Ressourcen / Lese-Tools:**
  - `session_overview` (Tempo, Scale, Tracks, Szenen, Selektion)
  - `track_detail`, `clip_notes`, `device_params`, `browser_search`
  - Abgerufen wird kompakt; Seitenweise-Laden (Pagination) und Felder-Filter sind optional.
- **Grobe Schreib-Tools:**
  - `edit_tracks`, `edit_clips`, `edit_notes` (Diff über Note-IDs: add/modify/remove)
  - `devices` (insert/param/rack), `transport`, `scenes`, `mixer`, `arrangement`
- **Kompositions-Tools:**
  - `compose` (kind drums, bass, chords oder melody; bis Teil B des Reviews vier eigene Tools), `transform_notes` (humanize, quantize, invert, arpeggiate, variation)
  - Alle sind scale- und kontextbewusst und reproduzierbar über einen Seed.
- **Plan/Apply:**
  - `plan_changes` liefert eine Vorschau als Diff (bei MCP Apps auch als Piano-Roll).
  - `apply_plan` führt den Plan als ein Undo-Schritt aus.
  - Destruktive Ops verlangen Bestätigung über `input_required`.
- **Escape-Hatch:** `lom_call` (Path / Property / Function) für Power-User. Standardmäßig aus, per Einstellung aktivierbar.

### Kompositions-Engine `compose/` (Kern-Differenzierung)
- **Musiktheorie:**
  - Skalen kommen aus `Song.scale_intervals` statt aus hartkodierten Listen.
  - Akkorde, Funktionsharmonik, Voice-Leading und Rhythmus-Raster (inkl. Taktart und Swing).
- **Drum-Mapping:** Drum-Rack-Pads werden über Namen und `DrumChain.in_note` erkannt, nicht über feste GM-Noten.
- **Generatoren:**
  - regelbasiert und kontextbewusst (bestehende Clips als Kontext: Akkorde erkennen, Bass folgt Kick)
  - Seed-basiert
  - Probability und Velocity Deviation werden genutzt.
- **Optionale ML-Stufe:** kleine lokale Modelle, z.B. für Groove-Extraktion. Erst ab Phase 3.
- **Bibliotheken:** zuerst reines Python oder numpy. Die Lizenzen von music21 (BSD) und anderen werden geprüft.

### Frontends in Live (Max 9)
1. **MidiBakery Chat (Audio-/MIDI-Effekt-AMXD):**
   - `v8ui` als Chat-Oberfläche, Node for Max als WebSocket-Client zur Core.
   - Die Agent-Logik läuft in der Core, nicht im Gerät.
   - Das Gerät zeigt Plan-Diffs an und hat einen Apply/Undo-Button.
2. **MidiBakery MIDI Tools (Generator + Transformation):**
   - `live.miditool.in` → Node → Core `compose/*` → `live.miditool.out`.
   - Damit sind KI-Generatoren direkt im Clip-View nutzbar und bekommen Scale, Grid und Seed von Live.
   - Gleicher Code wie die MCP-Kompositions-Tools.

### Agent / LLM-Provider (`agent/`)
- Provider-Interface mit zwei Implementierungen: **Anthropic** (Default `claude-sonnet-5-5`, wählbar `claude-opus-5-5`) und **Ollama** (lokal).
- Der Tool-Loop nutzt dieselben Katalog-Tools. Lokale Modelle bekommen dieselben Tools; ein reduziertes Tool-Set für Modelle mit kleinem Kontext ist optional.
- Bei der Umsetzung wird die `claude-api`-Skill-Referenz für die SDK-Nutzung herangezogen.

## Kommerzielle Aspekte
- **Lizenz:** proprietär. Kein Code aus ableton-mcp (MIT) und **keiner aus Producer Pal (GPL-3.0)**, nur Ideen. Abhängigkeiten nur unter permissiven Lizenzen (Lizenz-Scan in CI).
- **Marke:** nur „for Ableton Live“, kein Ableton-Logo; keine Aussagen, dass das Produkt offiziell von Ableton stammt.
- **Distribution:**
  - signierter und notarisierter macOS-Installer (`.pkg`), später auch Windows.
  - Der Installer kopiert das Remote Script in `User Library/Remote Scripts`, die AMXDs in die User Library und die Core als gebündelte App (z.B. PyInstaller oder `uv`-Bundle) mit Menüleisten-Status.
- **Lizenzierung:**
  - Lizenzschlüssel mit Offline-Grace-Period.
  - Der Lizenzserver ist ein späteres eigenes Thema; Cloudflare Worker sind dafür eine mögliche Option.
- **Versionsmatrix:**
  - Mindestens Live 12.3, wegen `insert_device`; Feature-Flags erkennen, was die jeweilige Live-Version kann.
  - Getestet wird gegen 12.3, 12.4.x und Max 9.1/9.2.
- **Telemetrie:** nur Opt-in. Die Crash-Logs der Core landen lokal.

## Projektstruktur (`/Users/maxx/Development/Ableton/MidiBakery`)
```
MidiBakery/
├─ pyproject.toml / uv workspace
├─ packages/core/src/midibakery/{catalog,bridge,compose,agent,mcp,api}/
├─ packages/remote_script/MidiBakery/  (__init__.py, registry.py, executor.py, ops/*.py, listeners.py)
├─ packages/m4l/{chat,miditools}/      (.maxpat-Quellen, v8/Node-JS, Build-Skript → .amxd)
├─ tools/codegen/                      (Katalog → Manifest, MCP, TS-Typen)
├─ tests/{unit,contract,live_smoke}/
└─ installer/
```
`ableton-mcp/` bleibt nur als Referenz liegen und wird nicht eingebunden; in `.gitignore` aufnehmen oder auslagern.

## Roadmap
1. **Fundament (MVP-Kern):**
   - Katalog plus Codegen.
   - Remote Script mit Registry, MainThreadExecutor, NDJSON und Token.
   - ~15 Ops: Session lesen, Tracks/Clips anlegen, Notes per Diff, Tempo/Transport, Device einfügen.
   - Core-Bridge-Client.
   - MCP-Server über stdio für Claude Desktop/Code.
2. **Komposition:** `compose/` mit Drums, Bass, Chords, Melody und Transform; Plan/Apply mit Undo; MCP-Apps-Vorschau.
3. **Live-Frontends:** Chat-AMXD und MIDI-Tools-AMXDs, Agent-Loop mit Anthropic und Ollama.
4. **Abdeckung & Events:** Mixer/Routing, Racks, Arrangement, Take Lanes, Listener-Events über `subscriptions/listen`.
   - Reihenfolge, je ein PR: Events → Mixer/Routing → Racks → Arrangement → Take Lanes.
   - Events: im Chat-Gerät zunächst nur eine Statuszeile (Transport, Tempo, Scale, was spielt).
   - Arrangement: Die Engine baut ganze Songstrukturen (Intro, Build, Drop, Break …), mit eigenen Struktur-Vorlagen pro Genre.
   - Take Lanes: `compose_takes` legt mehrere Varianten eines Parts (Hook, Melodie, Bass, Chords, Drums) über dieselben Akkorde in eigene Take Lanes, damit man in Live comppen kann. Ein Undo entfernt alle Takes. Das braucht Live 12.2 oder neuer; die Lanes sind in Live erst über „Show Take Lanes“ (⌘⌥U) sichtbar.
5. **Produktisierung:** Installer, Signierung, Lizenz, Doku, Beta-Programm.
6. **Optional:** Extensions-SDK-Adapter, sobald die SDK-Doku zugänglich und stabil ist.

## Verifikation
- **Unit:** `compose/` (deterministisch über Seed, Theorie-Checks), Katalog-Schemas, Codegen-Snapshots (`uv run pytest`).
- **Contract:** Eine Fake-LOM (Python 3.11) lädt das echte Remote Script, und jede Katalog-Op wird gegen Schema und Fehlercodes getestet. Das schließt die Lücke von ableton-mcp, wo das Remote Script ungetestet war.
- **Live-Smoke:** Ein Skript verbindet sich mit dem laufenden Live 12.4.6 und führt Ops in einem Test-Set aus: anlegen → prüfen → Undo → prüfen.
- **MCP:** Abnahme mit MCP Inspector und Claude Code (`claude mcp add midibakery …`), dabei Prompts wie „4-taktiges Deep-House-Pattern in der Session-Scale“.
- **M4L:** Die AMXDs in Live laden und Chat sowie MIDI-Tool-Apply im Clip-View testen.
- **Stabilität:** 1.000 Ops im Batch ohne Crash, keine LOM-Aufrufe außerhalb des Main-Threads (Assertion im Executor).

## Erster Umsetzungsschritt nach Freigabe
Phase 1: Repo-Gerüst (uv-Workspace), Katalog mit ~15 Ops, Remote Script mit `ableton.v3`, Bridge-Client und MCP-Server über stdio. End-to-End-Test: Claude Code legt einen MIDI-Clip in der Session-Scale an.
