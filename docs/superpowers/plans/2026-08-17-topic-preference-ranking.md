# Topic Preference Ranking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `FrictionScrollStudy`'s balanced 3-way topic assignment with a preference-driven one: participants rank SPORT/FOOD/TRAVEL before the feed, then see either their most- or least-preferred topic (never the middle), with that most/least choice being the new balanced, researcher-controlled factor (crossed with `nav_condition` into a 2×2).

**Architecture:** A new `B_TopicRanking` page (drag-free ▲▼ reorder list) is inserted between consent and the briefing page. Topic assignment moves from `creating_session()` (which runs before any participant interaction) to that page's `before_next_page` (which runs after the participant submits their ranking) — everything upstream of topic-specific filtering gets deferred. Pure logic (ranking selection, sequence finalization, JS reorder math) is extracted into already-tested-style helper modules (`feed_logic.py`, a new `topic_ranking.js`) so it's covered by plain pytest/Node tests; the oTree page glue itself is verified live (this codebase has no way to unit-test `DICE/__init__.py` — importing it requires a configured Django app registry, which is why `feed_logic.py` exists as a separate Django-free module).

**Tech Stack:** Python (oTree/Django, pandas, numpy), vanilla JS, pytest, Node `assert`, Playwright (manual verification only, not part of the automated suite).

**Full design spec:** `docs/superpowers/specs/2026-08-17-topic-preference-ranking-design.md` — read this first if anything in a task seems under-explained; it has the full rationale.

---

### Task 1: Extract `finalize_player_sequence` helper

**Files:**
- Modify: `feed_logic.py`
- Test: `tests/test_feed_logic_ranking.py` (new)

This pulls the sequence-fill/sort logic that currently lives inline in `creating_session`'s per-player loop (`DICE/__init__.py:94-106`) out into a standalone, testable function. It isn't wired into `__init__.py` yet — that happens in Task 4. This task only creates and tests the function.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_feed_logic_ranking.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_feed_logic_ranking.py -v`
Expected: FAIL with `ImportError: cannot import name 'finalize_player_sequence' from 'feed_logic'`

- [ ] **Step 3: Add the function to `feed_logic.py`**

Add `import numpy as np` to the top of `feed_logic.py` (alongside the existing `itertools`/`json`/`random` imports), then add this function after `assign_cycle_pairs` (i.e. after line 23):

```python
def finalize_player_sequence(posts):
    """Fill missing `sequence` values with a random permutation of the
    unused ranks, then sort by sequence. Mutates and returns `posts`.

    Shared by the immediate-assignment path (creating_session, when topic
    is researcher-assigned) and the deferred path (after the topic-ranking
    survey, when topic depends on the participant's own ranking).
    """
    if 'commented_post' in posts.columns:
        posts.loc[posts['commented_post'] == 1, 'sequence'] = 1
    else:
        posts['commented_post'] = 0

    ranks = np.arange(1, len(posts) + 1)
    available_ranks = ranks[~np.isin(ranks, posts['sequence'].dropna())]

    np.random.shuffle(available_ranks)
    missing_indices = posts['sequence'].isnull()
    posts.loc[missing_indices, 'sequence'] = available_ranks[:sum(missing_indices)]

    posts.sort_values(by='sequence', inplace=True)
    posts.reset_index(drop=True, inplace=True)
    return posts
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_feed_logic_ranking.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add feed_logic.py tests/test_feed_logic_ranking.py
git commit -m "feat: extract finalize_player_sequence helper for reuse"
```

---

### Task 2: Ranking-selection helpers

**Files:**
- Modify: `feed_logic.py`
- Test: `tests/test_feed_logic_ranking.py`, `tests/test_feed_logic_assignment.py`

Adds the logic that turns a participant's submitted ranking + their assigned `preference_alignment` into an actual topic, plus a safe parser for the raw client-submitted JSON and a formatter for the export column. Also confirms `assign_cycle_pairs` (already generic) works unchanged for the new `['most', 'least']` factor — no production code change needed for that part, just a test.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_feed_logic_ranking.py`:

```python
from feed_logic import select_ranked_topic, parse_topic_ranking, format_topic_ranking


def test_select_ranked_topic_returns_first_item_when_alignment_is_most():
    assert select_ranked_topic(['FOOD', 'SPORT', 'TRAVEL'], 'most') == 'FOOD'


def test_select_ranked_topic_returns_last_item_when_alignment_is_least():
    assert select_ranked_topic(['FOOD', 'SPORT', 'TRAVEL'], 'least') == 'TRAVEL'


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
```

Append to `tests/test_feed_logic_assignment.py`:

```python
def test_assign_cycle_pairs_generalizes_to_preference_alignment():
    alignments = ['most', 'least']
    nav_conditions = ['normal', 'friction']

    pairs = assign_cycle_pairs(alignments, nav_conditions, rng=random.Random(3))

    assert len(pairs) == 4
    assert set(pairs) == {
        ('most', 'normal'), ('most', 'friction'),
        ('least', 'normal'), ('least', 'friction'),
    }
```

- [ ] **Step 2: Run the tests to verify the new ones fail**

Run: `python -m pytest tests/test_feed_logic_ranking.py tests/test_feed_logic_assignment.py -v`
Expected: the 8 new ranking tests FAIL with `ImportError`; `test_assign_cycle_pairs_generalizes_to_preference_alignment` PASSES already (no code change needed for that one — it's confirming existing behavior).

- [ ] **Step 3: Add the helpers to `feed_logic.py`**

Add after `finalize_player_sequence`:

```python
def select_ranked_topic(ranking, alignment):
    """Pick the topic to show from a participant's full preference ranking.

    `ranking` is a list ordered most-preferred first. `alignment` is
    'most' or 'least' — which end of the ranking gets shown.
    """
    return ranking[0] if alignment == 'most' else ranking[-1]


def parse_topic_ranking(raw_json, fallback_topics):
    """Parse a participant's submitted topic ranking.

    Returns the parsed list if it's valid JSON containing exactly the same
    topics as `fallback_topics` (in any order); otherwise returns
    `fallback_topics` unchanged, so a missing/corrupt/tampered ranking still
    yields a usable (if uninformative) assignment instead of crashing.
    """
    try:
        parsed = json.loads(raw_json or 'null')
    except json.JSONDecodeError:
        return list(fallback_topics)
    if (isinstance(parsed, list)
            and all(isinstance(item, str) for item in parsed)
            and sorted(parsed) == sorted(fallback_topics)):
        return parsed
    return list(fallback_topics)


def format_topic_ranking(raw_json):
    """Render a participant's JSON topic ranking as a readable export string.

    Returns '' for missing/invalid input.
    """
    try:
        ranking = json.loads(raw_json or 'null')
    except json.JSONDecodeError:
        return ''
    if not isinstance(ranking, list) or not all(isinstance(item, str) for item in ranking):
        return ''
    return ', '.join(ranking)
```

(Fixed during Task 2's code-quality review: the original literal code above crashed with
`TypeError` on well-formed JSON that isn't a list of strings — e.g. `'["SPORT", 1, 2]'` — because
`sorted()`/`', '.join()` only fail safely on `JSONDecodeError`, not on wrong-shaped-but-valid JSON.
Since `topic_ranking` is a normal POST field a participant could tamper with via devtools, this is
reachable from a live request in Task 5, not just a theoretical gap.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_feed_logic_ranking.py tests/test_feed_logic_assignment.py -v`
Expected: PASS (12 tests in the ranking file, 3 in the assignment file)

- [ ] **Step 5: Commit**

```bash
git add feed_logic.py tests/test_feed_logic_ranking.py tests/test_feed_logic_assignment.py
git commit -m "feat: add topic-ranking selection, parsing, and export-formatting helpers"
```

---

### Task 3: New Player fields + session config flag

**Files:**
- Modify: `DICE/__init__.py:32-54` (Player model)
- Modify: `settings.py:9-15` (FrictionScrollStudy config)

- [ ] **Step 1: Add the two new Player fields**

In `DICE/__init__.py`, in the `Player` class, right after the `nav_condition` field (line 34), add:

```python
    preference_alignment = models.StringField(
        doc="'most' or 'least' -- which end of the participant's own topic ranking was actually shown to them.",
        blank=True)
    topic_ranking = models.LongStringField(
        doc='JSON list of topics ranked most-to-least preferred by the participant.',
        blank=True)
```

- [ ] **Step 2: Add the `rank_topics` config flag**

In `settings.py`, update the `FrictionScrollStudy` config dict (lines 9-15):

```python
    dict(
        name='FrictionScrollStudy',
        app_sequence=['DICE'],
        num_demo_participants=4,
        data_path='DICE/static/data/friction_scroll_videos.csv',
        nav_conditions=['normal', 'friction'],
        rank_topics=True,
    ),
```

(`num_demo_participants` drops from 6 to 4 to match the new 2×2 = 4-cell design, so the demo session covers every cell exactly once.)

- [ ] **Step 3: Reset the dev database**

The `Player` model changed shape, so any existing local `db.sqlite3` schema is now stale.

Run: `otree resetdb`
Expected: prompts to confirm, then recreates tables. Answer yes/`y` when prompted.

- [ ] **Step 4: Commit**

```bash
git add DICE/__init__.py settings.py
git commit -m "feat: add preference_alignment/topic_ranking fields and rank_topics config flag"
```

---

### Task 4: Refactor `creating_session` to defer topic assignment

**Files:**
- Modify: `DICE/__init__.py:1-9` (imports), `DICE/__init__.py:58-111` (`creating_session`)

This is the core architectural change: when `rank_topics` is set, topic assignment and sequence finalization no longer happen here — only `preference_alignment` and `nav_condition` get assigned, and the full (unfiltered) post list is stashed on `player.participant.videos` for `B_TopicRanking` (Task 5) to finish later. When `rank_topics` is not set (e.g. the `Feed` demo config), behavior is unchanged — just routed through the `finalize_player_sequence` helper instead of the old inline code.

- [ ] **Step 1: Update the import line**

Replace `DICE/__init__.py:9`:

```python
from feed_logic import assign_cycle_pairs, parse_json_field, build_export_row, compute_session_aggregates
```

with:

```python
from feed_logic import (
    assign_cycle_pairs, parse_json_field, build_export_row, compute_session_aggregates,
    finalize_player_sequence, select_ranked_topic, parse_topic_ranking, format_topic_ranking,
)
```

- [ ] **Step 2: Replace `creating_session`**

Replace the whole function body (`DICE/__init__.py:58-111`):

```python
def creating_session(subsession):
    # Load and preprocess data once but shuffle and assign for each player
    df = read_feed(path=subsession.session.config['data_path'], delim=subsession.session.config['delimiter'])
    processed_posts = preprocessing(df, subsession.session.config)

    # Check if the file contains any conditions and assign groups to it
    condition = subsession.session.config['condition_col']
    nav_conditions = subsession.session.config.get('nav_conditions')
    rank_topics = subsession.session.config.get('rank_topics', False)
    condition_present = condition in processed_posts.columns

    if condition_present:
        topics = list(processed_posts[condition].unique())
        subsession.feed_conditions = ', '.join(topics)
        if rank_topics:
            # Topic itself is chosen later, from each participant's own
            # ranking survey (see B_TopicRanking.before_next_page) — only
            # preference_alignment and nav_condition are balanced up front.
            assignment_cycle = itertools.cycle(assign_cycle_pairs(['most', 'least'], nav_conditions))
        elif nav_conditions:
            # Balanced shuffled round-robin across every (topic, nav_condition) cell
            assignment_cycle = itertools.cycle(assign_cycle_pairs(topics, nav_conditions))
        else:
            # No nav_conditions configured (e.g. the original single-factor demo):
            # preserve the original topic-only cycling behavior exactly.
            assignment_cycle = itertools.cycle((topic, None) for topic in topics)

    for player in subsession.get_players():
        # Deep copy the DataFrame to ensure each player gets a unique shuffled version
        posts = processed_posts.copy()

        if condition_present and rank_topics:
            # Topic (and therefore the filtered/sequenced post list) can't be
            # determined until the participant submits their ranking survey.
            player.preference_alignment, player.nav_condition = next(assignment_cycle)
            player.participant.videos = posts
            continue

        # Assign a condition to the player if conditions are present
        if condition_present:
            player.feed_condition, player.nav_condition = next(assignment_cycle)
            posts = posts[posts[condition] == player.feed_condition]

        posts = finalize_player_sequence(posts)
        player.participant.videos = posts

        # Record the sequence for each player
        player.sequence = ', '.join(map(str, posts['doc_id'].tolist()))
```

- [ ] **Step 3: Smoke-test that the app still imports and serves**

Run: `otree devserver 8000` (in the background), then once it's up:

Run: `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/`
Expected: `307` (redirect to the admin home) — confirms the app loaded without a Python error. A `500` or connection failure means there's a syntax/import error to fix before continuing.

Stop the dev server once confirmed.

- [ ] **Step 4: Commit**

```bash
git add DICE/__init__.py
git commit -m "feat: defer topic assignment to after the ranking survey when rank_topics is set"
```

---

### Task 5: New `B_TopicRanking` page

**Files:**
- Modify: `DICE/__init__.py:1` (add `import json`), `DICE/__init__.py:280-360` (add page class, update `page_sequence`)

- [ ] **Step 1: Add the `json` import**

`DICE/__init__.py` currently imports `re`, `random`, `itertools`, `urllib.parse` at the top (lines 4-7). Add `import json` alongside them.

**Note on `A_Intro.before_next_page`:** it currently recomputes `player.sequence` by filtering `player.participant.videos` on `player.feed_condition` (`DICE/__init__.py:284-289`). When `rank_topics` is on, `feed_condition` isn't set yet at that point (it's still `None`), so this produces a harmless empty string that this page's `before_next_page` immediately overwrites afterward. This is expected — don't "fix" it by reordering or guarding it, it's dead-but-harmless work with no observable effect.

- [ ] **Step 2: Add the page class**

In `DICE/__init__.py`, insert this new class between `A_Intro` and `B_Briefing` (i.e. right after line 289, before `class B_Briefing(Page):`):

```python
class B_TopicRanking(Page):
    form_model = 'player'

    @staticmethod
    def is_displayed(player):
        return bool(player.session.config.get('rank_topics'))

    @staticmethod
    def get_form_fields(player):
        return ['topic_ranking']

    @staticmethod
    def vars_for_template(player):
        topics = [t.strip() for t in player.subsession.feed_conditions.split(',')]
        random.shuffle(topics)
        return dict(topics=topics)

    @staticmethod
    def before_next_page(player, timeout_happened):
        topics = [t.strip() for t in player.subsession.feed_conditions.split(',')]
        ranking = parse_topic_ranking(player.topic_ranking, topics)
        player.topic_ranking = json.dumps(ranking)
        player.feed_condition = select_ranked_topic(ranking, player.preference_alignment)

        condition_col = player.session.config['condition_col']
        posts = player.participant.videos
        posts = posts[posts[condition_col] == player.feed_condition].copy()
        posts = finalize_player_sequence(posts)
        player.participant.videos = posts
        player.sequence = ', '.join(map(str, posts['doc_id'].tolist()))
```

- [ ] **Step 3: Wire it into `page_sequence`**

Replace `DICE/__init__.py:356-360`:

```python
page_sequence = [A_Intro,
                 B_Briefing,
                 C_Feed,
                 D_Redirect,
                 D_Debrief]
```

with:

```python
page_sequence = [A_Intro,
                 B_TopicRanking,
                 B_Briefing,
                 C_Feed,
                 D_Redirect,
                 D_Debrief]
```

- [ ] **Step 4: Note the missing template (expected — next task)**

`B_TopicRanking` doesn't have a template yet (`DICE/B_TopicRanking.html`), so the page will 500 if actually visited right now. That's fine — Task 8 adds it. Don't smoke-test by visiting the page yet; just confirm the app still *imports* cleanly:

Run: `otree devserver 8000` (background), then:
Run: `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/`
Expected: `307` (same as Task 4's check — proves no Python syntax error). Stop the server after.

- [ ] **Step 5: Commit**

```bash
git add DICE/__init__.py
git commit -m "feat: add B_TopicRanking page (assignment logic; template comes next)"
```

---

### Task 6: Export changes

**Files:**
- Modify: `feed_logic.py:37-79` (`build_export_row`)
- Modify: `DICE/__init__.py:363-399` (`custom_export`)
- Modify: `tests/test_feed_logic_export.py`

- [ ] **Step 1: Update the existing export tests to expect the new columns**

`preference_alignment` and `topic_ranking` are inserted right after `nav_condition`. Replace `tests/test_feed_logic_export.py` in full:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_feed_logic_export.py -v`
Expected: FAIL — the row-equality assertions mismatch (actual rows are 2 items shorter than expected).

- [ ] **Step 3: Update `build_export_row`**

In `feed_logic.py`, replace the `return [...]` block (lines 56-79) of `build_export_row`:

```python
    return [
        participant['session_code'],
        participant['participant_code'],
        participant['participant_label'],
        participant['id_in_group'],
        participant['feed_condition'],
        participant['nav_condition'],
        participant['preference_alignment'],
        participant['topic_ranking'],
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
```

Also update the docstring's field list (line 42) to mention the two new keys: `..., nav_condition, preference_alignment, topic_ranking, completed_feed, ...`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_feed_logic_export.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Wire the new columns into `custom_export`**

In `DICE/__init__.py`, update the header row (lines 364-370):

```python
    yield ['session', 'participant_code', 'participant_label', 'participant_in_session',
           'condition', 'nav_condition', 'preference_alignment', 'topic_ranking',
           'doc_id', 'sequence_position',
           'watch_time_seconds', 'video_length_seconds', 'watch_percentage',
           'liked', 'has_comment', 'comment',
           'friction_delay_seconds', 'voluntary_hesitation_seconds', 'ad_clicked',
           'completed_feed', 'last_position_viewed',
           'total_watch_time_seconds', 'session_duration_seconds', 'completion_rate']
```

And update the `participant = dict(...)` block (around lines 384-396) to add the two new keys right after `nav_condition=...`:

```python
        participant = dict(
            session_code=p.session.code,
            participant_code=p.participant.code,
            participant_label=p.participant.label,
            id_in_group=p.id_in_group,
            feed_condition=p.feed_condition,
            nav_condition=p.field_maybe_none('nav_condition'),
            preference_alignment=p.field_maybe_none('preference_alignment'),
            topic_ranking=format_topic_ranking(p.topic_ranking),
            completed_feed=p.field_maybe_none('completed_feed'),
            last_position_viewed=p.field_maybe_none('last_position_viewed'),
            total_watch_time_seconds=aggregates['total_watch_time_seconds'],
            session_duration_seconds=aggregates['session_duration_seconds'],
            completion_rate=aggregates['completion_rate'],
        )
```

- [ ] **Step 6: Run the full Python test suite**

Run: `python -m pytest tests/ -v`
Expected: PASS, all tests (existing + new)

- [ ] **Step 7: Commit**

```bash
git add feed_logic.py DICE/__init__.py tests/test_feed_logic_export.py
git commit -m "feat: export preference_alignment and topic_ranking columns"
```

---

### Task 7: JS reorder logic (pure function + tests)

**Files:**
- Create: `DICE/static/js/topic_ranking.js`
- Test: `tests/topic_ranking.test.js` (new)

Mirrors the existing `friction.js` / `friction.test.js` split: pure logic first, DOM wiring is added on top of the same file in Task 8 (once there's a template to wire it to).

- [ ] **Step 1: Write the failing test**

Create `tests/topic_ranking.test.js`:

```javascript
const assert = require('assert');
const { moveRankItem } = require('../DICE/static/js/topic_ranking.js');

// moveRankItem
assert.deepStrictEqual(moveRankItem(['SPORT', 'FOOD', 'TRAVEL'], 1, -1), ['FOOD', 'SPORT', 'TRAVEL']);
console.log('PASS: moveRankItem swaps with the previous item when direction is -1');

assert.deepStrictEqual(moveRankItem(['SPORT', 'FOOD', 'TRAVEL'], 1, 1), ['SPORT', 'TRAVEL', 'FOOD']);
console.log('PASS: moveRankItem swaps with the next item when direction is 1');

// Boundary: moving the first item up (direction -1) is a no-op
assert.deepStrictEqual(moveRankItem(['SPORT', 'FOOD', 'TRAVEL'], 0, -1), ['SPORT', 'FOOD', 'TRAVEL']);
console.log('PASS: moveRankItem is a no-op moving the first item up');

// Boundary: moving the last item down (direction 1) is a no-op
assert.deepStrictEqual(moveRankItem(['SPORT', 'FOOD', 'TRAVEL'], 2, 1), ['SPORT', 'FOOD', 'TRAVEL']);
console.log('PASS: moveRankItem is a no-op moving the last item down');

// Does not mutate the input array
const original = ['SPORT', 'FOOD', 'TRAVEL'];
moveRankItem(original, 0, 1);
assert.deepStrictEqual(original, ['SPORT', 'FOOD', 'TRAVEL']);
console.log('PASS: moveRankItem does not mutate its input');

// Out-of-range index (e.g. an unmatched indexOf returning -1) must not
// corrupt the array -- both the index and newIndex bounds are checked.
assert.deepStrictEqual(moveRankItem(['SPORT', 'FOOD', 'TRAVEL'], -1, 1), ['SPORT', 'FOOD', 'TRAVEL']);
console.log('PASS: moveRankItem is a no-op for a negative index');

assert.deepStrictEqual(moveRankItem(['SPORT', 'FOOD', 'TRAVEL'], 3, -1), ['SPORT', 'FOOD', 'TRAVEL']);
console.log('PASS: moveRankItem is a no-op for an index past the end');

console.log('All topic_ranking.test.js tests passed.');
```

- [ ] **Step 2: Run it to verify it fails**

Run: `node tests/topic_ranking.test.js`
Expected: FAIL — `Cannot find module '../DICE/static/js/topic_ranking.js'`

- [ ] **Step 3: Create the module with the pure function**

Create `DICE/static/js/topic_ranking.js`:

```javascript
// Pure ranking-reorder logic — no DOM access, safe to load as a plain
// <script> in the browser and to require() directly under Node for testing.

function moveRankItem(order, index, direction) {
    const newIndex = index + direction;
    if (index < 0 || index >= order.length || newIndex < 0 || newIndex >= order.length) {
        return order.slice();
    }
    const result = order.slice();
    const tmp = result[index];
    result[index] = result[newIndex];
    result[newIndex] = tmp;
    return result;
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { moveRankItem };
}
```

(Fixed during Task 7's code-quality review: the original literal code above only checked `newIndex`'s
bounds, not `index`'s -- an out-of-range `index` with an in-range `newIndex` silently corrupted the
array instead of no-op'ing, e.g. `moveRankItem(arr, -1, 1)` wrote to a negative index and
`moveRankItem(arr, arr.length, -1)` extended the array. Not reachable by Task 8's planned DOM caller
(index always comes from `indexOf` on the same list being reordered), but cheap to close and matches
this file's own convention of covering "shouldn't happen in normal operation" defensive cases.)

- [ ] **Step 4: Run it to verify it passes**

Run: `node tests/topic_ranking.test.js`
Expected: PASS (7 PASS lines + "All topic_ranking.test.js tests passed.")

- [ ] **Step 5: Commit**

```bash
git add DICE/static/js/topic_ranking.js tests/topic_ranking.test.js
git commit -m "feat: add pure ranking-reorder logic module with Node tests"
```

---

### Task 8: Ranking page template, CSS, and DOM wiring

**Files:**
- Create: `DICE/B_TopicRanking.html`
- Modify: `DICE/static/js/topic_ranking.js` (append DOM wiring)
- Modify: `DICE/static/css/styles.css`

- [ ] **Step 1: Create the template**

Create `DICE/B_TopicRanking.html`:

```html
{{ block scripts }}
<script src="{{ static 'js/topic_ranking.js' }}"></script>
{{ endblock }}

{{ block styles }}
<link rel="stylesheet" href="{{ static 'css/styles.css' }}">
<link rel="shortcut icon" type="image/x-icon" href="{{ static 'img/favicon.ico' }}">
{{ endblock }}

{{ block content }}
<body class="bg-light.bg-gradient">

    <div class="container">
        <div class="row justify-content-center mt-5">
            <div class="col-sm-10 col-md-10 col-lg-8">
                <div class="card rounded mt-3 shadow-lg">
                    <div class="card-body p-5">
                        <p class="fw-semibold mb-2">Rank these topics</p>
                        <p class="text-muted">Use the arrows to put them in order from your most to least favorite. We'll show you videos from one of them, based on your ranking.</p>

                        <ol id="ranking-list" class="ranking-list">
                            {{ for topic in topics }}
                            <li class="ranking-item" data-topic="{{ topic }}">
                                <span class="ranking-label">{{ topic }}</span>
                                <div class="ranking-controls">
                                    <button type="button" class="rank-btn rank-up" aria-label="Move {{ topic }} up">&#9650;</button>
                                    <button type="button" class="rank-btn rank-down" aria-label="Move {{ topic }} down">&#9660;</button>
                                </div>
                            </li>
                            {{ endfor }}
                        </ol>

                        <input type="hidden" name="topic_ranking" id="topic_ranking" value="">

                        <div class="d-flex justify-content-center mt-4 mb-3">
                            <button class="btn btn-success shadow" type="submit" id="submitButton">
                                Continue
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
{{ endblock }}
```

- [ ] **Step 2: Append DOM wiring to `topic_ranking.js`**

Add this below the existing `module.exports` block in `DICE/static/js/topic_ranking.js`:

```javascript
// DOM wiring — only runs in the browser (no-op under Node/require).
if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', function () {
        const list = document.getElementById('ranking-list');
        const hiddenInput = document.getElementById('topic_ranking');
        if (!list || !hiddenInput) return;

        function currentOrder() {
            return Array.from(list.querySelectorAll('.ranking-item')).map(function (li) {
                return li.dataset.topic;
            });
        }

        function render(order) {
            order.forEach(function (topic) {
                const li = list.querySelector('.ranking-item[data-topic="' + topic + '"]');
                if (li) list.appendChild(li);
            });
        }

        list.addEventListener('click', function (e) {
            const btn = e.target.closest('.rank-up, .rank-down');
            if (!btn) return;
            const li = btn.closest('.ranking-item');
            const order = currentOrder();
            const index = order.indexOf(li.dataset.topic);
            const direction = btn.classList.contains('rank-up') ? -1 : 1;
            render(moveRankItem(order, index, direction));
        });

        document.querySelectorAll('button[type="submit"]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                hiddenInput.value = JSON.stringify(currentOrder());
            });
        });
    });
}
```

- [ ] **Step 3: Add the CSS**

Append to `DICE/static/css/styles.css`:

```css
.ranking-list {
    list-style: none;
    padding: 0;
    margin: 24px 0;
}
.ranking-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 18px;
    margin-bottom: 10px;
    background: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 8px;
}
.ranking-label {
    font-weight: 600;
    text-transform: capitalize;
}
.ranking-controls {
    display: flex;
    gap: 6px;
}
.rank-btn {
    background: #fe2c55;
    color: #fff;
    border: none;
    border-radius: 6px;
    width: 32px;
    height: 32px;
    font-size: 14px;
    cursor: pointer;
}
.rank-btn:active { opacity: 0.85; }
```

- [ ] **Step 4: Re-run the JS test to confirm the DOM-wiring addition didn't break the pure function under Node**

Run: `node tests/topic_ranking.test.js`
Expected: PASS (same 5 PASS lines — `typeof document` is `'undefined'` under plain Node, so the new block is skipped entirely)

- [ ] **Step 5: Commit**

```bash
git add DICE/B_TopicRanking.html DICE/static/js/topic_ranking.js DICE/static/css/styles.css
git commit -m "feat: add topic ranking page template, styles, and DOM wiring"
```

---

### Task 9: Update docs

**Files:**
- Modify: `docs/superpowers/specs/2026-08-07-friction-scroll-experiment-design.md`
- Modify: `README.md`

- [ ] **Step 1: Point the original spec at the new one**

In `docs/superpowers/specs/2026-08-07-friction-scroll-experiment-design.md`, find this paragraph near the end of "Assignment mechanism" (currently reads "Topic assignment continues to use the existing `feed_condition` player field and `condition` CSV column — no change to that mechanism."). Replace it with:

```markdown
Topic assignment continues to use the existing `feed_condition` player
field and `condition` CSV column, but **as of
`2026-08-17-topic-preference-ranking-design.md`, topic is no longer
independently balanced** — it's derived from each participant's own
pre-feed topic-preference ranking. See that spec for the updated 2×2
design (preference_alignment × nav_condition) and the assignment
mechanism change.
```

- [ ] **Step 2: Update the README's study design section**

Replace `README.md` lines 5-14:

```markdown
## Study design

2×2 between-subjects design:

- **Preference alignment**: participants rank SPORT/FOOD/TRAVEL from most to least favorite before the feed starts, then see either their most- or least-preferred topic (never the middle one)
- **Navigation condition**: normal free scroll, or friction scroll (a black screen appears after every video; the participant must click Continue before the next video appears)

Every participant sees 6 videos in a fixed order: 5 regular videos, then a sponsored ad post as the final item. Engagement stats (likes/comments/shares) are matched by position across the three topics, so the topic itself can't confound the navigation-condition comparison.

Participants are assigned to one of the 4 (preference-alignment × navigation) cells automatically, balanced so every 4 participants covers all 4 cells exactly once. Topic itself is *not* separately balanced — it follows whatever each participant's own ranking puts in their assigned "most" or "least" slot.
```

- [ ] **Step 3: Add the new export columns to the README's field table**

In `README.md`, in the "What gets recorded" table, insert two rows right after the `nav_condition` row (currently line 96):

```markdown
| `preference_alignment` | Whether this participant was shown their most- or least-preferred topic |
| `topic_ranking` | The participant's full topic ranking, most to least preferred (e.g. "FOOD, SPORT, TRAVEL") |
```

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-08-07-friction-scroll-experiment-design.md README.md
git commit -m "docs: document the preference-ranking topic assignment change"
```

---

### Task 10: End-to-end verification

**Files:** none (verification only)

This is the only place the full flow gets exercised — there's no automated way to test oTree page glue in this codebase (see Architecture note at the top). Be thorough here.

- [ ] **Step 1: Run the full automated test suite**

Run:
```bash
python -m pytest tests/ -v
node tests/friction.test.js
node tests/topic_ranking.test.js
```
Expected: everything passes.

- [ ] **Step 2: Start the dev server**

Run: `otree devserver 8000` (background)
Poll `http://127.0.0.1:8000/` until it returns `307`.

- [ ] **Step 3: Walk through a `FrictionScrollStudy` demo participant**

Go to `http://127.0.0.1:8000/demo/FrictionScrollStudy` (or drive it with Playwright, matching the pattern used earlier in this project's history — launch chromium, `page.goto`, wait for the redirect off `/demo/...`, then follow one of the `InitializeParticipant` links). For at least one participant:

1. Complete consent (`A_Intro`).
2. Confirm the **Rank Topics** page appears, showing all 3 topics in a re-orderable list.
3. Click a ▼ button and confirm the item visibly moves down (and the item that was below it moves up).
4. Submit without further reordering.
5. Confirm the briefing page (`B_Briefing`) appears next, then the feed loads.
6. Inspect (via `player.subsession` in the admin, or by checking `window.NAV_CONDITION` / the rendered post captions) that the topic shown matches either the first or last item of whatever order was on screen at submit time.

- [ ] **Step 4: Confirm balance across cells**

Create a fresh demo session (`num_demo_participants=4`), and for each of the 4 participant links, capture `preference_alignment` and `nav_condition` (visible in the oTree admin's session data view, or by reading `player.participant.vars`/the DB directly). Confirm all 4 combinations of `{most, least} × {normal, friction}` appear exactly once.

- [ ] **Step 5: Confirm the export**

From the admin, export `FrictionScrollStudy` data (or call `custom_export` directly). Confirm the CSV/rows include `preference_alignment` and `topic_ranking` columns, populated for every row of a completed participant, with `topic_ranking` rendered as a comma-joined string (e.g. `FOOD, SPORT, TRAVEL`) rather than raw JSON.

- [ ] **Step 6: Confirm the `Feed` demo config is unaffected**

Go to `http://127.0.0.1:8000/demo/Feed` and confirm: no ranking page appears (goes straight from intro to briefing), and topic assignment still behaves as a plain random pick (no `preference_alignment`/`topic_ranking` involved — `rank_topics` isn't set on this config).

- [ ] **Step 7: Stop the dev server**

Stop the background `otree devserver` process.

- [ ] **Step 8: Final commit (if Step 3-6 surfaced any fixes)**

If any issue was found and fixed during manual verification, commit it separately with a message describing what was wrong (e.g. `fix: <specific bug found during end-to-end check>`). If nothing needed fixing, no commit is needed for this task.
