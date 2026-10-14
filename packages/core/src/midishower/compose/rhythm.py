"""Rhythm grid: meter-aware pulses, swing and quantisation. Times are in beats (quarter notes)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Meter:
    numerator: int = 4
    denominator: int = 4

    @property
    def beats_per_bar(self) -> float:
        return self.numerator * 4 / self.denominator

    @property
    def pulses(self) -> tuple[float, ...]:
        """Felt beats inside one bar, as offsets in beats.

        x/4 and x/2: every notated beat. Compound x/8 (6/8, 9/8, 12/8): dotted
        quarters. Other x/8 meters (5/8, 7/8): groups of 2 and 3 eighths, the
        3-groups last (7/8 = 2+2+3).
        """
        if self.denominator != 8:
            unit = 4 / self.denominator
            return tuple(i * unit for i in range(self.numerator))
        if self.numerator % 3 == 0 and self.numerator > 3:
            return tuple(i * 1.5 for i in range(self.numerator // 3))
        n = self.numerator
        if n <= 3:
            groups = [n]
        elif n % 2:
            groups = [2] * ((n - 3) // 2) + [3]
        else:
            groups = [2] * (n // 2)
        offsets, position = [], 0.0
        for group in groups:
            offsets.append(position)
            position += group * 0.5
        return tuple(offsets)

    def pulse_length(self, index: int) -> float:
        pulses = self.pulses + (self.beats_per_bar,)
        return pulses[index + 1] - pulses[index]

    @property
    def backbeats(self) -> tuple[float, ...]:
        """Where a snare/clap naturally falls: every second pulse, or the last pulse in odd meters."""
        pulses = self.pulses
        if len(pulses) == 1:
            return (self.beats_per_bar / 2,)
        if len(pulses) == 3:
            return (pulses[1], pulses[2]) if self.denominator != 8 else (pulses[2],)
        return pulses[1::2]

    def offbeats(self) -> tuple[float, ...]:
        return tuple(p + self.pulse_length(i) / 2 for i, p in enumerate(self.pulses))

    def accent(self, offset_in_bar: float) -> float:
        """Metric weight 0..1 of a position inside a bar."""
        eps = 1e-6
        if abs(offset_in_bar) < eps:
            return 1.0
        if any(abs(offset_in_bar - p) < eps for p in self.pulses):
            return 0.8
        if any(abs(offset_in_bar - p) < eps for p in self.offbeats()):
            return 0.6
        if abs((offset_in_bar / 0.25) - round(offset_in_bar / 0.25)) < eps:
            return 0.4
        return 0.25


@dataclass(frozen=True)
class Grid:
    meter: Meter = field(default_factory=Meter)
    step: float = 0.25
    swing: float = 0.0  # 0 = straight, 1 = full triplet feel
    swing_unit: float = 0.25  # swung note value in beats: 0.25 = 16ths, 0.5 = 8ths

    @property
    def steps_per_bar(self) -> int:
        return max(1, round(self.meter.beats_per_bar / self.step))

    def swung(self, offset_in_bar: float) -> float:
        """Delay every second `swing_unit` (the off-beat 16th or 8th) by up to a triplet."""
        if not self.swing:
            return offset_in_bar
        units = offset_in_bar / self.swing_unit
        if abs(units - round(units)) < 1e-9 and round(units) % 2 == 1:
            return offset_in_bar + self.swing_unit * self.swing / 3
        return offset_in_bar

    def position(self, bar: int, step_index: int) -> float:
        """Start time of a grid step, with swing applied."""
        return bar * self.meter.beats_per_bar + self.swung(step_index * self.step)

    def bar_positions(self, bar: int) -> list[float]:
        return [self.position(bar, i) for i in range(self.steps_per_bar)]

    def quantize(self, time: float, strength: float = 1.0) -> float:
        bpb = self.meter.beats_per_bar
        bar = int(time // bpb)
        best = time
        best_distance = float("inf")
        for b in (bar - 1, bar, bar + 1):
            if b < 0:
                continue
            k = round((time - b * bpb) / self.step)
            for index in (k - 1, k, k + 1):
                if index < 0:
                    continue
                candidate = b * bpb + self.swung(index * self.step)
                distance = abs(candidate - time)
                if distance < best_distance - 1e-12:
                    best, best_distance = candidate, distance
        return time + (best - time) * strength

    def offset_in_bar(self, time: float) -> float:
        return time % self.meter.beats_per_bar
