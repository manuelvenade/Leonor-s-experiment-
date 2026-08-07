const assert = require('assert');
const { shouldGateNavigation, computeFrictionEntry, getCountdownRemaining } = require('../DICE/static/js/friction.js');

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

// getCountdownRemaining
assert.strictEqual(getCountdownRemaining(1000, 1000, 3), 3);
assert.strictEqual(getCountdownRemaining(1000, 2500, 3), 2);
assert.strictEqual(getCountdownRemaining(1000, 4000, 3), 0);
assert.strictEqual(getCountdownRemaining(1000, 9000, 3), 0);
console.log('PASS: getCountdownRemaining counts down and floors at zero');

// Clock skew: now before gateShownAt (e.g. a backward-jumping system clock)
// must not produce a negative delay or an inflated countdown.
const skewedEntry = computeFrictionEntry(1, 5000, 1000);
assert.strictEqual(skewedEntry.delay_seconds, 0);
assert.strictEqual(getCountdownRemaining(5000, 1000, 3), 3);
console.log('PASS: negative elapsed time (clock skew) clamps to zero');

console.log('All friction.test.js tests passed.');
