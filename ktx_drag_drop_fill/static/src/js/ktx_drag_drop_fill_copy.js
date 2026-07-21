/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";
import { useEffect } from "@odoo/owl";
import { dragDropFillState } from "./ktx_drag_drop_fill_state";
import { extractCellText, cellHasCopyableContent, toClipboard } from "./ktx_drag_drop_fill_util";

/**
 * Hover copy affordances, folded in from the standalone clipboard module so
 * it can be uninstalled.
 *
 *  - Column copy button in each header: available in BOTH states.
 *  - Cell + row copy buttons and the cell/row/column cross-highlight:
 *    only while the spreadsheet mode is OFF. When it's ON, cell and row
 *    copying is done through the selection (press-and-hold + Ctrl+C), so
 *    those buttons stay out of the way and only the column button remains.
 *
 * Copy buttons never appear on cells whose content is a control (button or
 * checkbox), so they can't block clicking those.
 */

function mkBtn(kind, title, iconClass) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = `o_ddf_copy_btn o_ddf_copy_${kind}`;
    b.title = title;
    b.tabIndex = -1;
    b.setAttribute("aria-label", title);
    b.innerHTML = `<i class="fa ${iconClass}" aria-hidden="true"></i>`;
    // Never let a copy click reach Odoo's row handler or our own mousedown.
    b.addEventListener("mousedown", (e) => e.stopPropagation(), true);
    return b;
}

function flash(btn) {
    btn.classList.add("o_ddf_copied");
    setTimeout(() => btn.classList.remove("o_ddf_copied"), 700);
}

patch(ListRenderer.prototype, {
    setup() {
        super.setup();
        useEffect(
            (table) => {
                if (table) {
                    this._ktxCopyBind(table);
                }
            },
            () => [this.tableRef?.el]
        );
    },

    _ktxCopyBind(table) {
        if (table._ktxCopyBound) {
            return;
        }
        table._ktxCopyBound = true;
        table.addEventListener("mouseover", (ev) => this._ktxCopyOnHover(ev, table));
        table.addEventListener("mouseout", (ev) => this._ktxCopyOnOut(ev, table));
    },

    _ktxCopyOnHover(ev, table) {
        const th = ev.target.closest("thead th[data-name]");
        if (th) {
            this._ktxCopyEnsureColBtn(th);
            return;
        }

        const cell = ev.target.closest("td.o_data_cell[name]");
        if (!cell) {
            return;
        }
        // Cell/row copy + highlight are the OFF-mode affordance; when the
        // spreadsheet mode is ON the selection does that job.
        if (dragDropFillState.enabled) {
            return;
        }

        this._ktxCopyHighlight(cell, table);

        if (cellHasCopyableContent(cell) && !cell.querySelector(".o_ddf_copy_cell")) {
            const btn = mkBtn("cell", "Copiar celda", "fa-copy");
            btn.addEventListener("click", (e) => {
                e.preventDefault();
                e.stopPropagation();
                toClipboard(extractCellText(cell)).then(() => flash(btn));
            });
            cell.appendChild(btn);
        }

        const row = cell.closest("tr.o_data_row");
        if (row && !row.querySelector(".o_ddf_copy_row")) {
            const cells = row.querySelectorAll("td.o_data_cell");
            const last = cells[cells.length - 1];
            if (last) {
                const btn = mkBtn("row", "Copiar fila", "fa-align-justify");
                btn.addEventListener("click", (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    const vals = Array.from(row.querySelectorAll("td.o_data_cell"))
                        .map(extractCellText)
                        .filter(Boolean);
                    toClipboard(vals.join("\t")).then(() => flash(btn));
                });
                last.appendChild(btn);
            }
        }
    },

    _ktxCopyOnOut(ev, table) {
        const to = ev.relatedTarget;
        const cell = ev.target.closest("td.o_data_cell[name]");
        if (cell && (!to || !cell.contains(to))) {
            cell.querySelector(".o_ddf_copy_cell")?.remove();
        }
        const row = ev.target.closest("tr.o_data_row");
        if (row && (!to || !row.contains(to))) {
            row.querySelector(".o_ddf_copy_row")?.remove();
            this._ktxCopyClearHighlight(table);
        }
    },

    _ktxCopyEnsureColBtn(th) {
        if (th.querySelector(".o_ddf_copy_col")) {
            return;
        }
        const label = th.querySelector("span.text-truncate")?.textContent.trim() || th.textContent.trim();
        if (!label) {
            return;
        }
        const btn = mkBtn("col", `Copiar columna "${label}"`, "fa-clipboard");
        btn.addEventListener("click", (e) => {
            e.preventDefault();
            e.stopPropagation();
            this._ktxCopyColumn(th, btn);
        });
        (th.querySelector("div.d-flex") || th).prepend(btn);
    },

    _ktxCopyColumn(th, btn) {
        const table = this.tableRef?.el;
        if (!table) {
            return;
        }
        const name = th.dataset.name;
        const values = Array.from(table.querySelectorAll("tbody tr.o_data_row"))
            .map((r) => {
                const td = r.querySelector(`td[name="${CSS.escape(name)}"]`);
                return td ? extractCellText(td) : "";
            })
            .filter(Boolean);
        toClipboard(values.join("\n")).then(() => flash(btn));
    },

    _ktxCopyHighlight(cell, table) {
        if (this._ktxCopyHlCell === cell) {
            return;
        }
        this._ktxCopyClearHighlight(table);
        cell.classList.add("o_ddf_hl_cell");
        cell.closest("tr.o_data_row")?.classList.add("o_ddf_hl_row");
        const name = cell.getAttribute("name");
        if (name) {
            table.querySelectorAll(`td[name="${CSS.escape(name)}"]`).forEach((td) => td.classList.add("o_ddf_hl_col"));
        }
        this._ktxCopyHlCell = cell;
    },

    _ktxCopyClearHighlight(table) {
        (table || this.tableRef?.el)
            ?.querySelectorAll(".o_ddf_hl_cell, .o_ddf_hl_row, .o_ddf_hl_col")
            .forEach((el) => el.classList.remove("o_ddf_hl_cell", "o_ddf_hl_row", "o_ddf_hl_col"));
        this._ktxCopyHlCell = null;
    },
});

// ── Form view: single-field copy on hover (module-level, added once) ────────
document.addEventListener(
    "mouseover",
    (ev) => {
        if (ev.target.closest(".o_list_renderer")) {
            return;
        }
        const widget = ev.target.closest(".o_form_view .o_field_widget[name]");
        if (!widget || widget.querySelector(".o_ddf_copy_form")) {
            return;
        }
        if (widget.querySelector("button, input[type='checkbox'], input[type='radio']")) {
            return;
        }
        const btn = mkBtn("form", "Copiar campo", "fa-copy");
        btn.addEventListener("click", (e) => {
            e.preventDefault();
            e.stopPropagation();
            toClipboard(extractCellText(widget)).then(() => flash(btn));
        });
        widget.appendChild(btn);
    },
    { passive: true }
);
