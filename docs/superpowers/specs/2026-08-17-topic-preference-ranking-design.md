# Topic Preference Ranking — Design Spec

Date: 2026-08-17
Status: Approved, not yet implemented

## Background

`FrictionScrollStudy` currently assigns each participant's video topic
(SPORT/FOOD/TRAVEL) via a balanced, researcher-controlled 3-way random cycle,
crossed with navigation condition (normal/friction) — a 3×2, 6-cell design
(see `2026-08-07-friction-scroll-experiment-design.md`).

This spec replaces that with a preference-driven topic assignment: before
seeing the feed, participants rank the three topics from most to least
preferred, and are then shown either their most- or least-preferred topic —
never the middle one. Which end gets shown is the new researcher-controlled,
balanced factor.

## Research design

**Between-subjects, 2×2 factorial, 4 cells.**

| Factor | Levels |
|---|---|
| Preference alignment | Most-preferred topic shown, Least-preferred topic shown |
| Navigation condition | Normal scroll, Friction scroll |

Topic (SPORT/FOOD/TRAVEL) is **no longer independently balanced**. It's
whichever topic lands in the participant's own "most" or "least" slot,
determined by their ranking. This means topic exposure across the sample
will track participants' actual preferences rather than being forced even
(e.g. if most participants rank FOOD #1, "most-preferred" participants will
skew toward FOOD) — that's an intended consequence of measuring a real
preference, not a defect.

`preference_alignment` is assigned via the same balanced shuffled-cycle
mechanism already used for `nav_condition` (`assign_cycle_pairs` in
`feed_logic.py`), just crossing `['most', 'least']` with `nav_conditions`
instead of the topic list. This only applies when the session config sets
`rank_topics = True` — added for `FrictionScrollStudy` only. The original
`Feed` demo config is untouched and keeps its current 3-way random topic
assignment.

## New page: rank topics

**Placement:** `A_Intro` (consent) → **`B_TopicRanking`** (new) →
`B_Briefing` → `C_Feed` → ... `is_displayed` returns `False` (page skipped
entirely) when `rank_topics` isn't set on the session config, so this has no
effect on the `Feed` demo config.

**UI:** the three topics are rendered as a vertical list, each row with ▲/▼
buttons to move it up or down (not native HTML5 drag-and-drop — that API
doesn't support touch input at all without an extra JS library, which this
project doesn't currently pull in; ▲/▼ works identically via touch, mouse,
and keyboard). Initial list order is **randomized per participant** (not
fixed) to avoid a primacy-effect confound where whatever tops the list is
more likely to stay ranked #1 regardless of actual preference.

Submitting without touching the ▲/▼ controls is a valid response (the
randomized initial order becomes the ranking) — no forced-interaction gate,
consistent with how the rest of this app's forms work.

On submit, client-side JS serializes the current DOM order into a hidden
`topic_ranking` field as a JSON array, e.g. `["FOOD","SPORT","TRAVEL"]`
(most → least), following the same hidden-field-serialization pattern
already used for `friction_data` / `promoted_post_clicks` in
`video_feed.js`. The reorder logic itself (`moveRankItem(order, index,
direction)`) is a pure function in a new `DICE/static/js/topic_ranking.js`,
mirroring the `friction.js` / `friction.test.js` split so it's unit-testable
under plain Node without a browser.

**`before_next_page`** (this is where topic assignment actually happens):

1. Parse `player.topic_ranking`. If it's missing or isn't a valid
   permutation of the session's topics (e.g. JS failed to run), fall back to
   the topics in `subsession.feed_conditions` order (the CSV's own
   unique-value order, before the per-participant display shuffle) —
   recorded as-is in `topic_ranking`, no separate "fallback occurred" flag,
   since this is expected to be rare and the ranking data itself remains
   inspectable.
2. `player.feed_condition = ranking[0] if player.preference_alignment ==
   'most' else ranking[-1]`.
3. Filter the full (all-topics) `player.participant.videos` DataFrame down
   to that topic, then run the same sequence-fill/sort logic
   `creating_session` already runs for the non-deferred path — extracted
   into a shared `finalize_player_sequence(posts)` helper in `feed_logic.py`
   so both paths call the same code instead of duplicating it.
4. Set `player.sequence` from the finalized, filtered post list, same as
   today.

## Assignment mechanism changes

`creating_session()` in `DICE/__init__.py`:

- When `rank_topics` is set: build the assignment cycle from
  `assign_cycle_pairs(['most', 'least'], nav_conditions)` instead of
  `assign_cycle_pairs(topics, nav_conditions)`. Each player gets
  `preference_alignment` and `nav_condition` assigned immediately (same as
  today), but `player.participant.videos` is stored **unfiltered** (all
  three topics still mixed) and `feed_condition` / `sequence` are left unset
  — both get finalized later, in `B_TopicRanking.before_next_page`.
- When `rank_topics` is not set: behavior is completely unchanged from
  today — topic assignment, filtering, and sequence finalization all still
  happen immediately in `creating_session`, using the extracted
  `finalize_player_sequence` helper (a refactor, not a behavior change).

`A_Intro.before_next_page` currently recomputes `player.sequence` by
filtering `player.participant.videos` on `player.feed_condition`. When
`rank_topics` is on, `feed_condition` isn't set yet at that point, so this
produces a harmless empty string that `B_TopicRanking.before_next_page`
immediately overwrites afterward. Left as-is — not worth touching for a
transient value nothing reads.

## New Player fields

```python
preference_alignment = models.StringField(
    doc="'most' or 'least' — which end of the participant's own topic "
        "ranking was actually shown to them.",
    blank=True)
topic_ranking = models.LongStringField(
    doc='JSON list of topics ranked most→least preferred by the participant.',
    blank=True)
```

`feed_condition` (existing field) is unchanged in meaning — it still holds
whichever topic the participant actually saw.

## Export changes

`custom_export()` gains two participant-level columns (constant per
participant, alongside `nav_condition`):

```
preference_alignment  — from player.preference_alignment
topic_ranking          — from player.topic_ranking, rendered as a
                          comma-joined string ("FOOD, SPORT, TRAVEL")
                          rather than raw JSON, for readability
```

## Session config

`settings.py`, `FrictionScrollStudy` config gains:

```python
rank_topics=True,
```

## Out of scope

- Changing the `Feed` demo config's assignment behavior (untouched).
- Forcing participants to interact with the ranking controls before
  submitting (default randomized order is an acceptable, valid response).
- True drag-and-drop reordering (▲/▼ buttons only, for touch reliability
  without adding a JS dependency).
- Re-deriving `A_Intro.before_next_page`'s redundant sequence computation —
  left as dead-but-harmless work when `rank_topics` is on.

## Files expected to change

- `DICE/__init__.py` — new `Player` fields, `creating_session` deferred-path
  branch, new `B_TopicRanking` page, `page_sequence`, `custom_export`
- `feed_logic.py` — `finalize_player_sequence` helper (extracted, reused by
  both the immediate and deferred assignment paths), ranking-validation
  helper, `assign_cycle_pairs(['most','least'], ...)` reuse (no code change
  needed there — already generic)
- `settings.py` — `rank_topics` config flag on `FrictionScrollStudy`
- `DICE/B_TopicRanking.html` — new template (ranking UI)
- `DICE/static/js/topic_ranking.js` — new pure reorder-logic module + DOM
  wiring, mirroring `friction.js`
- `DICE/static/css/tiktok.css` — ranking list styles
- `tests/test_feed_logic_export.py`, new `tests/test_topic_ranking.js` (or
  similar) — coverage for the new helpers
- `docs/superpowers/specs/2026-08-07-friction-scroll-experiment-design.md` —
  update the "Research design" section to point at this spec / reflect the
  2×2 design instead of 3×2
- `README.md` — update study design description and export column table
