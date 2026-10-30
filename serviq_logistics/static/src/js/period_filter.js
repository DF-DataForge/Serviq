/** @odoo-module **/

// Shared "Situatie per" helpers: the live view or the last day of one of
// the last completed months, as used by the stock cards (Beschikbare voorraad)
// (the server rebuilds the situation at the end of that day).

export const PERIOD_MONTHS = 24;
const MONTHS_NL = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"];

export function isoDate(d) {
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** Last day of each completed month, most recent first. */
export function monthEndOptions(months = PERIOD_MONTHS) {
    const today = new Date();
    const options = [];
    for (let i = 0; i < months; i++) {
        const monthEnd = new Date(today.getFullYear(), today.getMonth() - i, 0);
        options.push({
            value: isoDate(monthEnd),
            label: `${monthEnd.getDate()} ${MONTHS_NL[monthEnd.getMonth()]} ${monthEnd.getFullYear()}`,
        });
    }
    return options;
}

/** 'YYYY-MM-DD' -> 'DD-MM-YYYY'. */
export function formatDay(iso) {
    if (!iso) return "";
    const [y, m, d] = iso.split("-");
    return `${d}-${m}-${y}`;
}

/** The value one step from `current` ("" = live): delta -1 goes one month
 *  further back, +1 one month closer to today. */
export function stepPeriodValue(current, delta, options = monthEndOptions()) {
    const values = ["", ...options.map((o) => o.value)];
    const idx = values.indexOf(current);
    const next = Math.min(Math.max(idx - delta, 0), values.length - 1);
    return values[next];
}
