# MidiBakery – Benutzerhandbuch

Für Musikerinnen und Musiker, die mit Ableton Live 12 arbeiten und noch am Anfang der Musikproduktion stehen. Du musst nichts programmieren können. Alles, was hier steht, kannst du in Live und im Chat von MidiBakery nachmachen.

English version: [USER_GUIDE.md](USER_GUIDE.md)

**Inhalt**

1. [Was ist MidiBakery?](#1-was-ist-midibakery)
2. [Was du brauchst](#2-was-du-brauchst)
3. [Installieren und aktualisieren](#3-installieren-und-aktualisieren)
4. [In Live einrichten](#4-in-live-einrichten)
5. [Eine KI wählen](#5-eine-ki-wählen)
6. [Der Chat: erste Schritte](#6-der-chat-erste-schritte)
7. [Beispiele: was du fragen kannst](#7-beispiele-was-du-fragen-kannst)
8. [Teile und ganze Songs komponieren](#8-teile-und-ganze-songs-komponieren)
9. [Clips bearbeiten](#9-clips-bearbeiten)
10. [Das Arrangement](#10-das-arrangement)
11. [Der Reference Analyzer](#11-der-reference-analyzer)
12. [Mixen und Klänge](#12-mixen-und-klänge)
13. [Generator und Transform ohne Chat](#13-generator-und-transform-ohne-chat)
14. [Probleme lösen](#14-probleme-lösen)
15. [Häufige Fragen](#15-häufige-fragen)
16. [Kleines Wörterbuch](#16-kleines-wörterbuch)
17. [MidiBakery aus Claude Desktop oder Claude Code benutzen](#17-midibakery-aus-claude-desktop-oder-claude-code-benutzen)

---

## 1. Was ist MidiBakery?

MidiBakery ist ein KI-Assistent, der **in** Ableton Live 12 sitzt. Du schreibst ihm in normalen Sätzen, was du möchtest, zum Beispiel „Mach mir vier Takte Deep-House-Drums auf Spur 1“, und er legt die Noten direkt in dein Live-Set. Er kann:

- **Teile komponieren:** Drums, Bass, Akkorde und Melodien, passend zur Tonart und zum Takt deines Sets.
- **Ganze Songs bauen:** Intro, Build, Drop, Break und Outro im Arrangement, nach Rezepten für fünf Genres (House, Melodic Techno, Peak-Time Techno, Drum & Bass, Trap).
- **Vorhandene Clips verändern:** variieren, transponieren, vermenschlichen, nur die zweite Hälfte ändern.
- **Live steuern:** Spuren, Clips, Tempo, Mixer, Effekte, Automation.
- **Einen Referenzsong zerlegen:** Das Gerät *Reference Analyzer* zeigt, wie ein Song aufgebaut ist, und MidiBakery kann deinen Song danach aufbauen.

MidiBakery erzeugt **MIDI-Noten** (und lädt Klänge aus Lives Bibliothek). Es erzeugt kein Audio und lädt keine eigenen Samples.

Alles, was MidiBakery tut, ist ein Schritt in Lives Rückgängig-Liste. Du kannst es immer zurücknehmen.

MidiBakery besteht aus vier Teilen, die du in Live siehst:

| Teil | Wofür |
|---|---|
| **Remote Script** „MidiBakery“ | die Verbindung zu Live (unsichtbar, einmal einstellen) |
| **MidiBakery Chat** | das Chat-Gerät: hier sprichst du mit der KI |
| **MidiBakery Generator** und **MidiBakery Transform** | zwei Werkzeuge in der Clip-Ansicht, ohne KI und ohne Chat |
| **MidiBakery Reference Analyzer** | analysiert einen Referenzsong |
| **MidiBakery Loudness Meter** | misst die Lautheit des Masters (LUFS) |

## 2. Was du brauchst

- **Ableton Live 12 Suite** (Live 12.3 oder neuer; die Take Lanes brauchen 12.2 oder neuer). In der Suite ist **Max for Live** enthalten, das die Geräte brauchen.
- **macOS** (Apple Silicon oder Intel) oder **Windows**.
- **Eine KI**, siehe [Kapitel 5](#5-eine-ki-wählen): entweder einen Schlüssel für die Claude-API (Internet nötig) oder ein lokales Modell auf deinem Rechner (kein Internet, keine Kosten pro Frage).
- Das Installationsprogramm von MidiBakery (Kapitel 3).

## 3. Installieren und aktualisieren

Beide Installationsprogramme installieren nur für dein Benutzerkonto. Du brauchst kein Administratorpasswort. Bevor du startest: **Schließe Live.**

### macOS

1. Lade die Datei `MidiBakery-<Version>-macos-arm64.pkg` (Apple Silicon: alle Macs seit 2020 mit M1 oder neuer) bzw. `MidiBakery-<Version>-macos-x64.pkg` (Intel-Macs).
2. Doppelklick auf die Datei und dem Installer folgen.
3. **Wenn macOS die Datei nicht öffnen will** („kann nicht geöffnet werden, da sie nicht von einem verifizierten Entwickler stammt“): Die Installer sind noch nicht von Apple beglaubigt. Das ist bei dieser Version normal. Öffne **Systemeinstellungen > Datenschutz & Sicherheit**, scrolle nach unten und klicke bei der Meldung zu MidiBakery auf **Dennoch öffnen**. Alternativ: Rechtsklick auf die Datei > **Öffnen**.
4. Am Ende zeigt der Installer, was zu tun ist (siehe Kapitel 4).

Das Programm landet in `~/Library/Application Support/MidiBakery/`, das Remote Script und die Geräte in deiner Live-**User Library**.

### Windows

1. Lade `MidiBakery-<Version>-windows-x64-setup.exe`.
2. Doppelklick und dem Setup folgen.
3. **Wenn Windows warnt** („Der Computer wurde durch Windows geschützt“): Auch das Windows-Setup ist noch nicht signiert. Klicke auf **Weitere Informationen > Trotzdem ausführen**.

Das Programm landet in `%LOCALAPPDATA%\Programs\MidiBakery\`. Das Setup kannst du später wie jedes Programm unter **Einstellungen > Apps** entfernen.

### Aktualisieren

MidiBakery fragt einmal am Tag bei `updates.klirrwerk.com`, ob es eine neue Version gibt. Dabei werden nur Version, Betriebssystem, Prozessor-Art und Update-Kanal gesendet.

1. Gibt es ein Update, zeigt das **Chat-Gerät** oben eine Zeile „MidiBakery … is available“.
2. Klicke **Install**. MidiBakery lädt den Installer herunter, prüft seine Signatur und öffnet ihn. Mit **Later** blendest du die Meldung aus.
3. Folge dem Installer. Er aktualisiert die vorhandene Installation und behält deine Einstellungen.
4. **Starte Live neu.**

Die Update-Prüfung abschalten: im Terminal `midibakery update --disable` (wieder an: `--enable`). Nur prüfen, ohne zu installieren: `midibakery update --check`. Im Terminal findest du das Programm bei der Installation unter `~/Library/Application Support/MidiBakery/runtime/<Version>/midibakery` (macOS) bzw. `%LOCALAPPDATA%\Programs\MidiBakery\runtime\<Version>\` (Windows).

### Deinstallieren

Windows: **Einstellungen > Apps > MidiBakery**. macOS: im Terminal `~/Library/Application Support/MidiBakery/runtime/<Version>/midibakery uninstall` (mit `--purge` löscht es auch Einstellungen und den gespeicherten Claude-Schlüssel). Das entfernt genau das, was die Installation geschrieben hat, und nichts von deiner Musik.

## 4. In Live einrichten

### Schritt 1: Remote Script einschalten (nur beim ersten Mal)

1. **Starte Live** (nach der Installation immer neu starten).
2. Öffne die Einstellungen: macOS **Live > Einstellungen** (⌘,), Windows **Optionen > Einstellungen** (Strg+,).
3. Wähle den Bereich **Link, Tempo & MIDI**.
4. Bei **Control Surface** wähle in einer freien Zeile **MidiBakery**. Input und Output kannst du auf *None* lassen.

Damit startet Live auch die MidiBakery-API (das „Gehirn“ im Hintergrund). Sie läuft, solange Live läuft.

### Schritt 2: Geräte finden

Die Geräte liegen in der **User Library** im Live-Browser (links, oder mit der Suche oben: „MidiBakery“):

| Gerät | Ordner | Typ |
|---|---|---|
| MidiBakery Chat | Presets > MIDI Effects > Max MIDI Effect > MidiBakery | MIDI-Effekt |
| MidiBakery Reference Analyzer | Presets > Audio Effects > Max Audio Effect > MidiBakery | Audio-Effekt |
| MidiBakery Loudness Meter | Presets > Audio Effects > Max Audio Effect > MidiBakery | Audio-Effekt |
| MidiBakery Generator | MIDI Tools > Max Generators | MIDI Tool |
| MidiBakery Transform | MIDI Tools > Max Transformations | MIDI Tool |

### Schritt 3: Chat-Gerät auf eine Spur legen

1. Lege eine **MIDI-Spur** an (⌘⇧T bzw. Strg+Shift+T).
2. Ziehe **MidiBakery Chat** auf diese Spur. Du siehst jetzt ein Chat-Fenster in der Geräteansicht. Die MIDI-Noten auf der Spur laufen unverändert hindurch; das Gerät stört nichts.
3. Oben im Fenster steht eine Statuszeile. Wenn dort „Connecting…“ lange stehen bleibt, schau in [Kapitel 14](#14-probleme-lösen).

Du brauchst das Gerät nur **einmal** im Set, auf irgendeiner MIDI-Spur. Am besten legst du dir eine eigene Spur „Chat“ an.

### Schritt 4: Prüfen

Schreibe in das Eingabefeld rechts im Gerät „Hallo“ und drücke Enter. Antwortet die KI, ist alles bereit. Falls nach einem Schlüssel gefragt wird: weiter mit Kapitel 5.

Jedes Gerät hat einen **About**-Knopf. Er zeigt die Versionen von Gerät, API und Remote Script. Sie sollten übereinstimmen.

## 5. Eine KI wählen

Das Chat-Gerät hat ein **Modell-Menü**. Dort stehen die Claude-Modelle und alle lokalen Modelle, die MidiBakery gefunden hat. Du kannst jederzeit wechseln.

| | Claude (Anthropic) | Lokale Modelle (LM Studio oder Ollama) |
|---|---|---|
| Internet | nötig | nicht nötig |
| Kosten | pro Nutzung, über dein Anthropic-Konto | keine, aber dein Rechner arbeitet |
| Datenschutz | Spurnamen, Noten und Tempo deines Sets gehen an Anthropic | alles bleibt auf deinem Rechner |
| Qualität | sehr verlässlich | hängt vom Modell und deinem Rechner ab; kleine Modelle machen mehr Fehler |
| Einrichtung | API-Schlüssel eintragen | Programm installieren, Modell laden |

### Option A: Claude mit eigenem API-Schlüssel

Standardmäßig benutzt MidiBakery **Claude Sonnet 5.5**. Im Menü gibt es auch Claude Opus 5.5 und Claude Haiku 5.5.

1. Erstelle bei Anthropic (console.anthropic.com) ein Konto, hinterlege eine Zahlungsmethode und erzeuge unter **API Keys** einen Schlüssel. Er beginnt mit `sk-ant-`. Das Claude-Abo für den Chat auf claude.ai ist etwas anderes und reicht dafür nicht: die API wird getrennt abgerechnet.
2. Wähle im Modell-Menü ein Claude-Modell. Rechts oben im Chat erscheint der Knopf **Key**.
3. Klicke **Key**. Im Chat-Gerät gibst du den Schlüssel dann **in das Eingabefeld rechts** ein (nicht in das Chat-Fenster) und drückst Enter. Der Schlüssel wird dabei nicht angezeigt und nie an ein Modell geschickt. Im Browser-Fenster (*Pop out*) gibt es ein eigenes Feld.
4. MidiBakery prüft den Schlüssel bei Anthropic und speichert ihn in der **macOS-Schlüsselbundverwaltung** (Dienst „MidiBakery“) bzw. der **Windows-Anmeldeinformationsverwaltung**. Danach steht auf dem Knopf „Key ✓“.
5. Entfernen: **Key** > **Remove**.

Alternativ kennt MidiBakery auch die Umgebungsvariable `ANTHROPIC_API_KEY` und ein Profil von `ant auth login`; im Terminal geht auch `midibakery auth set-key`.

### Option B: Lokale Modelle mit LM Studio

1. Installiere **LM Studio** (lmstudio.ai) und lade ein Modell herunter, das Werkzeuge („tool use“) kann. Beispiele sind Qwen- oder Gemma-Modelle. Probiere aus, welches auf deinem Rechner gut läuft.
2. Starte den **lokalen Server**: in LM Studio im Tab **Developer** „Start Server“, oder im Terminal `lms server start`. MidiBakery erwartet ihn auf `127.0.0.1:1234` (Standard).
3. **Wichtig: Lade das Modell mit großem Kontext.** MidiBakery schickt dem Modell die Beschreibung aller seiner Werkzeuge mit. Das braucht viel Platz („Kontext“). LM Studio lädt Modelle aber mit einem kleinen Standardwert, der dafür nicht reicht. Lade es so:

   ```bash
   lms load <modellname> -c 32768
   ```

   Zum Beispiel für ein Qwen-Modell: `lms load qwen/qwen3-8b -c 32768`. Den genauen Modellnamen zeigt `lms ls`. In der LM-Studio-Oberfläche geht dasselbe über **My Models** > Einstellungen des Modells > **Context Length** = mindestens 32768.
   Reicht der Kontext nicht, sagt dir der Chat das in einer Fehlermeldung („… too small a context for MidiBakery’s tools. Load it with a context length of at least 32768 …“). Dann neu laden und die Nachricht noch einmal senden.
4. Öffne im Chat das **Modell-Menü**: Dort steht jetzt „LM Studio · <Modellname>“. Wähle es.

### Option C: Lokale Modelle mit Ollama

1. Installiere **Ollama** (ollama.com) und lade ein Modell, zum Beispiel `ollama pull qwen3:8b`. Ollama muss laufen (`ollama serve` oder die Ollama-App); MidiBakery erwartet es auf `127.0.0.1:11434`.
2. Wähle im Modell-Menü „Ollama · <Modellname>“.
3. Wenn das Modell ungenau arbeitet, kann Ollamas Standard-Kontext zu klein sein. Stelle ihn in Ollama höher ein.

### Tipps für lokale Modelle

- Lokale Modelle bekommen **alle** Werkzeuge, aber in Kurzform. Sie machen eher Fehler als Claude. Du erkennst das, wenn das Modell etwas behauptet, aber nichts in Live passiert ist. MidiBakery bemerkt das oft selbst und hakt nach.
- Nenne Spur und Abschnitt beim Namen („Drop Bass“). Kurze, klare Aufträge funktionieren besser als lange.
- Eine Aufgabe nach der anderen.
- Bei großen Aufträgen wie ganzen Songs ist ein größeres Modell (oder Claude) verlässlicher.
- Wenn nichts mehr hilft: **New** drücken (vergisst das Gespräch) und neu formulieren.

## 6. Der Chat: erste Schritte

Das Fenster des Chat-Geräts:

| Element | Bedeutung |
|---|---|
| **Punkt und Statuszeile** (oben) | Verbindung zur API; daneben, was Live gerade tut: Tempo, Tonart, was spielt |
| **Modell-Menü** | welche KI antwortet |
| **Stop** | bricht die laufende Antwort ab |
| **Undo** | nimmt die letzte Änderung in Live zurück (dasselbe wie ⌘Z in Live) |
| **Key** | Claude-Schlüssel (nur bei Claude-Modellen) |
| **Copy** | kopiert das ganze Gespräch (Gedanken, Werkzeugaufrufe, Antworten) in die Zwischenablage |
| **New** | vergisst das Gespräch und fängt neu an (dein Set bleibt, wie es ist) |
| **Pop out** (rechts im Gerät) | öffnet denselben Chat im Browser, mit mehr Platz |
| **Eingabefeld** (rechts im Gerät) | hier tippst du; Enter sendet |

**Wichtig:** Live reicht Tastatureingaben nicht an das Chat-Fenster weiter. Tippen kannst du deshalb nur in das **Eingabefeld rechts im Gerät**. Im Browser-Fenster (*Pop out*) hat die Seite ein eigenes Eingabefeld.

**Kopieren:** In Live funktioniert ⌘C im Chat-Fenster nicht. Klicke stattdessen auf eine Antwort oder einen Gedankenblock, dann wird sie kopiert, oder nimm **Copy** für alles.

**Sprache:** Die KI antwortet in der Sprache deiner letzten Nachricht. Schreibe also einfach Deutsch oder Englisch.

### Ein erster Auftrag

1. Lege eine MIDI-Spur mit einem Drum Rack an (zum Beispiel ein Drum Rack aus dem Browser unter *Drums*).
2. Schreibe: **„Mach vier Takte House-Drums auf Spur 2.“** (Spuren zählst du ab 1, so wie Live sie anzeigt.)
3. Du siehst, wie die KI Werkzeuge aufruft („Running compose …“). Danach liegt ein neuer Clip im ersten freien Slot der Spur.
4. Spiele den Clip ab. Gefällt er nicht: **Undo**.
5. Schreibe: **„Nochmal, anders.“** – es entsteht eine neue Idee (anderer „Seed“).

### Vorschau, Apply und Bestätigung

MidiBakery schreibt auf zwei Arten:

- **Direkt:** Ein einzelner Teil („Mach eine Basslinie“) wird sofort geschrieben. Wenn dabei vorhandene Noten ersetzt würden, fragt dich der Chat vorher mit **Apply** und **Cancel**.
- **Mit Vorschau:** Mehrere Teile zusammen, ganze Songs und alles, wo du „erst mal ansehen“ sagst, erscheinen als **Karte im Chat**: ein kleines Piano Roll mit dem, was hinzukommt, oder bei Songs eine Zeitleiste der Abschnitte. **In Live ist dann noch nichts verändert.** Mit **Apply** schreibst du es. Danach steht auf der Karte „✓ applied · Undo reverts it“. Willst du es nicht, lass die Karte einfach liegen.

Du kannst die Vorschau auch ausdrücklich bestellen: „Zeig mir erst eine Vorschau von …“.

**Apply ist ein einziger Undo-Schritt**, auch wenn viele Teile zusammen geschrieben werden. Für ganze Songs (die auch Spuren, Effekte und Returns anlegen) können es ein paar Undo-Schritte sein: Drücke Undo mehrmals, bis alles weg ist.

Wenn sich ein Ziel-Clip zwischen Vorschau und Apply geändert hat, lehnt MidiBakery das ab (Meldung `CONFLICT`). Dann bitte eine neue Vorschau anfordern.

**Sicherheitsfragen:** Vor dem **Löschen von Spuren oder Clips** und dem **Ersetzen von Noten** fragt MidiBakery immer mit Apply/Cancel nach. Lehnst du ab, passiert nichts, und die KI sagt es dir.

### Undo

- Der **Undo**-Knopf im Chat oder ⌘Z / Strg+Z in Live.
- Jeder Schreibzugriff von MidiBakery ist ein eigener Schritt (ein Batch zählt als einer).
- Ob die KI „zurück“ versteht: „Mach das rückgängig“ geht auch.

## 7. Beispiele: was du fragen kannst

Du kannst Deutsch und Englisch mischen. Spuren und Clips kannst du beim Namen nennen („Bass“, „Intro Kick“) oder mit Nummer („Spur 3“, gezählt wie in Live ab 1).

### Fragen und Überblick

- „Was ist in meinem Set?“ / *What is in my set?*
- „Welches Tempo und welche Tonart hat der Song?“
- „Zeig mir die Noten von dem Clip auf Spur 2.“
- „Welche Clips liegen im Arrangement?“
- „Was spielt der Bass im Drop?“

### Drums, Bass, Akkorde, Melodie

- „Mach vier Takte Deep-House-Drums auf Spur 1.“ / *Make 4 bars of house drums on track 1.*
- „Schreib acht Takte Techno-Drums, dünner besetzt und mit etwas Swing.“
- „Trap-Drums mit vielen Hi-Hats, 2 Takte.“
- „Eine Basslinie, die der Kick folgt.“ / *A bassline that locks to the kick.*
- „Bass, der der Kick ausweicht und nur zwischen den Schlägen spielt.“
- „Eine ruhige, lange Basslinie mit gehaltenen Noten.“
- „Vier Akkorde in der Tonart des Sets, immer ein Akkord pro Takt.“
- „Akkorde i – VI – III – VII, als Stabs, mit Vierklängen.“ (Die Römischen Ziffern beziehen sich auf die Tonart des Sets; auch „Am F C G“ geht.)
- „Eine Melodie über diese Akkorde.“ / *A melody over the chords.*
- „Eine Melodie zwischen C4 und C6, nicht zu viele Noten.“
- „Mach Bass, Akkorde und Melodie zusammen, passend zu den Drums auf Spur 1.“ (mehrere Teile: kommt als Vorschau)

### Clips verändern

- „Transponiere den Clip auf Spur 3 eine Oktave nach unten.“ / *Transpose it down an octave.*
- „Um 3 Halbtöne nach oben.“ / *Up 3 semitones.*
- „Zwei Stufen in der Tonart nach oben.“ (Skalenstufen, siehe Kapitel 9)
- „Variiere den Bass ein bisschen.“ / *Give the bass a variation.*
- „Variiere nur die zweite Hälfte.“ / *Vary only the second half.*
- „Humanisiere die Drums, damit sie weniger starr klingen.“
- „Quantisiere die Melodie auf Sechzehntel.“
- „Spiele die Akkorde als Arpeggio, aufwärts, in Sechzehnteln.“
- „Kehre die Melodie um.“ (diatonisch gespiegelt)

### Das Arrangement

- „Baue mir einen House-Song, standard-lang, in der Tonart des Sets.“ / *Build me a house song.*
- „Ein Melodic-Techno-Track, etwa 6 Minuten, mit dem Tempo des Genres.“
- „Ein Drum-&-Bass-Song als Radio-Edit.“
- „Mach Vorschläge für den Bass im Drop: vier Varianten zum Zusammenschneiden.“ (Take Lanes, siehe Kapitel 10)
- „Variiere den ‚Drop Bass‘.“
- „Tausche ‚Intro Bass‘ und ‚Drop Bass‘.“ / *Swap Intro Bass and Drop Bass.*
- „Verschiebe ‚Break Chords‘ auf Takt 41.“
- „Lösche den Clip ‚Outro Hats‘.“
- „Setze einen Marker ‚Drop‘ auf Takt 33.“ (Locator)

### Live steuern

- „Setze das Tempo auf 126.“ / *Set the tempo to 126.*
- „Stelle die Tonart auf A-Moll.“
- „Benenne Spur 4 in ‚Lead‘ um und färbe sie rot.“
- „Lege eine neue MIDI-Spur an.“
- „Starte den Clip in Slot 2 auf Spur 1.“ / „Spiele den Song ab.“ / „Stopp.“
- „Starte Szene 3.“

### Mixen und Klänge

- „Dreh die Lautstärke von Spur 2 um 3 dB runter.“ / *Pull track 2 down by 3 dB.*
- „Pan die Hi-Hats leicht nach rechts.“
- „Stumm schalten: Spur 5.“ / „Solo auf den Bass.“
- „Lege einen Hall als Return an.“ / *Add a reverb return.*
- „Schick die Melodie mit -12 dB in den Hall.“
- „Lade ein 909-Kit auf Spur 1.“ / *Load a 909 kit.* (MidiBakery sucht im Live-Browser)
- „Füge einen Auto Filter auf dem Bass ein.“
- „Fahre den Filter-Cutoff der Akkorde über vier Takte von unten nach oben auf.“ (Clip-Automation)
- „Zeig mir die Parameter des Compressors auf Spur 3.“
- „Leg eine Master-Kette für Peak-Time Techno an.“ / *Set up a master chain for house.* (Vorschau, dann Apply; siehe Kapitel 12)

### Hilfe und Lernen

- „Warum klingt mein Bass matschig?“ — Die KI kann Hinweise geben und Mixer-Werte lesen, aber sie hört den Klang nicht. Entscheide mit deinen Ohren.
- „Was ist ein Drop?“ — Sie erklärt gern.

### Gute Aufträge

- **Konkret:** Spur, Länge, Stil. „4 Takte House-Drums auf Spur 1“ ist besser als „Mach was Cooles“.
- **Ein Teil nach dem anderen**, wenn du es genau willst; **mehrere Teile oder einen Song**, wenn du schnell etwas zum Weiterarbeiten brauchst.
- **Sag, was dir fehlt:** „Der Bass ist zu dicht“, „Mehr Luft in den Drums“ – die KI stellt Dichte, Swing oder Stil nach.
- **Seed:** Jede Idee hat eine Nummer (Seed). „Nimm Seed 42“ bringt dieselben Noten zurück. Wenn dir eine Idee gefallen hat, frage nach ihrem Seed.

## 8. Teile und ganze Songs komponieren

### Einzelne Teile

Einen Teil schreibst du als **neuen Clip in den ersten freien Slot** einer Spur. Vorhandene Clips werden nicht überschrieben, außer du verlangst es (dann fragt MidiBakery nach).

| Teil | Wichtige Stellschrauben (alle in normalen Worten verlangbar) |
|---|---|
| **Drums** | Stil: house, techno, hiphop, trap, rock, breakbeat. Dichte, Swing, Fills am Ende jeder Viertaktphrase, „Chance“ (wie zufällig Ghost-Notes und manche Hi-Hats kommen). Die Noten gehen auf die Pads des **Drum Racks** der Spur; Pads ohne Sound werden ausgelassen. |
| **Bass** | Stil: syncopated, sustained, pulse, offbeat, octave, walking. Oktave. Folgt den Akkorden und auf Wunsch der Kick eines Drum-Clips (einrasten oder ausweichen). |
| **Akkorde** | Rhythmus: sustain, pulse, offbeat, stabs. 3 oder 4 Stimmen, Tonhöhenbereich, Vierklänge, eigene Akkordfolge. |
| **Melodie** | Dichte, Tonhöhenbereich, folgt den Akkorden. Auch als [Gegenmelodie](#gegenmelodie) zu einem Lead. |

Gemeinsam: **Länge** in Takten (Standard 4), **Swing** (wie sehr die Offbeats nach hinten schwingen), **Seed** (reproduzierbar).

**Wie die Teile zusammenpassen:** Bass und Melodie richten sich nach den Akkorden eines Clips („passend zu den Akkorden auf Spur 3“). Der Bass richtet sich nach der Kick eines Drum-Clips. Bittest du um mehrere Teile in einem Auftrag, teilen sie sich dieselbe Akkordfolge.

Alles liegt **in der Tonart und im Takt deines Sets**. Stelle also zuerst Tonart (*Scale* in Live) und Tempo ein.

### Gegenmelodie

Eine zweite Melodie, die auf eine vorhandene Lead-Melodie antwortet. Frage: *„Schreib eine Gegenmelodie zum Lead in Slot 1 von Spur 2“*. Sie kommt in einen neuen Clip, der Lead bleibt unverändert. Ohne Akkorde werden diese aus den Noten des Leads abgeleitet. Der Lead darf auch ein Clip sein, der im selben Auftrag vorher geplant wurde.

Ein Lead im Arrangement, wie `plan_song` ihn schreibt: Frage *„Schreib eine Gegenmelodie zu den Breakdown-Lead-Clips auf einer neuen MIDI-Spur“*. Jeder Clip dieses Namens bekommt an denselben Takten und in derselben Länge einen Gegenclip auf der anderen Spur (*Breakdown Counter*), jeweils über den Akkorden des Akkord- oder Pad-Clips, der dort spielt. Die Lead-Spur allein beantwortet den ganzen Song. Nochmal fragen gibt diesen Clips neue Noten statt einer zweiten Lage.

Modi (in Worten sagen, Standard ist der erste):

- **fill_the_gaps**: spielt nur, wo der Lead eine Note hält oder pausiert.
- **call_and_response**: antwortet in den stillen Schlägen und Takten des Leads.
- **passive_over_active**: ruhige lange Noten über einem lebhaften Lead (mehr Noten über einem sparsamen).
- **contrasting_rhythm**: sparsam, wo der Lead dicht ist, und umgekehrt.
- **harmonic_notes**: geht im Rhythmus des Leads mit, auf einer passenden anderen Note.
- **note_layering**: die Noten des Leads eine Oktave entfernt, gleichzeitig oder verzögert.

Vier feste Figuren (der Lead bestimmt nur Lage und Reibungen; sie folgen nicht seinem Rhythmus):

- **dotted_eighth_pulse**: ein gleichmäßiger punktierter Achtelpuls (3-3-3-3-3-1) auf einem Akkordton pro Takt.
- **scale_staircase**: derselbe Puls, der alle ein bis zwei Takte eine Tonleiterstufe steigt und vor dem Neustart eine Stufe zurückgeht.
- **trance_dotted_eighth_staircase**: die 8-Takt-Figur aus dem Trance-Tutorial: der Puls auf den Stufen 1, 2, 3 und 5, je zwei Takte.
- **echo_gap_answer**: in langen Noten des Leads (ab 1,25 Schlägen) drei bis vier kurze Noten in Schritten, dann eine längere Note, die beim Wiedereinsatz des Leads weiterklingt. Über einem Lead ohne lange Noten schreibt sie nichts.

Lage (`counter_register`): **above** über dem Lead (Standard), **below** darunter oder **same** (dann beginnt sie nie gleichzeitig mit dem Lead). Auf betonten Zählzeiten spielt sie Terzen, Quinten, Sexten oder Oktaven zum Lead. Eine Figurennote, die auf einer betonten Zählzeit reiben würde, rückt auf den nächsten passenden Tonleiterton.

### Ganze Songs nach Genre

Du sagst das Genre, MidiBakery plant den Song, zeigt dir eine **Vorschau** (Zeitleiste der Abschnitte) und schreibt ihn bei **Apply** ins **Arrangement**.

| Genre | Tempo (mit „setze das Tempo des Genres“) | Abschnitte (Standardlänge) |
|---|---|---|
| **House** | 124 BPM | Intro, Build, Drop, Break, Build 2, Drop 2, Outro |
| **Melodic Techno** | 122 BPM | Intro, Build, Drop, Breakdown, Build 2, Climax, Outro |
| **Peak-Time Techno** | 128 BPM | Intro, Groove, Lift, Peak, Breakdown, Peak 2, Lift 2, Peak 3, Stripped Outro |
| **Drum & Bass** | 174 BPM | Intro, Build, Drop, Breakdown, Build 2, Drop 2, Outro |
| **Trap** | 145 BPM | Intro, Build, Drop, Verse, Build 2, Drop 2, Outro |

**Länge:** *radio* (kurz: Intro, Break und Outro halbiert), *standard*, *extended* (Intro und Outro doppelt, DJ-freundlich) oder eine Zielzeit in Minuten („etwa 5 Minuten“).

**Was MidiBakery dabei macht:**

- **Spuren:** Es sucht vorhandene Spuren für Drums (Spur mit Drum Rack), Bass, Akkorde und Lead (an Namen wie „Bass/Sub/808“, „Chords/Pad/Keys“, „Lead/Melody/Synth“). Fehlende Spuren legt es an, mit passendem Kit und Presets aus der Core Library. **Benenne deine Spuren also vorher passend**, wenn du eigene Klänge behalten willst. Mit „nimm Spur 3 als Bass“ weist du eine Rolle zu.
- **Noten:** Aufbau und Muster folgen Rezepten pro Genre (siehe [GENRES.md](../GENRES.md)): Drums mit Ghost-Notes und Fills, wechselnder Bass, zweite Harmonie im Break, eine Hook, die sich entwickelt. Dynamik steigt und fällt mit der Energie des Abschnitts.
- **Marker:** Es setzt **Locators** (Marker) an die Abschnitte.
- **Mix (an):** je ein Hall- und ein Delay-Return (vorhandene werden verwendet), Pegel und Sends für neue Spuren.
- **Automation (an):** Filterfahrten, Delay-Würfe.
- **Sidechain (an):** Bass und Pads ducken unter der Kick, über eine stumme Hilfsspur.
- **FX (an):** ein Riser vor jedem Drop und ein Impact auf der Eins des Drops.
- **Start:** hinter dem letzten Clip im Arrangement, oder an einem Takt, den du nennst („ab Takt 17“). **Es überschreibt nie vorhandene Arrangement-Clips**; es nennt dir stattdessen den ersten freien Takt.

Du kannst Teile abschalten: „ohne Sidechain“, „ohne Riser“, „keine neuen Spuren anlegen“, „ohne Mix-Returns“, „mit leeren Instrumenten statt Preset-Klängen“.

Weitere Wünsche: „mit der Akkordfolge i VI III VII“, „setze das Tempo auf das des Genres“, „benutze meinen Drum-Clip aus Slot 1 für die Drums“ (ein Session-Clip wird in jeden passenden Abschnitt kopiert).

**Grenzen:** Der Song muss im **4/4-Takt** sein (sonst sagt MidiBakery: stelle zuerst 4/4 ein). Breaks, Samples (Amen, Vocal Chops) und eigene Audioclips kann MidiBakery nicht erzeugen oder laden. Ein Song nach Rezept klingt genretypisch; **gut** wird er erst durch dein Hören und dein Arrangieren danach.

Nach dem Apply bleibt alles normal bearbeitbar: Es sind gewöhnliche MIDI-Clips und Spuren.

## 9. Clips bearbeiten

MidiBakery ändert vorhandene Noten als **Unterschied** („Diff“): nur das, was sich ändert, wird angefasst. Der Rest behält Wahrscheinlichkeit, Velocity-Abweichung und Undo-Verlauf. Zum Bearbeiten gibt es sechs Operationen:

| Operation | Was passiert | Beispiel |
|---|---|---|
| **Variation** | ein wenig Neues: Noten ändern, wegfallen oder hinzukommen. *Amount* bestimmt, wie viel. | „Variiere den Bass leicht.“ |
| **Transponieren** | höher oder tiefer. **Halbtöne** (12 = eine Oktave) oder **Skalenstufen** in der Tonart (2 Stufen = eine Terz). | „Eine Oktave tiefer.“ / „Um 5 Halbtöne hoch.“ / „Zwei Stufen in der Tonart höher.“ |
| **Humanize** | kleine Abweichungen in Timing und Velocity | „Mach die Hi-Hats lockerer.“ |
| **Quantize** | Noten aufs Raster ziehen (Sechzehntel usw.), mit Stärke und Swing | „Quantisiere auf Achtel, 70 %.“ |
| **Invert** | Melodie spiegeln, in der Tonart | „Spiegle die Melodie.“ |
| **Arpeggiate** | Akkorde werden zu Läufen (aufwärts, abwärts, auf-ab, zufällig; Schrittlänge, 1–3 Oktaven) | „Arpeggio in Sechzehnteln, auf-ab.“ |

**Nur ein Teil des Clips:** „die erste/zweite **Hälfte**“, oder nach Takten **des Clips**: „Takte 3 bis 4“. Der erste Takt des *Clips* ist Takt 1, nicht der Takt im Song. Beispiel: „Variiere nur die zweite Hälfte des Drop Bass.“

**Welchen Clip?**

- Ein **Session-Clip**: Spur und Slot nennen („Clip auf Spur 2, Slot 1“).
- Ein **Arrangement-Clip**: den **Namen** des Clips, z. B. „Groove Bass“ oder „Drop Chords“. Teilnamen gehen, wenn sie eindeutig sind (Groß-/Kleinschreibung egal). Songs aus `plan_song` benennen ihre Clips nach Abschnitt und Teil. Du findest die Namen im Arrangement oder fragst „welche Clips liegen im Arrangement?“.

**Neu schreiben statt ändern:** „Schreib den Bass im Drop neu“ ersetzt die Noten des Arrangement-Clips über seine ganze Länge (mit Nachfrage). Das Ergebnis liegt wieder im selben Clip.

**Einzelne Noten:** „Lösche die Note auf Zählzeit 3“, „Mach die letzte Note länger“: möglich, aber mit Klick in Lives Piano Roll oft schneller.

## 10. Das Arrangement

**Clips verwalten** (alles per Chat, ein Undo-Schritt pro Auftrag; ein Clip landet nie auf einem anderen):

- **Verschieben:** „Verschiebe ‚Break Chords‘ auf Takt 41.“ Ein Clip lässt sich nur verschieben, wenn er nicht gekürzt und kein Loop ist.
- **Tauschen:** „Tausche ‚Intro Bass‘ und ‚Drop Bass‘.“ Beide Clips tauschen ihren Startpunkt.
- **Löschen:** „Lösche ‚Outro Hats‘.“ (mit Nachfrage)
- **Kopieren aus der Session:** „Kopiere den Clip aus Slot 2 auf Spur 3 ins Arrangement, ab Takt 9.“
- **Neu anlegen:** MIDI-Clips mit Noten ins Arrangement.
- **Marker (Locators):** „Setze einen Marker ‚Drop‘ auf Takt 33“, „lösche den Marker bei Takt 17“. Dafür muss der **Transport stehen**; MidiBakery stellt die Abspielposition danach wieder her.

**Take Lanes zum Comping** (Live 12.2 oder neuer): Mehrere **Varianten eines Teils** (Hook, Melodie, Bass, Akkorde oder Drums) landen über denselben Akkorden jeweils in einer **eigenen Take Lane** einer Spur. Du hörst sie durch und wählst in Live die besten Stellen heraus.

- Auftrag: „Gib mir 4 Takes für die Melodie in Takt 17 bis 24 auf Spur 3.“ Standard: 4 Takes, 8 Takte, Hook.
- Die Lanes zeigt Live erst mit **Show Take Lanes** (⌘⌥U bzw. Strg+Alt+U) an.
- Ein Undo entfernt alle Takes.

## 11. Der Reference Analyzer

Er schaut sich einen **Referenzsong** an, den du magst, und zeigt, wie er aufgebaut ist: Abschnitte (Intro, Build, Drop, Break, Outro), Tonart, Tempo und pro Takt die Energie von Kick, Tiefen, Mitten und Höhen. Du lernst daraus, wie lang ein Intro typischerweise ist, wann der Drop kommt. Und du kannst MidiBakery bitten, **deinen Song nach diesem Aufbau** zu bauen.

### Analysieren

1. Lege eine **Audiospur** an und ziehe den Referenzsong ins **Arrangement** (nicht in die Session-Ansicht).
2. Ziehe **MidiBakery Reference Analyzer** auf diese Spur.
3. Drücke **Analyze**. Das Gerät rechnet in Live selbst (nichts wird hochgeladen).
4. Du siehst die Abschnitte, die Tonart und das Tempo und darunter vier Bahnen: **Kick, Lows, Mids, Hats**.

**Dateiformate:** Auf macOS liest das Gerät auch MP3, AAC u. ä. (über das Systemprogramm `afconvert`). Auf Windows geht nur **WAV**: Wandle den Song vorher in WAV.

**Gewarpte und ungewarpte Clips:** Ist der Clip in Live *gewarpt*, nutzt das Gerät Lives Takte. Ein **ungewarpter** Clip läuft in seinem eigenen Tempo; das Gerät erkennt Tempo und ersten Schlag selbst, warpt den Clip auf dein Raster (Takt 1 auf einer Taktlinie, dein Set-Tempo bleibt) und analysiert nochmal. Schlägt das fehl, sagt es das: Dann warpe von Hand (1.1.1 auf den ersten Schlag) und drücke noch einmal **Analyze**.

### Einstellungen

- **Genre** (Auto oder eines der fünf Genres): bestimmt die Abschnittsnamen (z. B. „Lift/Peak“ bei Peak-Time Techno), die Phrasenlänge (16 Takte bei Drum & Bass) und klärt halbes oder doppeltes Tempo.
- **Sensitivity** (je 0–100, Standard 50, für Kick, Lows, Mids, Hats): wie fein der Song geteilt wird. Bei **100** wird jede gefundene Änderung ein Abschnitt. Bei **50** werden gleichartige Nachbarn zu einem Abschnitt (vier Breaks hintereinander sind ein langer Break). Niedriger: Ein Drop und sein Groove werden einer. Das **Verhältnis** der vier Felder bestimmt, was als Änderung zählt: „Hats 30, der Rest 100“ lässt Hi-Hat-Wechsel durch, „nur Kick hoch“ teilt den Song dort, wo die Kick aufhört und wiederkommt. Die Analyse läuft von selbst neu, sobald du ein Feld loslässt.
- **Lock** (an): ändert sich ein Feld, bewegen sich die anderen um den gleichen Betrag.
- **Set Locators:** setzt Marker an die Abschnitte im Arrangement. Der Transport muss stehen.
- **Remove Locators:** entfernt alle Marker im Bereich des Clips.

Ergebnisse speichert das Gerät im MidiBakery-Ordner unter `references/`. Der Chat liest sie von dort.

### Im Chat nutzen

- „Welche Referenzen habe ich analysiert?“ / „Was ist der Aufbau von meinem Referenzsong?“
- „Bau mir einen Peak-Time-Techno-Song nach der Referenz ‚<Teil des Namens>‘.“ – Abschnittsfolge und -längen folgen dem Referenzsong, eingerastet auf das Raster des Genres. MidiBakery erzeugt dabei **nur den Aufbau**, nicht den Klang des Referenzsongs.
- „… und nimm Tempo und Tonart der Referenz.“
- Ein **ungewarpter** Referenzsong funktioniert nur, wenn dein Song im gleichen Tempo spielt (sonst Fehlermeldung).

## 12. Mixen und Klänge

MidiBakery kann Live-Parameter lesen und setzen. Es **hört nichts**. Zeitliche und klangliche Entscheidungen triffst du.

- **Mixer:** Lautstärke und Sends in dB (so wie Live sie anzeigt), Pan, Mute, Solo, Crossfader, Routing (Ein- und Ausgänge, nach den Namen in Live). Für Spuren, Returns und Master.
- **Returns:** Return-Spuren anlegen, auf Wunsch mit einem Live-Effekt („Hall-Return“).
- **Geräte:** native Live-Geräte einfügen, ihre Parameter lesen und setzen (Namen und Wertebereiche stehen im Chat), auch in Racks. Macros und Ketten eines Racks lesen und ändern.
- **Klänge laden:** „Lade ein 909-Kit“, „einen Pad-Sound“: MidiBakery sucht im Live-Browser (Core Library) nach Namen und lädt es auf die gewählte Spur. Ein Instrument oder Kit ersetzt das vorhandene Instrument, ein Effekt wird angehängt. Findet es nichts mit allen Wörtern, probiert es mit einem Teil.
- **Drum-Pads lesen:** Welches Pad hat welche Note?
- **Automation:** Clip-Automation für Geräteparameter und den Mixer der Spur (Lautstärke, Pan, Sends): Rampen, Sinus, Dreieck u. a. „Fahre den Cutoff über 8 Takte auf.“ Im Arrangement baut MidiBakery dafür den Clip neu auf; die Noten bleiben, vorhandene Hüllkurven dieses Clips werden dabei ersetzt.
- **Sidechain, Hall, Delay und Filter für ganze Songs:** übernimmt `plan_song` (Kapitel 8).
- **Master-Kette:** „Leg eine Master-Kette für House an“ setzt EQ Eight, Glue Compressor und Limiter mit den Werten des Genres ans Ende der Master-Spur. Das ist ein **Startpunkt, kein fertiges Mastering**. Was die Geräte tun:
  - Der EQ schneidet tiefes Rumpeln weg: 30 Hz, bei Drum & Bass und Trap 20 Hz.
  - Der Glue Compressor „klebt“ den Mix sanft zusammen (2:1, Attack 30 ms, Release Auto). Spiel den lautesten Teil ab und dreh seinen **Threshold**, bis die Nadel 1–2 dB zeigt.
  - Der Limiter fängt Spitzen bei -1 dB True Peak ab. Er macht den Song **nicht lauter**.
  - Wie bei Songs siehst du erst eine Vorschau und schreibst mit **Apply**. Zweimal **Undo** entfernt die Kette wieder.
  - Hat dein Master schon einen Limiter, EQ Eight oder Glue Compressor, lässt MidiBakery ihn in Ruhe.
  - Woher die Werte stammen, steht in [GENRES.md](../GENRES.md#master-kette-plan_master).
- **Lautheit messen:** Zieh das Gerät **MidiBakery Loudness Meter** (Browser: Audio Effects › Max Audio Effect › MidiBakery) als **letztes Gerät** auf die Master-Spur, nach dem Limiter. Während Live spielt, zeigt es:
  - **Momentary** (die letzten 0,4 s), **Short-term** (die letzten 3 s) und **Integrated** (alles seit dem Start oder Reset) in LUFS, nach ITU-R BS.1770 / EBU R 128.
  - **Peak**: die höchste Sample-Spitze seit dem Reset in dB. Eine echte True-Peak-Spitze kann bis etwa 0,5 dB höher liegen.
  - **Reset** startet Integrated und Peak neu. Für eine Zahl zum Vergleichen: Reset, dann den ganzen Song (oder den Drop) abspielen.
  - Im Chat: „Wie laut ist der Song?“ MidiBakery liest das Gerät mit `measure_master`. Ohne das Gerät auf dem Master nennt MidiBakery keine LUFS-Zahl.
  - Die Werte sind eine gute Näherung, kein geeichtes Messgerät: Max liest die Blöcke im 100-ms-Takt seines Schedulers.
- **Auf eine Ziel-Lautheit bringen:** „Mach den Song so laut wie House“ oder „auf -14 LUFS für Spotify“. Das braucht die Master-Kette und das Loudness Meter auf dem Master. Dann geht es in Runden:
  1. Reset am Meter, den Song (oder mindestens 30 s vom lautesten Teil) abspielen.
  2. MidiBakery schlägt vor, um wie viel dB es den **Input Gain** des Limiters ändert (höchstens 6 dB pro Runde), und schreibt es mit **Apply**. Ein Undo nimmt es zurück.
  3. Das Meter fängt neu an: noch einmal abspielen, dann die nächste Runde. Liegt der Song innerhalb von 0,5 LU am Ziel, sagt MidiBakery das.
  - Ziele: House -8, Melodic Techno -8,8, Peak-Time Techno -7,7, Drum & Bass -6,3, Trap -8,4, Streaming -14 LUFS. Es sind Mediane veröffentlichter Tracks ([GENRES.md](../GENRES.md#lautheitsziele-plan_loudness)), keine Pflicht.
  - Lauter heißt hier: mehr Limiting. Hör auf Pumpen und flache Drums; mehr als +12 dB gibt MidiBakery dem Limiter nicht.

Bei Ohren-Fragen („klingt matschig“) bekommst du Hinweise, aber keine Messung. Für genaue Analysen von Audio benutze Lives eigene Analyzer.

## 13. Generator und Transform ohne Chat

Die beiden Geräte **MidiBakery Generator** und **MidiBakery Transform** brauchen keinen Chat und keine KI, nur die laufende API (also das Remote Script, Kapitel 4). Sie sind Live-**MIDI Tools** und erscheinen in der Clip-Ansicht eines MIDI-Clips in den Bereichen **Generate** bzw. **Transform**. Sie arbeiten auf dem **markierten Zeitbereich** des Clips, in der Tonart des Clips (Live 12.2 oder neuer).

**Generator**

| Regler | Bedeutung |
|---|---|
| **Part** | Drums, Bass, Chords, Melody |
| **Style / Rhythm** (zweites Menü) | Stil des gewählten Teils (Drums: House, Techno, Hip-Hop, Trap, Rock, Breakbeat; Bass: Sustained, Pulse, Offbeat, Octave, Walking, Syncopated; Chords: Sustain, Pulse, Offbeat, Stabs) |
| **Density**, **Swing**, **Chance** (nur Drums) | Dichte, Swing, Zufälligkeit der Ghost-Notes |
| **Seed** und **Dice** | die Idee; Dice würfelt eine neue |
| **Replace** (Standard: an) | leert den markierten Bereich, bevor die neuen Noten hineinkommen. Ein Generator kann in Live sonst nur hinzufügen. |

**Transform:** **Operation** (Humanize, Quantize, Invert, Arpeggiate, Variation, Transpose), **Amount**, **Semis** (Halbtöne für Transpose), **Arp Rate** (1/32 bis 1/4), **Seed** und **Dice**. Ändert eine Operation nichts, steht der Grund in der Statuszeile des Geräts (zum Beispiel „No chords to arpeggiate“).

Beim ersten Anwenden zeigt das Gerät kurz „Working …“. Das Ergebnis kommt einen Moment später im selben Zyklus.

## 14. Probleme lösen

### Der Chat bleibt bei „Connecting…“ oder der Punkt ist rot

1. **Ist das Remote Script eingeschaltet?** Einstellungen > Link, Tempo & MIDI > Control Surface = **MidiBakery** (Kapitel 4). Live nach der Installation neu starten.
2. **Läuft die API?** Prüfe im Terminal (Programm aus dem Installationsordner, Kapitel 3): `midibakery ping`. Es sollte die Verbindung zu Live bestätigen.
3. **Gerät neu laden:** das Chat-Gerät von der Spur löschen und neu hineinziehen (die Chat-Seite lädt sich nach einem Update erst dadurch neu).
4. **Ein anderes Programm hat Port 8766:** Beende es oder starte Live neu.
5. **Zwei Versionen:** Läuft noch eine API einer älteren Version, tauscht MidiBakery sie beim Start aus. Gelingt das nicht, beende Live und starte es neu.

### „No Claude key“ / NO_API_KEY

Du hast ein Claude-Modell gewählt, aber noch keinen Schlüssel hinterlegt: **Key** drücken (Kapitel 5). Ist der Schlüssel falsch, sagt der Chat „INVALID_KEY“ („That does not look like a Claude API key“ bzw. von Anthropic abgelehnt).

### „Cannot reach LM Studio“ / „Cannot reach Ollama“

Der Server läuft nicht. LM Studio: Tab **Developer** > Server starten, oder `lms server start`. Ollama: `ollama serve` (oder Ollama-App starten). Läuft er auf einem anderen Rechner oder Port, gibt es die Umgebungsvariablen `LMSTUDIO_HOST` bzw. `OLLAMA_HOST`. Das Modell-Menü zeigt nur lokale Modelle, wenn der Server erreichbar ist.

### „… too small a context for MidiBakery’s tools“

LM Studio hat das Modell mit zu wenig Kontext geladen. Neu laden: `lms load <modell> -c 32768` (Kapitel 5).

### Das Modell antwortet auf Englisch, Türkisch, Koreanisch …

Lokale Modelle verlieren manchmal die Sprache. MidiBakery erinnert sie jede Nachricht daran. Hilft das nicht: kurz „Antworte auf Deutsch“ schreiben, oder **New** drücken.

### Die KI sagt „erledigt“, aber in Live ist nichts passiert

Das passiert gelegentlich bei kleinen lokalen Modellen. Schau in Lives Spuren und Clips nach (nicht nur in den Chat). Dann frage: „Hast du es wirklich geschrieben? Mach es jetzt mit den Werkzeugen.“ Der Chat zeigt jeden Werkzeugaufruf an („Running …“ und ein Haken oder ein Fehler); fehlt der, hat nichts stattgefunden.

### „Stopped: … failed 3 times“ (STUCK)

Das Modell hat denselben Fehler dreimal gemacht, oder alles schlug sechs Runden hintereinander fehl. MidiBakery bricht ab, bevor es weiter Schaden anrichtet. Nichts wurde weiter geändert. Formuliere um (Spur und Abschnitt nennen), mache den Auftrag kleiner oder nimm ein größeres Modell oder Claude.

### „Stopped after 24 tool rounds“

Der Auftrag war für das Modell zu groß. Teile ihn auf.

### „CONFLICT“

Etwas hat sich zwischen Vorschau und Apply geändert, oder ein Clip würde auf einen anderen fallen. Neue Vorschau anfordern, bzw. einen freien Ort nennen.

### „LICENSE_REQUIRED“

Betrifft nur Versionen, bei denen die Lizenzprüfung eingeschaltet ist (siehe Kapitel 15). Dann: **Start trial** oder **Enter key** im Chat.

### Der Song-Plan weigert sich

- „plan_song needs 4/4“: Stelle den Takt auf 4/4.
- Er nennt „den ersten freien Takt“: Auf dieser Position liegen schon Clips; wähle einen späteren Start.
- Referenz ungewarpt: nur im Tempo der Referenz möglich (Kapitel 11).

### Marker lassen sich nicht setzen

Der Transport muss stehen. Drücke Stopp und versuche es noch einmal.

### Take Lanes fehlen

Brauchen Live 12.2 oder neuer. Zeige sie mit **Show Take Lanes** (⌘⌥U bzw. Strg+Alt+U).

### Das Gerät lässt sich nicht laden / „Max for Live nicht verfügbar“

Geräte brauchen **Max for Live** (Teil der Live Suite). Prüfe Einstellungen > **Max for Live**, ob es aktiviert ist.

### Wo schaue ich nach?

Die Dateien liegen im MidiBakery-Ordner: macOS `~/Library/Application Support/MidiBakery/`, Windows `%APPDATA%\MidiBakery\`. Fürs Support-Gespräch sind diese nützlich (Schlüssel und Token sind darin geschwärzt oder nicht enthalten):

| Datei | Inhalt |
|---|---|
| `api.log` | Zeitstempel, jede deiner Nachrichten und jeder Werkzeugaufruf mit Fehlern: hier steht, warum ein Chat danebenging |
| `device-chat.log` | das Chat-Gerät |
| `device-miditool.log` | Generator und Transform |
| `device-reference.log` | Reference Analyzer |
| Lives `Log.txt` | Meldungen des Remote Scripts (beginnen mit „MidiBakery:“) |

Mit **Copy** im Chat bekommst du das ganze Gespräch inklusive Werkzeugaufrufe, praktisch für Fehlerberichte.

## 15. Häufige Fragen

**Verändert MidiBakery meine Projekte ohne zu fragen?**
Nur auf deinen Auftrag. Jeder Schritt ist ein Undo-Schritt. Löschen und Ersetzen fragt vorher nach. Ein ganzer Song kommt erst als Vorschau.

**Was kostet es?**
Claude: Nutzung der API nach deinem Anthropic-Tarif (Eingabe und Ausgabe pro Token; ein kurzer Auftrag kostet wenig, Gespräche mit viel Set-Inhalt mehr). Lokale Modelle: nichts. Zur MidiBakery-Lizenz: Die Lizenzprüfung ist in dieser Version **ausgeschaltet**; alles funktioniert ohne Testphase und ohne Schlüssel. Sobald sie eingeschaltet wird, gelten **30 Tage Testphase**, danach ein Lizenzschlüssel (dauerhaft nutzbar, 12 Monate Updates, auf zwei Rechnern). Ohne gültige Lizenz liest MidiBakery weiter dein Set und macht Undo, erzeugt und ändert aber nichts. Dein Set wird nie angefasst. Den Schlüssel gibst du im Chat unter **Enter key** ein.

**Welche Daten verlassen meinen Rechner?**
Mit **Claude**: Alles, was die KI zum Arbeiten liest, also Spur- und Clipnamen, Noten, Tempo, Tonart, Geräte. Mit **LM Studio oder Ollama**: nichts, alles bleibt lokal. Die tägliche **Update-Prüfung** schickt Version, Betriebssystem, Prozessor-Art und Kanal (aus: `midibakery update --disable`). Die Analyse des Reference Analyzers läuft komplett in Live.

**Funktioniert es mit Live Standard oder Intro?**
Die Geräte brauchen Max for Live (Suite oder Standard mit Max-for-Live-Zusatz). Getestet ist es mit Live 12 Suite.

**Kann MidiBakery Audio erzeugen oder Samples laden?**
Nein, nur MIDI, und es lädt Klänge aus Lives Browser. Samples und Breaks kann es nicht laden.

**Kann die KI meine Musik „hören“?**
Nein. Sie arbeitet mit Noten und Parametern. Den Reference Analyzer analysiert rechnerisch, aber die KI hört nicht.

**Warum lässt MidiBakery bei Songs Spuren und Returns anlegen?**
Damit das Ergebnis sofort nach einem Song klingt: Kit, Bass, Pad, Lead, Hall, Delay, Sidechain. Mit „ohne neue Spuren“ und „ohne Mix“ schaltest du es ab.

**Warum klingt der Song generisch?**
Weil Rezepte Konventionen sind. Nutze sie als Gerüst: Tausche Klänge, ändere die Akkorde, variiere Clips, und höre. Ein Referenzsong, der dir gefällt, hilft beim Aufbau.

**Ich habe mehrere Live-Sets offen.**
MidiBakery steuert das Set, das gerade offen und aktiv ist.

**Kann ich MidiBakery auch mit Claude Desktop oder Claude Code benutzen?**
Ja: Der MCP-Server bringt dieselben 40 Werkzeuge dorthin, siehe [Kapitel 17](#17-midibakery-aus-claude-desktop-oder-claude-code-benutzen).

**Wie entferne ich es?**
Kapitel 3, „Deinstallieren“.

## 16. Kleines Wörterbuch

| Wort | Bedeutung |
|---|---|
| **API** | die Brücke im Hintergrund zwischen Live und der KI |
| **Apply** | die Vorschau wirklich in Live schreiben |
| **BPM** | Tempo, Schläge pro Minute |
| **Build** | Aufbau vor dem Drop, Spannung steigt |
| **Clip** | ein Baustein mit Noten (oder Audio), in der Session oder im Arrangement |
| **Comping** | aus mehreren Aufnahmen (Takes) die besten Stellen zusammenschneiden |
| **Control Surface** | in Live ein Gerät oder Skript, das Live steuert; MidiBakery ist eines |
| **Drop** | der Höhepunkt: Kick und Bass setzen voll ein |
| **Drum Rack** | Live-Instrument, das jedem Pad einen Drum-Klang gibt |
| **Locator** | Marker im Arrangement, mit Namen |
| **Max for Live** | Teil von Live, in dem die MidiBakery-Geräte laufen |
| **Return** | Effekt-Spur (Hall, Delay), in die Spuren Signal schicken (Send) |
| **Seed** | die „Nummer“ einer Idee; derselbe Seed ergibt dieselben Noten |
| **Sidechain** | Ein Klang (Bass) wird leiser, wenn ein anderer (Kick) spielt |
| **Slot** | ein Feld in der Session-Ansicht; Slots zählt der Chat ab 1 |
| **Take Lane** | Zusatzspur unter einer Spur im Arrangement, für Varianten |
| **Velocity** | Anschlagstärke einer Note |

## 17. MidiBakery aus Claude Desktop oder Claude Code benutzen

Der **MCP-Server** bringt dieselben 40 Werkzeuge in Claude Desktop, Claude Code und andere MCP-Programme. Du schreibst dann in deren Fenster statt im Chat-Gerät, und Claude steuert dein Live-Set. Einrichtung, eine Erklärung in einfachen Worten und die Referenz jedes einzelnen Werkzeugs stehen in **[MCP-SERVER.md](MCP-SERVER.md)** (English: [MCP_SERVER.md](MCP_SERVER.md)).
