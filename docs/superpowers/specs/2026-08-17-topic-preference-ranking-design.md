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

**Analysis implication:** this means `preference_alignment` is partially
confounded with topic content, not just with uneven exposure counts — if the
modal #1 pick is FOOD and the modal #3 pick is TRAVEL, a most-vs-least
contrast is partly a FOOD-vs-TRAVEL content contrast too. The export carries
both `preference_alignment` and the full `topic_ranking`/`condition` per row,
so this can be covaried or stratified on in analysis, but it's a deliberate
tradeoff of this design (not resolvable in the assignment mechanism itself)
that any analysis plan needs to account for.

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
   recorded as-is in `topic_ranking`.

   **Update (added during final review, not in the original approved
   design):** the fallback above is deterministic (always the CSV's own
   topic order), so a JS failure confined to one browser/device class could
   silently install a topic × alignment confound with no trace in the
   export — the original design's assumption that "the ranking data itself
   remains inspectable" doesn't actually hold, since a fallback value is
   indistinguishable from a genuine ranking or an untouched default. Fixed
   by adding `player.topic_ranking_initial`: a second hidden field the
   client JS populates once, immediately on page load, with the order as
   first shown (before any reordering) — captured *as-submitted*, with no
   server-side fallback/normalization applied to it, so its emptiness is
   itself meaningful. Reading the pair together in the export:
   - `topic_ranking_initial` empty → the reorder JS never ran (the
     `topic_ranking` fallback fired).
   - `topic_ranking_initial == topic_ranking` → JS ran, but the participant
     never touched the ▲/▼ controls (submitted the shown default order).
   - `topic_ranking_initial != topic_ranking` → a genuine reorder happened.
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
`rank_topics` is on, `feed_condition` isn't set yet at that point.

**Update (found during Task 8's live verification, not anticipated when this
spec was written):** on this oTree version, directly accessing a `None`-valued
field on a frozen player instance raises `TypeError`, not a harmless empty
comparison as originally assumed here — `player.feed_condition` had to become
`player.field_maybe_none('feed_condition')` in that one line, or every
`rank_topics` participant's consent submission 500s. With that fix, the
*value* produced (an empty-string `player.sequence`, immediately overwritten
by `B_TopicRanking.before_next_page`) matches this spec's original intent —
only the crash needed fixing, not the logic.

This is the same underlying frozen-instance/`None` crash mechanism that
motivated the `field_maybe_none()` fixes for `topic_ranking`/`feed_condition`/
`sequence` in the export path (Task 6, and a final-review follow-up).
Those export fields were never actually at risk through oTree's real admin
export UI, which unfreezes every player first — the risk there is specific
to *direct* `custom_export()` invocation (scripts, tests, verification
tooling), which is exactly how each of those gaps was actually found.
`A_Intro.before_next_page`, by contrast, runs on every real page load, so
that one *was* a live production crash, not just a direct-invocation risk.

## New Player fields

```python
preference_alignment = models.StringField(
    doc="'most' or 'least' — which end of the participant's own topic "
        "ranking was actually shown to them.",
    blank=True)
topic_ranking = models.LongStringField(
    doc='JSON list of topics ranked most→least preferred by the participant.',
    blank=True)
topic_ranking_initial = models.LongStringField(
    doc='JSON list of topics in the order first shown to the participant, '
        'before any reordering -- stored as-submitted (not defaulted), so '
        'an empty/unparseable value is itself the signal that the reorder '
        'JS never ran. Added during final review; see "Update" note above.',
    blank=True)
```

`feed_condition` (existing field) is unchanged in meaning — it still holds
whichever topic the participant actually saw.

## Export changes

`custom_export()` gains three participant-level columns (constant per
participant, alongside `nav_condition`):

```
preference_alignment    — from player.preference_alignment
topic_ranking            — from player.topic_ranking, rendered as a
                            comma-joined string ("FOOD, SPORT, TRAVEL")
                            rather than raw JSON, for readability
topic_ranking_initial    — from player.topic_ranking_initial, same
                            comma-joined rendering. Compare against
                            topic_ranking per-row to distinguish a genuine
                            reorder, an untouched default, or a JS-failure
                            fallback (see the "Update" note above).
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
- `DICE/static/css/styles.css` — ranking list styles (the shared onboarding-page
  stylesheet already used by `A_Intro`/`B_Briefing`'s light bootstrap-card
  layout — `tiktok.css` is the dark video-feed theme and doesn't apply here)
- `tests/test_feed_logic_export.py`, new `tests/test_topic_ranking.js` (or
  similar) — coverage for the new helpers
- `docs/superpowers/specs/2026-08-07-friction-scroll-experiment-design.md` —
  update the "Research design" section to point at this spec / reflect the
  2×2 design instead of 3×2
- `README.md` — update study design description and export column table
