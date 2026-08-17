const assert = require('assert');
const { moveRankItem } = require('../DICE/static/js/topic_ranking.js');

// moveRankItem
assert.deepStrictEqual(moveRankItem(['SPORT', 'FOOD', 'TRAVEL'], 1, -1), ['FOOD', 'SPORT', 'TRAVEL']);
console.log('PASS: moveRankItem swaps with the previous item when direction is -1');

assert.deepStrictEqual(moveRankItem(['SPORT', 'FOOD', 'TRAVEL'], 1, 1), ['SPORT', 'TRAVEL', 'FOOD']);
console.log('PASS: moveRankItem swaps with the next item when direction is 1');

// Boundary: moving the first item up (direction -1) is a no-op
assert.deepStrictEqual(moveRankItem(['SPORT', 'FOOD', 'TRAVEL'], 0, -1), ['SPORT', 'FOOD', 'TRAVEL']);
console.log('PASS: moveRankItem is a no-op moving the first item up');

// Boundary: moving the last item down (direction 1) is a no-op
assert.deepStrictEqual(moveRankItem(['SPORT', 'FOOD', 'TRAVEL'], 2, 1), ['SPORT', 'FOOD', 'TRAVEL']);
console.log('PASS: moveRankItem is a no-op moving the last item down');

// Does not mutate the input array
const original = ['SPORT', 'FOOD', 'TRAVEL'];
moveRankItem(original, 0, 1);
assert.deepStrictEqual(original, ['SPORT', 'FOOD', 'TRAVEL']);
console.log('PASS: moveRankItem does not mutate its input');

// Out-of-range index (e.g. an unmatched indexOf returning -1) must not
// corrupt the array -- both the index and newIndex bounds are checked.
assert.deepStrictEqual(moveRankItem(['SPORT', 'FOOD', 'TRAVEL'], -1, 1), ['SPORT', 'FOOD', 'TRAVEL']);
console.log('PASS: moveRankItem is a no-op for a negative index');

assert.deepStrictEqual(moveRankItem(['SPORT', 'FOOD', 'TRAVEL'], 3, -1), ['SPORT', 'FOOD', 'TRAVEL']);
console.log('PASS: moveRankItem is a no-op for an index past the end');

console.log('All topic_ranking.test.js tests passed.');
