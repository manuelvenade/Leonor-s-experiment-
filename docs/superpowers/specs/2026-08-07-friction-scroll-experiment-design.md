# Friction Scroll Experiment — Design Spec

Date: 2026-08-07
Status: Approved, not yet implemented

## Background

DICE TikTok (this repo) is an oTree app that simulates a TikTok-style vertical
video feed for behavioral experiments. It already supports one between-subjects
content factor via a `condition` column in the feed CSV (round-robin assignment
in `creating_session()`). This spec adds a second, orthogonal factor — the
navigation mechanic itself — to run a 3×2 factorial study.

## Research design

**Between-subjects, 3×2 factorial, 6 cells.**

| Factor | Levels |
|---|---|
| Video topic | SPORT, FOOD, TRAVEL |
| Navigation condition | Normal scroll, Friction scroll |

Every participant sees a fixed 6-item sequence, always in this order:

```
video, video, video, video, video, AD
(pos 1) (pos 2) (pos 3) (pos 4) (pos 5) (pos 6)
```

The sequence is **not randomized** — position is fixed so that engagement stats
(likes/comments/shares) can be matched position-for-position across the three
topic conditions. This isolates the navigation-condition manipulation: any
difference in engagement between friction and normal-scroll groups can't be
attributed to differing starting stats or differing video order.

- Topic is the only thing that varies in *content* between the three topic
  groups. The ad (position 6, the last item) is identical across all three
  topics.
- Navigation condition (friction vs. normal) is a pure UI/interaction
  manipulation layered on top — it does not change which videos are shown.

**Friction scroll**, specifically: after every video, a full-screen black
interstitial appears with a "Continue" button, clickable immediately — there
is no enforced minimum wait or visible countdown. The participant must still
click it before the next video is revealed; the friction is the extra
interstitial/tap itself, not a timed delay. This applies to *every*
transition — forward,
backward (re-watching a previous video), and the final transition into the
end card. Normal-scroll participants never see this screen; navigation
behaves exactly as it does today (free swipe/arrow-key scrolling).

## Assignment mechanism

Extends `creating_session()` in `DICE/__init__.py`.

1. Build the 6 `(topic, nav_condition)` pairs via
   `itertools.product(unique topic values from CSV, nav_conditions)`.
2. Shuffle the list of 6 pairs once per session.
3. `itertools.cycle()` through the shuffled list, assigning one pair per
   player in creation order — same pattern already used for the single-factor
   `condition` cycle, just crossed with a second factor.

This guarantees exact balance across all 6 cells every 6 participants, with
non-predictable ordering (unlike two independent lockstep cycles, which would
produce the same fixed pairing sequence every session run).

New session config default in `settings.py`:

```python
nav_conditions = ['normal', 'friction']
```

New `Player` field:

```python
nav_condition = models.StringField(doc='normal or friction scroll condition')
```

Topic assignment continues to use the existing `feed_condition` player field
and `condition` CSV column — no change to that mechanism.

## CSV schema changes

Builds on the existing documented schema (see README "Configuring the feed").
Two additions:

1. **`sequence` is fully populated for every row** (values 1–6), not left
   blank. The existing preprocessing in `creating_session()` only randomizes
   rows where `sequence` is null — with every row filled in, the order is
   fully deterministic, which is what this design requires. No code change
   needed here, just CSV content.
2. **New `is_ad` column** (0/1). Set to 1 on the position-6 (last) row for
   each topic; 0 everywhere else.

Row count: 3 topics × 6 positions = **18 rows** (15 regular videos + 3 ad
rows). The 3 ad rows share identical `text`, `video`, `likes`, `reposts`,
`replies` values. At each shared `sequence` position (1–6), `likes`,
`reposts`, and `replies` are matched across the three topics — captions,
usernames, and video files differ freely.

| Column | Notes |
|---|---|
| `condition` | `SPORT` / `FOOD` / `TRAVEL` (existing column, reused) |
| `sequence` | 1–6, fixed, fully populated (existing column, now always filled) |
| `is_ad` | **new** — 0/1 |
| everything else | unchanged from current schema |

A template CSV with this structure (placeholder rows, real video/caption
content still to be sourced) will be generated as part of implementation, at
`DICE/static/data/friction_scroll_videos.csv`, alongside the existing sample
file (which stays untouched as a reference/demo).

## Friction scroll mechanic

Implementation approach: **one reusable full-screen overlay**, decoupled from
the scrollable feed (not an item you scroll past). Styled consistently with
the existing `#loadingScreen` / `.tap-to-start` pattern already in
`tiktok.css`.

All navigation currently funnels through a single function, `navigateTo()` in
`DICE/static/js/video_feed.js` — this is the interception point:

- Touch swipe (`touchend` handler) and arrow/PageUp/PageDown keys both call
  `navigateTo(index, items)`.
- Wheel/trackpad scroll is already fully blocked (`e.preventDefault()` on
  `wheel`), so no change needed there.

For `nav_condition === 'friction'`:

1. On any call to `navigateTo(targetIndex, items)`, instead of scrolling
   immediately: record `gateShownAt = Date.now()`, show the overlay with its
   Continue button already clickable, and store `targetIndex` as pending.
   There is no countdown and no enforced minimum wait — the only friction is
   the extra interstitial screen and the tap it takes to dismiss it.
2. On Continue click: compute `delay_seconds = (Date.now() - gateShownAt) /
   1000`, record `{ doc_id: <target item's doc_id>, delay_seconds }` into the
   in-memory friction log, hide the overlay, then perform the actual
   `scrollIntoView` navigation to `targetIndex`. `delay_seconds` here is
   purely how long the participant chose to sit on the gate before tapping
   Continue.
3. The end-card counts as a normal transition target — swiping from the last
   video into the end-card is gated the same way.
4. The very first video (on initial "Start" tap) is not gated — there is no
   transition *into* it from another feed item.

For `nav_condition === 'normal'`, `navigateTo()` behaves exactly as it does
today (no interception).

`nav_condition` is passed from the page to the script via `js_vars` on
`C_Feed` (or an equivalent data attribute), following the existing pattern
used elsewhere in this template for server→client value passing.

## New data captured

**Player fields** (`DICE/__init__.py`):

```python
friction_data = models.LongStringField(
    doc='tracks time-to-continue for each gated transition (friction condition only).',
    blank=True)
```

Content: JSON list of `{doc_id, delay_seconds}`, keyed by the *target*
video's `doc_id` (i.e., "how long the participant sat on the gate before
this video appeared"). At most one entry per `doc_id` — if a participant
is gated into the same video more than once (e.g. swiping back and then
forward again), only the *first* encounter's delay is kept, since that's
the more representative measure of the manipulation's cost and shouldn't
be silently overwritten by a later re-encounter. Empty list for
normal-condition participants.

`promoted_post_clicks` (existing field, currently written but never
populated with real data — `video_feed.js` hardcodes `JSON.stringify([])`).
Wired up to record ad CTA clicks: JSON list of `{doc_id, clicked: true}`,
one entry if the ad's CTA button was clicked, keyed by the ad's `doc_id`.

Both fields are added to `C_Feed.get_form_fields()` and populated in
`collectAllData()` in `video_feed.js`, following the exact pattern already
used for `likes_data` / `replies_data`.

## Export changes

`custom_export()` in `DICE/__init__.py` gains three columns, using the same
parse-and-lookup pattern already used for `viewport_data` / `likes_data` /
`replies_data`:

```
nav_condition        — from player.nav_condition (constant per participant)
friction_delay_seconds — from parsed friction_data, blank if not gated / normal condition
ad_clicked           — from parsed promoted_post_clicks, blank for non-ad rows
```

## Ad post UI

Renders in the same full-screen video layout as a regular post
(`T_Item_Post.html`), gated on `{{ if i.is_ad }}`:

- Small "Sponsored" tag near the caption text.
- A CTA button (e.g. "Learn more") in place of / alongside the caption area,
  styled consistently with existing button treatments (`.proceed-btn` /
  `#startBtn` conventions in `tiktok.css`).
- Like/comment/share sidebar remains fully functional, same as any other
  post, for realism.
- Clicking the CTA logs to `promoted_post_clicks` (see above) — does not
  navigate away or open any external link.

## Out of scope

- Sourcing/curating the actual SPORT/FOOD/TRAVEL video files and captions —
  the template CSV defines the schema; content curation is a separate,
  manual task.
- Any changes to the existing single-factor `condition` demo
  (`sample_videos.csv` stays as-is).
- Statistical power / sample size planning.

## Files expected to change

- `DICE/__init__.py` — assignment logic, new `Player` fields, `get_form_fields`, `custom_export`
- `settings.py` — `nav_conditions` config default
- `DICE/static/js/video_feed.js` — friction gate interception in `navigateTo()`, `collectAllData()` updates
- `DICE/C_Feed.html` — overlay markup, hidden fields for new data, `js_vars` for `nav_condition`
- `DICE/T_Item_Post.html` — ad post rendering (`is_ad` branch)
- `DICE/static/css/tiktok.css` — friction overlay styles, ad post styles
- `DICE/static/data/friction_scroll_videos.csv` — new template CSV (new file)
