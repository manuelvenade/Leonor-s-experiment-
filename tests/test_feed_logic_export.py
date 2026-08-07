from feed_logic import build_export_row, parse_json_field


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


def test_build_export_row_pulls_matching_doc_id_entries():
    viewport = {5: {'duration': 12.4}}
    likes = {5: {'liked': True}}
    replies = {5: {'hasReply': True, 'reply': 'nice!'}}
    friction = {5: {'delay_seconds': 2.1}}
    promoted = {}

    row = build_export_row(
        'sess1', 'p1', 'label1', 1, 'SPORT', 'friction', 5, 1,
        viewport, likes, replies, friction, promoted,
    )

    assert row == [
        'sess1', 'p1', 'label1', 1, 'SPORT', 'friction', 5, 1,
        12.4, True, True, 'nice!', 2.1, '',
    ]


def test_build_export_row_defaults_missing_doc_id_to_blank():
    row = build_export_row(
        'sess1', 'p1', 'label1', 1, 'SPORT', 'normal', 99, 3,
        {}, {}, {}, {}, {},
    )

    assert row == [
        'sess1', 'p1', 'label1', 1, 'SPORT', 'normal', 99, 3,
        '', '', '', '', '', '',
    ]
