# MidiBakery – Benutzerhandbuch

MidiBakery baut in Ableton Live 12 EDM-Songskizzen zur Inspiration: Drums, Bass, Akkorde und eine Lead im Arrangement, nach einem Genre-Rezept oder nach einem Live Set, das dir gefällt. Danach hörst du, tauschst Sounds und behältst, was funktioniert.

English version: [USER_GUIDE.md](USER_GUIDE.md)

**Inhalt**

1. [Was du bekommst](#1-was-du-bekommst)
2. [Installieren und aktualisieren](#2-installieren-und-aktualisieren)
3. [In Live einrichten](#3-in-live-einrichten)
4. [Eine KI wählen](#4-eine-ki-wählen)
5. [Einen Song bauen](#5-einen-song-bauen)
6. [Songs nach deinen eigenen Sets (Set Importer)](#6-songs-nach-deinen-eigenen-sets-set-importer)
7. [Songs nach einer Audiodatei (Reference Analyzer)](#7-songs-nach-einer-audiodatei-reference-analyzer)
8. [Das Ergebnis ändern](#8-das-ergebnis-ändern)
9. [Fehlerbehebung](#9-fehlerbehebung)
10. [FAQ](#10-faq)

---

## 1. Was du bekommst

| Teil | Zweck |
|---|---|
| **Remote Script** „MidiBakery“ | die Verbindung zu Live (einmal in den Einstellungen setzen) |
| **MidiBakery Bake** | ein Klick für einen ganzen Song, ohne KI |
| **MidiBakery Chat** | hier bittest du in normalen Sätzen um Songs |
| **MidiBakery Set Importer** | liest Live Sets (`.als`) als Referenzen und Loops ein |
| **MidiBakery Reference Analyzer** | schätzt Abschnitte, Tonart und Tempo einer Audiodatei (z. B. MP3) |

MidiBakery schreibt **MIDI-Noten** und lädt Sounds aus Lives Core Library. Es erzeugt kein Audio und lädt keine Samples. Jede Änderung ist ein Schritt in Lives Undo-Liste.

Du brauchst **Ableton Live 12 Suite** (12.3 oder neuer; Max for Live ist in Suite enthalten), macOS oder Windows und für den Chat eine KI: einen Claude-API-Key oder ein lokales Modell (Kapitel 4). Das Bake-Device braucht keine KI.

## 2. Installieren und aktualisieren

Schließe zuerst Live. Beide Installer installieren nur für dein Benutzerkonto, ohne Administrator-Passwort.

- **macOS:** `MidiBakery-<version>-macos-arm64.pkg` (Apple Silicon) oder `-macos-x64.pkg` (Intel). Wenn macOS das Öffnen verweigert (noch nicht notarisiert): **Systemeinstellungen > Datenschutz & Sicherheit > Dennoch öffnen**.
- **Windows:** `MidiBakery-<version>-windows-x64-setup.exe`. Wenn Windows warnt: **Weitere Informationen > Trotzdem ausführen**.

**Updates:** Einmal am Tag fragt MidiBakery `updates.klirrwerk.com` nach einer neueren Version (gesendet: Version, Betriebssystem, Prozessortyp, Kanal). Das Chat-Device zeigt dann „MidiBakery … ist verfügbar“: **Install** lädt den Installer, prüft ihn und öffnet ihn. Danach Live neu starten. Aus: `midibakery update --disable`.

**Deinstallieren:** Windows **Einstellungen > Apps > MidiBakery**. macOS: `~/Library/Application Support/MidiBakery/runtime/<version>/midibakery uninstall` (`--purge` löscht auch Einstellungen und den gespeicherten Key). Deine Musik wird nie angefasst.

## 3. In Live einrichten

1. **Live starten** (nach jeder Installation neu starten).
2. **Einstellungen > Link, Tempo & MIDI > Control Surface:** wähle in einer freien Zeile **MidiBakery**. Input und Output bleiben auf *None*. Live startet damit auch die MidiBakery-API im Hintergrund.
3. Im Browser unter **User Library** (oder Suche „MidiBakery“):

| Device | Ordner |
|---|---|
| MidiBakery Bake | Presets > MIDI Effects > Max MIDI Effect > MidiBakery |
| MidiBakery Chat | Presets > MIDI Effects > Max MIDI Effect > MidiBakery |
| MidiBakery Set Importer | Presets > MIDI Effects > Max MIDI Effect > MidiBakery |
| MidiBakery Reference Analyzer | Presets > Audio Effects > Max Audio Effect > MidiBakery |

4. Zieh **MidiBakery Chat** auf eine beliebige MIDI-Spur (MIDI läuft unverändert durch). Tippe „Hallo“ in das **Eingabefeld rechts im Device** und drück Enter.

Live gibt keine Tastatureingaben an das Chatfenster selbst weiter: tippe nur ins Eingabefeld rechts, oder nutze mit **Pop out** den Chat im Browser. Jedes Device hat einen **About**-Knopf mit den Versionen von Device, API und Remote Script; sie sollten übereinstimmen.

## 4. Eine KI wählen

Das **Modellmenü** des Chats listet die Claude-Modelle und gefundene lokale Modelle. Du kannst jederzeit wechseln.

| | Claude | LM Studio oder Ollama |
|---|---|---|
| Internet | nötig | nicht nötig |
| Kosten | pro Nutzung, auf deinem Anthropic-Konto | keine |
| Datenschutz | Spurnamen, Noten und Tempo gehen an Anthropic | alles bleibt auf deinem Rechner |
| Qualität | sehr zuverlässig | hängt vom Modell ab; kleine machen mehr Fehler |

**Claude:** erstelle einen Key auf console.anthropic.com (beginnt mit `sk-ant-`; ein claude.ai-Abo reicht nicht). Wähle ein Claude-Modell, klick **Key**, gib den Key ins Eingabefeld rechts ein und drück Enter. Er wird im macOS-Schlüsselbund bzw. in der Windows-Anmeldeinformationsverwaltung gespeichert. `ANTHROPIC_API_KEY` und `midibakery auth set-key` gehen auch.

**LM Studio:** lade ein Modell mit Tool-Nutzung (z. B. Qwen oder Gemma), starte den lokalen Server (Tab **Developer** oder `lms server start`) und lade das Modell mit genug Kontext:

```bash
lms load <modellname> -c 32768
```

**Ollama:** `ollama pull qwen3:8b`, Ollama laufen lassen, im Menü „Ollama · <Modell>“ wählen.

Lokale Modelle bekommen dieselben Werkzeuge in kompakter Form. Nenne Spuren und Clips beim Namen, bitte um eine Sache nach der anderen, und drück **New**, wenn ein Gespräch entgleist.

## 5. Einen Song bauen

### Mit einem Klick (Bake)

Zieh **MidiBakery Bake** auf eine beliebige MIDI-Spur. Wähle **Genre** und **Length**, optional **After** (ein importiertes Set oder ein analysierter Song, Kapitel 6 und 7) und **My loops** (Loops aus deinen importierten Sets). Dann:

- **Bake** schreibt einen neuen Song hinter den letzten Clip im Arrangement, im Tempo des Genres, auf passende Spuren (fehlende werden angelegt).
- **Again** ersetzt den zuletzt gebackenen Song durch einen anderen Seed: seine Clips und Locators werden gelöscht, die Spuren bleiben.
- **Back** holt den Seed davor zurück, an derselben Stelle.

Die Statuszeile zeigt Takte, Seed und Tempo. Bake merkt sich seinen letzten Song, bis Live neu startet; danach beginnt **Bake** einen neuen. Alles ist in Live rückgängig zu machen.

### Im Chat

Schreib zum Beispiel:

- „Bau mir einen House-Song mit zufälligem Seed, setze das Tempo passend zum Genre und lege die Spuren neu an.“
- „Nochmal, anders.“ (neuer Seed: anderer Bass, andere Akkorde, anderer Drum-Groove und Hook)
- „Nimm Seed 42.“ (dieselben Noten wieder)
- „Melodic Techno, etwa 6 Minuten.“ / „Drum and Bass, Radio Edit, in a-Moll.“
- „Nimm die Folge i - VI - III - VII.“ (römische Ziffern beziehen sich auf die Tonart des Sets; „Am F C G“ geht auch)

Im Chat bekommst du eine **Vorschau-Karte**: eine Zeitleiste der Abschnitte. In Live hat sich noch nichts geändert. **Apply** schreibt den Song ins Arrangement hinter den letzten Clip dort; bestehende Clips werden nie überschrieben.

| Genre | Tempo | Abschnitte (Standardlänge) |
|---|---|---|
| **House** | 124 | Intro, Build, Drop, Break, Build 2, Drop 2, Outro |
| **Melodic Techno** | 122 | Intro, Build, Drop, Breakdown, Build 2, Climax, Outro |
| **Peak-Time Techno** | 128 | Intro, Groove, Lift, Peak, Breakdown, Peak 2, Lift 2, Peak 3, Stripped Outro |
| **Drum & Bass** | 174 | Intro, Build, Drop, Breakdown, Build 2, Drop 2, Outro |
| **Trap** | 145 | Intro, Build, Drop, Verse, Build 2, Drop 2, Outro |

**Länge:** Radio, Standard, Extended (DJ-freundlich) oder eine Zeit in Minuten.

Was MidiBakery schreibt (bei Bake wie bei Apply):

- **Spuren:** es nimmt Spuren mit Namen wie Drums (oder mit Drum Rack), Bass/Sub/808, Chords/Pad/Keys und Lead/Melody/Synth. Fehlende werden mit einem Kit und Presets aus der Core Library angelegt. Benenne deine Spuren so, wenn du deine eigenen Sounds behalten willst.
- **Tempo:** das Tempo des Genres (oder der Referenz), je Seed etwas gestreut.
- **Noten:** Drums mit Ghost Notes und Fills, ein Bass, der den Akkorden folgt, eine Hook, die sich entwickelt, Dynamik nach der Energie jedes Abschnitts. Der Seed wählt Bassmuster, Akkord-Loop und Drum-Groove.
- **Arrangement:** Locators an den Abschnitten, ein Reverb- und ein Delay-Return, Sidechain-Pumpen auf Bass und Pads, Riser vor und Impacts auf den Drops.

Apply kann einige Undo-Schritte brauchen (Spuren, Returns, Clips): drück **Undo**, bis alles weg ist.

**Grenzen:** nur 4/4. Keine Samples, Breaks oder Vocals. Ein Rezept klingt genretypisch; deins wird es durch Hören, Sounds tauschen und Arrangieren.

### Dein eigener Sound pro Part

Neue Spuren bekommen die Presets des Genres. Im Bake-Gerät klickst du auf „Sounds“: das Gerät wechselt auf eine Seite mit Genre-Menü und einer Drop-Fläche pro Part; darunter steht das aktuelle Preset („Bake“ wechselt zurück). Höre ein Preset im Live-Browser vor und ziehe es auf Drums, Bass, Chords oder Lead. „Search in browser...“ öffnet eine Seite mit Suchfeld über Live's Browser. Die Auswahl gilt pro Genre (Genre-Menü im Fenster; „All genres“ ist der Standard). Im Terminal setzt `midibakery sound lead "…" --genre trap` ein Genre, ohne `--genre` alle (das eigene Genre gewinnt). Oder im Terminal (der Pfad ist ein Browser-Pfad; er beginnt in „sounds“, außer er beginnt mit „packs“, „user_library“ usw.):

```bash
midibakery sound lead "Synth Keys/Light Keys.adg"
```

Parts: `drums`, `bass`, `chords`, `lead`. `midibakery sound lead -` stellt das Genre-Preset wieder her; `midibakery sound` zeigt deine Auswahl. Sie steht in `sounds.json` im MidiBakery-Ordner.

## 6. Songs nach deinen eigenen Sets (Set Importer)

Freie Beispiel-Live-Sets und deine eigenen Projekte sind die beste Inspiration. Der **Set Importer** liest `.als`-Dateien exakt (Noten und Clips, keine Audioanalyse) und speichert alles auf deinem Rechner.

1. Zieh **MidiBakery Set Importer** auf eine beliebige MIDI-Spur.
2. Drück **Folder...** (viele Sets; `Backup`-Ordner werden übersprungen) oder **Set...** (eine Datei). Die Sets erscheinen mit Tempo und Tonart.
3. Klick ein Set an, um seine Abschnitte und die Rollen pro Abschnitt zu sehen. Klick den Genre-Chip, um das Genre zu setzen. Entferne Häkchen bei dem, was du nicht willst, und drück **Import**.
4. Der Tab **Library** listet alles Importierte mit seinen Loops; **Delete** entfernt ein Set.

Ein Import liefert:

- **Eine Referenz:** Abschnitte, Tempo, Tonart und Besetzung des Sets (welche Rollen in welchem Abschnitt spielen).
- **Loops:** Bass-, Lead- und Drumfiguren, die das Set wiederholt, und seine Akkordfolge, benannt wie `my_soundasapound_bass_1`. Sie folgen der Tonart deines Songs. Die Noten des Sets werden nie als Ganzes kopiert.

Dann frag:

- „Bau einen Song nach 'Sound as a Pound'.“ (Struktur, Tempo und die Loops des Sets; ohne Genre nimmt MidiBakery das im Importer gesetzte)
- „Nach 'Phantom', aber mit dem Bass von 'Sound as a Pound'.“ (`loops_from`: Drums, Bass, Lead oder Akkorde aus einem anderen Set)
- „Ein House-Song mit meinen eigenen Loops.“ (`my_loops`: der Seed zieht Drums, Bass, Lead und Akkorde aus deinen importierten Sets; „Nochmal, anders“ zieht eine andere Mischung)
- „Welche Sets habe ich importiert?“

Rollen, die ein Set nie spielt, werden aus dem Genre ergänzt. Akkord-Loops von Sets, die du mit einem Genre markiert hast, kommen zu den Akkordfolgen dieses Genres dazu.

**Grenzen:** nur 4/4-Sets. Drums als Audio ergeben keine Drum-Loops. Abschnitte sind eine Schätzung aus den Clips: prüf sie in der Library-Ansicht.

## 7. Songs nach einer Audiodatei (Reference Analyzer)

Für einen Song, den du nur als Audio hast (MP3, WAV): der Analyzer schätzt Abschnitte, Tonart, Tempo und die Energie pro Takt. Das ist eine grobe Orientierung, keine Wahrheit.

1. Zieh den Song auf eine **Audiospur** im **Arrangement**.
2. Zieh **MidiBakery Reference Analyzer** auf diese Spur und drück **Analyze**. Alles läuft in Live.
3. Du siehst Abschnitte, Tonart, Tempo und vier Spuren: **Kick, Lows, Mids, Hats**.

Unter Windows geht nur **WAV**. Ein ungewarpter Clip wird automatisch auf dein Raster gewarpt; klappt das nicht, warp ihn von Hand (1.1.1 auf den ersten Schlag) und analysiere erneut.

- **Genre** steuert Abschnittsnamen und Phrasenlängen.
- **Sensitivity** (Kick, Lows, Mids, Hats): höher teilt den Song feiner; **Lock** bewegt alle vier gemeinsam.
- **Set Locators** / **Remove Locators** setzen die Abschnitte ins Arrangement (Transport gestoppt).

Dann: „Bau mir einen Peak-Time-Techno-Song nach der Referenz '<Teil des Namens>'.“ Übernommen wird nur die Struktur, nicht der Klang.

## 8. Das Ergebnis ändern

- „Schreib den Bass in 'Drop 2' neu.“ (die Noten dieses Arrangement-Clips werden nach einer Rückfrage ersetzt)
- „Mach 8 Takte Techno-Drums auf Spur 1.“ / „Eine Bassline, die auf die Kick einrastet.“ (ein neuer Session-Clip)
- „Schieb 'Break Chords' auf Takt 41.“ / „Tausch 'Intro Bass' und 'Drop Bass'.“ / „Lösch 'Outro Hats'.“
- „Setz einen Marker 'Drop' auf Takt 33.“ (Transport gestoppt)
- „Setz das Tempo auf 126.“ / „Spiel ab.“ / „Stopp.“ / „Mach das rückgängig.“

Feinschliff, Mixing und Sounddesign gehen in Live selbst schneller.

## 9. Fehlerbehebung

**„Connecting…“ bleibt oder der Punkt ist rot:** Control Surface prüfen (Kapitel 3), `midibakery ping` im Terminal, Chat-Device entfernen und neu einfügen, Live neu starten.

**NO_API_KEY / INVALID_KEY:** **Key** drücken und einen gültigen Claude-Key eingeben.

**„Cannot reach LM Studio / Ollama“:** Server starten (`lms server start`, `ollama serve`). Anderer Host oder Port: `LMSTUDIO_HOST`, `OLLAMA_HOST`.

**„… too small a context“:** Modell mit `lms load <modell> -c 32768` neu laden.

**Die KI sagt „erledigt“, aber nichts hat sich geändert:** ein kleines lokales Modell. Jeder Tool-Aufruf steht im Chat; ohne einen ist nichts passiert. Frag „Mach es jetzt mit den Werkzeugen“ oder nimm ein größeres Modell oder Claude.

**„Stopped: … failed 3 times“ / „Stopped after 24 tool rounds“:** umformulieren, die Bitte verkleinern oder ein größeres Modell nehmen.

**CONFLICT:** zwischen Vorschau und Apply hat sich etwas geändert. Frag erneut.

**„plan_song needs 4/4“:** Taktart auf 4/4 stellen.

**LICENSE_REQUIRED:** nur bei eingeschalteter Lizenzprüfung: **Start trial** oder **Enter key** im Chat.

**Logs:** macOS `~/Library/Application Support/MidiBakery/`, Windows `%APPDATA%\MidiBakery\`: `api.log` (jede Nachricht und jeder Tool-Aufruf), `device-chat.log`, `device-importer.log`, `device-reference.log`; Lives `Log.txt` für das Remote Script. **Copy** im Chat kopiert das ganze Gespräch für eine Fehlermeldung.

## 10. FAQ

**Ändert MidiBakery mein Projekt ungefragt?** Nur auf Bitte; ein Song kommt erst als Vorschau, Löschen und Ersetzen fragen nach, alles ist rückgängig zu machen.

**Was kostet es?** Claude: API-Nutzung auf deinem Anthropic-Konto. Lokale Modelle: nichts. Die MidiBakery-Lizenzprüfung ist in dieser Version **aus**.

**Welche Daten verlassen meinen Rechner?** Mit Claude: was die KI liest (Spur- und Clipnamen, Noten, Tempo, Tonart). Mit lokalen Modellen: nichts. Die Update-Prüfung sendet Version, Betriebssystem, Prozessor und Kanal.

**Hört die KI meine Musik?** Nein. Sie arbeitet mit Noten. Entscheide mit deinen Ohren.

**Claude Desktop oder Claude Code?** Der MCP-Server bietet dort dieselben 16 Werkzeuge: siehe [MCP_SERVER.de.md](MCP_SERVER.de.md).
