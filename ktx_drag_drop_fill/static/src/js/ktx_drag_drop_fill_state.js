/** @odoo-module **/

import { reactive } from "@odoo/owl";

const KEYS = {
    enabled: "ktx_drag_drop_fill_enabled",
    color: "ktx_drag_drop_fill_color",
    thickness: "ktx_drag_drop_fill_thickness",
    cursor: "ktx_drag_drop_fill_cursor",
    activation: "ktx_drag_drop_fill_activation",
};

const DEFAULTS = {
    enabled: false,
    color: "#1a73e8",
    thickness: 2,
    // CSS `cursor: cell` is the browser's own "select a table cell" cursor.
    cursor: "cell",
    // "hold"  -> a quick click stays native Odoo; press-and-hold (or drag)
    //            starts the spreadsheet selection. This is the default so
    //            the module never hijacks a normal single click.
    // "click" -> a single click immediately starts the selection.
    activation: "hold",
};

export const CURSOR_OPTIONS = ["cell", "crosshair", "copy", "pointer", "grab"];
export const ACTIVATION_OPTIONS = [
    { value: "hold", label: "Clic sostenido" },
    { value: "click", label: "Un clic" },
];

function loadBool(key, fallback) {
    try {
        const raw = localStorage.getItem(key);
        return raw === null ? fallback : raw === "1";
    } catch {
        return fallback;
    }
}

function loadStr(key, fallback) {
    try {
        return localStorage.getItem(key) || fallback;
    } catch {
        return fallback;
    }
}

function loadNum(key, fallback) {
    try {
        const raw = localStorage.getItem(key);
        const n = raw === null ? NaN : Number(raw);
        return Number.isFinite(n) ? n : fallback;
    } catch {
        return fallback;
    }
}

function persist(key, value) {
    try {
        localStorage.setItem(key, String(value));
    } catch {
        // localStorage unavailable (e.g. private browsing) - state still
        // applies in-memory for the current tab.
    }
}

/**
 * Single reactive object shared between every patched ListRenderer and the
 * systray toggle/settings popover. Persisted in localStorage so the user's
 * choices survive page reloads/new tabs, but are per-browser (not synced
 * server side) so they can be flipped instantly with zero network round-trip.
 */
export const dragDropFillState = reactive({
    enabled: loadBool(KEYS.enabled, DEFAULTS.enabled),
    color: loadStr(KEYS.color, DEFAULTS.color),
    thickness: loadNum(KEYS.thickness, DEFAULTS.thickness),
    cursor: loadStr(KEYS.cursor, DEFAULTS.cursor),
    activation: loadStr(KEYS.activation, DEFAULTS.activation),
});

export function toggleDragDropFill() {
    dragDropFillState.enabled = !dragDropFillState.enabled;
    persist(KEYS.enabled, dragDropFillState.enabled ? "1" : "0");
}

export function setDragDropFillOption(key, value) {
    if (!(key in KEYS)) {
        return;
    }
    dragDropFillState[key] = value;
    persist(KEYS[key], value);
}
