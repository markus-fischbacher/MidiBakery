"""Composition engine: music theory, seeded generators, note transformations and Plan/Apply.

Generators only produce note lists; Live is changed exclusively through the
bridge ops ``clip.create`` and ``notes.apply``, bundled into one ``batch``.
"""

from midishower.compose.plan import Plan, PlanStore, apply_plan, build_plan
from midishower.compose.specs import BassSpec, ChordsSpec, DrumsSpec, MelodySpec, Step, TransformSpec

__all__ = [
    "BassSpec",
    "ChordsSpec",
    "DrumsSpec",
    "MelodySpec",
    "Plan",
    "PlanStore",
    "Step",
    "TransformSpec",
    "apply_plan",
    "build_plan",
]
