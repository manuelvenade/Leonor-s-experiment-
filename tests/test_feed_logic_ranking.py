import pandas as pd

from feed_logic import finalize_player_sequence


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


def test_finalize_player_sequence_adds_commented_post_column_if_missing():
    posts = pd.DataFrame({
        'doc_id': [1, 2],
        'sequence': [1, 2],
    })

    result = finalize_player_sequence(posts)

    assert result['commented_post'].tolist() == [0, 0]
