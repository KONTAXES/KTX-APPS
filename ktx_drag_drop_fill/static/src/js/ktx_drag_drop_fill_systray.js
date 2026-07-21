/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { Component, useState, useExternalListener } from "@odoo/owl";
import {
    dragDropFillState,
    toggleDragDropFill,
    setDragDropFillOption,
    CURSOR_OPTIONS,
    ACTIVATION_OPTIONS,
} from "./ktx_drag_drop_fill_state";

export class KtxDragDropFillToggle extends Component {
    static template = "ktx_drag_drop_fill.SystrayToggle";
    static props = {};

    setup() {
        this.state = useState(dragDropFillState);
        this.popoverState = useState({ open: false });
        this.notification = useService("notification");
        this.cursorOptions = CURSOR_OPTIONS;
        this.activationOptions = ACTIVATION_OPTIONS;
        // 3x3 inner cells of the grid icon, filled with the chosen color
        // when the feature is active.
        const coords = [4, 10, 16];
        this.cells = [];
        for (const y of coords) {
            for (const x of coords) {
                this.cells.push({ x, y });
            }
        }
        // Close the settings popover on any click outside it, without
        // fighting the drag-fill overlay's own "click outside" handling.
        useExternalListener(document, "mousedown", (ev) => {
            if (!this.popoverState.open) {
                return;
            }
            if (!ev.target.closest(".o_ktx_ddf_wrapper")) {
                this.popoverState.open = false;
            }
        });
    }

    get title() {
        return this.state.enabled
            ? _t("Modo Excel activo — clic para desactivar")
            : _t("Activar modo Excel (arrastrar/doble clic para copiar celdas)");
    }

    onClick() {
        toggleDragDropFill();
        this.notification.add(
            this.state.enabled
                ? _t("Modo Excel activado: arrastra o selecciona celdas para copiar.")
                : _t("Modo Excel desactivado."),
            { type: this.state.enabled ? "success" : "info", sticky: false }
        );
    }

    toggleSettings(ev) {
        ev.stopPropagation();
        this.popoverState.open = !this.popoverState.open;
    }

    onColorChange(ev) {
        setDragDropFillOption("color", ev.target.value);
    }

    onThicknessChange(ev) {
        setDragDropFillOption("thickness", Number(ev.target.value));
    }

    onCursorChange(ev) {
        setDragDropFillOption("cursor", ev.target.value);
    }

    onActivationChange(ev) {
        setDragDropFillOption("activation", ev.target.value);
    }
}

registry.category("systray").add(
    "ktx_drag_drop_fill.toggle",
    { Component: KtxDragDropFillToggle },
    { sequence: 1 }
);
