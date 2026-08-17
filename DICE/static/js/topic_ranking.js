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

// DOM wiring — only runs in the browser (no-op under Node/require).
if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', function () {
        const list = document.getElementById('ranking-list');
        const hiddenInput = document.getElementById('topic_ranking');
        const status = document.getElementById('ranking-status');
        if (!list || !hiddenInput) return;

        function currentOrder() {
            return Array.from(list.querySelectorAll('.ranking-item')).map(function (li) {
                return li.dataset.topic;
            });
        }

        function render(order) {
            order.forEach(function (topic) {
                const li = list.querySelector('.ranking-item[data-topic="' + topic + '"]');
                if (li) list.appendChild(li);
            });
        }

        list.addEventListener('click', function (e) {
            const btn = e.target.closest('.rank-up, .rank-down');
            if (!btn) return;
            const li = btn.closest('.ranking-item');
            const order = currentOrder();
            const index = order.indexOf(li.dataset.topic);
            const direction = btn.classList.contains('rank-up') ? -1 : 1;
            // render() re-appends every item, which moves (and therefore
            // blurs) whichever one currently has focus -- restore it
            // afterward so keyboard/screen-reader users don't lose their
            // place on every click.
            const focused = document.activeElement;
            const newOrder = moveRankItem(order, index, direction);
            render(newOrder);
            if (focused && list.contains(focused)) focused.focus();
            if (status) {
                const newPosition = newOrder.indexOf(li.dataset.topic) + 1;
                status.textContent = li.dataset.topic + ' moved to position ' + newPosition + ' of ' + newOrder.length;
            }
        });

        document.querySelectorAll('button[type="submit"]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                hiddenInput.value = JSON.stringify(currentOrder());
            });
        });
    });
}
