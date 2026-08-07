# Friction Scroll Experiment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a 3×2 between-subjects friction-scroll experiment (SPORT / FOOD / TRAVEL topic × normal / friction navigation) in the DICE TikTok oTree app, per the approved design spec at `docs/superpowers/specs/2026-08-07-friction-scroll-experiment-design.md`.

**Architecture:** Two new `Player` fields (`nav_condition`, `friction_data`) and a balanced shuffled-cycle assignment mechanism extend the existing single-factor `condition` system already used for content conditions. A new pure-Python module, `feed_logic.py`, holds unit-testable assignment/parsing/export logic *outside* the `DICE` app package — this sidesteps a real constraint: `DICE/__init__.py` does `from otree.api import *` and defines Django ORM model classes at import time, which requires a configured Django app registry and cannot be safely imported by a bare `pytest` run. Keeping the pure logic in a dependency-free sibling module means it's testable with plain `pytest`, no Django bootstrap required. The friction-scroll gate is a single reusable full-screen overlay intercepting the existing `navigateTo()` choke point in `video_feed.js`; its pure delay-calculation logic is isolated into a new dependency-free `friction.js` file so it's testable under plain Node without a build step, following the same separate-global-script pattern this codebase already uses for `format_numbers.js` / `mobile.js`.

**Tech Stack:** Python 3 / oTree 5 / pandas (existing). Adds `pytest` (dev-only) for backend logic tests and relies on Node's built-in `assert` module (zero npm dependencies — no `package.json` introduced) for the one pure JS module. This repo has no existing test runner or build step. DOM/video-dependent interaction code (swipe handling, overlay show/hide, video playback) is **not** covered by automated tests — it's verified by hand via `otree devserver` in a real browser, consistent with the project's existing "Tested on: Chrome / macOS" posture. This is a deliberate scope decision: standing up a full browser-test framework (Jest+jsdom, Playwright, etc.) for one feature in a project with zero prior test infrastructure would be disproportionate; pure logic is extracted and tested, DOM glue is manually verified.

---

## Prerequisites

- Python environment with `requirements.txt` already installed (`pip install -r requirements.txt`), per the existing README.
- Node.js installed (any reasonably recent version) — used only to run one dependency-free test file (`tests/friction.test.js`) via `node`, no `npm install` needed.
- Working directory: repo root (`c:\Users\manue\Downloads\DICE-tiktok-main`), which is now a git repo with one commit (baseline) plus the design spec commit.

---

### Task 1: Test infrastructure setup

**Files:**
- Create: `requirements-dev.txt`
- Create: `tests/conftest.py`
- Create: `tests/test_smoke.py`

- [ ] **Step 1: Create the dev requirements file**

`requirements-dev.txt`:
```
pytest>=7.4
```

- [ ] **Step 2: Install it**

Run: `pip install -r requirements-dev.txt`
Expected: pytest installs successfully (or reports already satisfied).

- [ ] **Step 3: Create conftest.py so tests can import repo-root modules**

`tests/conftest.py`:
```python
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

- [ ] **Step 4: Write a smoke test to confirm the harness works**

`tests/test_smoke.py`:
```python
def test_pytest_runs():
    assert 1 + 1 == 2
```

- [ ] **Step 5: Run it**

Run: `python -m pytest tests/ -v`
Expected: `tests/test_smoke.py::test_pytest_runs PASSED`, 1 passed.

- [ ] **Step 6: Commit**

```bash
git add requirements-dev.txt tests/conftest.py tests/test_smoke.py
git commit -m "test: add pytest infrastructure"
```

---

### Task 2: feed_logic.py — assignment helper

**Files:**
- Create: `feed_logic.py`
- Test: `tests/test_feed_logic_assignment.py`

- [ ] **Step 1: Write the failing test**

`tests/test_feed_logic_assignment.py`:
```python
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
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_feed_logic_assignment.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'feed_logic'`

- [ ] **Step 3: Create feed_logic.py with the implementation**

`feed_logic.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_feed_logic_assignment.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add feed_logic.py tests/test_feed_logic_assignment.py
git commit -m "feat: add balanced shuffled-cycle assignment helper"
```

---

### Task 3: feed_logic.py — export parsing helpers

**Files:**
- Modify: `feed_logic.py`
- Test: `tests/test_feed_logic_export.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_feed_logic_export.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_feed_logic_export.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_export_row' from 'feed_logic'`

- [ ] **Step 3: Add the implementation to feed_logic.py**

Append to `feed_logic.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_feed_logic_export.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add feed_logic.py tests/test_feed_logic_export.py
git commit -m "feat: add export row builder and JSON field parser"
```

---

### Task 4: feed_logic.py — matched-stats validator

**Files:**
- Modify: `feed_logic.py`
- Test: `tests/test_feed_logic_validation.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_feed_logic_validation.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_feed_logic_validation.py -v`
Expected: FAIL — `ImportError: cannot import name 'validate_matched_stats' from 'feed_logic'`

- [ ] **Step 3: Add the implementation to feed_logic.py**

Append to `feed_logic.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_feed_logic_validation.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add feed_logic.py tests/test_feed_logic_validation.py
git commit -m "feat: add matched-stats validator for feed CSV content"
```

---

### Task 5: Friction-scroll feed CSV template

**Files:**
- Create: `DICE/static/data/friction_scroll_videos.csv`
- Test: `tests/test_csv_validation.py`

The FOOD topic and the ad use real footage, already copied into `DICE/static/mp4/` as `food1.mp4`, `food2.mp4`, `food3.mp4`, `food4.mp4`, `food6.mp4` (positions 1–4 and 6) and `ad.mp4` (position 5, shared identically across all three topics per the spec). SPORT and TRAVEL still use placeholder video files (reusing the existing demo clips in `DICE/static/mp4/`) and placeholder captions — sourcing that footage is a separate manual task per the spec's "Out of scope" section. Captions for FOOD/ad rows are still placeholder copy (the real videos' actual content wasn't reviewed) — swap them for real caption copy once you've watched the footage. The schema and matched-stats invariant are what this task locks in.

- [ ] **Step 1: Write the failing tests**

`tests/test_csv_validation.py`:
```python
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


def test_csv_has_exactly_one_ad_per_topic_at_position_five():
    df = load_csv()
    for condition, group in df.groupby('condition'):
        ad_rows = group[group['is_ad'] == 1]
        assert len(ad_rows) == 1
        assert ad_rows.iloc[0]['sequence'] == 5


def test_csv_ad_content_is_identical_across_topics():
    df = load_csv()
    ad_rows = df[df['is_ad'] == 1]
    for col in ('text', 'video', 'likes', 'reposts', 'replies', 'username', 'handle'):
        assert ad_rows[col].nunique() == 1, f"ad '{col}' differs across topics"


def test_csv_engagement_stats_match_across_topics_by_position():
    df = load_csv()
    violations = validate_matched_stats(df)
    assert violations == [], violations
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_csv_validation.py -v`
Expected: FAIL — `FileNotFoundError` (the CSV doesn't exist yet)

- [ ] **Step 3: Create the CSV template**

`DICE/static/data/friction_scroll_videos.csv`:
```
doc_id;datetime;text;video;likes;reposts;replies;username;handle;user_description;user_image;user_followers;condition;sequence;is_ad
0;01.06.25 09:00;Nailed this trick shot on the first try 🏀 #basketball #sports;1.mp4;15000;320;210;CourtKingz;courtkingz;Hooping every single day.;;52000;SPORT;1;0
1;02.06.25 09:00;Preseason training is no joke 💪 #fitness #training;2.mp4;28400;610;450;IronYard;ironyard;Strength and conditioning coach.;;88000;SPORT;2;0
2;03.06.25 09:00;Half-time routine that keeps me sharp ⚽ #soccer #sports;3.mp4;9800;140;95;PitchPerfect;pitchperfectofficial;Weekend league, full-time passion.;;21000;SPORT;3;0
3;04.06.25 09:00;This comeback win still gives me chills 🔥 #sports #comeback;4.mp4;42100;980;670;GameDayGlory;gamedayglory;Living for the clutch moments.;;134000;SPORT;4;0
4;05.06.25 09:00;The one thing everyone's been talking about lately. Shop now.;ad.mp4;3200;45;28;ProGearCo;progearco;Official partner.;;9800;SPORT;5;1
5;06.06.25 09:00;Sunday morning run, best therapy there is 🏃 #running #sports;6.mp4;18700;390;260;TrailAndError;trailanderror;Chasing personal bests.;;61000;SPORT;6;0
6;01.06.25 09:00;Nailed this recipe on the first try 🍝 #cooking #food;food1.mp4;15000;320;210;KitchenKingz;kitchenkingz;Cooking every single day.;;52000;FOOD;1;0
7;02.06.25 09:00;Meal-prep Sunday is no joke 🥗 #mealprep #food;food2.mp4;28400;610;450;FreshYard;freshyard;Home cook, full pantry.;;88000;FOOD;2;0
8;03.06.25 09:00;This plating trick keeps my dishes sharp 🍽️ #foodie #food;food3.mp4;9800;140;95;PlatePerfect;plateperfectofficial;Weeknight dinners, full-time passion.;;21000;FOOD;3;0
9;04.06.25 09:00;This dessert save still gives me chills 🍰 #baking #food;food4.mp4;42100;980;670;BakeDayGlory;bakedayglory;Living for the sweet moments.;;134000;FOOD;4;0
10;05.06.25 09:00;The one thing everyone's been talking about lately. Shop now.;ad.mp4;3200;45;28;ProGearCo;progearco;Official partner.;;9800;FOOD;5;1
11;06.06.25 09:00;Sunday morning bake, best therapy there is 🍞 #baking #food;food6.mp4;18700;390;260;CrumbAndError;crumbanderror;Chasing the perfect crust.;;61000;FOOD;6;0
12;01.06.25 09:00;Nailed this hidden gem on the first try 🗺️ #travel #wanderlust;4.mp4;15000;320;210;RoamKingz;roamkingz;Exploring every single day.;;52000;TRAVEL;1;0
13;02.06.25 09:00;Backpacking prep is no joke 🎒 #travel #backpacking;6.mp4;28400;610;450;TrailYard;trailyard;Trail guide and gear nerd.;;88000;TRAVEL;2;0
14;03.06.25 09:00;This packing trick keeps my trips sharp ✈️ #travel #packing;8.mp4;9800;140;95;PackPerfect;packperfectofficial;Carry-on only, full-time passion.;;21000;TRAVEL;3;0
15;04.06.25 09:00;This flight delay save still gives me chills 🛫 #travel #airport;9.mp4;42100;980;670;GateDayGlory;gatedayglory;Living for the standby upgrade.;;134000;TRAVEL;4;0
16;05.06.25 09:00;The one thing everyone's been talking about lately. Shop now.;ad.mp4;3200;45;28;ProGearCo;progearco;Official partner.;;9800;TRAVEL;5;1
17;06.06.25 09:00;Sunday morning hike, best therapy there is ⛰️ #hiking #travel;1.mp4;18700;390;260;PeakAndError;peakanderror;Chasing the summit.;;61000;TRAVEL;6;0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_csv_validation.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

The real FOOD/ad video files (`food1.mp4`, `food2.mp4`, `food3.mp4`, `food4.mp4`, `food6.mp4`, `ad.mp4`) were already copied into `DICE/static/mp4/` ahead of this task — include them in this commit too.

```bash
git add DICE/static/data/friction_scroll_videos.csv tests/test_csv_validation.py DICE/static/mp4/food1.mp4 DICE/static/mp4/food2.mp4 DICE/static/mp4/food3.mp4 DICE/static/mp4/food4.mp4 DICE/static/mp4/food6.mp4 DICE/static/mp4/ad.mp4
git commit -m "feat: add friction-scroll feed CSV template with matched stats and real FOOD/ad footage"
```

---

### Task 6: Session config for the friction-scroll study

**Files:**
- Modify: `settings.py:3-9`

- [ ] **Step 1: Add a new session config, leaving the existing demo untouched**

In `settings.py`, replace:
```python
SESSION_CONFIGS = [
    dict(
        name='Feed',
        app_sequence=['DICE'],
        num_demo_participants=3,
    ),
]
```

with:
```python
SESSION_CONFIGS = [
    dict(
        name='Feed',
        app_sequence=['DICE'],
        num_demo_participants=3,
    ),
    dict(
        name='FrictionScrollStudy',
        app_sequence=['DICE'],
        num_demo_participants=6,
        data_path='DICE/static/data/friction_scroll_videos.csv',
        nav_conditions=['normal', 'friction'],
    ),
]
```

This keeps the original `Feed` demo config (and `sample_videos.csv`) exactly as-is. `nav_conditions` is only set on the new config, so `creating_session` (Task 8) can safely default to the old single-factor behavior whenever it's absent.

- [ ] **Step 2: Sanity-check the file parses**

Run: `python -c "import settings; print([c['name'] for c in settings.SESSION_CONFIGS])"`
Expected: `['Feed', 'FrictionScrollStudy']`

- [ ] **Step 3: Commit**

```bash
git add settings.py
git commit -m "feat: add FrictionScrollStudy session config"
```

---

### Task 7: Player fields for nav_condition and friction_data

**Files:**
- Modify: `DICE/__init__.py:31-47`

- [ ] **Step 1: Add the two new fields to the Player model**

In `DICE/__init__.py`, the current `Player` class:
```python
class Player(BasePlayer):
    feed_condition = models.StringField(doc='indicates the feed condition a player is randomly assigned to')
    sequence = models.StringField(doc='prints the sequence of posts based on doc_id')

    scroll_sequence = models.LongStringField(doc='tracks the sequence of feed items a participant scrolled through.')
    viewport_data = models.LongStringField(doc='tracks the time feed items were visible in a participants viewport.')
    rowheight_data = models.LongStringField(doc='tracks the height of feed items in pixels.')
    likes_data = models.LongStringField(doc='tracks likes.', blank=True)
    replies_data = models.LongStringField(doc='tracks replies.', blank=True)
    promoted_post_clicks = models.LongStringField(doc='tracks the clicks on sponsored posts.', blank=True)
```

becomes:
```python
class Player(BasePlayer):
    feed_condition = models.StringField(doc='indicates the feed condition a player is randomly assigned to')
    nav_condition = models.StringField(doc='indicates the navigation condition (normal or friction) a player is randomly assigned to', blank=True)
    sequence = models.StringField(doc='prints the sequence of posts based on doc_id')

    scroll_sequence = models.LongStringField(doc='tracks the sequence of feed items a participant scrolled through.')
    viewport_data = models.LongStringField(doc='tracks the time feed items were visible in a participants viewport.')
    rowheight_data = models.LongStringField(doc='tracks the height of feed items in pixels.')
    likes_data = models.LongStringField(doc='tracks likes.', blank=True)
    replies_data = models.LongStringField(doc='tracks replies.', blank=True)
    promoted_post_clicks = models.LongStringField(doc='tracks the clicks on sponsored posts.', blank=True)
    friction_data = models.LongStringField(doc='tracks time-to-continue for each gated transition (friction condition only).', blank=True)
```

(`nav_condition` is `blank=True` because sessions using the original `Feed` config never set it.)

- [ ] **Step 2: Sanity-check the module still parses**

Run: `python -c "import ast; ast.parse(open('DICE/__init__.py').read())"`
Expected: no output (no `SyntaxError` raised).

- [ ] **Step 3: Commit**

```bash
git add DICE/__init__.py
git commit -m "feat: add nav_condition and friction_data player fields"
```

---

### Task 8: Ad-flag preprocessing

**Files:**
- Modify: `DICE/__init__.py` (add function near the other `prepare_*` helpers, wire into `preprocessing`)

- [ ] **Step 1: Add prepare_ad_flag next to the other prepare_* functions**

In `DICE/__init__.py`, immediately after `prepare_video` (which ends just before `def prepare_user_profiles`), insert:
```python
def prepare_ad_flag(df):
    """Ensure is_ad is a clean boolean flag, defaulting missing values to False."""
    if 'is_ad' not in df.columns:
        df['is_ad'] = False
    else:
        df['is_ad'] = df['is_ad'].fillna(0).astype(int).astype(bool)
    return df
```

- [ ] **Step 2: Wire it into the preprocessing pipeline**

Change:
```python
def preprocessing(df, config):
    """Orchestrate all preprocessing steps."""
    df = format_dates(df)
    df = highlight_entities(df)
    df = prepare_numeric_fields(df)
    df = prepare_media(df)
    df = prepare_video(df)
    df = prepare_user_profiles(df)
```

to:
```python
def preprocessing(df, config):
    """Orchestrate all preprocessing steps."""
    df = format_dates(df)
    df = highlight_entities(df)
    df = prepare_numeric_fields(df)
    df = prepare_media(df)
    df = prepare_video(df)
    df = prepare_ad_flag(df)
    df = prepare_user_profiles(df)
```

- [ ] **Step 3: Sanity-check the module still parses**

Run: `python -c "import ast; ast.parse(open('DICE/__init__.py').read())"`
Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add DICE/__init__.py
git commit -m "feat: normalize is_ad flag during feed preprocessing"
```

---

### Task 9: Crossed assignment in creating_session

**Files:**
- Modify: `DICE/__init__.py:1-9` (imports), `DICE/__init__.py:51-94` (creating_session)

- [ ] **Step 1: Import the new helper**

At the top of `DICE/__init__.py`, change:
```python
from otree.api import *
import pandas as pd
import numpy as np
import re
import random
import itertools
import urllib.parse
import json
```

to:
```python
from otree.api import *
import pandas as pd
import numpy as np
import re
import random
import itertools
import urllib.parse
import json

from feed_logic import assign_cycle_pairs, parse_json_field, build_export_row
```

- [ ] **Step 2: Cross topic and nav_condition assignment in creating_session**

Change:
```python
def creating_session(subsession):
    # Load and preprocess data once but shuffle and assign for each player
    df = read_feed(path=subsession.session.config['data_path'], delim=subsession.session.config['delimiter'])
    processed_posts = preprocessing(df, subsession.session.config)

    # Check if the file contains any conditions and assign groups to it
    condition = subsession.session.config['condition_col']
    if condition in processed_posts.columns:
        feed_conditions = itertools.cycle(processed_posts[condition].unique())
        subsession.feed_conditions = ', '.join(processed_posts[condition].unique())

    for player in subsession.get_players():
        # Deep copy the DataFrame to ensure each player gets a unique shuffled version
        posts = processed_posts.copy()

        # Assign a condition to the player if conditions are present
        if condition in posts.columns:
            player.feed_condition = next(feed_conditions)
            posts = posts[posts[condition] == player.feed_condition]
```

to:
```python
def creating_session(subsession):
    # Load and preprocess data once but shuffle and assign for each player
    df = read_feed(path=subsession.session.config['data_path'], delim=subsession.session.config['delimiter'])
    processed_posts = preprocessing(df, subsession.session.config)

    # Check if the file contains any conditions and assign groups to it
    condition = subsession.session.config['condition_col']
    nav_conditions = subsession.session.config.get('nav_conditions')
    condition_present = condition in processed_posts.columns

    if condition_present:
        topics = list(processed_posts[condition].unique())
        subsession.feed_conditions = ', '.join(topics)
        if nav_conditions:
            # Balanced shuffled round-robin across every (topic, nav_condition) cell
            assignment_cycle = itertools.cycle(assign_cycle_pairs(topics, nav_conditions))
        else:
            # No nav_conditions configured (e.g. the original single-factor demo):
            # preserve the original topic-only cycling behavior exactly.
            assignment_cycle = itertools.cycle((topic, None) for topic in topics)

    for player in subsession.get_players():
        # Deep copy the DataFrame to ensure each player gets a unique shuffled version
        posts = processed_posts.copy()

        # Assign a condition to the player if conditions are present
        if condition_present:
            player.feed_condition, player.nav_condition = next(assignment_cycle)
            posts = posts[posts[condition] == player.feed_condition]
```

- [ ] **Step 3: Sanity-check the module still parses**

Run: `python -c "import ast; ast.parse(open('DICE/__init__.py').read())"`
Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add DICE/__init__.py
git commit -m "feat: cross topic and nav_condition into balanced 6-cell assignment"
```

---

### Task 10: Pass nav_condition to the template and collect friction_data

**Files:**
- Modify: `DICE/__init__.py` (`C_Feed.get_form_fields`, `C_Feed.vars_for_template`)

- [ ] **Step 1: Add friction_data to the collected form fields**

Change:
```python
    @staticmethod
    def get_form_fields(player: Player):
        fields = ['likes_data', 'replies_data', 'promoted_post_clicks', 'touch_capability', 'device_type', 'screen_resolution',
                   'viewport_data']
        return fields
```

to:
```python
    @staticmethod
    def get_form_fields(player: Player):
        fields = ['likes_data', 'replies_data', 'promoted_post_clicks', 'friction_data', 'touch_capability',
                   'device_type', 'screen_resolution', 'viewport_data']
        return fields
```

- [ ] **Step 2: Pass nav_condition into the template context**

Change:
```python
    @staticmethod
    def vars_for_template(player: Player):
        label_available = player.participant.label is not None
        # Reset index to ensure consistent ordering (important for generic feed swiper)
        posts_df = player.participant.videos.reset_index(drop=True)
        return dict(
            posts=posts_df.to_dict('index'),
            label_available=label_available,
        )
```

to:
```python
    @staticmethod
    def vars_for_template(player: Player):
        label_available = player.participant.label is not None
        # Reset index to ensure consistent ordering (important for generic feed swiper)
        posts_df = player.participant.videos.reset_index(drop=True)
        return dict(
            posts=posts_df.to_dict('index'),
            label_available=label_available,
            nav_condition=player.nav_condition or 'normal',
        )
```

(Defaulting to `'normal'` means the original `Feed` demo — where `nav_condition` is always blank — renders with friction gating fully disabled, exactly as it does today.)

- [ ] **Step 3: Sanity-check the module still parses**

Run: `python -c "import ast; ast.parse(open('DICE/__init__.py').read())"`
Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add DICE/__init__.py
git commit -m "feat: pass nav_condition to feed template and collect friction_data"
```

---

### Task 11: custom_export additions

**Files:**
- Modify: `DICE/__init__.py:327-361` (custom_export)

- [ ] **Step 1: Rewrite custom_export to use the shared helpers and new columns**

Replace the entire function:
```python
def custom_export(players):
    yield ['session', 'participant_code', 'participant_label', 'participant_in_session',
           'condition', 'doc_id', 'sequence_position', 'watch_time_seconds', 'liked', 'has_comment', 'comment']

    for p in players:
        if not p.sequence:
            continue

        doc_ids = [int(x.strip()) for x in p.sequence.split(',')]

        def parse(field):
            """Parse a JSON list field into a dict keyed by doc_id."""
            try:
                return {entry['doc_id']: entry for entry in json.loads(field or '[]')}
            except (json.JSONDecodeError, KeyError, TypeError):
                return {}

        viewport = parse(p.viewport_data)
        likes    = parse(p.likes_data)
        replies  = parse(p.replies_data)

        for position, doc_id in enumerate(doc_ids, start=1):
            yield [
                p.session.code,
                p.participant.code,
                p.participant.label,
                p.id_in_group,
                p.feed_condition,
                doc_id,
                position,
                viewport.get(doc_id, {}).get('duration', ''),
                likes.get(doc_id,    {}).get('liked',    ''),
                replies.get(doc_id,  {}).get('hasReply', ''),
                replies.get(doc_id,  {}).get('reply',    ''),
            ]
```

with:
```python
def custom_export(players):
    yield ['session', 'participant_code', 'participant_label', 'participant_in_session',
           'condition', 'nav_condition', 'doc_id', 'sequence_position', 'watch_time_seconds',
           'liked', 'has_comment', 'comment', 'friction_delay_seconds', 'ad_clicked']

    for p in players:
        if not p.sequence:
            continue

        doc_ids = [int(x.strip()) for x in p.sequence.split(',')]

        viewport = parse_json_field(p.viewport_data)
        likes    = parse_json_field(p.likes_data)
        replies  = parse_json_field(p.replies_data)
        friction = parse_json_field(p.friction_data)
        promoted = parse_json_field(p.promoted_post_clicks)

        for position, doc_id in enumerate(doc_ids, start=1):
            yield build_export_row(
                p.session.code, p.participant.code, p.participant.label, p.id_in_group,
                p.feed_condition, p.nav_condition, doc_id, position,
                viewport, likes, replies, friction, promoted,
            )
```

- [ ] **Step 2: Sanity-check the module still parses**

Run: `python -c "import ast; ast.parse(open('DICE/__init__.py').read())"`
Expected: no output.

- [ ] **Step 3: Run the full pytest suite to confirm nothing in feed_logic regressed**

Run: `python -m pytest tests/ -v`
Expected: all tests pass (smoke + assignment + export + validation + CSV validation).

- [ ] **Step 4: Commit**

```bash
git add DICE/__init__.py
git commit -m "feat: export nav_condition, friction_delay_seconds, and ad_clicked"
```

---

### Task 12: friction.js — pure gate-logic module

**Files:**
- Create: `DICE/static/js/friction.js`
- Test: `tests/friction.test.js`

- [ ] **Step 1: Write the failing test**

`tests/friction.test.js`:
```javascript
const assert = require('assert');
const { shouldGateNavigation, computeFrictionEntry } = require('../DICE/static/js/friction.js');

// shouldGateNavigation
assert.strictEqual(shouldGateNavigation('friction'), true);
assert.strictEqual(shouldGateNavigation('normal'), false);
assert.strictEqual(shouldGateNavigation(undefined), false);
console.log('PASS: shouldGateNavigation only gates the friction condition');

// computeFrictionEntry
const entry = computeFrictionEntry(42, 1000, 2500);
assert.strictEqual(entry.doc_id, 42);
assert.strictEqual(entry.delay_seconds, 1.5);
console.log('PASS: computeFrictionEntry computes delay in seconds, keyed by doc_id');

console.log('All friction.test.js tests passed.');
```

- [ ] **Step 2: Run it to verify it fails**

Run: `node tests/friction.test.js`
Expected: throws `Error: Cannot find module '../DICE/static/js/friction.js'`

- [ ] **Step 3: Create friction.js**

`DICE/static/js/friction.js`:
```javascript
// Pure friction-gate logic — no DOM access, safe to load as a plain
// <script> in the browser (video_feed.js calls these as globals) and to
// require() directly under Node for testing.

function shouldGateNavigation(navCondition) {
    return navCondition === 'friction';
}

function computeFrictionEntry(docId, gateShownAt, now) {
    return { doc_id: docId, delay_seconds: Number(((now - gateShownAt) / 1000).toFixed(3)) };
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { shouldGateNavigation, computeFrictionEntry };
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `node tests/friction.test.js`
Expected:
```
PASS: shouldGateNavigation only gates the friction condition
PASS: computeFrictionEntry computes delay in seconds, keyed by doc_id
All friction.test.js tests passed.
```

- [ ] **Step 5: Commit**

```bash
git add DICE/static/js/friction.js tests/friction.test.js
git commit -m "feat: add pure friction-gate logic module with node tests"
```

---

### Task 13: Friction gate overlay markup, styles, and nav_condition wiring

**Files:**
- Modify: `DICE/C_Feed.html`
- Modify: `DICE/static/css/tiktok.css`

- [ ] **Step 1: Add the hidden field for friction_data**

In `DICE/C_Feed.html`, in the `<!-- Hidden Fields -->` block, change:
```html
<!-- Hidden Fields -->
<input type="hidden" name="viewport_data" id="viewport_data" value="">
<input type="hidden" name="promoted_post_clicks" id="promoted_post_clicks" value="">
<input type="hidden" id="likes_data" name="likes_data">
<input type="hidden" id="replies_data" name="replies_data">
<input type="hidden" id="touch_capability" name="touch_capability" value="">
<input type="hidden" id="device_type" name="device_type" value="">
<input type="hidden" id="screen_resolution" name="screen_resolution" value="">
```

to:
```html
<!-- Hidden Fields -->
<input type="hidden" name="viewport_data" id="viewport_data" value="">
<input type="hidden" name="promoted_post_clicks" id="promoted_post_clicks" value="">
<input type="hidden" id="likes_data" name="likes_data">
<input type="hidden" id="replies_data" name="replies_data">
<input type="hidden" id="friction_data" name="friction_data" value="">
<input type="hidden" id="touch_capability" name="touch_capability" value="">
<input type="hidden" id="device_type" name="device_type" value="">
<input type="hidden" id="screen_resolution" name="screen_resolution" value="">
```

- [ ] **Step 2: Add the overlay markup, and a nav_condition bootstrap script, and load friction.js before video_feed.js**

Change:
```html
{{ block scripts }}
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js" integrity="sha384-kenU1KFdBIe4zVF0s0G1M5b4hcpxyD9F7jL+jjXkk+Q2h455rYXK/7HAuoJl+0I4" crossorigin="anonymous"></script>
    <script src="{{ static 'js/format_numbers.js' }}"></script>
    <script src="{{ static 'js/mobile.js' }}"></script>
    <script src="{{ static 'js/video_feed.js' }}"></script>
{{ endblock }}
```

to:
```html
{{ block scripts }}
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js" integrity="sha384-kenU1KFdBIe4zVF0s0G1M5b4hcpxyD9F7jL+jjXkk+Q2h455rYXK/7HAuoJl+0I4" crossorigin="anonymous"></script>
    <script src="{{ static 'js/format_numbers.js' }}"></script>
    <script src="{{ static 'js/mobile.js' }}"></script>
    <script>
        window.NAV_CONDITION = "{{ nav_condition }}";
    </script>
    <script src="{{ static 'js/friction.js' }}"></script>
    <script src="{{ static 'js/video_feed.js' }}"></script>
{{ endblock }}
```

Then, still in `DICE/C_Feed.html`, add the overlay markup right after the loading screen `</div>` and before `<div id="mainContent"...>`:
```html
<!-- Loading Screen -->
<div id="loadingScreen" class="d-flex justify-content-center align-items-center" style="position:fixed;top:0;left:0;width:100%;height:100%;z-index:9999;background:#000;">
    <div class="tap-to-start">
        <i class="bi bi-play-circle-fill logo-icon"></i>
        <p>Tap to start</p>
        <button id="startBtn" type="button">Start</button>
    </div>
</div>

<!-- Friction gate overlay -->
<div id="friction-gate" class="d-none">
    <button id="frictionContinueBtn" type="button">Continue</button>
</div>

<!-- Main Content -->
<div id="mainContent" style="display:none;">
```

- [ ] **Step 3: Add friction gate styles**

In `DICE/static/css/tiktok.css`, after the `/* ---- Loading screen ---- */` block (after the `#startBtn:active { opacity: 0.85; }` rule), add:
```css
/* ---- Friction gate ---- */
#friction-gate {
    position: fixed;
    inset: 0;
    background: #000;
    z-index: 500;
    display: flex;
    align-items: center;
    justify-content: center;
}
#frictionContinueBtn {
    background: #fe2c55;
    border: none;
    border-radius: 24px;
    color: #fff;
    font-size: 16px;
    font-weight: 700;
    padding: 13px 52px;
    cursor: pointer;
}
#frictionContinueBtn:active { opacity: 0.85; }
```

(`#friction-gate` uses Bootstrap's existing `.d-none` utility class to start hidden, same pattern already used for `#loadingScreen`.)

- [ ] **Step 4: Sanity-check the template still parses**

Run: `python -c "import re; content = open('DICE/C_Feed.html', encoding='utf-8').read(); assert content.count('{{ block') == content.count('endblock }}')"`
Expected: no output (no `AssertionError`).

- [ ] **Step 5: Commit**

```bash
git add DICE/C_Feed.html DICE/static/css/tiktok.css
git commit -m "feat: add friction gate overlay markup and styles"
```

---

### Task 14: video_feed.js — gate interception, Continue button, data collection

**Files:**
- Modify: `DICE/static/js/video_feed.js`

- [ ] **Step 1: Add friction state near the top of the file**

Change:
```javascript
// State
let audioUnlocked = false;
const commentData = {}; // { docId: { text, hasComment } }
let activeCommentDocId = null;
let currentIndex = 0;
let isNavigating = false;
let touchStartY = 0;
let navLockTimer = null;
```

to:
```javascript
// State
let audioUnlocked = false;
const commentData = {}; // { docId: { text, hasComment } }
let activeCommentDocId = null;
let currentIndex = 0;
let isNavigating = false;
let touchStartY = 0;
let navLockTimer = null;

// Friction-scroll state
const navCondition = window.NAV_CONDITION || 'normal';
let pendingNavigation = null; // { index, items }
let gateShownAt = null;
const frictionLog = [];
const promotedClicks = [];
```

- [ ] **Step 2: Split navigateTo into a gate check plus the actual scroll**

Change:
```javascript
function navigateTo(index, items) {
    if (isNavigating) return;
    if (index < 0 || index >= items.length) return;

    isNavigating = true;
    currentIndex = index;
    items[index].scrollIntoView({ behavior: 'smooth', block: 'start' });

    clearTimeout(navLockTimer);
    navLockTimer = setTimeout(function () { isNavigating = false; }, 500);
}
```

to:
```javascript
function navigateTo(index, items) {
    if (isNavigating) return;
    if (index < 0 || index >= items.length) return;

    if (shouldGateNavigation(navCondition)) {
        pendingNavigation = { index: index, items: items };
        gateShownAt = Date.now();
        document.getElementById('friction-gate').classList.remove('d-none');
        return;
    }

    performNavigation(index, items);
}

function performNavigation(index, items) {
    isNavigating = true;
    currentIndex = index;
    items[index].scrollIntoView({ behavior: 'smooth', block: 'start' });

    clearTimeout(navLockTimer);
    navLockTimer = setTimeout(function () { isNavigating = false; }, 500);
}
```

- [ ] **Step 3: Wire the Continue button**

In the `document.addEventListener('DOMContentLoaded', function () { ... })` block, immediately after the `postCommentBtn` wiring (right before the `// Comment input: submit on Enter` comment), add:
```javascript
    // Friction gate: Continue button
    const frictionContinueBtn = document.getElementById('frictionContinueBtn');
    if (frictionContinueBtn) {
        frictionContinueBtn.addEventListener('click', function () {
            if (!pendingNavigation) return;

            const targetItem = pendingNavigation.items[pendingNavigation.index];
            const docId = targetItem && targetItem.dataset.docId ? parseInt(targetItem.dataset.docId) : null;
            if (docId !== null) {
                frictionLog.push(computeFrictionEntry(docId, gateShownAt, Date.now()));
            }

            document.getElementById('friction-gate').classList.add('d-none');
            performNavigation(pendingNavigation.index, pendingNavigation.items);
            pendingNavigation = null;
            gateShownAt = null;
        });
    }

    // Ad CTA click tracking
    document.querySelectorAll('.ad-cta-button').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            e.stopPropagation();
            const docId = parseInt(btn.dataset.docId);
            const alreadyLogged = promotedClicks.some(function (entry) { return entry.doc_id === docId; });
            if (!alreadyLogged) {
                promotedClicks.push({ doc_id: docId, clicked: true });
            }
        });
    });
```

(Transitions into the end-card are gated the same way as any other transition — `#end-card` has no `data-doc-id`, so those specific gate events simply don't produce a `friction_data` entry, since there's no video to key the delay to. The gate still visually appears and still requires a click.)

- [ ] **Step 4: Serialize the new fields in collectAllData**

Change:
```javascript
    document.getElementById('likes_data').value = JSON.stringify(likes);
    document.getElementById('replies_data').value = JSON.stringify(replies);
    document.getElementById('promoted_post_clicks').value = JSON.stringify([]);
    document.getElementById('viewport_data').value = serializeViewportData();

    console.log('Data collected. Likes:', likes.length, 'Replies:', replies.length);
```

to:
```javascript
    document.getElementById('likes_data').value = JSON.stringify(likes);
    document.getElementById('replies_data').value = JSON.stringify(replies);
    document.getElementById('promoted_post_clicks').value = JSON.stringify(promotedClicks);
    document.getElementById('friction_data').value = JSON.stringify(frictionLog);
    document.getElementById('viewport_data').value = serializeViewportData();

    console.log('Data collected. Likes:', likes.length, 'Replies:', replies.length);
```

- [ ] **Step 5: Re-run the friction.js node test to confirm the shared functions still resolve correctly**

Run: `node tests/friction.test.js`
Expected: same 2 PASS lines as Task 12 (video_feed.js calling `shouldGateNavigation`/`computeFrictionEntry` as globals doesn't change friction.js itself).

- [ ] **Step 6: Commit**

```bash
git add DICE/static/js/video_feed.js
git commit -m "feat: intercept navigateTo with friction gate, track ad clicks"
```

---

### Task 15: Ad post markup and styles

**Files:**
- Modify: `DICE/T_Item_Post.html`
- Modify: `DICE/static/css/tiktok.css`

- [ ] **Step 1: Add the Sponsored tag and CTA button**

In `DICE/T_Item_Post.html`, change:
```html
    <!-- Bottom video info -->
    <div class="video-info">
        <p class="video-username">@{{ i.handle }}</p>
        <p class="video-description">{{ i.text }}</p>
        <div class="video-audio">
            <i class="bi bi-music-note-beamed"></i>
            <span class="audio-text">{{ i.username }} · original sound</span>
        </div>
    </div>
```

to:
```html
    <!-- Bottom video info -->
    <div class="video-info">
        {{ if i.is_ad }}
        <span class="sponsored-tag">Sponsored</span>
        {{ endif }}
        <p class="video-username">@{{ i.handle }}</p>
        <p class="video-description">{{ i.text }}</p>
        <div class="video-audio">
            <i class="bi bi-music-note-beamed"></i>
            <span class="audio-text">{{ i.username }} · original sound</span>
        </div>
        {{ if i.is_ad }}
        <button type="button" class="ad-cta-button" data-doc-id="{{ i.doc_id }}">Learn more</button>
        {{ endif }}
    </div>
```

- [ ] **Step 2: Add the CSS**

In `DICE/static/css/tiktok.css`, after the `/* ---- Bottom video info ---- */` block (after the `.audio-text { ... }` rule), add:
```css
/* ---- Sponsored ad post ---- */
.sponsored-tag {
    display: inline-block;
    background: rgba(255,255,255,0.15);
    color: rgba(255,255,255,0.85);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.3px;
    text-transform: uppercase;
    padding: 3px 8px;
    border-radius: 4px;
    margin-bottom: 8px;
}
.ad-cta-button {
    display: block;
    background: #fff;
    color: #000;
    border: none;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 700;
    padding: 10px 16px;
    margin-top: 10px;
    cursor: pointer;
    width: fit-content;
}
.ad-cta-button:active { opacity: 0.85; }
```

- [ ] **Step 3: Commit**

```bash
git add DICE/T_Item_Post.html DICE/static/css/tiktok.css
git commit -m "feat: render Sponsored tag and CTA on ad posts"
```

---

### Task 16: End-to-end manual verification

**Files:** none (verification only)

This is the point where DOM/video-dependent behavior — not covered by the automated tests above — gets checked by hand, per the project's existing testing posture.

- [ ] **Step 1: Run the full automated suite one more time**

Run: `python -m pytest tests/ -v && node tests/friction.test.js`
Expected: all pytest tests pass, both friction.test.js PASS lines print.

- [ ] **Step 2: Start the oTree dev server**

Run: `otree devserver`
Expected: server starts on `http://localhost:8000` with no startup errors.

- [ ] **Step 3: Verify the normal-scroll condition**

In a browser, go to `http://localhost:8000`, start a demo session for **FrictionScrollStudy**, and open a play link. Tap Start.
- Swipe/scroll through videos — confirm navigation is instant, no black screen appears, exactly as the existing `Feed` demo behaves today.
- Confirm the ad post (5th item) shows a "Sponsored" tag and a "Learn more" button, and clicking it doesn't navigate away or break the feed.
- Reach the end card and submit.

- [ ] **Step 4: Verify the friction-scroll condition**

Open a second play link from the same demo session (round-robin assignment means the next participant should land in a different cell — open several links if needed until you see the black gate appear).
- Confirm after every video, swiping forward shows a full-screen black "Continue" screen, and the next video only appears after clicking Continue.
- Confirm swiping backward to a previous video also shows the gate.
- Confirm the transition into the end card also shows the gate.
- Complete the feed and submit.

- [ ] **Step 5: Check the exported data**

In the oTree admin (`http://localhost:8000/admin`), open the session, go to Data, and download the app's custom export CSV.
- Confirm `nav_condition` is populated for both participants tested above (one `normal`, one `friction`).
- Confirm `friction_delay_seconds` has values only for the friction participant, blank for the normal participant.
- Confirm `ad_clicked` is `True` only for the row where the ad's CTA was clicked (if you clicked it in Step 3/4).
- Confirm `condition` shows the assigned topic (SPORT/FOOD/TRAVEL) and matches what was actually displayed.

- [ ] **Step 6: Confirm the original Feed demo is unaffected**

Start a demo session for the original **Feed** config and click through it briefly — confirm it behaves exactly as before (no gate, no Sponsored tags, since `sample_videos.csv` has no `is_ad` column and that config has no `nav_conditions`).

- [ ] **Step 7: Stop the dev server**

Stop the `otree devserver` process (Ctrl+C).

---

### Task 17: Final wrap-up

**Files:** none

- [ ] **Step 1: Confirm git log tells a clean story**

Run: `git log --oneline`
Expected: one commit per task above, in order, on top of the two earlier commits (baseline source + design spec).

- [ ] **Step 2: Confirm working tree is clean**

Run: `git status`
Expected: `nothing to commit, working tree clean`
