# Leonor's Experiment — Friction Scroll Study

A TikTok-style feed experiment testing how a "friction scroll" navigation mechanic (an extra interstitial tap between videos) affects engagement, built with [oTree](https://otree.readthedocs.io/en/latest/) on top of the [DICE](https://github.com/Howquez/DICE) platform.

## Study design

2×2 between-subjects design:

- **Preference alignment**: participants rank SPORT/FOOD/TRAVEL from most to least favorite before the feed starts, then see either their most- or least-preferred topic (never the middle one)
- **Navigation condition**: normal free scroll, or friction scroll (a black screen appears after every video; the participant must click Continue before the next video appears)

Every participant sees 6 videos in a fixed order: 5 regular videos, then a sponsored ad post as the final item. Engagement stats (likes/comments/shares) are matched by position across the three topics, so the topic itself can't confound the navigation-condition comparison.

Participants are assigned to one of the 4 (preference-alignment × navigation) cells automatically, balanced so every 4 participants covers all 4 cells exactly once. Topic itself is *not* separately balanced — it follows whatever each participant's own ranking puts in their assigned "most" or "least" slot. This means `preference_alignment` is partially confounded with topic content (e.g. if most people rank FOOD #1, a most-vs-least comparison is partly a FOOD-vs-other-topics comparison) — the export includes each participant's full ranking so this can be accounted for in analysis, but it's worth planning for.

## Running it

```bash
git clone https://github.com/manuelvenade/Leonor-s-experiment-.git
cd Leonor-s-experiment-
pip install -r requirements.txt
otree devserver
```

Open `http://localhost:8000/demo/FrictionScrollStudy` — this creates a demo session with 4 participants (one per preference-alignment × navigation cell) and gives you a play link for each one.

## Deploying online (oTreeHub)

[oTreeHub](https://www.otreehub.com) hosts oTree studies without you needing to manage a server.

1. Run `otree zip` in the project folder — this creates a `.otreezip` file.
2. Log in to [otreehub.com](https://www.otreehub.com), create a new project, and upload that `.otreezip`.
3. Click **Deploy**. You get a public URL to send to participants.

Whenever you change a video, the CSV, or any code, repeat `otree zip` and re-upload to redeploy. Session data can be downloaded from the oTreeHub dashboard.

## How to add or replace a video

All feed content lives in one file: `DICE/static/data/friction_scroll_videos.csv`. It has 18 rows — one per (topic, position) combination — and it's semicolon-separated (open it in Excel/Sheets and set the delimiter to `;`, or edit it directly as text).

**To replace an existing video** (e.g. swap out one of the placeholder SPORT or TRAVEL clips):

1. **Add your video file** to `DICE/static/mp4/`. Give it a clear name, e.g. `sport1.mp4`. Keep clips short (under 30 seconds) and small (under ~15 MB) — large files slow down deployment.
2. **Find its row** in the CSV. Each row has a `condition` column (SPORT/FOOD/TRAVEL) and a `sequence` column (1–6, its position in that topic's feed). For example, the SPORT topic's first video is the row where `condition=SPORT` and `sequence=1`.
3. **Update only these three columns** in that row:
   - `video` → your new filename (e.g. `sport1.mp4`)
   - `text` → the caption to show under the username
   - `username` / `handle` → whatever poster identity you want for that clip
4. **Leave every other column in that row untouched** — especially `likes`, `reposts`, `replies`, `doc_id`, `condition`, `sequence`, and `is_ad`. Those numbers are deliberately identical across SPORT/FOOD/TRAVEL at each position; changing them breaks the experimental control the study depends on.

**To check you haven't broken anything**, run:

```bash
python -m pytest tests/test_csv_validation.py -v
```

This checks the row count, that every topic has all 6 positions, that the ad is where it should be, and that the engagement numbers still match across topics. If it passes, you're good.

**Currently in the CSV:**
- FOOD topic (positions 1–4, 6) and the ad (position 5, identical across all three topics) use real footage already in `DICE/static/mp4/`.
- SPORT and TRAVEL still use short placeholder clips (`1.mp4`–`9.mp4`) and need to be replaced with real footage before running the actual study.

**Using a video hosting service instead of local files:** you can also just paste a direct `.mp4` URL into the `video` column (e.g. from Cloudinary, Bunny.net, or S3) instead of a local filename — this keeps the repo small and is recommended if you have many/large videos. The service just needs to allow cross-origin requests (most CDNs do this by default). Do not use YouTube or TikTok links directly — those platforms block embedding.

## How to change the survey redirect link

After finishing the feed, participants are redirected to an external survey. To point this at your own survey:

1. Open `settings.py`.
2. Find this line inside `SESSION_CONFIG_DEFAULTS`:
   ```python
   survey_link = 'https://unisg.qualtrics.com/jfe/form/SV_0DnMoLpM0VxjhrM',
   ```
3. Replace the URL with your own survey's link (Qualtrics, SoSci Survey, Google Forms, etc.):
   ```python
   survey_link = 'https://your-survey-platform.com/your-survey-id',
   ```
4. If your survey needs to know which participant this is (to link feed data to survey responses), check `url_param` right below it:
   ```python
   url_param = 'PROLIFIC_PID',
   ```
   This is the name of the URL query parameter the participant's ID gets attached as, e.g. `?PROLIFIC_PID=abc123`. Set this to match whatever your survey platform calls its embedded-data field (in Qualtrics this is usually the "Embedded Data" field name you set up to receive it).

**If you don't have a survey yet**, leave `survey_link` as an empty string — participants will see a simple built-in "Thank you" debrief page instead:
```python
survey_link = '',
```

## What gets recorded

For each participant × video, the export (`Data` tab in oTree's admin, or `/export` locally) contains:

| Field | Description |
|-------|-------------|
| `condition` | Video topic: SPORT, FOOD, or TRAVEL |
| `nav_condition` | Navigation condition: normal or friction |
| `preference_alignment` | Whether this participant was shown their most- or least-preferred topic |
| `topic_ranking` | The participant's final submitted topic ranking, most to least preferred (e.g. "FOOD, SPORT, TRAVEL") |
| `topic_ranking_initial` | The order shown before any reordering. Compare to `topic_ranking`: identical = never touched the controls; different = genuinely reordered; blank = the ranking page's JS never ran (treat `topic_ranking` with caution for that row) |
| `sequence_position` | Position of this video in the feed (1–6) |
| `watch_time_seconds` | Seconds the video was actually playing |
| `video_length_seconds` | The clip's actual length |
| `watch_percentage` | `watch_time_seconds` as a % of the clip's length |
| `liked` | Whether the participant liked the video |
| `has_comment` / `comment` | Whether they commented, and the text |
| `friction_delay_seconds` | Total time on the black gate before this video (friction condition only) |
| `voluntary_hesitation_seconds` | Same as `friction_delay_seconds` — there's no mandatory wait, so all of it is voluntary |
| `ad_clicked` | Whether they clicked the ad's "Learn more" button |
| `completed_feed` | Whether they watched through to the end, or left early |
| `last_position_viewed` | The last video position they reached |
| `total_watch_time_seconds`, `session_duration_seconds`, `completion_rate` | Session-level totals, repeated on every row for that participant |

Device info (device type, screen resolution, touch capability) is also recorded per participant.

A participant who never reaches the feed (e.g. abandons on the ranking survey) doesn't appear in the export at all — this changed slightly from earlier versions of the study, so exported row counts won't necessarily match total Prolific/participant submissions.

## Customizing further

- **Researcher info and consent text** — `DICE/T_Consent.html` and `settings.py` (`full_name`, `eMail`, `study_name`)
- **Topic ranking survey** (shown right after consent, for `FrictionScrollStudy`) — wording in `DICE/B_TopicRanking.html`; toggled on/off entirely via the `rank_topics` flag in that session's config in `settings.py`
- **Briefing instructions** (shown before the feed starts) — `DICE/B_Briefing.html`
- **Friction gate** — the black interstitial has no enforced wait; the Continue button is clickable as soon as it appears (`DICE/static/js/video_feed.js`, `DICE/C_Feed.html`)
- **Ad content** — the three rows in the CSV where `is_ad=1` (one per topic, identical to each other by design)

## Citation

This project builds on DICE. If you use it in a published study, please cite:

> Roggenkamp, H., Boegershausen, J., & Hildebrand, C. (2026). DICE: Advancing Social Media Research Through Digital In-Context Experiments. Journal of Marketing. https://doi.org/10.1177/00222429251371702

## Tested on

Chrome / macOS and Windows. Designed for mobile browsers (iOS Safari, Android Chrome) as the primary target platform.
