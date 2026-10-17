# MidiBakery – wie die Teile zusammenspielen

MidiBakery besteht aus fünf Teilen:

- **Remote Script** in Live: steuert das Live-Set.
- **Core** in Python: Kompositions-Engine, MCP-Server, Agent und lokale API.
- **Chat-Gerät**: Max-for-Live-Gerät für den Chat.
- **Generator** und **Transform**: zwei Max-for-Live-MIDI-Tools in der Clip-Ansicht.
- **Reference**: Max-for-Live-Audio-Effekt, der einen Referenzsong im Arrangement analysiert.

Den Live-Set verändert nur das Remote Script; alle anderen Teile reden mit ihm oder mit der API. Einzige Ausnahme: Die MIDI Tools geben ihre Noten über Lives eigenen MIDI-Tool-Mechanismus zurück.

```mermaid
flowchart LR
  subgraph Live["Ableton Live 12"]
    RS["Remote Script<br/>(Control Surface 'MidiBakery')"]
    CHAT["Chat-Gerät<br/>(MIDI Effect)"]
    TOOLS["Generator / Transform<br/>(MIDI Tools, Clip-Ansicht)"]
    REF["Reference<br/>(Audio Effect)"]
  end
  subgraph Core["midibakery (Python)"]
    MCP["MCP-Server<br/>midibakery mcp"]
    API["Lokale API<br/>midibakery api :8766"]
    AGENT["Agent-Loop"]
    ENGINE["Kompositions-Engine<br/>compose/"]
  end
  CC["Claude Code /<br/>Claude Desktop"]
  LLM["LLM: Claude API,<br/>LM Studio, Ollama"]

  CC -- "MCP (stdio)" --> MCP
  MCP -- "TCP :47681 (NDJSON + Token)" --> RS
  CHAT -- "jweb: HTTP /ui + WebSocket /chat" --> API
  API --> AGENT
  AGENT -- "MCP in-process" --> MCP
  AGENT <--> LLM
  TOOLS -- "node.script: HTTP /miditool/*" --> API
  REF -- "references/*.json" --> MCP
  API --> ENGINE
  MCP --> ENGINE
```

## Die Teile

| Teil | Wo | Sprache | Gestartet von | Spricht mit |
|---|---|---|---|---|
| Remote Script | `packages/remote_script/MidiBakery` → User Library/Remote Scripts | Python 3.11 (Lives eigener Interpreter, nur Standardbibliothek) | Live, wenn „MidiBakery“ als Control Surface gewählt ist | Live Object Model (LOM); nimmt Verbindungen auf `127.0.0.1:47681` an |
| MCP-Server | `packages/core/src/midibakery/mcp` | Python 3.12 | Claude Code / Desktop (`midibakery mcp`, je Session ein Prozess) | Remote Script |
| Lokale API | `packages/core/src/midibakery/api` | Python 3.12 | das Remote Script beim Laden (`launcher.json`) oder du: `uv run midibakery api --provider …` | Remote Script; LLM-Anbieter; Max-Geräte |
| Chat-Gerät | `packages/m4l` → Presets/MIDI Effects/Max MIDI Effect/MidiBakery | Max-Patch, `jweb` (HTML/JS), Node for Max | Live, wenn das Gerät auf einer Spur liegt | API |
| Generator / Transform | `packages/m4l` → MIDI Tools/Max Generators bzw. Max Transformations | Max-Patch, `v8`, Node for Max | Live, wenn das Tool in der Clip-Ansicht gewählt ist | API |
| Reference | `packages/m4l` → Presets/Audio Effects/Max Audio Effect/MidiBakery | Max-Patch, `v8`, `v8ui`, Node for Max | Live, wenn das Gerät auf einer Spur liegt | Live API; schreibt `references/` |

### Remote Script: die einzige Hand am Live-Set

- Läuft **in** Live und führt atomare Operationen aus, zum Beispiel `song.get`, `track.create`, `notes.apply`, `device.insert` oder `batch`. Der Katalog ist in `catalog/ops.py` definiert, die Prüfliste dazu in `manifest.json`.
- Alle LOM-Zugriffe laufen auf Lives Main-Thread. Ein Socket-Thread nimmt Anfragen an, `update_display()` arbeitet sie etwa alle 100 ms ab.
- Jede schreibende Operation ist ein Undo-Schritt; ein `batch` ist ein gemeinsamer Undo-Schritt.
- Manche Änderungen übernimmt Live erst im nächsten Tick, etwa eine neue Abspielposition. Ops wie `arrangement.locators` und `song.position` laufen deshalb über mehrere Ticks: Der Executor setzt sie einmal pro `update_display()` fort und antwortet, wenn Live die Änderung zeigt. Sie laufen nicht in einem `batch`.
- Beim Start schreibt es Port und Token nach `~/Library/Application Support/MidiBakery/bridge.json` (nur für dich lesbar). Clients lesen diese Datei und melden sich mit dem Token an.
- Mehrere Clients gleichzeitig sind erlaubt: der MCP-Server von Claude Code und die API zum Beispiel. Live arbeitet ihre Aufträge nacheinander ab.
- **Events:** Ein Client kann `{"subscribe": ["state"]}` senden. Dann liest `update_display()` etwa alle 200 ms einen kompakten Zustand (Tempo, Taktart, Scale, Transport, Auswahl, was pro Track spielt, startet oder stoppt) und schickt ihn als `state`-Event, sobald er sich ändert. Abfragen statt LOM-Listener: Es gibt nichts an- und abzumelden, wenn Tracks, Clips oder das Set wechseln. Die API folgt diesen Events und zeigt sie in der Statuszeile des Chats.

### Core: Engine, MCP-Server, Agent, API

- **Kompositions-Engine** (`compose/`): Drums, Bass, Akkorde, Melodie und Transformationen. Sie ist skalen- und taktbewusst, und mit demselben Seed entstehen dieselben Noten. Sie berechnet nur Noten und weiß nichts von Live.
- **MCP-Server** (`mcp/`): stellt 36 Tools für Claude bereit, darunter `get_session`, `compose`, `edit_notes`, `plan_changes` und `apply_plan`. Die Schemas kommen aus dem Op-Katalog, Kompositions-Tools rufen die Engine auf, und alles, was Live verändert, geht über den Bridge-Client ans Remote Script.
  - Tool-Budget für lokale Modelle: Tool-Schemas plus Systemprompt bleiben unter 36.000 Zeichen (geprüft in `tests/test_agent.py`), derzeit etwa 32.400. Neue Tools sollten bestehende Schemas teilen, statt Felder zu wiederholen.
- **Agent-Loop** (`agent/`): ein Gespräch mit einem LLM, also Claude über die Anthropic API, LM Studio oder Ollama. Er ruft **dieselben** MCP-Tools auf, nur in-process statt über stdio. Claude Code und das Chat-Gerät haben damit exakt dieselben Fähigkeiten. Lokale Modelle bekommen ebenfalls alle Tools, nur mit knapperen Schemas und Ergebnissen; eine reduzierte Auswahl gibt es auf Wunsch (`tools=small` / `--small`).
- **Lokale API** (`api/`, `127.0.0.1:8766`): das Tor für die Max-Geräte. Das Remote Script startet sie als eigenen Prozess, wenn Live es lädt, und beendet sie mit Live. In Lives Python läuft sie nicht: Sie braucht Python 3.12 und Pakete außerhalb der Standardbibliothek. Läuft auf dem Port schon eine API, etwa von Hand gestartet, bleibt es bei dieser.
  - `GET /ui`: die Chat-Seite (ohne Geheimnisse)
  - `WS /chat`: der Agent im Chat
  - `GET /models`: die Modellauswahl
  - `POST /miditool/generate` und `/miditool/transform`: die Engine für die MIDI Tools
  - `GET /health`
  Port und Token stehen in `api.json`; jede Anfrage braucht den Token.

### Chat-Gerät

- Ein MIDI-Effekt auf einer beliebigen MIDI-Spur; MIDI läuft unverändert durch.
- Links zeigt `jweb` (eingebetteter Browser) die Chat-Seite `/ui`. Der Token steckt im URL-Fragment `#token=…`, das der Browser nie an den Server schickt.
- Rechts liegen native Max-Bedienelemente, weil Live keine Tastatur an `jweb` weiterreicht und Dropdowns darin nicht aufgehen:
  - **Model-Menü** (`umenu`): Die Seite füllt es mit der Liste aus `/models`, die Auswahl geht als `model_index` zurück.
  - **Eingabefeld** (`textedit`): Enter schickt den Text als `chat_input` an die Seite, danach bekommt das Feld den Fokus zurück.
  - **Pop out** öffnet dieselbe Seite im Browser.
- `node.script midibakery-chat.js` liest `api.json`, gibt `jweb` die URL und sendet sie erneut, bis die Seite „loaded“ meldet. Ändert sich der Token, etwa bei einem Neustart der API, lädt es die Seite automatisch neu.

### Generator und Transform (MIDI Tools)

- Sie erscheinen in der Clip-Ansicht unter **Generate** bzw. **Transform** und arbeiten auf dem markierten Zeitbereich in der Skala des Clips.
- Live verlangt pro Apply-Zyklus eine **synchrone** Antwort, die Noten kommen aber per HTTP von der API. Deshalb arbeitet der eingebettete `v8`-Code in zwei Durchgängen:
  1. **Sofort antworten:** mit gecachtem Ergebnis, sonst mit „nichts ändern“.
  2. **Anfrage stellen:** Der Request geht über `node.script midibakery-miditool.js` an die API, und zwar als Max-Dictionary, nicht als Nachricht, weil die Noten eines Clips zu groß dafür sind.
  3. **Erneut auslösen:** Kommt die Antwort, wird sie gecacht, und das Tool löst sich selbst noch einmal aus, außerhalb von Lives Apply-Aufruf. Live übernimmt dann das Ergebnis.
- **Generator:** Ein Generator kann in Live nur hinzufügen. **Replace** (Standard: an) leert den Zeitbereich deshalb vorher über die Live API, einmal pro Apply-Zyklus. Innerhalb eines Zyklus, also beim Drehen an Reglern oder bei Dice, ersetzt Live das eigene Zwischenergebnis immer selbst.
- **Transform:** Die Operation läuft über Note-IDs, Eigenschaften wie Probability bleiben erhalten. Ändert sie nichts, steht der Grund in der Statuszeile.
- Diese Tools benutzen das Remote Script nicht. Sie bekommen die Noten von Live und geben sie an Live zurück; die API rechnet nur.

### Reference (Audio Effect)

- Liegt auf der Audiospur mit dem Referenzsong. Der `v8`-Code sucht über die Live API den längsten Audio-Clip im Arrangement der Spur und liest Datei, Lage, Start-Marker und Warp-Marker.
- `node.script midibakery-reference.js` dekodiert die Datei mit `afconvert` (22,05 kHz mono) und analysiert sie in `reference-analysis.js`, bei gewarpten Clips auf Lives Beat-Raster aus den Warp-Markern, bei ungewarpten auf einem eigenen Raster (Tempo aus dem stärksten Achtel-Puls, Zählzeit eins dort, wo die Tiefen steigen): Energie in vier Bändern pro Takt, Kick aus wiederkehrenden Anstiegen der Tiefen, Tonart aus Chroma und Bass, Abschnitte in 8-Takt-Schritten mit Namen (Intro, Build, Drop, Break, Outro).
- Das Ergebnis zeigt ein `v8ui` an und es landet in `references/<hash>.json`; das MCP-Tool `get_reference` liest es. **Set Locators** setzt nacheinander Locators an die Abschnitte, **Remove Locators** entfernt alle Locators im Bereich des Clips. Live setzt und entfernt Locators nur an der Abspielposition und rastet sie dabei aufs sichtbare Raster ein, deshalb ein Task mit Ticks, der neue und verschwundene Locators an ihren IDs erkennt; der Transport muss stehen.
- Weder API noch Remote Script sind nötig.

## Welcher Prozess hostet was

| Prozess | Gestartet von | Was darin läuft | Ports / Verbindungen |
|---|---|---|---|
| **Ableton Live** | du | Remote Script (Lives Python); Max for Live mit den Patches der drei Geräte und dem `v8`-Code der MIDI Tools | lauscht auf `127.0.0.1:47681` |
| **Max Helper (Renderer)** (Kind von Live) | Live/Max | Chromium für `jweb`: die Chat-Seite und ihr WebSocket | → `:8766` |
| **N4M PM** → je ein **node** pro `node.script` (Kinder von Live) | Node for Max | `midibakery-chat.js` bzw. `midibakery-miditool.js`: Discovery über `api.json`, HTTP der MIDI Tools | → `:8766` |
| **`midibakery api`** | du (Terminal) | lokale API **plus** Agent-Loop, Kompositions-Engine und eine eigene MCP-Server-Instanz, die der Agent direkt im Prozess aufruft | lauscht auf `127.0.0.1:8766`; → `:47681`; → LLM (Claude API, LM Studio `:1234`, Ollama `:11434`) |
| **`midibakery mcp`** (einer pro Claude-Code-/Desktop-Session) | Claude-App | MCP-Server für Claude über stdio, mit eigener Engine | → `:47681`, erst beim ersten Tool-Aufruf |

Der MCP-Code läuft also mehrfach: in der API für den Chat und je Claude-Session als eigener Prozess. Alle Instanzen sind Clients desselben Remote Scripts, das ihre Aufträge in Live nacheinander abarbeitet. Ein `midibakery mcp` läuft mit dem Code des Ordners, in dem die Claude-Session gestartet wurde; Sessions in einem Worktree nutzen also dessen Stand.

## Drei typische Abläufe

**1. Claude Code komponiert:** „Leg auf Spur 1 vier Takte House-Drums an.“

1. Claude ruft das MCP-Tool `compose` mit `kind: "drums"` auf.
2. Der MCP-Server liest per `song.get` und `tracks.list` die Session (Tempo, Skala, Drum-Rack-Pads), und die Engine erzeugt die Noten.
3. Der MCP-Server schickt einen `batch` mit `clip.create` und `notes.apply` ans Remote Script.
4. Live legt den Clip in einem einzigen Undo-Schritt an.

**2. Chat im Gerät:** gleicher Wunsch, im Chat-Gerät getippt.

1. `textedit` schickt `chat_input` an die Seite, die Seite per WebSocket an die API.
2. Der Agent fragt das gewählte LLM, und das LLM ruft `compose` mit `kind: "drums"` auf.
3. Von hier an ist es derselbe Weg wie in Ablauf 1, nur in-process.
4. Destruktive Änderungen fragt die Seite mit „Apply / Cancel“ ab.

**3. MIDI Tool:** Generator → Drums → Generate.

1. Live übergibt Zeitbereich, Skala und Noten an `v8`, und `v8` antwortet sofort leer.
2. Über Node geht `POST /miditool/generate` an die API, die Engine liefert Noten, und `v8` cached sie.
3. Bei aktivem Replace leert `v8` den Bereich, dann löst es das Tool erneut aus und Live fügt die Noten ein.

## Starten und aktualisieren

| Was | Wann nötig | Wie |
|---|---|---|
| Remote Script und Max-Geräte | einmalig; nach Änderungen am Remote Script oder in `packages/m4l` | `uv run midibakery install` (baut die Geräte, installiert beides; `--link` verlinkt das Remote Script), dann Live neu starten bzw. Gerät neu laden. Beim ersten Mal „MidiBakery“ als Control Surface wählen |
| Lokale API | für die Max-Geräte; nach Änderungen im Core | `uv run midibakery api --provider lmstudio` (oder `anthropic`, `ollama`), danach neu starten. Die Geräte übernehmen den neuen Token selbst. |
| Chat-Seite | nach Änderungen an `chat.html` | Die API liefert sie neu aus; das Chat-Gerät muss neu geladen werden (löschen und neu einfügen). |
| Installierte Version (Paket) | wenn eine neue erscheint | Die API fragt einmal am Tag bei `updates.klirrwerk.com` nach; About-Zeile und Chat-Gerät zeigen das Update, *Install* lädt den Installer, prüft ihn gegen das signierte Manifest und öffnet ihn. Im Terminal: `midibakery update`. Details: `services/updates/README.md` |
| MCP für Claude Code | einmalig | `claude mcp add midibakery -- uv --directory <Repo> run midibakery mcp`; nach Core-Änderungen eine neue Claude-Code-Session starten |

## Wo man nachsieht, wenn etwas hakt

| Datei / Ort | Inhalt |
|---|---|
| `~/Library/Application Support/MidiBakery/bridge.json` | Port und Token des Remote Scripts; fehlt die Datei, läuft es nicht |
| `~/Library/Application Support/MidiBakery/api.json` | Port und Token der API |
| `~/Library/Application Support/MidiBakery/device-chat.log` | Chat-Gerät: gesendete URLs, Meldungen von `jweb`, Seitengröße (Token geschwärzt) |
| `~/Library/Application Support/MidiBakery/device-miditool.log` | Generator/Transform: Anfragen, Antwortzeiten, Fehler mit Schritt |
| `~/Library/Application Support/MidiBakery/device-reference.log` | Reference: analysierte Clips, Dauer, Fehler |
| `~/Library/Application Support/MidiBakery/references/` | Analysen des Reference-Geräts |
| Terminal mit `midibakery api` | Aufrufe an LM Studio/Ollama, Fehler der API |
| Lives `Log.txt` | Meldungen des Remote Scripts (`MidiBakery: …`) |
| `uv run midibakery ping` | prüft die Verbindung zum Remote Script |

## Sicherheit in Kürze

- Alles bindet nur an `127.0.0.1`.
- Remote Script und API verlangen jeweils einen zufälligen Token aus einer Datei, die nur dein Benutzer lesen kann.
- Die Chat-Seite enthält keinen Token; das Gerät übergibt ihn im URL-Fragment.
- Logs schwärzen den Token.
- Lizenz: Testphase und Lizenz sind vom Dienst signierte Tokens, die die App offline prüft; gebunden an einen Hash der Rechner-ID, nichts Persönliches. Ohne Lizenz bleiben Lesen und Undo möglich, ein Set wird nie verändert.
- Updates: Ein Installer wird nur geöffnet, wenn das Manifest mit einem in der App hinterlegten Ed25519-Schlüssel signiert ist und die SHA-256 der Datei passt. Der Update-Check schickt nur Version, System, Architektur und Kanal; `midibakery update --disable` schaltet ihn ab.
- Cloud-LLMs (Claude) bekommen Session-Informationen wie Spurnamen, Noten und Tempo. Mit LM Studio oder Ollama bleibt alles lokal.
