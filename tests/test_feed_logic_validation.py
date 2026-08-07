import pandas as pd

from feed_logic import validate_matched_stats


def test_validate_matched_stats_passes_when_all_groups_match():
    df = pd.DataFrame({
        'condition': ['SPORT', 'FOOD', 'TRAVEL', 'SPORT', 'FOOD', 'TRAVEL'],
        'sequence': [1, 1, 1, 2, 2, 2],
        'likes': [100, 100, 100, 200, 200, 200],
        'reposts': [10, 10, 10, 20, 20, 20],
        'replies': [5, 5, 5, 8, 8, 8],
    })

    assert validate_matched_stats(df) == []


def test_validate_matched_stats_flags_a_mismatch():
    df = pd.DataFrame({
        'condition': ['SPORT', 'FOOD', 'TRAVEL'],
        'sequence': [1, 1, 1],
        'likes': [100, 999, 100],
        'reposts': [10, 10, 10],
        'replies': [5, 5, 5],
    })

    violations = validate_matched_stats(df)

    assert len(violations) == 1
    assert 'likes' in violations[0]
    assert 'sequence=1' in violations[0]
