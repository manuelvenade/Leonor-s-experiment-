// Pure friction-gate logic — no DOM access, safe to load as a plain
// <script> in the browser (video_feed.js calls these as globals) and to
// require() directly under Node for testing.

function shouldGateNavigation(navCondition) {
    return navCondition === 'friction';
}

function computeFrictionEntry(docId, gateShownAt, now) {
    return { doc_id: docId, delay_seconds: Number(((now - gateShownAt) / 1000).toFixed(3)) };
}

function getCountdownRemaining(gateShownAt, now, countdownSeconds) {
    const elapsed = (now - gateShownAt) / 1000;
    return Math.max(0, Math.ceil(countdownSeconds - elapsed));
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { shouldGateNavigation, computeFrictionEntry, getCountdownRemaining };
}
