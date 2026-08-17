"""Pure, Django-free helper functions for the DICE app.

Kept outside the DICE package so these can be unit tested with plain
pytest — DICE/__init__.py imports otree.api and defines Django model
classes at import time, which requires a configured Django app registry
and cannot be safely imported by a bare pytest run.
"""
import itertools
import json
import random

import numpy as np


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


def finalize_player_sequence(posts):
    """Fill missing `sequence` values with a random permutation of the
    unused ranks, then sort by sequence. Mutates and returns `posts`.

    Shared by the immediate-assignment path (creating_session, when topic
    is researcher-assigned) and the deferred path (after the topic-ranking
    survey, when topic depends on the participant's own ranking).
    """
    if 'commented_post' not in posts.columns:
        posts['commented_post'] = 0

    # If there's a commented_post, force it to sequence 1, and reassign conflicts
    commented_mask = posts['commented_post'] == 1
    if commented_mask.any():
        posts.loc[commented_mask, 'sequence'] = 1
        # Any other posts that already have sequence 1 need to be reassigned
        conflict_mask = (posts['sequence'] == 1) & ~commented_mask
        if conflict_mask.any():
            ranks = np.arange(1, len(posts) + 1)
            used_ranks = posts.loc[~conflict_mask, 'sequence'].dropna()
            available_ranks = ranks[~np.isin(ranks, used_ranks)]
            np.random.shuffle(available_ranks)
            posts.loc[conflict_mask, 'sequence'] = available_ranks[:sum(conflict_mask)]

    # Fill NaN sequences with available ranks
    ranks = np.arange(1, len(posts) + 1)
    available_ranks = ranks[~np.isin(ranks, posts['sequence'].dropna())]
    np.random.shuffle(available_ranks)
    missing_indices = posts['sequence'].isnull()
    posts.loc[missing_indices, 'sequence'] = available_ranks[:sum(missing_indices)]

    posts.sort_values(by='sequence', inplace=True)
    posts.reset_index(drop=True, inplace=True)
    return posts


def parse_json_field(raw_json):
    """Parse a JSON list field into a dict keyed by doc_id.

    Returns {} on missing, empty, or invalid input.
    """
    try:
        return {entry['doc_id']: entry for entry in json.loads(raw_json or '[]')}
    except (json.JSONDecodeError, KeyError, TypeError):
        return {}


def build_export_row(participant, doc_id, position, viewport, likes, replies, friction, promoted):
    """Assemble one custom_export row from parsed per-doc_id lookup dicts.

    `participant` is a dict of participant-level values that stay constant
    across every row for a given participant: session_code, participant_code,
    participant_label, id_in_group, feed_condition, nav_condition,
    completed_feed, last_position_viewed, total_watch_time_seconds,
    session_duration_seconds, completion_rate.
    """
    viewport_entry = viewport.get(doc_id, {})
    watch_time = viewport_entry.get('duration', '')
    video_length = viewport_entry.get('video_length_seconds', '')

    watch_percentage = ''
    if isinstance(watch_time, (int, float)) and isinstance(video_length, (int, float)) and video_length > 0:
        watch_percentage = round(watch_time / video_length * 100, 1)

    friction_entry = friction.get(doc_id, {})

    return [
        participant['session_code'],
        participant['participant_code'],
        participant['participant_label'],
        participant['id_in_group'],
        participant['feed_condition'],
        participant['nav_condition'],
        doc_id,
        position,
        watch_time,
        video_length,
        watch_percentage,
        likes.get(doc_id, {}).get('liked', ''),
        replies.get(doc_id, {}).get('hasReply', ''),
        replies.get(doc_id, {}).get('reply', ''),
        friction_entry.get('delay_seconds', ''),
        friction_entry.get('voluntary_hesitation_seconds', ''),
        promoted.get(doc_id, {}).get('clicked', ''),
        participant['completed_feed'],
        participant['last_position_viewed'],
        participant['total_watch_time_seconds'],
        participant['session_duration_seconds'],
        participant['completion_rate'],
    ]


def compute_session_aggregates(viewport, last_position_viewed, total_videos, session_duration_seconds):
    """Compute participant-level session aggregates from parsed viewport data.

    total_watch_time_seconds sums each video's dwell time (malformed/missing
    entries are skipped rather than raising). completion_rate is
    last_position_viewed / total_videos, or 0 if total_videos is 0.
    session_duration_seconds is passed through unchanged — it's a single
    client-reported value, not derived from viewport.
    """
    total_watch_time = sum(
        entry.get('duration', 0) for entry in viewport.values()
        if isinstance(entry.get('duration'), (int, float))
    )
    completion_rate = round(last_position_viewed / total_videos, 3) if total_videos else 0

    return {
        'total_watch_time_seconds': round(total_watch_time, 3),
        'completion_rate': completion_rate,
        'session_duration_seconds': session_duration_seconds,
    }


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
