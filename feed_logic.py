"""Pure, Django-free helper functions for the DICE app.

Kept outside the DICE package so these can be unit tested with plain
pytest — DICE/__init__.py imports otree.api and defines Django model
classes at import time, which requires a configured Django app registry
and cannot be safely imported by a bare pytest run.
"""
import itertools
import json
import random


def assign_cycle_pairs(topics, nav_conditions, rng=None):
    """Build a shuffled list of every (topic, nav_condition) pair.

    Used with itertools.cycle() to round-robin-assign participants across
    all cells of a crossed factorial design, guaranteeing exact balance
    every len(topics) * len(nav_conditions) participants.
    """
    rng = rng if rng is not None else random.Random()
    pairs = list(itertools.product(topics, nav_conditions))
    rng.shuffle(pairs)
    return pairs
