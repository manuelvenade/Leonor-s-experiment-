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
const FRICTION_COUNTDOWN_SECONDS = 3;
let pendingNavigation = null; // { index, items }
let gateShownAt = null;
let countdownTimer = null;
const frictionLog = [];
const promotedClicks = [];

// Session-level metrics
let sessionStartedAt = null;
const videoDurations = {}; // { docId: seconds } — each clip's own length, from <video>.duration

// Play-time tracking
const playData = {}; // { docId: { totalSeconds, playStartTime } }

function onVideoPlay(docId) {
    if (!playData[docId]) playData[docId] = { totalSeconds: 0, playStartTime: null };
    playData[docId].playStartTime = Date.now();
}

function onVideoPause(docId) {
    const d = playData[docId];
    if (!d || d.playStartTime === null) return;
    d.totalSeconds += (Date.now() - d.playStartTime) / 1000;
    d.playStartTime = null;
}

function flushPlayData() {
    const now = Date.now();
    Object.keys(playData).forEach(function (docId) {
        const d = playData[docId];
        if (d.playStartTime !== null) {
            d.totalSeconds += (now - d.playStartTime) / 1000;
            d.playStartTime = null;
        }
    });
}

function serializeViewportData() {
    flushPlayData();
    return JSON.stringify(
        Object.keys(playData).map(function (docId) {
            const entry = { doc_id: parseInt(docId), duration: Number(playData[docId].totalSeconds.toFixed(3)) };
            if (videoDurations[docId] !== undefined) {
                entry.video_length_seconds = Number(videoDurations[docId].toFixed(3));
            }
            return entry;
        })
    );
}

// Pause timing when tab is hidden, resume when visible again
document.addEventListener('visibilitychange', function () {
    if (document.hidden) {
        flushPlayData();
    } else {
        // Restart clock for any video that was playing
        document.querySelectorAll('.video-player').forEach(function (v) {
            if (!v.paused) {
                const item = v.closest('.video-item[data-doc-id]');
                if (item) onVideoPlay(parseInt(item.dataset.docId));
            }
        });
    }
});

window.addEventListener('beforeunload', function () {
    document.getElementById('viewport_data').value = serializeViewportData();
});

// IntersectionObserver for video autoplay/pause
const videoObserver = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
        const item = entry.target;
        const video = item.querySelector('.video-player');
        if (!video) return;

        if (entry.isIntersecting) {
            video.muted = !audioUnlocked;
            video.play().catch(function () {
                // Fallback: play muted if browser blocks audio
                video.muted = true;
                video.play().catch(function () {});
            });
        } else {
            video.pause();
        }
    });
}, { threshold: 0.6 });

// Tap-to-start button: unlock audio and reveal feed
document.getElementById('startBtn').addEventListener('click', function () {
    audioUnlocked = true;
    sessionStartedAt = Date.now();

    document.getElementById('loadingScreen').classList.add('d-none');
    const mainContent = document.getElementById('mainContent');
    mainContent.style.display = '';

    // Observe all video items (data-doc-id excludes end-card)
    document.querySelectorAll('.video-item[data-doc-id]').forEach(function (item) {
        videoObserver.observe(item);
        const docId = parseInt(item.dataset.docId);
        const video = item.querySelector('.video-player');
        if (video) {
            video.addEventListener('play', function () { onVideoPlay(docId); });
            video.addEventListener('pause', function () { onVideoPause(docId); });
            video.addEventListener('ended', function () { onVideoPause(docId); });
            video.addEventListener('loadedmetadata', function () {
                if (isFinite(video.duration)) {
                    videoDurations[docId] = video.duration;
                }
            });
        }
    });

    // Lock scroll to one video at a time
    const feed = document.getElementById('video-feed');

    // Block native wheel/trackpad scroll — keyboard-only on desktop
    document.addEventListener('wheel', function (e) {
        e.preventDefault();
    }, { passive: false });

    // Keyboard: arrow keys and Page Up/Down
    document.addEventListener('keydown', function (e) {
        if (e.key === 'ArrowDown' || e.key === 'PageDown') {
            e.preventDefault();
            navigateTo(currentIndex + 1, document.querySelectorAll('.video-item'));
        } else if (e.key === 'ArrowUp' || e.key === 'PageUp') {
            e.preventDefault();
            navigateTo(currentIndex - 1, document.querySelectorAll('.video-item'));
        }
    });

    // Touch: keep on feed element (touch is always over the column on mobile)
    feed.addEventListener('touchstart', function (e) {
        touchStartY = e.touches[0].clientY;
    }, { passive: true });

    feed.addEventListener('touchmove', function (e) {
        e.preventDefault();
    }, { passive: false });

    feed.addEventListener('touchend', function (e) {
        const delta = touchStartY - e.changedTouches[0].clientY;
        if (Math.abs(delta) < 30) return; // ignore micro-swipes
        const items = document.querySelectorAll('.video-item');
        navigateTo(delta > 0 ? currentIndex + 1 : currentIndex - 1, items);
    }, { passive: true });

    // Attempt to play first video with audio
    const firstItem = document.querySelector('.video-item[data-doc-id]');
    if (firstItem) {
        const video = firstItem.querySelector('.video-player');
        if (video) {
            video.muted = false;
            video.play().catch(function () {
                video.muted = true;
                video.play().catch(function () {});
            });
        }
    }
});

document.addEventListener('DOMContentLoaded', function () {

    // Mute/unmute toggle
    const muteBtn = document.getElementById('mute-btn');
    if (muteBtn) {
        muteBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            audioUnlocked = !audioUnlocked;
            const icon = muteBtn.querySelector('i');
            icon.className = audioUnlocked ? 'bi bi-volume-up-fill' : 'bi bi-volume-mute-fill';
            // Apply to currently active video
            document.querySelectorAll('.video-player').forEach(function (v) {
                if (!v.paused) v.muted = !audioUnlocked;
            });
        });
    }

    // Like button toggle
    document.querySelectorAll('.like-button').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            e.stopPropagation();
            const icon = btn.querySelector('.like-icon');
            const countEl = btn.querySelector('.like-count');
            let count = parseInt(countEl.textContent) || 0;

            const isAbbreviated = /[KM]/.test(countEl.textContent);
            if (icon.classList.contains('bi-heart')) {
                icon.classList.replace('bi-heart', 'bi-heart-fill');
                icon.style.color = '#fe2c55';
                if (!isAbbreviated) countEl.textContent = count + 1;
            } else {
                icon.classList.replace('bi-heart-fill', 'bi-heart');
                icon.style.color = '';
                if (!isAbbreviated) countEl.textContent = Math.max(0, count - 1);
            }
        });
    });

    // Comment button: open drawer
    document.querySelectorAll('.comment-button').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            e.stopPropagation();
            openComments(parseInt(btn.dataset.docId));
        });
    });

    // Tap area: play/pause toggle
    document.querySelectorAll('.tap-area').forEach(function (area) {
        area.addEventListener('click', function () {
            const item = area.closest('.video-item');
            const video = item.querySelector('.video-player');
            const indicator = item.querySelector('.play-indicator');

            if (video.paused) {
                video.play().catch(function () {});
                showIndicator(indicator, 'bi-play-fill');
            } else {
                video.pause();
                showIndicator(indicator, 'bi-pause-fill');
            }
        });
    });

    // Comment drawer: post comment
    const postCommentBtn = document.getElementById('post-comment');
    if (postCommentBtn) {
        postCommentBtn.addEventListener('click', function () {
            submitComment();
        });
    }

    // Friction gate: Continue button
    const frictionContinueBtn = document.getElementById('frictionContinueBtn');
    if (frictionContinueBtn) {
        frictionContinueBtn.addEventListener('click', function () {
            if (!pendingNavigation) return;

            const targetItem = pendingNavigation.items[pendingNavigation.index];
            const docId = targetItem && targetItem.dataset.docId ? parseInt(targetItem.dataset.docId) : null;
            if (docId !== null) {
                // Keep only the first gate encounter per video — a participant who
                // swipes back and forth shouldn't have an earlier (often more
                // representative) delay silently overwritten by a later one.
                const alreadyLogged = frictionLog.some(function (entry) { return entry.doc_id === docId; });
                if (!alreadyLogged) {
                    frictionLog.push(computeFrictionEntry(docId, gateShownAt, Date.now(), FRICTION_COUNTDOWN_SECONDS));
                }
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

    // Comment input: submit on Enter (without Shift)
    const commentInput = document.getElementById('comment-input');
    if (commentInput) {
        commentInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                submitComment();
            }
        });
    }

    // Close comments
    const closeBtn = document.getElementById('close-comments');
    if (closeBtn) closeBtn.addEventListener('click', closeComments);

    const overlay = document.getElementById('comment-overlay');
    if (overlay) overlay.addEventListener('click', closeComments);

    // Submit buttons: collect all data before form submission
    document.querySelectorAll('button[type="submit"]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            collectAllData();
        });
    });

    // Bootstrap popovers (for profile nav button)
    document.querySelectorAll('[data-bs-toggle="popover"]').forEach(function (el) {
        new bootstrap.Popover(el);
    });

});

function navigateTo(index, items) {
    if (isNavigating) return;
    if (index < 0 || index >= items.length) return;

    if (shouldGateNavigation(navCondition)) {
        if (pendingNavigation) return; // gate already showing — ignore repeat triggers (e.g. held arrow keys)
        pendingNavigation = { index: index, items: items };
        gateShownAt = Date.now();
        document.getElementById('friction-gate').classList.remove('d-none');
        startFrictionCountdown();
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

function startFrictionCountdown() {
    const countdownEl = document.getElementById('friction-countdown');
    const continueBtn = document.getElementById('frictionContinueBtn');
    continueBtn.disabled = true;

    clearInterval(countdownTimer);

    function tick() {
        const remaining = getCountdownRemaining(gateShownAt, Date.now(), FRICTION_COUNTDOWN_SECONDS);
        countdownEl.textContent = remaining;
        if (remaining <= 0) {
            clearInterval(countdownTimer);
            countdownTimer = null;
            continueBtn.disabled = false;
        }
    }

    tick();
    countdownTimer = setInterval(tick, 100);
}

function openComments(docId) {
    activeCommentDocId = docId;

    // Restore any previously typed comment
    const input = document.getElementById('comment-input');
    if (input) input.value = commentData[docId] ? commentData[docId].text : '';

    document.getElementById('comment-drawer').classList.add('open');
    document.getElementById('comment-overlay').classList.add('visible');

    // Focus the input
    setTimeout(function () {
        if (input) input.focus();
    }, 300);

    // Pause current video while commenting
    document.querySelectorAll('.video-player').forEach(function (v) {
        if (!v.paused) v.pause();
    });
}

function closeComments() {
    // Save partial input if any text typed
    if (activeCommentDocId !== null) {
        const input = document.getElementById('comment-input');
        const text = input ? input.value.trim() : '';
        if (text && !commentData[activeCommentDocId]) {
            commentData[activeCommentDocId] = { text: text, hasComment: false };
        }
    }

    document.getElementById('comment-drawer').classList.remove('open');
    document.getElementById('comment-overlay').classList.remove('visible');
    activeCommentDocId = null;

    // Resume the video currently centered in view
    document.querySelectorAll('.video-item[data-doc-id]').forEach(function (item) {
        const rect = item.getBoundingClientRect();
        if (rect.top >= -50 && rect.top < window.innerHeight * 0.4) {
            const video = item.querySelector('.video-player');
            if (video && video.paused) {
                video.muted = !audioUnlocked;
                video.play().catch(function () {});
            }
        }
    });
}

function submitComment() {
    const input = document.getElementById('comment-input');
    const text = input ? input.value.trim() : '';
    if (!text || activeCommentDocId === null) return;

    commentData[activeCommentDocId] = { text: text, hasComment: true };

    // Update comment count in sidebar
    const countEl = document.getElementById('reply_count_' + activeCommentDocId);
    if (countEl) {
        const c = parseInt(countEl.textContent) || 0;
        countEl.textContent = c + 1;
    }

    // Highlight comment icon
    const commentBtn = document.getElementById('comment_button_' + activeCommentDocId);
    if (commentBtn) {
        const icon = commentBtn.querySelector('.bi-chat-fill');
        if (icon) icon.style.color = '#fe2c55';
    }

    // Add comment to list in drawer
    const list = document.getElementById('comment-list');
    if (list) {
        const emptyState = list.querySelector('.comment-empty-state');
        if (emptyState) emptyState.remove();

        const comment = document.createElement('div');
        comment.className = 'comment-entry';
        comment.innerHTML = '<span class="comment-author">You</span><span class="comment-text">' + escapeHtml(text) + '</span>';
        list.appendChild(comment);
    }

    if (input) input.value = '';
    closeComments();
}

function showIndicator(el, iconClass) {
    if (!el) return;
    el.innerHTML = '<i class="bi ' + iconClass + '"></i>';
    el.classList.add('show');
    setTimeout(function () { el.classList.remove('show'); }, 600);
}

function escapeHtml(str) {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function collectAllData() {
    // Likes
    const likes = [];
    document.querySelectorAll('.like-button').forEach(function (btn) {
        const docId = parseInt(btn.id.replace('like_button_', ''));
        const icon = btn.querySelector('.like-icon');
        likes.push({ doc_id: docId, liked: icon.classList.contains('bi-heart-fill') });
    });

    // Replies/comments
    const replies = [];
    document.querySelectorAll('.video-item[data-doc-id]').forEach(function (item) {
        const docId = parseInt(item.dataset.docId);
        const data = commentData[docId];
        replies.push({
            doc_id: docId,
            reply: data ? data.text : '',
            hasReply: data ? data.hasComment : false
        });
    });

    document.getElementById('likes_data').value = JSON.stringify(likes);
    document.getElementById('replies_data').value = JSON.stringify(replies);
    document.getElementById('promoted_post_clicks').value = JSON.stringify(promotedClicks);
    document.getElementById('friction_data').value = JSON.stringify(frictionLog);
    document.getElementById('viewport_data').value = serializeViewportData();

    // Session-level metrics
    const totalVideos = document.querySelectorAll('.video-item[data-doc-id]').length;
    const completedFeed = currentIndex >= totalVideos;
    const lastPositionViewed = Math.min(currentIndex + 1, totalVideos);
    document.getElementById('completed_feed').value = completedFeed;
    document.getElementById('last_position_viewed').value = lastPositionViewed;
    document.getElementById('session_duration_seconds').value =
        sessionStartedAt !== null ? ((Date.now() - sessionStartedAt) / 1000).toFixed(3) : '';

    console.log('Data collected. Likes:', likes.length, 'Replies:', replies.length);
}
