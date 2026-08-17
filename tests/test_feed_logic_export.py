from feed_logic import build_export_row, compute_session_aggregates, parse_json_field


def test_parse_json_field_keys_entries_by_doc_id():
    raw = '[{"doc_id": 3, "liked": true}, {"doc_id": 7, "liked": false}]'

    parsed = parse_json_field(raw)

    assert parsed == {
        3: {'doc_id': 3, 'liked': True},
        7: {'doc_id': 7, 'liked': False},
    }


def test_parse_json_field_handles_empty_and_invalid_input():
    assert parse_json_field('') == {}
    assert parse_json_field(None) == {}
    assert parse_json_field('not json') == {}


def make_participant(**overrides):
    base = dict(
        session_code='sess1',
        participant_code='p1',
        participant_label='label1',
        id_in_group=1,
        feed_condition='SPORT',
        nav_condition='friction',
        preference_alignment='most',
        topic_ranking='SPORT, FOOD, TRAVEL',
        completed_feed=True,
        last_position_viewed=6,
        total_watch_time_seconds=42.0,
        session_duration_seconds=88.5,
        completion_rate=1.0,
    )
    base.update(overrides)
    return base


def test_build_export_row_pulls_matching_doc_id_entries():
    viewport = {5: {'duration': 12.4, 'video_length_seconds': 20.0}}
    likes = {5: {'liked': True}}
    replies = {5: {'hasReply': True, 'reply': 'nice!'}}
    friction = {5: {'delay_seconds': 2.1, 'voluntary_hesitation_seconds': 0.5}}
    promoted = {5: {'clicked': True}}

    row = build_export_row(
        make_participant(), 5, 1,
        viewport, likes, replies, friction, promoted,
    )

    assert row == [
        'sess1', 'p1', 'label1', 1, 'SPORT', 'friction', 'most', 'SPORT, FOOD, TRAVEL', 5, 1,
        12.4, 20.0, 62.0,
        True, True, 'nice!',
        2.1, 0.5, True,
        True, 6,
        42.0, 88.5, 1.0,
    ]


def test_build_export_row_defaults_missing_doc_id_to_blank():
    row = build_export_row(
        make_participant(nav_condition='normal'), 99, 3,
        {}, {}, {}, {}, {},
    )

    assert row == [
        'sess1', 'p1', 'label1', 1, 'SPORT', 'normal', 'most', 'SPORT, FOOD, TRAVEL', 99, 3,
        '', '', '',
        '', '', '',
        '', '', '',
        True, 6,
        42.0, 88.5, 1.0,
    ]


def test_build_export_row_leaves_watch_percentage_blank_without_video_length():
    viewport = {5: {'duration': 12.4}}  # no video_length_seconds

    row = build_export_row(
        make_participant(), 5, 1,
        viewport, {}, {}, {}, {},
    )

    assert row[10] == 12.4   # watch_time_seconds
    assert row[11] == ''     # video_length_seconds
    assert row[12] == ''     # watch_percentage


def test_compute_session_aggregates_sums_watch_time_and_computes_completion_rate():
    viewport = {
        0: {'duration': 10.0},
        1: {'duration': 5.5},
        2: {'duration': 'not a number'},  # malformed entries are ignored, not summed
    }

    result = compute_session_aggregates(viewport, last_position_viewed=3, total_videos=6, session_duration_seconds=120.0)

    assert result == {
        'total_watch_time_seconds': 15.5,
        'completion_rate': 0.5,
        'session_duration_seconds': 120.0,
    }


def test_compute_session_aggregates_handles_zero_total_videos():
    result = compute_session_aggregates({}, last_position_viewed=0, total_videos=0, session_duration_seconds='')

    assert result == {
        'total_watch_time_seconds': 0,
        'completion_rate': 0,
        'session_duration_seconds': '',
    }
