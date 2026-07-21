/** @odoo-module **/

import { dragDropFillState } from "./ktx_drag_drop_fill_state";

/**
 * Floating overlay layer for the selection UI.
 *
 * Everything here is rendered in `position: fixed` divs appended once to
 * `document.body` and repositioned via `getBoundingClientRect()` of the
 * target cells. Nothing is ever injected into a table cell itself - an
 * earlier version added a real `<span>` handle inside the `<td>` and forced
 * `overflow: visible` on it, which broke text truncation/column width on
 * narrow columns as soon as you hovered a cell. Floating overlays sidestep
 * that entirely.
 *
 * The selection can be several disjoint rectangles (Ctrl+click), so boxes
 * are drawn from a small reusable pool.
 */

let els = null;
let boxPool = [];

// The handle is a floating div appended to document.body, not a descendant
// of any <table> - events on it never bubble through a ListRenderer's own
// listeners. Whichever ListRenderer last rendered a selection registers
// here; the handle's own listeners (attached once) delegate to it.
let activeHandlers = null;

export function setActiveHandlers(handlers) {
    activeHandlers = handlers;
}

function ensureEls() {
    if (els) {
        return els;
    }
    const root = document.createElement("div");
    root.className = "o_ddf_overlay_root";

    const boxes = document.createElement("div");
    boxes.className = "o_ddf_boxes";

    const fillPreview = document.createElement("div");
    fillPreview.className = "o_ddf_fill_preview";
    fillPreview.style.display = "none";

    const handle = document.createElement("div");
    handle.className = "o_ddf_handle";
    handle.style.display = "none";
    handle.addEventListener("mousedown", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        activeHandlers?.onMouseDown();
    });
    handle.addEventListener("dblclick", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        activeHandlers?.onDblClick();
    });

    root.append(boxes, fillPreview, handle);
    document.body.appendChild(root);

    els = { root, boxes, fillPreview, handle };
    return els;
}

function applyVars(el) {
    el.style.setProperty("--ddf-color", dragDropFillState.color);
    el.style.setProperty("--ddf-thickness", `${dragDropFillState.thickness}px`);
}

function place(el, rect) {
    el.style.display = "block";
    el.style.left = `${rect.left}px`;
    el.style.top = `${rect.top}px`;
    el.style.width = `${rect.width}px`;
    el.style.height = `${rect.height}px`;
}

/**
 * @param {Array<{left,top,width,height}>} rects  one per selection rectangle
 * @param {{right:number, bottom:number}|null} handlePos  where to pin the fill handle
 */
export function renderSelection(rects, handlePos) {
    const { boxes, handle } = ensureEls();

    while (boxPool.length < rects.length) {
        const box = document.createElement("div");
        box.className = "o_ddf_selection_box";
        boxes.appendChild(box);
        boxPool.push(box);
    }
    boxPool.forEach((box, i) => {
        if (i < rects.length) {
            applyVars(box);
            box.classList.remove("o_ddf_marching");
            place(box, rects[i]);
        } else {
            box.style.display = "none";
            box.classList.remove("o_ddf_marching");
        }
    });

    if (handlePos) {
        applyVars(handle);
        handle.style.display = "block";
        handle.style.left = `${handlePos.right}px`;
        handle.style.top = `${handlePos.bottom}px`;
    } else {
        handle.style.display = "none";
    }
}

export function hideSelection() {
    if (!els) {
        return;
    }
    boxPool.forEach((box) => {
        box.style.display = "none";
        box.classList.remove("o_ddf_marching");
    });
    els.handle.style.display = "none";
    els.fillPreview.style.display = "none";
}

/** Dashed preview of the range a fill-drag is about to write into. */
export function showFillPreview(rect) {
    const { fillPreview } = ensureEls();
    applyVars(fillPreview);
    place(fillPreview, rect);
}

export function hideFillPreview() {
    if (els) {
        els.fillPreview.style.display = "none";
    }
}

/** "Marching ants" copy feedback on every visible selection box. */
export function flashCopied() {
    ensureEls();
    boxPool.forEach((box) => {
        if (box.style.display !== "none") {
            box.classList.add("o_ddf_marching");
        }
    });
}

/** True if el is part of the overlay itself (e.g. the handle) - so the
 * "click outside clears the selection" logic doesn't treat clicking the
 * handle as clicking outside, since the handle lives outside the table. */
export function isOverlayEl(el) {
    return !!els && els.root.contains(el);
}
