# DICE TikTok

A TikTok-style social media feed simulator for online behavioral experiments, built with [oTree](https://otree.readthedocs.io/en/latest/).

## Background

[DICE](https://github.com/Howquez/DICE) (Digital In-Context Experiments) is a platform for simulating social media feeds in controlled experiments. It comes with a graphical interface at [dice-app.org](https://dice-app.org) that lets you build and deploy feed experiments without writing code. [DICE Lite](https://github.com/Howquez/DICE-lite) is a stripped-down version for researchers who prefer working directly with code — same core logic, no GUI layer.

DICE TikTok is a further iteration. It replaces the microblogging-style feed of DICE Lite with a short-form video interface that mimics TikTok: full-screen vertical videos, swipe-to-navigate, like and comment interactions, and a bottom navigation bar. The behavioral measurement logic is adapted accordingly (including video play time).

## What researchers can use it for

DICE TikTok is designed for experiments where the stimulus is short-form video content. Some examples:

- **Misinformation research** — expose participants to a feed containing true and false video claims and measure engagement (likes, watch time, comments) by content type
- **Advertising effects** — study how sponsored video content affects attitudes or behavior compared to organic content
- **Algorithmic curation** — compare engagement across different feed orderings or video selection conditions
- **Platform literacy** — examine how people interact with TikTok-style interfaces across age groups or demographics

Like DICE and DICE Lite, this version integrates naturally with survey platforms (Qualtrics, SoSci Survey, etc.) via a redirect at the end of the feed. Participant IDs are passed as URL parameters so you can link feed behavior data to survey responses.

## What it measures

For each participant × video combination, the export contains:

| Field | Description |
|-------|-------------|
| `watch_time_seconds` | Seconds the video was actually playing (paused time excluded) |
| `liked` | Whether the participant liked the video |
| `has_comment` | Whether the participant left a comment |
| `comment` | The comment text |
| `sequence_position` | Position of this video in the feed |

Device information (device type, screen resolution, touch capability) is also recorded at the session level.

## Getting started

### Quickest path: download the `.otreezip`

The releases page includes a ready-to-use `.otreezip` file. If you just want to run the experiment as-is or make small tweaks to the CSV and templates, this is the easiest route — no git required.

To run it locally, download the `.otreezip` file, then:

```bash
otree unzip DICE-tiktok.otreezip
cd DICE-tiktok
otree devserver
```

To deploy it directly to oTreeHub, skip the unzip step and upload the `.otreezip` file as described below.

### Running it locally from source

If you want to modify the code, clone the repository instead:

```bash
git clone https://github.com/Howquez/DICE-tiktok.git
cd DICE-tiktok
pip install -r requirements.txt
otree devserver
```

Then open `http://localhost:8000` in your browser.

### Deploying to oTreeHub

[oTreeHub](https://www.otreehub.com) is the simplest way to host an oTree experiment online — no server setup required. To deploy:

1. If you're working from source, run `otree zip` in the project directory to create a `.otreezip` file. If you downloaded the release, use that file directly.
2. Log in to [otreehub.com](https://www.otreehub.com), create a new project, and upload the `.otreezip` file.
3. Click **Deploy**. oTreeHub provisions a server and gives you a public URL to share with participants.

When you update the project, repeat steps 1–2 and redeploy. Session data can be downloaded from the oTreeHub dashboard as CSV files.

## Adding your own videos

The feed is driven by a CSV file. The `video` column tells the app which video to show for each row — it accepts either a local filename or a full URL.

### Option 1: Local files

Place `.mp4` files in `DICE/static/mp4/` and reference them by filename in the CSV:

```
video
1.mp4
2.mp4
```

This works well for development and for small studies. For oTreeHub deployment, keep in mind that large video files will increase the size of your `.otreezip` and may slow things down. A few short clips (under 30 seconds, under 10 MB each) are fine.

### Option 2: A video hosting service

Upload your videos to a service that provides a direct `.mp4` URL — [Cloudinary](https://cloudinary.com), [Bunny.net](https://bunny.net), or AWS S3 all work. Paste the URL directly into the CSV:

```
video
https://your-cdn.com/videos/clip1.mp4
https://your-cdn.com/videos/clip2.mp4
```

This is the recommended approach for larger studies. Videos load from the CDN rather than your oTreeHub server, which keeps the app fast and the `.otreezip` small. The service just needs to allow cross-origin requests (CORS) — most CDNs do this by default.

### Option 3: Downloading videos for research use

If you want to use existing TikTok or YouTube Shorts videos as stimuli, you can download them with [`yt-dlp`](https://github.com/yt-dlp/yt-dlp), then host them using Option 1 or 2. Bear in mind your institution's policies on using third-party content in research.

Once downloaded, host the files somewhere accessible (your university server, S3, a CDN) and reference them by URL in the CSV. Do not embed YouTube or TikTok links directly — those platforms do not allow it.

## Configuring the feed

The feed is controlled by a CSV file pointed to in `settings.py`:

```python
data_path = "DICE/static/data/sample_videos.csv"
```

You can change this to a local path or a public URL (GitHub raw, Google Drive). The file uses `;` as delimiter by default.

### Required columns

| Column | Description |
|--------|-------------|
| `doc_id` | Unique integer identifier for each video |
| `datetime` | Post timestamp (format: `DD.MM.YY HH:MM`) |
| `text` | Caption text shown below the username |
| `video` | Filename or URL (see above) |
| `likes` | Starting like count |
| `reposts` | Starting share count |
| `replies` | Starting comment count |
| `username` | Display name |
| `handle` | @handle |
| `user_description` | Short profile bio |
| `user_image` | Profile picture URL (leave blank for a generated icon) |
| `user_followers` | Follower count |
| `condition` | Experimental condition label (e.g. `A`, `B`) — used for between-subjects designs |
| `sequence` | Fixed position in the feed (leave blank to randomize) |

The sample file at `DICE/static/data/sample_videos.csv` shows the expected format.

### Between-subjects conditions

If your CSV contains multiple values in the `condition` column, participants are automatically assigned to conditions in rotation. Only the videos matching a participant's condition are shown. Set `condition_col` in `settings.py` if your column has a different name.

## Customizing the experiment

Most things you'd want to change are in `settings.py` or in the HTML templates:

- **Researcher info and consent text** — `DICE/T_Consent.html` and `settings.py` (`full_name`, `eMail`, `study_name`)
- **Briefing instructions** — `DICE/B_Briefing.html`
- **Survey redirect** — set `survey_link` and `url_param` in `settings.py`
- **Hidden form fields are managed manually** — if you add a new Player field in `__init__.py`, you also need to add the corresponding `<input type="hidden">` in `C_Feed.html` and include the field in `get_form_fields()`

## Citation

If you use DICE TikTok in a published study, please cite the original DICE paper:

> Roggenkamp, H., Boegershausen, J., & Hildebrand, C. (2026). DICE: Advancing Social Media Research Through Digital In-Context Experiments. Journal of Marketing. https://doi.org/10.1177/00222429251371702 

or check `Cite this repository` to the right.

## Tested on

Chrome 146 / macOS 26.3.1 (arm64). Designed for mobile browsers (iOS Safari, Android Chrome) as the primary target platform.

---

Questions, bug reports, and pull requests are welcome via [GitHub Issues](https://github.com/Howquez/DICE-tiktok/issues).
