import pandas as pd
import pytest

from feed_logic import finalize_player_sequence, select_ranked_topic, parse_topic_ranking, format_topic_ranking


def test_finalize_player_sequence_sorts_by_existing_sequence():
    posts = pd.DataFrame({
        'doc_id': [3, 1, 2],
        'sequence': [3, 1, 2],
    })

    result = finalize_player_sequence(posts)

    assert result['doc_id'].tolist() == [1, 2, 3]


def test_finalize_player_sequence_fills_missing_sequence_values():
    posts = pd.DataFrame({
        'doc_id': [10, 20, 30],
        'sequence': [1.0, None, None],
    })

    result = finalize_player_sequence(posts)

    # doc_id 10 already had sequence=1, so it must stay first...
    assert result.iloc[0]['doc_id'] == 10
    # ...and the other two fill the remaining ranks {2, 3}, in some order.
    assert sorted(result['sequence'].tolist()) == [1, 2, 3]
    assert set(result['doc_id'].tolist()) == {10, 20, 30}


def test_finalize_player_sequence_forces_commented_post_to_sequence_one():
    posts = pd.DataFrame({
        'doc_id': [1, 2, 3],
        'sequence': [1, 2, 3],
        'commented_post': [0, 1, 0],
    })

    result = finalize_player_sequence(posts)

    assert result.iloc[0]['doc_id'] == 2
    # The displaced doc_id=1 (which held sequence=1 before doc_id=2 took
    # over that slot) must land on a valid, unused rank -- not overwritten,
    # not dropped, not left tied with anything else.
    assert sorted(result['sequence'].tolist()) == [1, 2, 3]
    assert set(result['doc_id'].tolist()) == {1, 2, 3}


def test_finalize_player_sequence_adds_commented_post_column_if_missing():
    posts = pd.DataFrame({
        'doc_id': [1, 2],
        'sequence': [1, 2],
    })

    result = finalize_player_sequence(posts)

    assert result['commented_post'].tolist() == [0, 0]


def test_select_ranked_topic_returns_first_item_when_alignment_is_most():
    assert select_ranked_topic(['FOOD', 'SPORT', 'TRAVEL'], 'most') == 'FOOD'


def test_select_ranked_topic_returns_last_item_when_alignment_is_least():
    assert select_ranked_topic(['FOOD', 'SPORT', 'TRAVEL'], 'least') == 'TRAVEL'


def test_select_ranked_topic_raises_on_unexpected_alignment():
    with pytest.raises(ValueError):
        select_ranked_topic(['FOOD', 'SPORT', 'TRAVEL'], None)


def test_parse_topic_ranking_returns_parsed_list_when_valid_permutation():
    result = parse_topic_ranking('["TRAVEL", "FOOD", "SPORT"]', ['SPORT', 'FOOD', 'TRAVEL'])
    assert result == ['TRAVEL', 'FOOD', 'SPORT']


def test_parse_topic_ranking_falls_back_on_missing_input():
    result = parse_topic_ranking('', ['SPORT', 'FOOD', 'TRAVEL'])
    assert result == ['SPORT', 'FOOD', 'TRAVEL']


def test_parse_topic_ranking_falls_back_on_invalid_json():
    result = parse_topic_ranking('not json', ['SPORT', 'FOOD', 'TRAVEL'])
    assert result == ['SPORT', 'FOOD', 'TRAVEL']


def test_parse_topic_ranking_falls_back_when_topics_dont_match():
    # Missing TRAVEL, or containing a topic that doesn't exist: both invalid.
    result = parse_topic_ranking('["SPORT", "FOOD"]', ['SPORT', 'FOOD', 'TRAVEL'])
    assert result == ['SPORT', 'FOOD', 'TRAVEL']


def test_parse_topic_ranking_falls_back_on_non_string_items():
    # Well-formed JSON that isn't a list of strings (e.g. a tampered
    # submission) must fall back rather than crash on sorted()/join().
    result = parse_topic_ranking('["SPORT", 1, 2]', ['SPORT', 'FOOD', 'TRAVEL'])
    assert result == ['SPORT', 'FOOD', 'TRAVEL']


def test_format_topic_ranking_joins_list_with_commas():
    assert format_topic_ranking('["FOOD", "SPORT", "TRAVEL"]') == 'FOOD, SPORT, TRAVEL'


def test_format_topic_ranking_returns_empty_string_for_missing_input():
    assert format_topic_ranking('') == ''
    assert format_topic_ranking(None) == ''


def test_format_topic_ranking_returns_empty_string_for_non_string_items():
    assert format_topic_ranking('["FOOD", 1, "TRAVEL"]') == ''
