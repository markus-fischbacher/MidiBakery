"""Synthetic Live Sets (gzipped XML shaped like Live 11 and 12 write them) for the importer's tests."""

import gzip
from pathlib import Path


def note(time, duration=0.25, velocity=100, enabled=True):
    return f'<MidiNoteEvent Time="{time}" Duration="{duration}" Velocity="{velocity}" IsEnabled="{str(enabled).lower()}"/>'


def keytrack(pitch, *notes):
    return f'<KeyTrack><Notes>{"".join(notes)}</Notes><MidiKey Value="{pitch}"/></KeyTrack>'


def midi_clip(start, end, keytracks, loop_start=0, loop_end=None, start_relative=0, loop_on=False, name=""):
    loop_end = (end - start) if loop_end is None else loop_end
    return (
        f'<MidiClip Time="{start}"><CurrentStart Value="{start}"/><CurrentEnd Value="{end}"/><Name Value="{name}"/>'
        f'<Loop><LoopStart Value="{loop_start}"/><LoopEnd Value="{loop_end}"/><StartRelative Value="{start_relative}"/>'
        f'<LoopOn Value="{str(loop_on).lower()}"/></Loop><Notes><KeyTracks>{"".join(keytracks)}</KeyTracks></Notes></MidiClip>'
    )


def audio_clip(start, end, name="loop.wav"):
    return (
        f'<AudioClip Time="{start}"><CurrentStart Value="{start}"/><CurrentEnd Value="{end}"/><Name Value="{name}"/>'
        f'<SampleRef><FileRef><RelativePath Value="Samples/Imported/{name}"/></FileRef></SampleRef></AudioClip>'
    )


def drum_rack(pads):
    branches = "".join(
        f'<DrumBranch><Name><EffectiveName Value="{name}"/></Name>'
        f'<ZoneSettings><ReceivingNote Value="{128 - pitch}"/></ZoneSettings></DrumBranch>' for pitch, name in pads)
    return f'<DrumGroupDevice><UserName Value=""/><Branches>{branches}</Branches></DrumGroupDevice>'


def track(kind, name, clips="", devices="", group=-1, id_=1):
    return (
        f'<{kind} Id="{id_}"><Name><EffectiveName Value="{name}"/></Name><TrackGroupId Value="{group}"/>'
        f'<DeviceChain><DeviceChain><Devices>{devices}</Devices></DeviceChain><MainSequencer>'
        f'<ClipTimeable><ArrangerAutomation><Events>{clips}</Events></ArrangerAutomation></ClipTimeable>'
        f'<ClipSlotList/></MainSequencer></DeviceChain></{kind}>'
    )


def write_set(path, tracks, *, live=12, tempo=128, signature=201, locators=()):
    """Live 12 writes MainTrack, Live 11 MasterTrack; both keep return tracks inside <Tracks>."""
    main = "MainTrack" if live >= 12 else "MasterTrack"
    loc = "".join(f'<Locator><Time Value="{t}"/><Name Value="{n}"/></Locator>' for t, n in locators)
    xml = (
        f'<?xml version="1.0" encoding="UTF-8"?><Ableton Creator="Ableton Live {live}.0.1">'
        f'<LiveSet><{main}><DeviceChain><Mixer><Tempo><Manual Value="{tempo}"/></Tempo>'
        f'<TimeSignature><Manual Value="{signature}"/></TimeSignature></Mixer><DeviceChain><Devices/></DeviceChain>'
        f'</DeviceChain></{main}><Tracks>{"".join(tracks)}</Tracks><Locators><Locators>{loc}</Locators></Locators>'
        f'</LiveSet></Ableton>'
    )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(xml.encode()))
    return path


def four_on_the_floor(bars, start_bar=0):
    """A kick clip: one hit per beat for `bars` bars from bar `start_bar`."""
    beats = bars * 4
    return midi_clip(start_bar * 4, start_bar * 4 + beats, [keytrack(36, *(note(b, 0.25) for b in range(beats)))])


def edm_set(path, live=12, **kwargs):
    """Intro (kick), a drop with kick+bass+lead+drums, a break, a second drop: 8 + 8 + 8 + 8 bars."""
    def over(*spans, make):
        return "".join(make(a, b) for a, b in spans)

    def kicks(a, b):
        return four_on_the_floor(b - a, a)

    def bass(a, b):
        return midi_clip(a * 4, b * 4, [keytrack(31, *(note(i, 0.5) for i in range(0, (b - a) * 4)))], name="")

    def lead(a, b):
        return midi_clip(a * 4, b * 4, [keytrack(67, *(note(i * 8, 4) for i in range((b - a) // 2))), keytrack(70, *(note(i * 8 + 4, 4) for i in range((b - a) // 2)))])

    def drums(a, b):
        return midi_clip(a * 4, b * 4, [keytrack(37, *(note(i + 1, 0.25) for i in range(0, (b - a) * 4, 2)))])

    tracks = [
        track("MidiTrack", "Kick", over((0, 8), (8, 16), (24, 32), make=kicks), id_=1),
        track("MidiTrack", "Bass", over((4, 16), (24, 32), make=bass), id_=2),
        track("MidiTrack", "Lead", over((8, 16), (24, 32), make=lead), id_=3),
        track("MidiTrack", "Drums", over((8, 16), (24, 32), make=drums),
              devices=drum_rack([(36, "Kick"), (37, "Clap"), (38, "Hat")]), id_=4),
        track("ReturnTrack", "A-Reverb", id_=5),
    ]
    return write_set(path, tracks, live=live, **kwargs)
