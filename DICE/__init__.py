from otree.api import *
import pandas as pd
import numpy as np
import re
import random
import itertools
import urllib.parse
import json

from feed_logic import (
    assign_cycle_pairs, parse_json_field, build_export_row, compute_session_aggregates,
    finalize_player_sequence, select_ranked_topic, parse_topic_ranking, format_topic_ranking,
)


doc = """
Mimic social media feeds with DICE.
"""


class C(BaseConstants):
    NAME_IN_URL = 'DICE'
    PLAYERS_PER_GROUP = None
    NUM_ROUNDS = 1

    CONSENT_TEMPLATE = "DICE/T_Consent.html"
    ITEM_POST = "DICE/T_Item_Post.html"

class Subsession(BaseSubsession):
    feed_conditions = models.StringField(doc='indicates the feed condition a player is randomly assigned to')

class Group(BaseGroup):
    pass


class Player(BasePlayer):
    feed_condition = models.StringField(doc='indicates the feed condition a player is randomly assigned to')
    nav_condition = models.StringField(doc='indicates the navigation condition (normal or friction) a player is randomly assigned to', blank=True)
    preference_alignment = models.StringField(
        doc="'most' or 'least' -- which end of the participant's own topic ranking was actually shown to them.",
        blank=True)
    topic_ranking = models.LongStringField(
        doc='JSON list of topics ranked most-to-least preferred by the participant.',
        blank=True)
    sequence = models.StringField(doc='prints the sequence of posts based on doc_id')

    scroll_sequence = models.LongStringField(doc='tracks the sequence of feed items a participant scrolled through.')
    viewport_data = models.LongStringField(doc='tracks the time feed items were visible in a participants viewport.')
    rowheight_data = models.LongStringField(doc='tracks the height of feed items in pixels.')
    likes_data = models.LongStringField(doc='tracks likes.', blank=True)
    replies_data = models.LongStringField(doc='tracks replies.', blank=True)
    promoted_post_clicks = models.LongStringField(doc='tracks the clicks on sponsored posts.', blank=True)
    friction_data = models.LongStringField(doc='tracks time-to-continue for each gated transition (friction condition only).', blank=True)

    completed_feed = models.BooleanField(doc='whether the participant scrolled through every video before leaving the feed.', blank=True)
    last_position_viewed = models.IntegerField(doc='the last video sequence position the participant reached before submitting.', blank=True)
    session_duration_seconds = models.FloatField(doc='seconds from tapping Start to submitting the feed page.', blank=True)

    touch_capability = models.BooleanField(doc="indicates whether a participant uses a touch device to access survey.",
                                           blank=True)
    device_type = models.StringField(doc="indicates the participant's device type based on screen width.",
                                           blank=True)
    screen_resolution = models.StringField(doc="indicates the participant's screen resolution, i.e., width x height.",
                                           blank=True)


# FUNCTIONS -----
def creating_session(subsession):
    # Load and preprocess data once but shuffle and assign for each player
    df = read_feed(path=subsession.session.config['data_path'], delim=subsession.session.config['delimiter'])
    processed_posts = preprocessing(df, subsession.session.config)

    # Check if the file contains any conditions and assign groups to it
    condition = subsession.session.config['condition_col']
    nav_conditions = subsession.session.config.get('nav_conditions')
    rank_topics = subsession.session.config.get('rank_topics', False)
    condition_present = condition in processed_posts.columns

    if rank_topics and not condition_present:
        # B_TopicRanking depends on subsession.feed_conditions being set,
        # which only happens when condition_present -- fail loudly here
        # instead of every participant hitting AttributeError on their
        # first page load.
        raise ValueError(
            f"rank_topics=True requires a '{condition}' column in the feed data, but none was found."
        )

    if condition_present:
        topics = list(processed_posts[condition].unique())
        subsession.feed_conditions = ', '.join(topics)
        if rank_topics and nav_conditions:
            # Topic itself is chosen later, from each participant's own
            # ranking survey (see B_TopicRanking.before_next_page) — only
            # preference_alignment and nav_condition are balanced up front.
            assignment_cycle = itertools.cycle(assign_cycle_pairs(['most', 'least'], nav_conditions))
        elif rank_topics:
            # rank_topics without nav_conditions: balance preference_alignment
            # alone, mirroring the topic-only fallback below.
            assignment_cycle = itertools.cycle((alignment, None) for alignment in ['most', 'least'])
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


def read_feed(path, delim):
    if re.match(r'^https?://\S+', path):
        if 'github' in path:
            posts = pd.read_csv(path, sep=delim)
        elif 'drive.google.com' in path:
            if '/uc?' in path:
                # Already in the correct format
                posts = pd.read_csv(path, sep=delim)
            else:
                # Convert from /file/d/ format
                file_id = path.split('/')[-2]
                download_url = f'https://drive.google.com/uc?id={file_id}'
                posts = pd.read_csv(download_url, sep=delim)
        else:
            raise ValueError("Unrecognized URL format")
    else:
        posts = pd.read_csv(path, sep=delim)
    return posts


# Check if a string is a URL (starts with http)
def is_url(s):
    return bool(re.match(r'^https?:\/\/', str(s)))


def format_dates(df):
    """Parse and format date columns."""
    df['datetime'] = pd.to_datetime(df['datetime'], errors='coerce')
    mask = df['datetime'].isna()
    if mask.any():
        df.loc[mask, 'datetime'] = pd.to_datetime(
            df.loc[mask, 'datetime'],
            errors='coerce',
            format='%d.%m.%y %H:%M'
        )
    df['date'] = df['datetime'].dt.strftime('%d %b').str.replace(' ', '. ')
    df['date'] = df['date'].str.lstrip('0')
    df['formatted_datetime'] = df['datetime'].dt.strftime('%I:%M %p · %b %d, %Y')
    return df


def highlight_entities(df):
    """Highlight hashtags, cashtags, mentions, and URLs in post text."""
    df['text'] = df['text'].str.replace(r'\B(\#[a-zA-Z0-9_]+\b)',
                                        r'<span class="text-primary">\g<0></span>', regex=True)
    df['text'] = df['text'].str.replace(r'\B(\$[a-zA-Z0-9_\.]+\b)',
                                        r'<span class="text-primary">\g<0></span>', regex=True)
    df['text'] = df['text'].str.replace(r'\B(\@[a-zA-Z0-9_]+\b)',
                                        r'<span class="text-primary">\g<0></span>', regex=True)
    # remove the href below, if you don't want them to leave your page
    df['text'] = df['text'].str.replace(
        r'(http|ftp|https):\/\/([\w_-]+(?:(?:\.[\w_-]+)+))([\w.,@?^=%&:\/~+#-]*[\w@?^=%&\/~+#-])',
        r'<a class="text-primary">\g<0></a>', regex=True)
    return df


def prepare_numeric_fields(df):
    """Convert replies/reposts/likes to int, filling NAs with 0."""
    df['replies'] = df['replies'].fillna(0).astype(int)
    df['reposts'] = df['reposts'].fillna(0).astype(int)
    df['likes'] = df['likes'].fillna(0).astype(int)
    return df


def prepare_media(df):
    """Clean media URLs and set pic_available flag."""
    df['media'] = df['media'].astype(str).str.replace("'|,", '', regex=True) if 'media' in df.columns else ''
    df['pic_available'] = np.where(df['media'].astype(str).str.contains('http', na=False), True, False) if 'media' in df.columns else False
    return df


def prepare_video(df):
    """Prepare video source paths. Handles both URLs and local filenames."""
    if 'video' not in df.columns:
        df['video'] = ''
        df['video_is_url'] = False
        df['video_path'] = ''
        df['video_local_fallback'] = ''
        return df
    df['video'] = df['video'].fillna('').astype(str)
    df['video_is_url'] = df['video'].apply(is_url)
    # For local filenames, prepend 'mp4/' so {{ static i.video_path }} resolves correctly
    df['video_path'] = df.apply(
        lambda row: row['video'] if row['video_is_url'] else (f"mp4/{row['video']}" if row['video'] else ''),
        axis=1
    )
    # Fallback source (same basename under mp4/) so a remote URL that hasn't
    # been uploaded yet, or is briefly unreachable, can still play from a
    # local copy dropped into DICE/static/mp4/ under the same filename.
    df['video_local_fallback'] = df['video'].apply(
        lambda v: f"mp4/{urllib.parse.urlparse(v).path.rsplit('/', 1)[-1]}" if v else ''
    )
    return df


def prepare_ad_flag(df):
    """Ensure is_ad is a clean boolean flag, defaulting missing values to False."""
    if 'is_ad' not in df.columns:
        df['is_ad'] = False
    else:
        df['is_ad'] = df['is_ad'].fillna(0).astype(int).astype(bool)
    return df


def prepare_user_profiles(df):
    """Prepare profile pics, icons, colors, descriptions, followers, and tooltip HTML."""
    df['profile_pic_available'] = df['user_image'].apply(is_url)
    df['icon'] = df['username'].str[:2].str.title()

    # Assign a random color class from a predefined list
    color_classes = ['p1', 'p2', 'p3', 'p4', 'p5', 'p6', 'p7', 'p8']
    df['color_class'] = np.random.choice(color_classes, size=len(df))

    # make sure user descriptions do not entail any '' or "" as this complicates visualization
    # also replace nan with some whitespace
    df['user_description'] = df['user_description'].str.replace("'", '')
    df['user_description'] = df['user_description'].str.replace('"', '')
    df['user_description'] = df['user_description'].fillna(' ')

    # make number of followers a formatted string
    df['user_followers'] = df['user_followers'].map('{:,.0f}'.format).str.replace(',', '.')

    # Build tooltip HTML once per row
    df['tooltip_html'] = (
        "<div class='text-start text-secondary'><b class='text-dark'>" + df['username'] + "</b><br>"
        "@" + df['handle'] + "<br><br>"
        + df['user_description'] + " <br><br><b class='text-dark'>" + df['user_followers'] + "</b> Followers</div>"
    )

    return df


def preprocessing(df, config):
    """Orchestrate all preprocessing steps."""
    df = format_dates(df)
    df = highlight_entities(df)
    df = prepare_numeric_fields(df)
    df = prepare_media(df)
    df = prepare_video(df)
    df = prepare_ad_flag(df)
    df = prepare_user_profiles(df)

    # Check if 'condition_col' is set and not empty, and if it's an existing column in df
    if ('condition_col' in config and
            config['condition_col'] and
            config['condition_col'] in df.columns):
        df.rename(columns={config['condition_col']: 'condition'}, inplace=True)

    return df


def create_redirect(player):
    """Build the survey redirect URL with query parameters."""
    participant_id = player.participant.label or player.participant.code
    params = {player.session.config['url_param']: participant_id}

    completion_code = player.session.vars.get('completion_code')
    if completion_code is not None:
        params['cc'] = completion_code

    if player.feed_condition is not None:
        params['condition'] = player.feed_condition

    return player.session.config['survey_link'] + '?' + urllib.parse.urlencode(params)


# PAGES
class A_Intro(Page):
    form_model = 'player'

    @staticmethod
    def before_next_page(player, timeout_happened):
        # update sequence
        df = player.participant.videos
        posts = df[df['condition'] == player.feed_condition]
        player.sequence = ', '.join(map(str, posts['doc_id'].tolist()))

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

class B_Briefing(Page):
    form_model = 'player'


class C_Feed(Page):
    form_model = 'player'

    @staticmethod
    def get_form_fields(player: Player):
        fields = ['likes_data', 'replies_data', 'promoted_post_clicks', 'friction_data', 'touch_capability',
                   'device_type', 'screen_resolution', 'viewport_data',
                   'completed_feed', 'last_position_viewed', 'session_duration_seconds']
        return fields

    @staticmethod
    def vars_for_template(player: Player):
        label_available = player.participant.label is not None
        # Reset index to ensure consistent ordering (important for generic feed swiper)
        posts_df = player.participant.videos.reset_index(drop=True)
        return dict(
            posts=posts_df.to_dict('index'),
            label_available=label_available,
            nav_condition=player.field_maybe_none('nav_condition') or 'normal',
        )

    @staticmethod
    def before_next_page(player, timeout_happened):
        player.participant.finished = True

        completion_code = player.session.vars.get('completion_code')
        base_url = 'https://app.prolific.com/submissions/complete'
        if player.session.vars.get('prolific_completion_url') is not None:
            player.session.vars['prolific_completion_url'] = (
                f'{base_url}?cc={completion_code}' if completion_code else base_url
            )
        else:
            player.session.vars['prolific_completion_url'] = 'NA'

        if player.id_in_group != 1:
            player.participant.videos = ""


class D_Redirect(Page):

    @staticmethod
    def is_displayed(player):
        return len(player.session.config['survey_link']) > 0

    @staticmethod
    def vars_for_template(player: Player):
        return dict(link=create_redirect(player))

    @staticmethod
    def js_vars(player):
        return dict(
            link=create_redirect(player),
            redirect_delay=player.session.config.get('redirect_delay', 3000),
        )

class D_Debrief(Page):

    @staticmethod
    def is_displayed(player):
        return len(player.session.config['survey_link']) == 0

page_sequence = [A_Intro,
                 B_TopicRanking,
                 B_Briefing,
                 C_Feed,
                 D_Redirect,
                 D_Debrief]


def custom_export(players):
    yield ['session', 'participant_code', 'participant_label', 'participant_in_session',
           'condition', 'nav_condition', 'doc_id', 'sequence_position',
           'watch_time_seconds', 'video_length_seconds', 'watch_percentage',
           'liked', 'has_comment', 'comment',
           'friction_delay_seconds', 'voluntary_hesitation_seconds', 'ad_clicked',
           'completed_feed', 'last_position_viewed',
           'total_watch_time_seconds', 'session_duration_seconds', 'completion_rate']

    for p in players:
        if not p.sequence:
            continue

        doc_ids = [int(x.strip()) for x in p.sequence.split(',')]

        viewport = parse_json_field(p.viewport_data)
        likes    = parse_json_field(p.likes_data)
        replies  = parse_json_field(p.replies_data)
        friction = parse_json_field(p.friction_data)
        promoted = parse_json_field(p.promoted_post_clicks)

        aggregates = compute_session_aggregates(
            viewport,
            p.field_maybe_none('last_position_viewed') or 0,
            len(doc_ids),
            p.field_maybe_none('session_duration_seconds'),
        )

        participant = dict(
            session_code=p.session.code,
            participant_code=p.participant.code,
            participant_label=p.participant.label,
            id_in_group=p.id_in_group,
            feed_condition=p.feed_condition,
            nav_condition=p.field_maybe_none('nav_condition'),
            completed_feed=p.field_maybe_none('completed_feed'),
            last_position_viewed=p.field_maybe_none('last_position_viewed'),
            total_watch_time_seconds=aggregates['total_watch_time_seconds'],
            session_duration_seconds=aggregates['session_duration_seconds'],
            completion_rate=aggregates['completion_rate'],
        )

        for position, doc_id in enumerate(doc_ids, start=1):
            yield build_export_row(participant, doc_id, position, viewport, likes, replies, friction, promoted)
