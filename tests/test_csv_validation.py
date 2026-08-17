import os

import pandas as pd

from feed_logic import validate_matched_stats

CSV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'DICE', 'static', 'data', 'friction_scroll_videos.csv',
)


def load_csv():
    return pd.read_csv(CSV_PATH, sep=';')


def test_csv_has_eighteen_rows():
    df = load_csv()
    assert len(df) == 18


def test_csv_has_three_topics_with_six_positions_each():
    df = load_csv()
    assert set(df['condition'].unique()) == {'SPORT', 'FOOD', 'TRAVEL'}
    for condition, group in df.groupby('condition'):
        assert sorted(group['sequence'].tolist()) == [1, 2, 3, 4, 5, 6]


def test_csv_has_exactly_one_ad_per_topic_at_position_six():
    df = load_csv()
    for condition, group in df.groupby('condition'):
        ad_rows = group[group['is_ad'] == 1]
        assert len(ad_rows) == 1
        assert ad_rows.iloc[0]['sequence'] == 6


def test_csv_ad_content_is_identical_across_topics():
    df = load_csv()
    ad_rows = df[df['is_ad'] == 1]
    for col in ('text', 'video', 'likes', 'reposts', 'replies', 'username', 'handle'):
        assert ad_rows[col].nunique() == 1, f"ad '{col}' differs across topics"


def test_csv_engagement_stats_match_across_topics_by_position():
    df = load_csv()
    violations = validate_matched_stats(df)
    assert violations == [], violations
