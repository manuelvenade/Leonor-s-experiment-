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


def parse_json_field(raw_json):
    """Parse a JSON list field into a dict keyed by doc_id.

    Returns {} on missing, empty, or invalid input.
    """
    try:
        return {entry['doc_id']: entry for entry in json.loads(raw_json or '[]')}
    except (json.JSONDecodeError, KeyError, TypeError):
        return {}


def build_export_row(session_code, participant_code, participant_label, id_in_group,
                      feed_condition, nav_condition, doc_id, position,
                      viewport, likes, replies, friction, promoted):
    """Assemble one custom_export row from parsed per-doc_id lookup dicts."""
    return [
        session_code,
        participant_code,
        participant_label,
        id_in_group,
        feed_condition,
        nav_condition,
        doc_id,
        position,
        viewport.get(doc_id, {}).get('duration', ''),
        likes.get(doc_id, {}).get('liked', ''),
        replies.get(doc_id, {}).get('hasReply', ''),
        replies.get(doc_id, {}).get('reply', ''),
        friction.get(doc_id, {}).get('delay_seconds', ''),
        promoted.get(doc_id, {}).get('clicked', ''),
    ]


def validate_matched_stats(df, group_col='condition', position_col='sequence',
                            stat_cols=('likes', 'reposts', 'replies')):
    """Check that every position has identical stat values across all groups.

    Returns a list of human-readable violation messages (empty if valid).
    Used to guard the "same initial condition per position across topics"
    invariant that the friction-scroll design depends on.
    """
    violations = []
    for position, position_df in df.groupby(position_col):
        for stat_col in stat_cols:
            unique_values = position_df[stat_col].unique()
            if len(unique_values) > 1:
                mapping = dict(zip(position_df[group_col], position_df[stat_col]))
                violations.append(
                    f"{position_col}={position}: '{stat_col}' differs across groups ({mapping})"
                )
    return violations
