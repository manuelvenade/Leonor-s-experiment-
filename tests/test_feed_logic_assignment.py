import random

from feed_logic import assign_cycle_pairs


def test_assign_cycle_pairs_covers_full_cartesian_product():
    topics = ['SPORT', 'FOOD', 'TRAVEL']
    nav_conditions = ['normal', 'friction']

    pairs = assign_cycle_pairs(topics, nav_conditions, rng=random.Random(42))

    assert len(pairs) == 6
    assert len(set(pairs)) == 6
    assert set(pairs) == {
        ('SPORT', 'normal'), ('SPORT', 'friction'),
        ('FOOD', 'normal'), ('FOOD', 'friction'),
        ('TRAVEL', 'normal'), ('TRAVEL', 'friction'),
    }


def test_assign_cycle_pairs_is_deterministic_for_a_given_seed():
    topics = ['SPORT', 'FOOD', 'TRAVEL']
    nav_conditions = ['normal', 'friction']

    pairs_a = assign_cycle_pairs(topics, nav_conditions, rng=random.Random(7))
    pairs_b = assign_cycle_pairs(topics, nav_conditions, rng=random.Random(7))

    assert pairs_a == pairs_b


def test_assign_cycle_pairs_generalizes_to_preference_alignment():
    alignments = ['most', 'least']
    nav_conditions = ['normal', 'friction']

    pairs = assign_cycle_pairs(alignments, nav_conditions, rng=random.Random(3))

    assert len(pairs) == 4
    assert set(pairs) == {
        ('most', 'normal'), ('most', 'friction'),
        ('least', 'normal'), ('least', 'friction'),
    }
