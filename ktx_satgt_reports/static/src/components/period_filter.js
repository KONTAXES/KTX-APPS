/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// ── Base mixin ────────────────────────────────────────────────────────────────

class PeriodFilterBase extends Component {
    static props = { record: Object, readonly: { type: Boolean, optional: true }, "*": true };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ periodOpen: false, comparisonOpen: false });
        this._onMousedown = (e) => {
            if (!this.__owl__.bdom?.el?.contains(e.target)) {
                this.state.periodOpen = false;
                this.state.comparisonOpen = false;
            }
        };
        onMounted(() => document.addEventListener("mousedown", this._onMousedown));
        onWillUnmount(() => document.removeEventListener("mousedown", this._onMousedown));
    }

    async _call(method, e) {
        if (e) { e.preventDefault(); e.stopPropagation(); }
        const rec = this.props.record;
        if (rec.isNew) await rec.save();
        await this.orm.call(rec.resModel, method, [[rec.resId]]);
        await rec.load();
        this.state.periodOpen = false;
        this.state.comparisonOpen = false;
    }

    async _write(vals, e) {
        if (e) { e.preventDefault(); e.stopPropagation(); }
        const rec = this.props.record;
        if (rec.isNew) await rec.save();
        await this.orm.write(rec.resModel, [rec.resId], vals);
        await rec.load();
        this.state.periodOpen = false;
        this.state.comparisonOpen = false;
    }

    togglePeriod(e) {
        e.stopPropagation();
        this.state.periodOpen = !this.state.periodOpen;
        this.state.comparisonOpen = false;
    }

    toggleComparison(e) {
        e.stopPropagation();
        this.state.comparisonOpen = !this.state.comparisonOpen;
        this.state.periodOpen = false;
    }
}

// ── IVA: strictly monthly ─────────────────────────────────────────────────────

class SatgtIvaPeriodFilter extends PeriodFilterBase {
    static template = "ktx_satgt.IvaPeriodFilter";

    get display() { return this.props.record.data.iva_period_display || "—"; }
    get comparison() { return this.props.record.data.iva_comparison || "none"; }
    get comparisonLabel() {
        return { none: "Comparación", prev: "Mes anterior", same_year: "Mismo mes año anterior" }
            [this.comparison] || "Comparación";
    }
    get isComparisonActive() { return this.comparison !== "none"; }

    prev(e) { return this._call("action_iva_prev", e); }
    next(e) { return this._call("action_iva_next", e); }
    setComparison(val, e) { return this._write({ iva_comparison: val }, e); }
}

// ── ISR: monthly or quarterly ─────────────────────────────────────────────────

class SatgtIsrPeriodFilter extends PeriodFilterBase {
    static template = "ktx_satgt.IsrPeriodFilter";

    get display() { return this.props.record.data.isr_period_display || "—"; }
    get periodType() { return this.props.record.data.isr_period_type || "mes"; }
    get comparison() { return this.props.record.data.isr_comparison || "none"; }
    get comparisonLabel() {
        return { none: "Comparación", prev: "Período anterior", same_year: "Mismo período año anterior" }
            [this.comparison] || "Comparación";
    }
    get isComparisonActive() { return this.comparison !== "none"; }

    setMes(e)  { return this._call("action_isr_set_mes", e); }
    setTrim(e) { return this._call("action_isr_set_trim", e); }
    prev(e)    { return this._call("action_isr_prev", e); }
    next(e)    { return this._call("action_isr_next", e); }
    setComparison(val, e) { return this._write({ isr_comparison: val }, e); }
}

// ── Register ──────────────────────────────────────────────────────────────────

registry.category("view_widgets").add("satgt_iva_period_filter",  { component: SatgtIvaPeriodFilter });
registry.category("view_widgets").add("satgt_isr_period_filter", { component: SatgtIsrPeriodFilter });
