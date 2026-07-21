/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";
import { ListController } from "@web/views/list/list_controller";
import { useEffect, useExternalListener } from "@odoo/owl";
import { dragDropFillState } from "./ktx_drag_drop_fill_state";
import { extractCellText } from "./ktx_drag_drop_fill_util";
import {
    renderSelection,
    hideSelection,
    showFillPreview,
    hideFillPreview,
    flashCopied,
    setActiveHandlers,
    isOverlayEl,
} from "./ktx_drag_drop_fill_overlay";

const NUMERIC_TYPES = ["integer", "float", "monetary"];
const DRAG_THRESHOLD = 4; // px before a press is treated as a drag
const HOLD_MS = 200; // press-and-hold duration that starts a selection
const DBLCLICK_MS = 260; // window to disambiguate single vs double click

// Top-level document lists that this module forces editable (see
// views/account_move_views.xml). On these, a single click must still open
// the record's form (draft or not), a double click edits inline (drafts
// only), and the spreadsheet gestures layer on top - so navigation isn't
// lost the way it is on a plain editable list.
const DOCUMENT_MODELS = ["account.move"];

function rafThrottle(fn) {
    let scheduled = false;
    let lastArgs = null;
    return (...args) => {
        lastArgs = args;
        if (scheduled) {
            return;
        }
        scheduled = true;
        requestAnimationFrame(() => {
            scheduled = false;
            fn(...lastArgs);
        });
    };
}

/**
 * Excel-like cell selection + fill handle for editable list / one2many
 * views. Enabled/configured entirely from the systray toggle - no per-view
 * setup. See the module description for the full interaction model.
 */
patch(ListRenderer.prototype, {
    setup() {
        super.setup();
        this._ktxDdf = { sel: null };

        useEffect(
            (table) => {
                if (table) {
                    this._ktxDdfBind(table);
                }
            },
            () => [this.tableRef?.el]
        );

        // Clearing the selection when clicking outside lives on `document`,
        // so it must be tied to the component lifecycle (auto-removed on
        // unmount) to avoid leaking a listener per list navigation.
        useExternalListener(document, "mousedown", (ev) => this._ktxDdfOnDocMouseDown(ev), { capture: true });
    },

    get _ktxDdfActive() {
        const list = this.props.list;
        if (!list) {
            return false;
        }
        return !!(list.editable || this.props.editable);
    },

    _ktxDdfIsDocList() {
        return DOCUMENT_MODELS.includes(this.props.list?.resModel);
    },

    /** True when this list is a one2many/many2many sub-list inside a form.
     * There a plain click already enters edit, so we mirror the selection
     * on click instead of requiring a press-and-hold. */
    _ktxDdfInX2Many() {
        return !!this.tableRef?.el?.closest(".o_field_x2many");
    },

    // ── Grid snapshot & coordinate helpers ───────────────────────────────

    _ktxDdfFlatten(list) {
        if (list && list.groups && list.groups.length) {
            let out = [];
            for (const group of list.groups) {
                if (group.list && !group.isFolded) {
                    out = out.concat(this._ktxDdfFlatten(group.list));
                }
            }
            return out;
        }
        return (list && list.records) || [];
    },

    _ktxDdfFieldType(fieldName) {
        try {
            return this.props.list.fields?.[fieldName]?.type || null;
        } catch {
            return null;
        }
    },

    /** Snapshot of rows/records/columns, taken once per gesture (not per mouse-move). */
    _ktxDdfGrid(table) {
        const rows = Array.from(table.querySelectorAll("tbody tr.o_data_row"));
        const records = this._ktxDdfFlatten(this.props.list);
        if (records.length !== rows.length) {
            return null; // mapping unreliable here - bail out safely
        }
        const columns = Array.from(table.querySelectorAll("thead th[data-name]")).map((th) => th.dataset.name);
        if (!columns.length) {
            return null;
        }
        return { rows, records, columns };
    },

    _ktxDdfCellRC(grid, cell) {
        const r = grid.rows.indexOf(cell.closest("tr.o_data_row"));
        const c = grid.columns.indexOf(cell.getAttribute("name"));
        return r === -1 || c === -1 ? null : { r, c };
    },

    _ktxDdfCellAt(grid, r, c) {
        const fieldName = grid.columns[c];
        if (!fieldName || !grid.rows[r]) {
            return null;
        }
        return grid.rows[r].querySelector(`td[name="${CSS.escape(fieldName)}"]`);
    },

    _ktxDdfNorm(a, b) {
        return { r1: Math.min(a.r, b.r), c1: Math.min(a.c, b.c), r2: Math.max(a.r, b.r), c2: Math.max(a.c, b.c) };
    },

    /** The rectangle currently being formed (anchor..focus). */
    _ktxDdfActiveRect(sel) {
        return this._ktxDdfNorm(sel.anchor, sel.focus);
    },

    // ── Binding ──────────────────────────────────────────────────────────

    _ktxDdfBind(table) {
        if (table._ktxDdfBound) {
            return;
        }
        table._ktxDdfBound = true;

        table.addEventListener("mousedown", (ev) => this._ktxDdfOnMouseDown(ev, table), true);
        table.addEventListener(
            "click",
            (ev) => {
                if (this._ktxDdf.suppressNextClick) {
                    this._ktxDdf.suppressNextClick = false;
                    ev.preventDefault();
                    ev.stopPropagation();
                    ev.stopImmediatePropagation();
                }
            },
            true
        );
        table.addEventListener("dblclick", (ev) => this._ktxDdfOnDblClick(ev, table), true);
        table.addEventListener("keydown", (ev) => this._ktxDdfOnKeyDown(ev));
    },

    _ktxDdfOnDocMouseDown(ev) {
        const table = this.tableRef?.el;
        if (!this._ktxDdf.sel || !table || table.contains(ev.target) || isOverlayEl(ev.target)) {
            return;
        }
        this._ktxDdf.sel = null;
        hideSelection();
    },

    // ── Mouse down: click / hold / drag / modifier disambiguation ────────

    _ktxDdfOnMouseDown(ev, table) {
        if (ev.button !== 0 || !this._ktxDdfActive) {
            return;
        }
        // Native record selection (left checkboxes) active: let Odoo handle
        // row clicks as selection toggles, exactly like before this module.
        const nativeSel = this.props.list.selection;
        if (nativeSel && nativeSel.length) {
            return;
        }

        // A click on a hover copy button (see ktx_drag_drop_fill_copy.js) is
        // its own action - never treat it as a cell gesture.
        if (ev.target.closest(".o_ddf_copy_btn")) {
            return;
        }
        const cell = ev.target.closest("td.o_data_cell[name]");
        if (!cell || cell.classList.contains("o_handle_cell")) {
            return;
        }
        const grid = this._ktxDdfGrid(table);
        if (!grid) {
            return;
        }
        const rc = this._ktxDdfCellRC(grid, cell);
        if (!rc) {
            return;
        }

        const st = this._ktxDdf;
        st.grid = grid;
        clearTimeout(st.docClickTimer);
        const enabled = dragDropFillState.enabled;
        const docList = this._ktxDdfIsDocList();
        const inX2Many = this._ktxDdfInX2Many();

        // Non-document editable list with the feature off: never interfere.
        if (!enabled && !docList) {
            return;
        }

        // Ctrl/Shift multi-select (feature on). Readonly cells are allowed:
        // they can be selected (and copied) even if they can't be written.
        // Beginning a drag lets Ctrl+drag grow a new disjoint block and
        // Shift+drag keep extending the active one, like a spreadsheet.
        if (enabled && (ev.ctrlKey || ev.metaKey || ev.shiftKey)) {
            ev.preventDefault();
            ev.stopPropagation();
            this._ktxDdfModifierClick(ev.shiftKey ? "shift" : "ctrl", rc);
            st.suppressNextClick = true;
            this._ktxDdfBeginDrag(st);
            return;
        }

        // One2many / inline-editable sub-list inside a form: a plain click
        // both edits (native) and shows the selection border + handle;
        // dragging across cells extends the selection.
        if (enabled && inX2Many) {
            this._ktxDdfStartSelect(rc);
            requestAnimationFrame(() => this._ktxDdfRenderSelection());
            this._ktxDdfBeginSoftDrag(ev);
            return; // no preventDefault: native edit still happens on a plain click
        }

        // "Un clic" mode on a top-level list: select immediately.
        if (enabled && dragDropFillState.activation === "click") {
            ev.preventDefault();
            ev.stopPropagation();
            st.suppressNextClick = true;
            this._ktxDdfStartSelect(rc);
            this._ktxDdfBeginDrag(st);
            return;
        }

        // Otherwise: a pending gesture resolved on move / hold-timer / up.
        // We deliberately do NOT preventDefault yet, so a plain quick click
        // stays native.
        st.pending = { rc, docList, enabled, startX: ev.clientX, startY: ev.clientY, committed: null, moved: false };
        const onMove = rafThrottle((e) => this._ktxDdfPendingMove(e));
        const onUp = () => {
            clearTimeout(st.pending?.timer);
            document.removeEventListener("mousemove", onMove);
            document.removeEventListener("mouseup", onUp);
            this._ktxDdfPendingUp();
        };
        document.addEventListener("mousemove", onMove);
        document.addEventListener("mouseup", onUp);
        if (enabled && dragDropFillState.activation === "hold") {
            st.pending.timer = setTimeout(() => this._ktxDdfPendingHold(), HOLD_MS);
        }
    },

    _ktxDdfPendingMove(e) {
        const st = this._ktxDdf;
        const p = st.pending;
        if (!p) {
            return;
        }
        if (!p.committed) {
            const dx = Math.abs(e.clientX - p.startX);
            const dy = Math.abs(e.clientY - p.startY);
            if (dx < DRAG_THRESHOLD && dy < DRAG_THRESHOLD) {
                return;
            }
            p.moved = true;
            if (p.enabled) {
                p.committed = "select";
                clearTimeout(p.timer);
                document.body.classList.add("o_ddf_dragging");
                document.body.style.setProperty("--ddf-cursor", dragDropFillState.cursor);
                this._ktxDdfStartSelect(p.rc);
            } else {
                p.committed = "native"; // module off (document list) - leave the drag alone
            }
        }
        if (p.committed === "select") {
            const el = document.elementFromPoint(e.clientX, e.clientY);
            const cell = el && el.closest("td.o_data_cell[name]");
            const rc = cell && this._ktxDdfCellRC(st.grid, cell);
            if (rc) {
                st.sel.focus = rc;
                this._ktxDdfRenderSelection();
            }
        }
    },

    _ktxDdfPendingHold() {
        const st = this._ktxDdf;
        const p = st.pending;
        if (!p || p.committed) {
            return;
        }
        p.committed = "select";
        document.body.classList.add("o_ddf_dragging");
        document.body.style.setProperty("--ddf-cursor", dragDropFillState.cursor);
        this._ktxDdfStartSelect(p.rc);
    },

    _ktxDdfPendingUp() {
        const st = this._ktxDdf;
        const p = st.pending;
        st.pending = null;
        if (!p) {
            return;
        }
        document.body.classList.remove("o_ddf_dragging");

        if (p.committed === "select") {
            st.suppressNextClick = true;
            return;
        }
        if (p.moved) {
            return; // a native/readonly drag - don't turn it into a click action
        }
        // Quick single click.
        if (p.docList) {
            const rec = st.grid.records[p.rc.r];
            if (!rec) {
                return;
            }
            st.suppressNextClick = true;
            st.sel = null;
            hideSelection();
            if (!p.enabled) {
                this.props.openRecord(rec); // module off: behave like the original non-editable list
            } else {
                // Delay so a double click (edit) can pre-empt the open.
                st.docClickTimer = setTimeout(() => this.props.openRecord(rec), DBLCLICK_MS);
            }
        }
        // Non-document quick click: do nothing, let Odoo edit natively.
    },

    // ── Selection model ──────────────────────────────────────────────────

    _ktxDdfStartSelect(rc) {
        this._ktxDdf.sel = { ranges: [], anchor: rc, focus: rc };
        this._ktxDdfRenderSelection();
    },

    _ktxDdfBeginDrag(st) {
        const onMove = rafThrottle((e) => {
            const el = document.elementFromPoint(e.clientX, e.clientY);
            const cell = el && el.closest("td.o_data_cell[name]");
            const rc = cell && this._ktxDdfCellRC(st.grid, cell);
            if (rc && st.sel) {
                st.sel.focus = rc;
                this._ktxDdfRenderSelection();
            }
        });
        const onUp = () => {
            document.removeEventListener("mousemove", onMove);
            document.removeEventListener("mouseup", onUp);
            document.body.classList.remove("o_ddf_dragging");
        };
        document.body.classList.add("o_ddf_dragging");
        document.body.style.setProperty("--ddf-cursor", dragDropFillState.cursor);
        document.addEventListener("mousemove", onMove);
        document.addEventListener("mouseup", onUp);
    },

    /** Drag-to-extend for one2many lists: we never preventDefault the
     * initial press (so a plain click still edits), and only start ranging
     * once the pointer crosses into a different cell. */
    _ktxDdfBeginSoftDrag(ev) {
        const st = this._ktxDdf;
        const x0 = ev.clientX;
        const y0 = ev.clientY;
        let ranging = false;
        const onMove = rafThrottle((e) => {
            if (!ranging) {
                if (Math.abs(e.clientX - x0) < DRAG_THRESHOLD && Math.abs(e.clientY - y0) < DRAG_THRESHOLD) {
                    return;
                }
                ranging = true;
                document.body.classList.add("o_ddf_dragging");
                document.body.style.setProperty("--ddf-cursor", dragDropFillState.cursor);
                window.getSelection?.()?.removeAllRanges?.();
            }
            const el = document.elementFromPoint(e.clientX, e.clientY);
            const cell = el && el.closest("td.o_data_cell[name]");
            const rc = cell && this._ktxDdfCellRC(st.grid, cell);
            if (rc && st.sel) {
                st.sel.focus = rc;
                this._ktxDdfRenderSelection();
            }
        });
        const onUp = () => {
            document.removeEventListener("mousemove", onMove);
            document.removeEventListener("mouseup", onUp);
            document.body.classList.remove("o_ddf_dragging");
            if (ranging) {
                st.suppressNextClick = true; // a range drag shouldn't also open/edit
            }
        };
        document.addEventListener("mousemove", onMove);
        document.addEventListener("mouseup", onUp);
    },

    _ktxDdfModifierClick(kind, rc) {
        const st = this._ktxDdf;
        if (!st.sel) {
            this._ktxDdfStartSelect(rc);
            return;
        }
        if (kind === "shift") {
            st.sel.focus = rc; // extend the active rectangle from the anchor
        } else {
            // Ctrl: commit the current rectangle and start a new disjoint one.
            st.sel.ranges.push(this._ktxDdfActiveRect(st.sel));
            st.sel.anchor = rc;
            st.sel.focus = rc;
        }
        this._ktxDdfRenderSelection();
    },

    _ktxDdfAllRects(sel) {
        return [...sel.ranges, this._ktxDdfActiveRect(sel)];
    },

    _ktxDdfPixelRect(rect) {
        const tl = this._ktxDdfCellAt(this._ktxDdf.grid, rect.r1, rect.c1);
        const br = this._ktxDdfCellAt(this._ktxDdf.grid, rect.r2, rect.c2);
        if (!tl || !br) {
            return null;
        }
        const a = tl.getBoundingClientRect();
        const b = br.getBoundingClientRect();
        const left = Math.min(a.left, b.left);
        const top = Math.min(a.top, b.top);
        const right = Math.max(a.right, b.right);
        const bottom = Math.max(a.bottom, b.bottom);
        return { left, top, right, bottom, width: right - left, height: bottom - top };
    },

    _ktxDdfRenderSelection() {
        const st = this._ktxDdf;
        if (!st.sel) {
            hideSelection();
            return;
        }
        const pixelRects = this._ktxDdfAllRects(st.sel)
            .map((r) => this._ktxDdfPixelRect(r))
            .filter(Boolean);
        const active = this._ktxDdfPixelRect(this._ktxDdfActiveRect(st.sel));
        renderSelection(pixelRects, active ? { right: active.right, bottom: active.bottom } : null);
        setActiveHandlers({
            onMouseDown: () => this._ktxDdfStartFillDrag(),
            onDblClick: () => this._ktxDdfFillToLastRow(),
        });
    },

    // ── Copy ─────────────────────────────────────────────────────────────

    _ktxDdfOnKeyDown(ev) {
        const st = this._ktxDdf;
        if (ev.key === "Escape" && st.sel) {
            st.sel = null;
            hideSelection();
            return;
        }
        if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "c" && st.sel && st.grid) {
            this._ktxDdfCopySelection();
        }
    },

    _ktxDdfCopySelection() {
        const st = this._ktxDdf;
        const rects = this._ktxDdfAllRects(st.sel);
        const bbox = {
            r1: Math.min(...rects.map((r) => r.r1)),
            c1: Math.min(...rects.map((r) => r.c1)),
            r2: Math.max(...rects.map((r) => r.r2)),
            c2: Math.max(...rects.map((r) => r.c2)),
        };
        const inSel = (r, c) => rects.some((rect) => r >= rect.r1 && r <= rect.r2 && c >= rect.c1 && c <= rect.c2);

        const lines = [];
        for (let r = bbox.r1; r <= bbox.r2; r++) {
            const cols = [];
            for (let c = bbox.c1; c <= bbox.c2; c++) {
                const cell = inSel(r, c) ? this._ktxDdfCellAt(st.grid, r, c) : null;
                cols.push(cell ? extractCellText(cell) : "");
            }
            lines.push(cols.join("\t"));
        }
        const text = lines.join("\n");
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(text).catch(() => {});
        }
        flashCopied();
    },

    // ── Double click: edit (documents) ──────────────────────────────────

    _ktxDdfOnDblClick(ev, table) {
        if (isOverlayEl(ev.target)) {
            return; // the handle's own dblclick is wired in the overlay
        }
        if (!this._ktxDdfActive || !this._ktxDdfIsDocList()) {
            return; // one2many / normal lists: native double-click
        }
        const cell = ev.target.closest("td.o_data_cell[name]");
        if (!cell) {
            return;
        }
        clearTimeout(this._ktxDdf.docClickTimer);
        ev.preventDefault();
        ev.stopPropagation();

        const grid = this._ktxDdfGrid(table);
        const rc = grid && this._ktxDdfCellRC(grid, cell);
        const rec = rc && grid.records[rc.r];
        if (!rec) {
            return;
        }
        const draft = rec.data?.state === "draft";
        if (dragDropFillState.enabled && draft) {
            // Draft: select the cell (border + handle) and, if it's
            // writable, enter inline edit. Never navigate away.
            this._ktxDdf.grid = grid;
            this._ktxDdfStartSelect(rc);
            if (!cell.classList.contains("o_readonly_modifier")) {
                this._ktxDdfEditCell(rec, cell.getAttribute("name"));
            }
        } else {
            this.props.openRecord(rec);
        }
    },

    async _ktxDdfEditCell(record, fieldName) {
        await this.props.list.enterEditMode(record);
        requestAnimationFrame(() => {
            const row = this.tableRef?.el?.querySelector("tr.o_data_row.o_selected_row");
            const cell = row?.querySelector(`td[name="${CSS.escape(fieldName)}"]`);
            const input = cell?.querySelector("input, textarea, select");
            if (input) {
                input.focus();
                input.select?.();
            }
        });
    },

    // ── Fill handle ──────────────────────────────────────────────────────

    _ktxDdfStartFillDrag() {
        const st = this._ktxDdf;
        if (!st.sel || !st.grid) {
            return;
        }
        st.fillAxis = null;
        st.fillStartX = null;
        st.fillStartY = null;
        st.fillBase = this._ktxDdfActiveRect(st.sel);
        st.fillTarget = { r: st.fillBase.r2, c: st.fillBase.c2 };
        document.body.classList.add("o_ddf_dragging");
        document.body.style.setProperty("--ddf-cursor", dragDropFillState.cursor);

        let cancelled = false;
        const onMove = rafThrottle((ev) => this._ktxDdfOnFillMove(ev));
        const onKeyDown = (ev) => {
            if (ev.key === "Escape") {
                cancelled = true;
                onUp();
            }
        };
        const onUp = () => {
            document.removeEventListener("mousemove", onMove);
            document.removeEventListener("mouseup", onUp);
            document.removeEventListener("keydown", onKeyDown);
            document.body.classList.remove("o_ddf_dragging", "o_ddf_axis_row", "o_ddf_axis_col");
            hideFillPreview();
            if (!cancelled && st.fillAxis) {
                this._ktxDdfApplyFill().then(() => this._ktxDdfRenderSelection());
            } else {
                this._ktxDdfRenderSelection();
            }
        };
        document.addEventListener("mousemove", onMove);
        document.addEventListener("mouseup", onUp);
        document.addEventListener("keydown", onKeyDown);
    },

    _ktxDdfOnFillMove(ev) {
        const st = this._ktxDdf;
        if (st.fillStartX === null) {
            st.fillStartX = ev.clientX;
            st.fillStartY = ev.clientY;
        }
        const el = document.elementFromPoint(ev.clientX, ev.clientY);
        if (!el) {
            return;
        }
        if (!st.fillAxis) {
            const dx = Math.abs(ev.clientX - st.fillStartX);
            const dy = Math.abs(ev.clientY - st.fillStartY);
            if (dx < DRAG_THRESHOLD && dy < DRAG_THRESHOLD) {
                return;
            }
            st.fillAxis = dx > dy ? "col" : "row";
            document.body.classList.add(st.fillAxis === "row" ? "o_ddf_axis_row" : "o_ddf_axis_col");
        }

        const base = st.fillBase;
        let full;
        if (st.fillAxis === "row") {
            const r = st.grid.rows.indexOf(el.closest("tr.o_data_row"));
            if (r === -1) {
                return;
            }
            st.fillTarget = { r, c: base.c2 };
            full = { r1: Math.min(base.r1, r), c1: base.c1, r2: Math.max(base.r2, r), c2: base.c2 };
        } else {
            const cell = el.closest("td.o_data_cell[name]");
            const c = cell ? st.grid.columns.indexOf(cell.getAttribute("name")) : -1;
            if (c === -1) {
                return;
            }
            st.fillTarget = { r: base.r2, c };
            full = { r1: base.r1, c1: Math.min(base.c1, c), r2: base.r2, c2: Math.max(base.c2, c) };
        }
        const px = this._ktxDdfPixelRect(full);
        if (px) {
            showFillPreview(px);
        }
    },

    /** value(offset) extending the series at the selection's edge. */
    _ktxDdfPatternValue(seriesValues, offset, fieldType, forward) {
        const n = seriesValues.length;
        if (n === 0) {
            return undefined;
        }
        if (n === 1) {
            return seriesValues[0];
        }
        if (NUMERIC_TYPES.includes(fieldType) && seriesValues.every((v) => typeof v === "number")) {
            const step = seriesValues[1] - seriesValues[0];
            const arithmetic = seriesValues.every((v, i) => i === 0 || Math.abs(v - seriesValues[i - 1] - step) < 1e-9);
            if (arithmetic && step !== 0) {
                const baseVal = forward ? seriesValues[n - 1] : seriesValues[0];
                return baseVal + (forward ? 1 : -1) * step * offset;
            }
        }
        const idx = forward ? (offset - 1) % n : n - 1 - ((offset - 1) % n);
        return seriesValues[Math.max(0, idx)];
    },

    async _ktxDdfSafeUpdate(record, fieldName, value) {
        try {
            await record.update({ [fieldName]: value });
        } catch {
            // Readonly/computed for this record, or an incompatible value shape - skip.
        }
    },

    /**
     * Selection/copy always work; a fill only writes to records that are
     * actually editable. Posted/cancelled documents - and the lines of such
     * documents (via parent_state) - are skipped, so dragging over them
     * changes nothing, exactly like it would fail to save on the server.
     * Records with no posting state are left to Odoo's own readonly rules.
     */
    _ktxDdfWritable(record) {
        const data = record.data || {};
        const state = data.state ?? data.parent_state;
        if (state === "posted" || state === "cancel" || state === "cancelled") {
            return false;
        }
        return true;
    },

    async _ktxDdfApplyFill() {
        const st = this._ktxDdf;
        const base = st.fillBase;
        const writable = (record) => this._ktxDdfWritable(record);

        let full;
        if (st.fillAxis === "row") {
            const r = st.fillTarget.r;
            full = { r1: Math.min(base.r1, r), c1: base.c1, r2: Math.max(base.r2, r), c2: base.c2 };
        } else {
            const c = st.fillTarget.c;
            full = { r1: base.r1, c1: Math.min(base.c1, c), r2: base.r2, c2: Math.max(base.c2, c) };
        }
        if (full.r1 === base.r1 && full.r2 === base.r2 && full.c1 === base.c1 && full.c2 === base.c2) {
            return; // never left the selection
        }

        const updates = [];
        if (st.fillAxis === "row") {
            for (let c = base.c1; c <= base.c2; c++) {
                const fieldName = st.grid.columns[c];
                const fieldType = this._ktxDdfFieldType(fieldName);
                const seriesValues = [];
                for (let r = base.r1; r <= base.r2; r++) {
                    seriesValues.push(st.grid.records[r]?.data[fieldName]);
                }
                for (let r = full.r1; r <= full.r2; r++) {
                    if (r >= base.r1 && r <= base.r2) {
                        continue;
                    }
                    const record = st.grid.records[r];
                    if (!record || !writable(record)) {
                        continue;
                    }
                    const forward = r > base.r2;
                    const offset = forward ? r - base.r2 : base.r1 - r;
                    updates.push(this._ktxDdfSafeUpdate(record, fieldName, this._ktxDdfPatternValue(seriesValues, offset, fieldType, forward)));
                }
            }
        } else {
            for (let r = base.r1; r <= base.r2; r++) {
                const record = st.grid.records[r];
                if (!record || !writable(record)) {
                    continue;
                }
                const seriesValues = [];
                for (let c = base.c1; c <= base.c2; c++) {
                    seriesValues.push(record.data[st.grid.columns[c]]);
                }
                for (let c = full.c1; c <= full.c2; c++) {
                    if (c >= base.c1 && c <= base.c2) {
                        continue;
                    }
                    const fieldName = st.grid.columns[c];
                    const fieldType = this._ktxDdfFieldType(fieldName);
                    const forward = c > base.c2;
                    const offset = forward ? c - base.c2 : base.c1 - c;
                    updates.push(this._ktxDdfSafeUpdate(record, fieldName, this._ktxDdfPatternValue(seriesValues, offset, fieldType, forward)));
                }
            }
        }

        await Promise.all(updates);
        st.sel = { ranges: [], anchor: { r: full.r1, c: full.c1 }, focus: { r: full.r2, c: full.c2 } };
    },

    _ktxDdfFillToLastRow() {
        const st = this._ktxDdf;
        if (!st.sel || !st.grid) {
            return;
        }
        const base = this._ktxDdfActiveRect(st.sel);
        const lastRow = st.grid.rows.length - 1;
        if (lastRow <= base.r2) {
            return;
        }
        st.fillBase = base;
        st.fillAxis = "row";
        st.fillTarget = { r: lastRow, c: base.c2 };
        this._ktxDdfApplyFill().then(() => this._ktxDdfRenderSelection());
    },
});

// Document lists (account.move) are only forced editable so the fill handle
// works there. On an editable list the "New" button adds an inline row, but
// a full document must be opened in its form to be filled in - so restore
// the native "open the form" behaviour of the New button for those models.
patch(ListController.prototype, {
    async createRecord(params = {}) {
        const resModel = this.props.resModel || this.model?.root?.resModel;
        if (DOCUMENT_MODELS.includes(resModel)) {
            return this.props.createRecord();
        }
        return super.createRecord(params);
    },
});
