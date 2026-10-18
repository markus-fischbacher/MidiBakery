# Genre-Rezepte für die Song-Engine

Was House, Melodic Techno, Peak-Time Techno, Drum & Bass und EDM-Trap typischerweise ausmacht, zusammengetragen aus Fachartikeln und Tutorials (Stand Oktober 2026). Die Vorlagen in `packages/core/src/midibakery/compose/structures.py` und die Generatoren sollen diesen Rezepten folgen.

**Wie belastbar eine Angabe ist:**
- **●** mehrere Quellen sagen dasselbe
- **◐** nur eine Quelle oder Quellen widersprechen sich (die Varianten stehen dabei)
- **○** keine Quelle nennt es ausdrücklich: übliche Konvention, nach Gehör zu prüfen

**Schreibweisen:**
- Schritte zählen in einem Takt mit 16 Sechzehnteln, Schritt 1 = Zählzeit 1. Schritt 5 ist Zählzeit 2, Schritt 9 Zählzeit 3, Schritt 13 Zählzeit 4. Die Offbeats sind 3, 7, 11 und 15.
- MIDI-Noten gelten wie in Live: 60 = C3. Quellen benennen Oktaven unterschiedlich, deshalb sind Lagen hier über die Frequenz umgerechnet.
- Swing in Prozent im MPC-Sinn: 50 % = gerade. In Lives Groove-Pool entspricht das ungefähr „Amount“ ab 0.

Rezepte sind Konventionen, keine Gesetze. Ein Track nach Rezept klingt genretypisch, gut klingt er erst nach dem Hören. Für Einsteiger hilft ein Referenztrack: Das Reference-Analyzer-Gerät zerlegt einen Song, der gefällt, in Abschnitte, und `plan_song` mit `reference` baut den neuen Song nach dessen Aufbau (siehe unten).

---

## Gemeinsame Grundregeln (alle Genres)

- **●** Abschnitte sind Vielfache von 8 Takten, meist 16 oder 32.
- **●** Etwas Kleines ändert sich alle 4 bis 8 Takte (Hat, Clap, Fill). Etwas Großes ändert sich alle 16 Takte (Bass, Chords, Melodie).
- **●** Fills und Drop-outs liegen im letzten Takt einer Phrase, kurz vor dem Wechsel.
- **●** Ein DJ-freundliches Intro und Outro besteht aus Drums mit wenigen Elementen und ohne oder mit wenig Sub-Bass. Das Outro baut ab, statt das Intro zu kopieren.
- **●** Vor dem Drop verschwindet die Kick, und oft gibt es eine kurze Stille.
- **●** Der zweite Drop ist nicht identisch mit dem ersten: andere Variation, mehr Energie.
- **●** Keine flachen Velocities. Ghost-Notes sind deutlich leiser, etwa 30 bis 50 % oder 6 bis 12 dB.
- **●** Der Bass klebt nicht auf der Kick: Er spielt in den Lücken oder unter der Kick mit Sidechain, aber nie dagegen.
- **●** Moll überwiegt. Akkordfolgen haben 2 bis 4 Akkorde und laufen als Loop über 2 bis 8 Takte.
- **●** Eine Hook, nicht viele: ein kurzes Motiv über 2 bis 4 Takte, das wiederkehrt und variiert. Die Melodie liegt über den Chords, nicht in derselben Oktave.
- **●** Typische Anfängerfehler sind ein Loop ohne Entwicklung, zu viele Elemente gleichzeitig, alles starr auf dem Raster, alle Änderungen immer auf Takt 1 eines Abschnitts, ein überladenes Intro und eine Kick, die mit dem Bass kollidiert.

---

## House

Familie aus Mainstream-, Deep- und Tech-House. Deep House ist langsamer und jazziger, mit Septim- und Nonakkorden. Tech House ist trockener und perkussiver, die Hook ist oft ein gestimmtes Percussion-Riff.

**Tempo und Swing**
- **●** 120–128 BPM. Deep House 120–124, Mainstream 124–126, Tech House 125–128.
- **◐** Swing auf Sechzehnteln, je nach Stil 55–65 %, Tech House bis 75 %. Attack schwingt alle Spuren, nicht nur den Shaker. Vorgabe: **etwa 58–62 %**.

**Struktur** (Phrasen 8/16/32)
- **●** Intro 16–32 Takte, zuerst Drums. Elektronauts empfiehlt sparsamer 8–16 Takte mit höchstens 2–3 Elementen.
- **◐** Ein übliches Schema: Intro 16–32, Build 8–16, Drop 32, Breakdown 16–32, Drop 2 32, Outro 16–32.
- **◐** Länge: Eine Auswertung von 63 Platten ergab im Median 4:31 für Extended und 3:31 für Radio-Edits. Clubmixe sind oft 6–7 Minuten lang (○).

**Aufbau**
- **◐** Native Instruments: Beat und Akkorde ab Takt 1, eine Orgel ab Takt 9, die erste Lead-Linie ab Takt 17. Alle 16 Takte ein Riser, beim Bass-Einstieg ein FX-Hit.
- **●** Riser über 8 oder 16 Takte, die genau auf einer Phrasengrenze auflösen. Dazu ein Filter-Sweep, ein Snare-Roll und im Breakdown ohne Kick.
- **◐** Fills (909-Toms und -Snare) alle 8 Takte, jedes Mal etwas anders. Das stärkste Signal wird für den größten Wechsel aufgehoben.

**Drums**
- **●** Kick auf 1, 5, 9, 13.
- **●** Clap oder Snare auf 5 und 13, oft zwei Claps übereinander. Bei Attack ein paar Millisekunden zu früh.
- **●** Open Hat auf den Offbeats 3, 7, 11, 15, leiser als die Kick (NI: Velocity 83).
- **◐** Closed Hat: bei Loopmasters auf dem 1., 2. und 4. Sechzehntel jeder Zählzeit, das 3. bleibt für die Open Hat frei. Bei Attack (Soulful) dagegen auf den Zählzeiten.
- **◐** Shaker auf allen 16 Schritten mit wechselnder Velocity, leise. Er trägt den Swing.
- **◐** Im Tech House zusätzlich ein Ride auf jeder Zählzeit.
- **◐** Ghost-Notes: ein etwa 6 dB leiserer Clap auf dem ersten Sechzehntel nach dem letzten Clap eines 2-Takt-Loops. Im Tech House Ghost-Snares kurz vor den Kicks.
- **◐** Variation: Crash am Anfang jeder 2-Takt-Sequenz, Open Hat erst in der zweiten Drop-Hälfte, Fill alle 8 Takte.

**Bass**
- **●** Zwischen den Kicks oder auf den Offbeats (Schritte 3, 7, 11, 15), mit Sidechain zur Kick.
- **◐** Notenlänge: kurz auf der Zählzeit (etwa 60 % eines Sechzehntels), auf dem Offbeat lang (90–100 %). Monofon, keine überlappenden Noten.
- **◐** Lage: Grundton etwa 35–70 Hz, also **MIDI 25–37**. Dazu kann ein Layer eine Oktave höher kommen.
- **●** Folgt den Akkord-Grundtönen und geht manchmal zur Terz.

**Harmonik**
- **●** Meist Moll. Deep House nutzt m7-, maj7- und m9-Akkorde.
- **◐** Folgen aus den Quellen: zwei Akkorde (i–bVII), i–v–iv, i–bIII–v. 1–2 Akkorde pro Takt in Loops über 2 oder 4 Takte.
- **◐** Stabs: kurze Akkord-Hits (m7/m9) mit kurzer Hüllkurve, etwa ein Sechzehntel bis ein Achtel lang (○). Pads liegen im Hintergrund.
- **◐** Enge Lage, damit der Loop fließt. Etwa C3–C5, also MIDI 60–84 (○). Pads mit Tiefpass um 400 Hz.

**Lead und Hook** (dünn belegt)
- **◐** Sparsam. Call and Response: der Ruf kurz, die Antwort länger und auf anderer Tonhöhe. Eine Variation folgt 4 Takte später.
- **◐** Im Tech House ist die Hook oft ein gestimmtes Percussion-Riff (Clave, Cowbell).
- **○** Motive über 2–4 Takte, 3–8 Noten pro Takt, überwiegend Akkordtöne, Pausen auf der Eins, etwa eine Oktave über den Chords.

**Sounds** (native Live-Devices)
- Drum Rack mit 909-, 808- oder CR-78-Kit.
- Bass mit Simpler (MS2-Filter, Drive), Drift oder Analog.
- Chord-Stabs mit Orgel- oder E-Piano-Sound: Operator, Electric, Wavetable oder Simpler mit Akkord-Sample.
- Effekte: Reverb, Echo, Auto Filter.

**Filterfahrten** (Auto Filter, Clip-Automation)

| Abschnitt | Drums (High-pass) | Chords (Low-pass) |
|---|---|---|
| Intro | offen | ab Takt 9: 150 Hz → 20 kHz, öffnet spät |
| Build, Build 2 | 20 → 400 Hz bzw. 500 Hz | offen |
| Break | 150 Hz, dünn | 200 Hz → 20 kHz, öffnet spät |
| Outro | offen (Kick bleibt für den DJ) | 20 kHz → 150 Hz in 8 Takten |

Die Drops sind offen. Im Break steigt die Resonanz der Chords mit dem Cutoff von 5 auf 40 %. Delay-Throws: Im Drop wirft der Lead auf der letzten Zählzeit jedes 8. Takts ins Delay.

**Quellen:** Ableton Learning Music (Tempo); EDMProd „Classic Deep House“; Native Instruments „Deep House Track“; Attack Magazine Beat Dissected (Soulful Deep House, Deep Tech House, Chugging Tech House, Dusted Deep House); Attack Passing Notes (Deep House Chords); Attack Deconstructed (Tiga „Bugatti“); Mixed In Key (Arrangement); Mixgraph (Intro, Riser); Loopmasters (Tech House Beat & Bass); The Producer School und Boombox (Tech-House-Basslines); Mode Audio (Deep House Chords); MusicRadar (m9-Akkorde, Hooks); EDMProd (Call and Response); Violet Recording (House); Foren: Gearspace, Elektronauts, KVR, DJTechTools (schwächer belegt).

---

## Melodic Techno

Melodic Techno (etwa Afterlife: Anyma, ARTBAT, Stephan Bodzin) ist langsamer und harmonischer als Peak-Time Techno. Es hat 2 bis 4 Akkorde, Pads und eine Arpeggio- oder Lead-Hook. Raw/Industrial Techno ist schneller und fast atonal, das gehört nicht hierher.

**Tempo und Swing**
- **●** 120–125 BPM, typisch 122. Attacks Deep-Melodic-Beat liegt bei 120–123.
- **◐** Swing leicht: Attack 10 %, Beatportal „subtil“ auf Hats und Shakern. Vorgabe: **0–15 % nur auf Hats und Percussion, nie auf der Kick**.

**Struktur**
- **●** Abschnitte sind Vielfache von 8 Takten. DJ-Intro und -Outro mit 16–32 Takten Drums und Percussion.
- **◐** Beatportal: Intro 16 (Kick, Hats, Atmosphäre), Build 16 (dazu Bass, Pads, FX), Drop 16, Breakdown 16 (nur Pads und FX), Höhepunkt 16.

**Aufbau**
- **◐** Native Instruments:
  - Takt 1–8: Kick, Hats, Percussion, Pad.
  - Ab Takt 9: Clap, Shaker, Rim, Noise und Bass.
  - Ab Takt 17: Lead.
  - Ab Takt 25: Shaker und Rim fallen weg.
- **●** Den Pad-Filter über 16 Takte öffnen, den Bass-Tiefpass durch Breakdowns und Builds fahren. Riser und Impacts sparsam, ein Sub-Drop vor jedem Drop (Beatportal).

**Drums**
- **●** Kick auf 1, 5, 9, 13, Clap auf 5 und 13. Attack nutzt stattdessen einen synkopierten Clap am Ende jedes zweiten Takts, dazu alle 4 Takte einen Doppelschlag.
- **●** Closed Hat auf den Offbeats plus eine leise Sechzehntel-Schicht. Shaker in Sechzehnteln, der Rim leicht vor den Upbeats.

**Bass**
- **●** Folgt den Akkord-Grundtönen. NI wechselt den Grundton alle 2 Takte.
- **◐** Lage etwa MIDI 32–48 (NI: Ab1).

**Harmonik**
- **●** 1 Akkord pro 1–2 Takte in einem Loop über 4–8 Takte. Beispiele: Am–F–C–G, Am–Dm–Em–C.
- **◐** Pads in 2–3 Schichten (hell, mittel, tief) mit langsamem Attack. Natürlich Moll, alternativ Phrygisch oder Dorisch.

**Lead**
- **◐** Einfaches Arpeggio in der Tonart. NI behält einen Rhythmus über 1 Takt mit kurzen Stotter-Noten und versetzt ihn alle 2 Takte auf die Akkordtöne.
- **○** Sechzehntel-Raster, 4–10 Noten pro Takt, MIDI 60–84.

**Sounds:** Pads und Leads mit Wavetable oder Drift, langem Reverb und Delay (1/8 oder 3/16). Bass mit Analog oder Drift.

**Filterfahrten** (Auto Filter, Clip-Automation): Langsames Öffnen gehört zu den langen Builds des Genres.

| Abschnitt | Drums (High-pass) | Pads (Low-pass) | Arp (Low-pass) |
|---|---|---|---|
| Intro | offen | 150 Hz → 3 kHz | – |
| Build | 12 Takte offen, dann 20 → 200 Hz | 3 → 20 kHz, öffnet spät | ab Takt 9: 500 Hz → 2 kHz |
| Drop | offen | offen | 800 Hz → 6 kHz in 16 Takten, zurück auf 3 kHz |
| Breakdown | – | 150 Hz → 8 kHz, öffnet spät | 600 Hz → 2,5 kHz |
| Build 2 | 20 → 350 Hz | offen | 2,5 → 10 kHz |
| Climax | offen | offen | 2 → 12 kHz |
| Outro | offen | 12 kHz → 150 Hz in 8 Takten | – |

Im Build steigt die Resonanz der Pads von 10 auf 35 %. Delay-Throws: Im Breakdown wirft das Arp auf der letzten Zählzeit jedes 8. Takts ins Delay.

**Quellen:** Beatportal (Melodic House & Techno: Anyma, Miss Monique, ARTBAT, Stephan Bodzin); Native Instruments (Melodic Techno); Attack Magazine (Deep Melodic/Progressive Techno).

---

## Peak-Time Techno

Peak-Time oder Driving Techno ist die Beatport-Kategorie „Peak Time / Driving“, der Stil von Drumcode: Adam Beyer, Amelie Lens, Charlotte de Witte, Enrico Sangiuliano, Layton Giordani, Eli Brown. Er ist perkussiv, treibend und kommt mit fast keiner Harmonik aus. Spannung entsteht durch schrittweise Veränderung, nicht durch große Drops.

**Tempo und Swing**
- **●** 126–132 BPM, Beatportal empfiehlt 128 als Start. Der Drumcode-Stil liegt eher um 135, neuere Releases von Amelie Lens und Charlotte de Witte um 138. Ab 140 ist es Hard Techno, nicht mehr dieser Stil.
- **●** Das Tempo steigt seit Jahren: lange um 127, dann die Welle mit 150 und mehr (Attack, MusicTech).
- **●** Kaum Swing: 0–20 % nur auf Hats, Shakern und Percussion. Kick und Bass bleiben gerade.
- Vorgabe: **128 BPM** wie die Referenz unten.

**Struktur** (Abschnitte als Vielfache von 8 Takten, meist 16 oder 32)
- **◐** EDMProd: DJ-Intro, Breakdown, Drop, Drop-Variation (32+), Breakdown, Drop, Outro, je 16–32 Takte.
- **◐** Beatportal (bei 128 BPM umgerechnet): Intro ~32, Build ~32, Drop ~16, Breakdown ~32, Drop 2 ~32, Outro mit Abbau.
- **◐** Vorschlag für die Engine, etwa 192–224 Takte (6–7 Minuten bei 130 BPM): Intro 32, Groove A 32, Breakdown 1 16, Peak 1 32, Groove B 16–32, Breakdown 2 16–32, Peak 2 32, Outro 32.
- **●** Intro und Outro mit 16–32 Takten nur Drums. Im Outro geht zuerst der Bass, und es ist keine Kopie des Intros.
- **●** Alle 8 Takte ändert sich etwas, alle 16 Takte markiert ein Fill oder Impact die Phrase. Pro 8 oder 16 Takte ändert sich nur eine Dimension (Filter, Decay oder Akzent).
- **◐** Breakdowns mit 8, 16 oder 32 Takten (Attack: 24 = 3 × 8, oder 32). Die Kick ist raus. Percussion, Clap, Offbeat-Hat, ein hochpassgefilterter Bass, Textur und die Hook laufen weiter.
- **●** Spannung ohne großen Drop: Der Peak läuft mindestens 32 Takte, darin optional Mini-Breaks von 1–2 Takten. Oft reicht es, Kick oder Bass kurz wegzunehmen, ein Riser ist nicht nötig.

**Referenzen** (Analyse vom Oktober 2026; gemessen wurde pro Takt die Energie von Kick, Bass, Mitten und Höhen, Melodien lassen sich aus dem fertigen Mix so nicht ablesen):
- Y-Traxx – Mystery Land (Spektre Remix): 128 BPM, A-Moll, 7:30, rund 232 Takte.
- Katoff – The Signal: 126 BPM, Dis-Moll; nur eine 3-Minuten-Fassung ohne DJ-Intro und Outro.
- T78 – Nezquik (Original Mix): 128 BPM, A-Moll, 7:00, rund 220 Takte.

Was alle drei tun:
- **●** Vor jedem großen Drop geht zuerst der Bass für etwa 8 Takte, dann wird die Kick über 3–5 Takte herausgefiltert. Die letzten 2–3 Takte laufen ohne Kick, und genau dann ist der Synth am lautesten.
- **●** Im Outro geht zuerst der Bass, dann die Kick, am Ende bleiben die Hats.

Was zwei von drei tun:
- **◐** Nach einem Breakdown kommen die Hats verzögert: 8–16 Takte Kick, Bass und Synth mit wenig Hats, dann voll (Katoff, T78).
- **◐** Nach einem Peak 8 Takte nur Kick und Bass, ohne Hats und Synth (Spektre, T78).
- **◐** Im Breakdown ohne Kick rumpelt der Bass leise weiter (Katoff, T78).

Einzelne Tracks:
- **◐** T78 nimmt am Ende vieler 8- und 16-Takt-Phrasen für einen Takt Kick und Bass weg.
- **◐** Katoff setzt im Groove einen Synth-Akzent auf den Anfang jeder 8-Takt-Phrase und spielt im Breakdown den Synth im Wechsel von 2 Takten an, 2 Takten aus, mit 2 Takten Stille vor dem Drop.

Die Vorlage kombiniert die drei, 224 Takte, also 7:00 bei 128 BPM:

| Takte | Abschnitt | Was passiert | Vorbild |
|---|---|---|---|
| 1–32 | Intro | Kick und Hats, nach 16 Takten der Bass | Spektre |
| 33–48 | Groove | Synth-Akzent auf jedem Phrasenanfang, 1 Takt Pause von Kick und Bass am Ende jeder Phrase | Katoff, T78 |
| 49–64 | Lift | 8 Takte ohne Bass, dann kommen die Stabs, nach 12 Takten geht die Kick | alle drei |
| 65–96 | Peak | Alles läuft, 1 Takt Pause am Ende jeder 16 Takte | T78 |
| 97–120 | Breakdown | Ohne Kick: Rumpel-Bass, die Hats gehen nach 8 Takten, Synth im Wechsel, 2 Takte Stille | Katoff, Spektre |
| 121–152 | Peak 2 | 8 Takte mit wenig Hats, dann voll | Katoff, T78 |
| 153–160 | Lift 2 | Ohne Bass, die Kick geht, die Acid-Line bleibt | alle drei |
| 161–176 | Peak 3 | Alles läuft | T78 |
| 177–184 | Stripped | Nur Kick und Bass | Spektre, T78 |
| 185–224 | Outro | 24 Takte Groove ohne Hook, dann geht der Bass, dann die Kick, zuletzt bleiben die Hats | alle drei |

In den Referenzen wird die Kick oft herausgefiltert, statt hart zu enden. Die Engine macht das mit einem Auto Filter pro Spur, dessen Cutoff sie pro Clip automatisiert (`sweeps` in der Vorlage):

| Abschnitt | Drums (High-pass) | Chords (Low-pass) | Lead (Low-pass) |
|---|---|---|---|
| Lift | 8 Takte offen, dann 20 → 300 Hz | 200 Hz → 20 kHz, öffnet spät | 600 Hz → 2,5 kHz |
| Peak | offen: die Kick ist sofort voll da | offen | 400 Hz → 5 kHz in 24 Takten, zurück auf 1,5 kHz |
| Breakdown | 250 Hz, dünn | 150 Hz → 9 kHz, öffnet spät | 800 Hz → 3 kHz |
| Peak 2 | offen | offen | 800 Hz → 8 kHz in 16 Takten, zurück auf 2 kHz |
| Lift 2 | 20 → 400 Hz | offen | 2 → 12 kHz |
| Peak 3 | offen | offen | 6 → 3 kHz |

Resonanz: Im Lift steigt sie bei den Chords von 0 auf 50 %. Die Acid-Line wird in den Peaks spitzer (Peak 20 → 60 % in 24 Takten, zurück auf 30 %; Peak 2 30 → 70 %, zurück auf 40 %; Lift 2 40 → 75 %). Delay-Throws: Die Chords werfen in Groove und Breakdown auf der letzten Zählzeit jedes 8. Takts ins Delay.

Jeder Clip einer gefilterten Spur bekommt eine Hüllkurve, auch wenn sie nur „offen“ ist. So bleibt kein Filter aus dem vorigen Abschnitt hängen.

Ein Abschnitt kann statt einer Geraden auch eine Kurve oder Welle fahren: `300>8000~exp` beginnt langsam und öffnet am Ende schnell (`~log` umgekehrt), `400>3000~sine/2` schwingt alle 2 Takte zwischen beiden Werten (auch `triangle`, `saw`, `square`).

**Aufbau**
- **●** Elemente einzeln einführen. Rides kommen erst im Drop. Die Hook wird schon im Intro angedeutet, leise und gefiltert.
- **●** Die letzten 8 Takte eines Breakdowns:
  - Riser, Clap-Roll und schneller werdende Percussion.
  - Der Snare-Roll wird lauter und dichter, am Ende 32tel.
  - Die Tiefen werden per Hochpass bis zum Drop weggefiltert.
  - Ein Sub-Drop-Hit auf der Eins des Drops.
- **◐** Clap-Rolls in Sechzehnteln in Takt 4 ab Zählzeit 2, alle 4 Takte (EDMProd).
- **◐** Kick-Edits: zusätzliche Kicks, die Kick am Abschnittsende weg, Reverse-Kicks.
- **●** „Der Moment“: Die Hook (Stab oder Lead) wird im Breakdown vorgestellt und kommt im Drop mit voller Wucht. Den stärksten Lead hebt man sich für den letzten Drop auf.

**Drums**
- **●** Kick auf 1, 5, 9, 13, kurz und druckvoll. Sie läuft durch, außer im Breakdown.
- **◐** Ghost-Kick auf Schritt 4 und/oder 12. Variante „rollend“: leise Offbeat-Kicks auf 3, 4, 7, 8, 11, 12, 15, 16, etwa 10 dB leiser (Attack).
- **◐** Clap, hier widersprechen sich die Quellen:
  - Beatportal: sparsam auf 5 und 13.
  - EDMProd: kein House-Clap, sondern synkopierte Snares um Schritt 1–2 und 7–8 im 2-Takt-Zyklus.
  - Charlotte de Witte verzichtet ganz auf Claps und schichtet bis zu sieben Hat- und Becken-Sounds.
  - Vorgabe: Clap optional und sparsam.
- **●** Closed Hats in durchgehenden Sechzehnteln mit „tanzender“ Velocity. Offbeat-Hat (oft offen) auf 3, 7, 11, 15. Eine Open Hat auf 2 und 4 mit Lücken, eine davon verspätet mit etwa 50 %.
- **◐** Ride auf jedem Achtel (ungerade Schritte), auf Zählzeit 1 und 3 leiser, damit er sich gegen die Kick duckt.
- **◐** Percussion: Toms in Sechzehnteln im Wechsel. Rim auf den Kick-Schritten und auf 6 und 14, ein Low Tom auf 14. Ghost-Claps rund um den Haupt-Clap.
- **○** Velocity: Kick 127, Haupt-Hits 100–115, Hats im Wechsel um 70 und 100, Ghosts 30–55.
- **○** Variation: ein Kern über 1 Takt, ein Turnaround über 4 Takte (Fill in den letzten 2 Zählzeiten), ein Abschnittswechsel alle 8 oder 16 Takte.
- **◐** Rumble ist Klangbearbeitung: eine Sub- oder Rumble-Fahne unter einem knackigen Transienten, ein Delay in Sechzehnteln auf einer Kick-Kopie, gefiltert und angezerrt.

**Bass**
- **●** **Rollende Sechzehntel**, das erste Sechzehntel jeder Zählzeit bleibt für die Kick frei: Schritte 2–4, 6–8, 10–12, 14–16. Meist ein Ton, gelegentlich ein anderer. Variante: nur Offbeats (3, 7, 11, 15).
- **◐** Ein Top-Bass mit demselben Rhythmus und Oktavsprüngen. EDMProd springt bei jeder zweiten Wiederholung eine Oktave.
- **◐** Notenlänge: ein Sechzehntel mit 70–90 % Gate, kurze Lücken (Producer School). EDMProd nutzt 99 %.
- **●** Lage:
  - Sub MIDI 28–36 (41–65 Hz).
  - Rollender Mid-Bass MIDI 36–48 (65–131 Hz). Attacks Hauptton liegt bei 98 Hz, also MIDI 43.
  - Acid eine Oktave über dem Bass.
- **●** Die Kick ist auf den Grundton gestimmt, ihre Resonanz liegt meist bei 47–60 Hz (MIDI 30–35). Attack stimmt sie auf F (43,65 Hz, MIDI 29).

**Stabs, Synths und Hooks**
- **●** Hook: ein Loop über 1–2 Takte, minimal und repetitiv. Er bewegt sich über Cutoff, Resonanz und LFO, nicht über neue Noten. Ein Motiv aus 3 Tönen (Grundton, Quinte, kleine Septime) mit Pausen.
- **●** **Parallele Stabs:**
  - Eine Moll-Dreiklangsform wird als Block verschoben, auch aus der Tonart heraus, immer in derselben Umkehrung.
  - Jeder Hit ist ein Sechzehntel lang, meist neben der Eins.
  - Aus 2 Takten werden 4, indem man 1–2 Hits stummschaltet oder verschiebt.
  - ○ Etwa 3–6 Hits pro Takt.
- **●** **Acid** im 303-Stil: Sägezahn, 16 Schritte. Slides nur zwischen kurzen Noten, denn gleitet jede Note, fällt der Slide nicht mehr auf. Wenige Akzente vor den Kicks, Cutoff tief und Resonanz hoch, über den Track hinweg geöffnet.
- **◐** Riff-Variation: alle 8–16 Takte einen Parameter ändern oder alle 8 Takte einen Ton tauschen, der Kern bleibt.
- **◐** Lage der Stabs MIDI 60–79 (C3–G4).
- **●** Vocals als kurze, wiederholte Schnipsel, gern auch zum Schluss.

**Harmonik**
- **●** Sehr wenig, oft keine klassische Tonleiter. „Atonal“ ist in Ordnung (EDMProd).
- **●** Moll, etwa F-Moll oder E-Moll. Ein Akkord oder ein Drone ist Standard. Eine Verschiebung zwischen zwei Akkorden bringt Bewegung.
- **◐** Ein Moll-Dreiklang in Grundstellung, optional mit dem Grundton eine Oktave höher verdoppelt. Akkorde tauchen, wenn überhaupt, im Breakdown auf.

**Sounds** (native Live-Devices)
- Kick: Drum Rack mit 909-Sample oder Kick Analog, Drum Buss mit „Boom“ auf dem Grundton, Saturator.
- Rumble: Kick-Send in Echo (1/16) und Hybrid Reverb, dann Auto Filter (Tiefpass ~80 Hz), dann Roar.
- Mid-Bass: Analog oder Drift (Sägezahn, kurze Filterhüllkurve). EQ Eight mit Hochpass um 65 Hz und Tiefpass um 350 Hz, Multiband Dynamics statt OTT, Compressor mit Sidechain zur Kick.
- Acid: Drift oder Analog, mono und legato, resonanter Tiefpass, dazu Roar und Saturator.
- Stabs: Wavetable mit verstimmten Sägezähnen oder Rechteck, Roar, Echo ping-pong, Hybrid Reverb (~1,5 s).
- FM-Hits: Operator. Vocals und Texturen: Simpler. Filterfahrten: Auto Filter.

**Anfängerfehler:** zu früh übersteuern, das Intro als Outro kopieren, keine Sidechain auf dem Bass, verwaschene Layer ohne Platz für die Kick, ein Pattern nach nur einem Takt beurteilen, zu früh zu viele Layer, nach dem Limiter arrangieren, bei Acid jede Note gleiten lassen oder zu viel akzentuieren.

**Quellen:** Beatportal (Peak-Time/Driving im Stil von Layton Giordani, Eli Brown, Adam Beyer); Mixed In Key (Techno-Arrangement); EDMProd (How to Make Techno); The Producer School (Drumcode Beats); Attack Magazine (Rolling Techno, Big Beat Techno, Warehouse Rolling Bass, Parallel Chord Stabs, Techno Synth Stabs, Effective Breakdown, Tempo-Trend); MusicTech (Sam Paganini); Lost Stories Academy (DJ-freundlich); Production Music Live (Techno); Skiddle (Interview Charlotte de Witte); Aulart (Kick-Tuning, Hannes Bieger); Roland (TB-303); Elektronauts und Ableton-Forum (schwächer belegt).

---

## Drum & Bass

Drei Spielarten:
- **Liquid:** Pads, Rhodes, Groove über Velocity und Mikrotiming.
- **Dancefloor:** poppige Akkorde.
- **Neurofunk:** Reese- und FM-Bässe, kurze Stabs, fast atonal.

**Tempo und Swing**
- **●** 170–176 BPM, Standard **174**. Liquid 170–176, Neuro 172–174, Halftime 170–175 (fühlt sich wie ~87 an).
- **◐** Swing nur auf den Hats (52–60 %). Kick und Haupt-Snares bleiben auf dem Raster, sonst ist der Track schwer zu mixen.

**Struktur** (Phrasen 4/8/16/32/64)
- **●** Intro 16–32, Build 8–16, Drop 32–64, Breakdown 16–32 ohne Drums, Build 2 8–16, Drop 2 32–64 (härter, anderer Bass), Outro 16–32. Etwa 256 Takte, knapp 6 Minuten. Ein Takt dauert bei 174 BPM rund 1,38 Sekunden.
- **◐** KAN-Vorlage: Intro 32, Build 16, Drop 64 (2 × 32), Mittelteil 16–32, Breakdown 32, Build 16, Drop 2 64, Outro 32. Kürzere Fassungen (EDMProd Liquid: 6 × 16 = 96 Takte) und Radio-Edits mit 3–4 Minuten sind auch üblich.
- **●** Kleine Änderungen alle 4–8 Takte, größere alle 16 Takte. Drop 1 besteht oft aus 4 Phrasen à 16 Takten, jede mit etwas Neuem oder Weggelassenem.
- **●** Intro und Outro mit Drums und Percussion, wenig oder kein Sub, die Mitten im Intro sparsam.

**Aufbau**
- **◐** Neues im Intro alle 8–16 Takte. Bei KAN kommt der erste Bass-Hit in Takt 17.
- **●** Build: Noise-Riser, sich öffnender Filter, Snare-Roll (Sechzehntel bis 32tel, Velocity von 50 auf 100 %, eventuell 1–2 Halbtöne nach oben), zusätzliche Hats. Build 2 ist dramatischer als Build 1.
- **◐** EDMProd Liquid: die Drums 4 Takte vor dem Drop ganz raus, die Kick in Vierteln, dann Achteln, dann Sechzehnteln. Crash auf Zählzeit 1 des Drops.
- **●** Kurze Stille vor jedem Drop. Nicht jede Änderung auf Takt 1 eines Abschnitts legen.

**Drums**
- **●** Two-Step: **Kick auf 1 und 11, Snare auf 5 und 13**. KAN setzt die zweite Kick auf 9.
- **◐** Varianten: Rolling/Liquid mit Kick auf 1 und 7 und einem Break-Loop über alle 16 Schritte. Halftime mit Kick auf 1 und 7, Snare auf 9. Amen/Jungle mit Kick auf 1, 3, 11, 12 und Ghosts auf 8, 10, 16.
- **●** Ghost-Snares auf 3, 8, 10, 16, Velocity 30–50. Ein „Skip“-Snare auf Schritt 12 jeden zweiten Takt mit 50–70. Höchstens 1–2 Ghost-Kicks pro 2 Takte.
- **◐** Hats in Achteln oder Sechzehnteln mit 70–80 % und zufälliger Velocity (KAN: abwechselnd 100/70). Ride in Achteln.
- **◐** Haupt-Snares: die erste etwa 90 %, die zweite 100 %.
- **◐** Variation: Shuffles in jedem vierten Takt, eine Ghost-Kick am Ende jedes achten Takts, die erste Kick jeden zweiten Takt weglassen.
- **●** Breaks (Amen, Think, Apache) zerschnitten und neu angeordnet, ab 150–200 Hz gefiltert, unter Kick und Snare gelegt. Das braucht Samples, die API kann keine laden.

**Bass**
- **●** Zwei Schichten: ein Sub (Sinus oder Dreieck, mono, Release 300–600 ms) und ein Mid- oder Reese-Bass (zwei verstimmte Sägezähne, Filter, Distortion, ab 80–100 Hz gefiltert).
- **●** Lage: nicht tiefer als D#1 (etwa 39 Hz). Sweet Spot etwa **MIDI 27–32 für den Sub** (39–52 Hz). E-, F- und F#-Moll geben dem Bass Gewicht.
- **◐** Liquid: lange, gezogene Noten, die den Akkorden folgen. Neuro und Jump-Up: Ein-Ton-Basslines mit rhythmischer Variation. Sub-Noten kurz halten, mit Sidechain.
- **◐** EDMProd Liquid: eine Linie über 4 Takte als 16-Takt-Loop, ein zusätzlicher Lauf in jedem zweiten 4-Takt-Block, die letzten 2 Zählzeiten der 16 Takte stumm.

**Harmonik**
- **●** Meist Moll. Liquid nutzt m7- und maj7-Akkorde in Dorisch oder natürlich Moll.
- **●** Folgen: i–VI–III–VII mit **2 Takten pro Akkord**, i–III–VI–iv (Liquid), i–VII–VI–VII, i–iv–v. Pad-Loops mit 2–3 Akkorden.
- **◐** Lage etwa C3–C5, nie unter C2, also etwa MIDI 48–72.
- **●** Liquid mit gehaltenen Pads, Rhodes oder Klavier. Neuro mit kurzen Stabs und Drones. Dancefloor mit poppigen Akkorden.

**Lead und Melodie** (dünn belegt)
- **◐** Ein Loop über 4–8 Takte, der mit Variation wiederkehrt, dazu Synkopen und Triolen. Nur eine Hook. Bei EDMProd eine Glocken-Gegenmelodie über 8 Takte, eine Oktave höher wiederholt.
- **◐** Call and Response über etwa einen halben Takt. Eine Linie nur aus Akkordtönen klingt „nach Eurodance“: also auch Durchgangstöne zulassen.

**Sounds**
- Sub: Operator oder Drift (Sinus).
- Reese: Analog mit zwei Oszillatoren, um ±0,27 Halbtöne verstimmt, mono (Attacks Patch), alternativ Wavetable.
- Neuro-Bass: Operator oder Wavetable mit Roar oder Saturator.
- Pads: Wavetable oder Drift.
- Keys: Electric.
- Bell- oder Pluck-Leads: Simpler oder Operator.
- Breaks: Simpler im Slice-Modus.

**Filterfahrten** (Auto Filter, Clip-Automation)

| Abschnitt | Drums (High-pass) | Chords (Low-pass) |
|---|---|---|
| Intro | offen | 200 Hz → 20 kHz, öffnet spät |
| Build | 20 → 500 Hz | offen |
| Breakdown | – | 150 Hz → 8 kHz, öffnet spät; Resonanz 0 → 35 % |
| Build 2 | 20 → 600 Hz | 8 → 20 kHz |
| Outro | offen | 20 kHz → 150 Hz in 16 Takten |

Delay-Throws: Im Drop wirft der Lead auf der letzten Zählzeit jedes 8. Takts ins Delay.

**Quellen:** KAN Samples (DnB Drums, Arrangement, Chord Progressions); DnB Academy (Drum Patterns, BPM & Structure); EDMProd (How to Make DnB, Liquid DnB); Attack Magazine (Raw DnB, Incessant DnB Beat, Reese Bass Redux); Unison (DnB Drum Patterns, How to Make DnB); Violet Recording (DnB); Beatportal (Sub Focus / Delta Heavy); iZotope (Basslines); Beat Kitchen (Swing); MusicRadar (Liquid Chords, nur Ausschnitt); Foren: DnB Forum, DJTechTools (schwächer belegt).

---

## Trap (EDM- und Festival-Trap)

Festival-Trap, nicht Hip-Hop-Trap, mit denselben Wurzeln. Die Quellenlage ist dünner als bei den anderen Genres: Die MusicRadar-Artikel ließen sich nicht abrufen, von Attack, Sound On Sound und Ableton gab es nichts Trap-Spezifisches.

**Tempo und Swing**
- **●** 140–150 BPM im Halftime-Gefühl (wirkt wie 70–75), härter bis 160. Die Angaben streuen von 128 bis 170.
- **◐** Wenig Swing (8–15 % auf 808 und Hats) oder einzelne Hats von Hand verschieben. Velocities der Akkorde variieren, Noten leicht neben das Raster setzen.

**Struktur** (Phrasen 4/8)
- **◐** Cymatics: Intro 4, Verse 8, Build 4–8, Drop 16, Breakdown/Verse 8, Build 4–8, Drop 2 16–32, Outro 8.
- **◐** EDMProd: Intro 8–16, Build 8–16, Drop 16–32, Variation 16, Outro 16.
- **◐** Gesamt 2–3,5 Minuten, kürzer als House oder Techno.
- **○** Etwas ändert sich alle 4–8 Takte.

**Aufbau**
- **◐** EDMProd-Beispiel: Kick ab Takt 9 nur auf der Eins. Ab Takt 13 verdichtet sie sich (alle 2 Zählzeiten, dann jede Zählzeit, dann halbe Zählzeiten), und ein Hochpass-Sweep läuft mit. Pad und Keys kommen kurz vor dem Drop, ein Tom-Fill eine Zählzeit davor.
- **●** Snare-Roll in Achteln, dann Sechzehnteln, dann 32teln in den Drop, dazu ein steigender Pitch, Riser und Noise.
- **●** Bass kurz vor dem Drop raus, Stille vor dem Drop (eine Zählzeit oder weniger), ein Vocal-Chop direkt davor, gelegentlich Fake-Drops.
- **○** Kick und 808 in den letzten 1–2 Zählzeiten vor dem Drop stumm. Keine Quelle sagt das ausdrücklich.

**Drums**
- **●** Snare oder Clap auf **Schritt 9** (Zählzeit 3 im Halftime-Gefühl). Manche Quellen schreiben das als „2 und 4“ im doppelten Tempo, gemeint ist dasselbe Gefühl.
- **◐** Kick auf 1, eine zusätzliche Kick kurz vor der Snare (um Schritt 8) und Offbeat-Kicks. Nicht überladen.
- **●** Hats als Grundmuster in Achteln oder Sechzehnteln. **Rolls** in 32teln oder 64teln vor Snares und am Taktende, dazu **Triolen** (1/8T, 1/16T). Rolls in der Tonhöhe verändern und die Velocity in den nächsten Takt hinein steigern.
- **◐** Eine Open Hat auf einem Offbeat, die von der nächsten Closed Hat abgeschnitten wird. Vor einem großen Roll einen oder zwei Takte gerade Hats.
- **◐** Rims und Shaker auf Kick oder Snare gelegt, Tom-Fills.

**808**
- **●** Ein 808-Ton unter jeder Kick, dazu ein paar Noten zum nächsten Takt hin, die der Snare antworten. Nicht jedes Sechzehntel füllen.
- **◐** Monofon und legato mit überlappenden Noten für Glides, höchstens 1–2 Glides pro Takt, auf einen Akzent hin. Keine Quelle nennt eine Glide-Zeit.
- **●** Folgt Tonart und Grundtönen: auf dem Grundton beginnen, zur Quinte gehen, im Drop tiefer. Bleibt meist innerhalb einer Oktave.
- **◐** Lage etwa **MIDI 28–43** (E1–G2, rund 41–98 Hz). F-, F#- und G-Moll liegen gut im 808-Bereich. Unter etwa 150 Hz mono, Sidechain zur Kick.

**Harmonik**
- **●** Moll: natürlich Moll, harmonisch Moll, Phrygisch oder Dorisch.
- **◐** Folgen: i–VI–v–i, i–v–iv, i–III–V–iv, i–iv–v, i–III–VI–VII, oft nur zwei Akkorde. Loops über 2–4 Takte.
- **◐** Den Grundton weglassen, wenn die 808 ihn spielt. Terz, Septime und Erweiterungen behalten, Akkordnoten kurz gegen die 808.
- **◐** Klavier oder Glocke oben, gedämpfte Pads darunter.
- **○** 1 Akkord pro 1–2 Takte.

**Lead und Hook**
- **●** Kurzes Motiv über 2 Takte in einem Loop über 2–4 Takte, sparsam, dunkel, Moll. Melodien eher sparsam einsetzen.
- **◐** Über der 808. Die Lead-Linie beginnt auf Quinte oder Septime statt auf dem Grundton.
- **◐** EDMProd-Drop-Lead: jeder zweite Grundton-Schlag mit einem Slide um +12, die erste Note um 2 Zählzeiten verzögert, Variation bei jeder zweiten Wiederholung.
- **●** Brass- oder Horn-Stabs im Drop.

**Sounds**
- 808: Simpler mit langem gestimmtem Sample und Saturator, oder Operator mit Sinus und Pitch-Hüllkurve.
- Drums: Drum Rack mit Drum Buss.
- Lead: Wavetable oder Analog mit verstimmten Sägezähnen.
- Brass-Stabs: Wavetable oder Analog mit schneller Filterhüllkurve.
- Plucks und Glocken: Operator oder Drift.
- Pads: Drift oder Wavetable.
- Vocal-Chops: Simpler.

**Filterfahrten** (Auto Filter, Clip-Automation)

| Abschnitt | Drums (High-pass) | Chords (Low-pass) |
|---|---|---|
| Intro | offen | 200 Hz → 20 kHz, öffnet spät |
| Build, Build 2 | 20 → 300 Hz bzw. 400 Hz | offen |
| Outro | offen | 20 kHz → 150 Hz |

Delay-Throws: Der Lead wirft im Drop, die Chords im Verse, jeweils auf der letzten Zählzeit jedes 8. Takts.

**Quellen:** Future Proof Music School (Festival Trap, Trap Beat in 10 Minutes, Genre Explorer); EDMProd (How to Make Trap); Cymatics (How to Make Trap); eMastered (Trap Drum Patterns, Trap Chord Progressions); Violet Recording (Trap Beats, 808 Patterns); Loopmasters (Top 10 Trap Tips); RouteNote (Build-ups, Drops); UJAM (Swells & Brass Stabs); Native Instruments (Hip-Hop Chord Progressions).

---

## Was die Engine umsetzt und was nicht

Stand nach dem Umbau auf die Rezepte (`compose/grooves.py`, `compose/hook.py`, Vorlagen in `compose/structures.py`).

**Umgesetzt**

| Thema | Umsetzung |
|---|---|
| Drums | Spuren als Daten pro Genre (Schritte, Velocity, Ghost-Notes, Zyklen), Swing nur auf den Spuren, die schwingen dürfen; wechselnde Fills alle 8 Takte, ein Roll in neue Abschnitte, Hat- und Clap-Rolls (Trap, Peak-Time); Spuren ohne passenden Pad im Kit fallen weg |
| Aufbau | Teile steigen innerhalb eines Abschnitts ein und aus (`"kick_hats:8,groove"`), eine Zählzeit Stille vor Drops, Drums 4 Takte vor dem D&B-Drop raus, der Bass verlässt das Outro zuerst, späte Spuren (Open Hat, Ride) erst in der zweiten Drop-Hälfte |
| Bass | Muster pro Genre: House offbeat, Peak-Time rollende Sechzehntel, Melodic zwischen den Kicks, D&B-Sub lang, Trap-808 unter den Kicks mit Glide; Lagen aus den Rezepten |
| Harmonik | Genre-Loops nach Tonart (Dur/Moll), Septakkorde für House und Liquid, parallele Moll-Stabs mit Akkordverschiebung für Peak-Time, Trap ohne Grundton |
| Lead | House, D&B, Trap: Hook mit Ruf/Antwort; Melodic: Arpeggio; Peak-Time: Acid-Line, die sich alle 8 Takte entwickelt und im letzten Peak steigt |
| Struktur | Vorlagen nach den Rezepten (Tempo: House 124, Melodic Techno 122, Peak-Time 128, D&B 174, Trap 145 BPM, mit `set_tempo` gesetzt); Längen Radio/Standard/Extended oder Minuten; mit `reference` folgen Abschnittsfolge und -längen einem vom Reference Analyzer analysierten Song, eingerastet auf das Phrasenraster des Genres (ein ungewarpter Song nur im eigenen Tempo); die Abschnittsarten ohne Gegenstück im Genre fallen auf eine verwandte zurück |
| Sounds | Neue Spuren bekommen Kit und Presets des Genres aus der Core Library; die Drum-Noten landen auf den Pads des Kits |
| Mix | Ein Reverb- und ein Delay-Return (vorhandene nutzt der Song), Fader-Pegel und Sends pro Rolle für neue Spuren; vorhandene Spuren behalten ihren Fader und senden nur in neue Returns. Nachhall und Delay-Zeit pro Genre, z. B. Melodic Techno 4,5 s, House 1,8 s |
| Automation | Auto-Filter-Fahrten pro Clip in allen Genres, dazu Resonanz-Fahrten (Acid in Peak-Time, Pads in Breaks und Builds). Delay-Throws: Der Send einer Rolle springt auf der letzten Zählzeit jedes 8. Takts auf -4 dB und fällt danach auf seinen Pegel zurück |
| Sidechain | Bass und Pads ducken unter der Kick. Eine eigene, stumme Sidechain-Spur (Operator, Fader auf -inf) spielt über den ganzen Song 1/16-Noten auf den Kick-Schritten des Genres, auch dort, wo die Kick pausiert (House, Melodic, Peak-Time jede Zählzeit, D&B Schritte 1 und 11, Trap 1, 8 und 11). Ein Compressor (4:1, Attack 1 ms) auf Bass und Pads hört ihr Post-FX-Signal. Threshold und Release pro Genre: House Bass -24 / Chords -18 dB, 160 ms; Melodic -22 / -16 dB, 200 ms; Peak-Time -24 / -20 dB, 120 ms; D&B nur Bass -18 dB, 90 ms; Trap nur 808 -14 dB, 100 ms |
| FX | Ein Riser füllt die letzten Takte (höchstens 8) vor jedem Drop, der auf einen anderen Abschnitt folgt, und endet an der Pause davor; Lautstärke und Filter-Makro steigen exponentiell. Ein Impact (Sub 808 Pitch Boom) trifft die Eins des Drops. Riser-Presets: House und Trap Riser Basic, Melodic und Peak-Time Hyper Riser, D&B ENCOM Riser |

**Noch offen**

| Thema | Warum |
|---|---|
| Vergleich mit echten Tracks | wie gut ein Song klingt, prüft bisher nur das Ohr. Ein Referenzsong gibt nur Abschnittsfolge und -längen vor (`reference`), die Klänge und Noten vergleicht die Engine nicht mit ihm |
| Weitere Genres | Trance, Dubstep, Hardstyle u. a. lassen sich als Vorlage ergänzen, sobald es ein Rezept gibt |
| Andere Taktarten | die Grooves sind 16-Schritt-Takte; `plan_song` braucht deshalb 4/4 und meldet das sonst |

## Master-Kette (`plan_master`)

`plan_master` setzt drei native Geräte ans Ende der Master-Spur: EQ Eight, Glue Compressor, Limiter. Das ist ein Startpunkt und kein fertiges Mastering, denn MidiBakery hört den Song nicht. Die Kette macht den Song nicht lauter, und eine Lautheit (LUFS) misst sie nicht.

| Gerät | Einstellung | House, Melodic Techno, Peak-Time Techno | Drum & Bass, Trap |
|---|---|---|---|
| EQ Eight | Low Cut (Band 1) | 30 Hz, 12 dB/Oktave | 20 Hz, 48 dB/Oktave |
| Glue Compressor | Ratio, Attack, Release | 2:1, 30 ms, Auto | gleich |
| Glue Compressor | Threshold | -10 dB als Startwert | gleich |
| Glue Compressor | Sidechain-EQ | High Pass 150 Hz | gleich |
| Limiter | Ceiling, Modus | -1 dB, True Peak (einstellbar -3 bis -0,1 dB) | gleich |
| Limiter | Input Gain | 0 dB | gleich |

- **●** Limiter als letztes Gerät, Ceiling -1 dBTP für Streaming. Spotify empfiehlt -2 dBTP nur für Master, die lauter als -14 LUFS sind.
- **●** Glue als Bus-Kompressor: 2:1, Attack 30 ms (die Transienten der Kick kommen durch), Release Auto, in den lautesten Teilen 1–2 dB Gain Reduction.
- **◐** Sidechain-EQ des Glue: Hochpass um 150 Hz, damit Kick und Sub nicht den ganzen Mix pumpen lassen. Das sagt nur eine Quelle.
- **◐** Low Cut auf dem Master bei 20–30 Hz entfernt Rumpeln unterhalb des Hörbaren. Die Quellen widersprechen sich, ob er auf den Master gehört oder nur auf einzelne Spuren:
  - Ein sanfter Cut bei 30 Hz gilt als unhörbar.
  - Sub-lastige Genres (808, Reese-Subs bis 25 Hz) brauchen einen tieferen, steilen Cut.
  - EQ Eight bietet als Steilheit nur 12 oder 48 dB/Oktave; eine Quelle nennt 24 dB/Oktave.
- **○** Glue-Threshold -10 dB: Das nennt keine Quelle. Weil die Kette nichts hört, ist es nur ein Startwert. Stelle den Threshold beim lautesten Teil so ein, dass die Nadel 1–2 dB zeigt.
- **○** Limiter Input Gain 0 dB ist Absicht: Lauter machen ohne Messung wäre geraten.

Gemessen in Live 12.4:
- Die Parameternamen der drei Geräte.
- Glue Attack, Ratio und Release sind Stufen (roh 0–6, 0–2, 0–6).
- Ein Batch, der Geräte einfügt und danach ihre Parameter setzt, hinterlässt zwei Undo-Schritte. `apply_plan` schreibt die Kette deshalb in zwei Batches; zwei Undo-Schritte entfernen sie.

`plan_master` setzt keine Kette auf einen Master, der schon einen Limiter, einen EQ Eight oder einen Glue Compressor hat. Andere Geräte dort bleiben vor der Kette; das MidiBakery Loudness Meter bleibt dahinter.

**Quellen:**
- Violet Recording (Bus-Kompressoren, Mastering-Kompressoren)
- MusicHub (Compressor-Einstellungen)
- Ableton-Forum (Glue Compressor auf dem Master)
- Production Advice (Spotify True Peak)
- Flux (True-Peak-Limiting)
- AES TD1008, nur über Zusammenfassungen
- Soundbridge (Sub-Bass)
- Richie ZXY (Mastering Drum & Bass)
- Gearspace, schwächer belegt (808, High-Pass-Filter, Master-Bus-Kompression)


## Lautheit messen (`measure_master`)

Das Max-for-Live-Gerät **MidiBakery Loudness Meter** sitzt als letztes Gerät auf dem Master und misst nach ITU-R BS.1770-4. `measure_master` liest seine Werte.

- **K-Filter:** pro Kanal zwei biquad~ (Pre-Filter als High Shelf, dann RLB-Hochpass). Die Koeffizienten berechnet `loudness.js` für die aktuelle Samplerate nach den Formeln von libebur128; bei 48 kHz sind es die Tabellenwerte aus BS.1770 (Test prüft das).
- **Blöcke:** average~ rms über 100 ms pro Kanal, alle 100 ms gelesen. Momentary = die letzten 4 Blöcke (400 ms), Short-term = die letzten 30 (3 s), wie EBU Tech 3341 sie festlegt.
- **Integrated:** jeder 400-ms-Block (75 % Überlappung) seit dem Reset; Gates bei -70 LUFS absolut und 10 LU unter dem ungegateten Mittel.
- **Kalibrierung:** ein 997-Hz-Sinus mit 0 dBFS in einem Kanal ergibt -3,01 LUFS (Test mit derselben Filterkette in Node).
- **Grenzen:** Sample-Peak statt True Peak (bis ~0,5 dB darunter). Max liest die Blöcke im Scheduler-Takt, nicht samplegenau: eine Näherung, kein geeichtes Messgerät.

**Quellen:**
- ITU-R BS.1770-4 (K-Filter, Gating, Kalibrierung)
- EBU R 128 und EBU Tech 3341 (Momentary, Short-term, Integrated)
- libebur128 (Koeffizienten für beliebige Sampleraten)

## Lücken

- **Lead-Dichte und Stab-Länge** nennen die Quellen kaum in Zahlen. Die Werte oben sind Konventionen (○) und gehören nach Gehör justiert.
- **Notenraster aus Attacks „Beat Dissected“** liegen nur als Bilder vor. Die Schrittpositionen stammen aus den Texten und aus anderen Quellen.
- **Sound-Techniken** wie Rumble, Reese und Sidechain sind Klangbearbeitung. Die Engine deutet sie durch Pausen, Dichte und Velocity an; Sidechain baut sie als Compressor, den eine stumme Trigger-Spur steuert. Filterfahrten und Resonanz schreibt sie als Clip-Automation eines Auto Filters, Delay-Throws als Send-Automation, Riser als Preset mit Hüllkurven auf Lautstärke und Filter-Makro.
- **Breaks und Samples** (Amen, Vocal-Chops, 808-Samples) kann Lives API nicht laden.
