// Pure ranking-reorder logic — no DOM access, safe to load as a plain
// <script> in the browser and to require() directly under Node for testing.

function moveRankItem(order, index, direction) {
    const newIndex = index + direction;
    if (index < 0 || index >= order.length || newIndex < 0 || newIndex >= order.length) {
        return order.slice();
    }
    const result = order.slice();
    const tmp = result[index];
    result[index] = result[newIndex];
    result[newIndex] = tmp;
    return result;
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { moveRankItem };
}
