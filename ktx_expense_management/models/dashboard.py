# -*- coding: utf-8 -*-
from odoo import api, fields, models


class KtxExpenseDashboard(models.TransientModel):
    _name = "ktx.expense.dashboard"
    _description = "Tablero de Liquidaciones"

    total_draft = fields.Integer(compute="_compute_kpis")
    total_confirmed = fields.Integer(compute="_compute_kpis")
    total_approved = fields.Integer(compute="_compute_kpis")
    total_posted = fields.Integer(compute="_compute_kpis")
    total_paid = fields.Integer(compute="_compute_kpis")
    amount_pending = fields.Monetary(compute="_compute_kpis", currency_field="company_currency_id")
    amount_paid_month = fields.Monetary(compute="_compute_kpis", currency_field="company_currency_id")
    amount_paid_year = fields.Monetary(compute="_compute_kpis", currency_field="company_currency_id")
    company_currency_id = fields.Many2one("res.currency", compute="_compute_kpis")
    staging_pending = fields.Integer(compute="_compute_kpis")
    staging_in_settlement = fields.Integer(compute="_compute_kpis")

    # Chart data as HTML
    top_employees_html = fields.Html(compute="_compute_charts", sanitize=False)
    top_partners_html = fields.Html(compute="_compute_charts", sanitize=False)
    monthly_html = fields.Html(compute="_compute_charts", sanitize=False)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "Tablero de Liquidaciones"

    def _compute_kpis(self):
        for rec in self:
            company = self.env.company
            rec.company_currency_id = company.currency_id
            cid = company.id
            Settlement = self.env["ktx.settlement"]
            today = fields.Date.today()
            first_day_month = today.replace(day=1)
            first_day_year = today.replace(month=1, day=1)

            base = [("company_id", "=", cid)]
            rec.total_draft = Settlement.search_count(base + [("state", "=", "draft")])
            rec.total_confirmed = Settlement.search_count(base + [("state", "=", "confirmed")])
            rec.total_approved = Settlement.search_count(base + [("state", "=", "approved")])
            rec.total_posted = Settlement.search_count(base + [("state", "=", "posted")])
            rec.total_paid = Settlement.search_count(base + [("state", "=", "paid")])

            pending = Settlement.search(base + [("state", "in", ["confirmed", "approved", "posted"])])
            rec.amount_pending = sum(pending.mapped("amount_total"))

            paid_month = Settlement.search(base + [("state", "=", "paid"), ("date", ">=", first_day_month)])
            rec.amount_paid_month = sum(paid_month.mapped("amount_total"))

            paid_year = Settlement.search(base + [("state", "=", "paid"), ("date", ">=", first_day_year)])
            rec.amount_paid_year = sum(paid_year.mapped("amount_total"))

            Staging = self.env["ktx.settlement.staging"]
            rec.staging_pending = Staging.search_count([("state", "=", "pending"), ("company_id", "=", cid)])
            rec.staging_in_settlement = Staging.search_count([("state", "=", "in_settlement"), ("company_id", "=", cid)])

    def _compute_charts(self):
        for rec in self:
            rec.top_employees_html = rec._build_top_employees_html()
            rec.top_partners_html = rec._build_top_partners_html()
            rec.monthly_html = rec._build_monthly_html()

    def _build_top_employees_html(self):
        cid = self.env.company.id
        self.env.cr.execute("""
            SELECT rp.name, SUM(s.amount_total) as total
            FROM ktx_settlement s
            JOIN res_partner rp ON rp.id = s.employee_id
            WHERE s.state IN ('approved','posted','in_payment','paid')
              AND s.employee_id IS NOT NULL
              AND s.company_id = %s
            GROUP BY rp.name
            ORDER BY total DESC
            LIMIT 8
        """, (cid,))
        rows = self.env.cr.fetchall()
        if not rows:
            return "<p class='text-muted text-center py-3'>Sin datos</p>"
        max_val = rows[0][1] if rows else 1
        currency = self.env.company.currency_id.symbol or "Q"
        html = "<div style='padding:4px 0'>"
        colors = ["#4e73df","#1cc88a","#36b9cc","#f6c23e","#e74a3b","#858796","#5a5c69","#2e59d9"]
        for i, (name, total) in enumerate(rows):
            pct = (total / max_val * 100) if max_val else 0
            color = colors[i % len(colors)]
            html += f"""
            <div style='margin-bottom:10px'>
              <div style='display:flex;justify-content:space-between;margin-bottom:3px'>
                <span style='font-size:13px;font-weight:500'>{name}</span>
                <span style='font-size:13px;color:{color};font-weight:600'>{currency} {total:,.2f}</span>
              </div>
              <div style='background:#e9ecef;border-radius:4px;height:10px'>
                <div style='width:{pct:.1f}%;background:{color};height:10px;border-radius:4px;transition:width 0.6s'></div>
              </div>
            </div>"""
        html += "</div>"
        return html

    def _build_top_partners_html(self):
        cid = self.env.company.id
        self.env.cr.execute("""
            SELECT rp.name, SUM(sl.amount_to_pay) as total
            FROM ktx_settlement_line sl
            JOIN ktx_settlement s ON s.id = sl.settlement_id
            JOIN ktx_settlement_staging ss ON ss.id = sl.staging_id
            JOIN account_move am ON am.id = ss.move_id
            JOIN res_partner rp ON rp.id = am.partner_id
            WHERE s.state IN ('approved','posted','in_payment','paid')
              AND s.company_id = %s
            GROUP BY rp.name
            ORDER BY total DESC
            LIMIT 8
        """, (cid,))
        rows = self.env.cr.fetchall()
        if not rows:
            return "<p class='text-muted text-center py-3'>Sin datos</p>"
        max_val = rows[0][1] if rows else 1
        currency = self.env.company.currency_id.symbol or "Q"
        html = "<div style='padding:4px 0'>"
        colors = ["#1cc88a","#4e73df","#f6c23e","#36b9cc","#e74a3b","#858796","#2e59d9","#5a5c69"]
        for i, (name, total) in enumerate(rows):
            pct = (total / max_val * 100) if max_val else 0
            color = colors[i % len(colors)]
            html += f"""
            <div style='margin-bottom:10px'>
              <div style='display:flex;justify-content:space-between;margin-bottom:3px'>
                <span style='font-size:13px;font-weight:500'>{name or "Sin proveedor"}</span>
                <span style='font-size:13px;color:{color};font-weight:600'>{currency} {total:,.2f}</span>
              </div>
              <div style='background:#e9ecef;border-radius:4px;height:10px'>
                <div style='width:{pct:.1f}%;background:{color};height:10px;border-radius:4px;transition:width 0.6s'></div>
              </div>
            </div>"""
        html += "</div>"
        return html

    def _build_monthly_html(self):
        cid = self.env.company.id
        self.env.cr.execute("""
            SELECT TO_CHAR(date, 'Mon YY') as mes,
                   DATE_TRUNC('month', date) as mes_date,
                   SUM(amount_total) as total,
                   COUNT(*) as cnt
            FROM ktx_settlement
            WHERE state IN ('posted','in_payment','paid')
              AND date >= CURRENT_DATE - INTERVAL '12 months'
              AND company_id = %s
            GROUP BY mes, mes_date
            ORDER BY mes_date
        """, (cid,))
        rows = self.env.cr.fetchall()
        if not rows:
            return "<p class='text-muted text-center py-3'>Sin datos de los últimos 12 meses</p>"
        max_val = max(r[2] for r in rows) if rows else 1
        currency = self.env.company.currency_id.symbol or "Q"
        html = "<div style='display:flex;align-items:flex-end;gap:6px;height:120px;padding:0 4px'>"
        colors = ["#4e73df","#1cc88a","#36b9cc","#f6c23e","#e74a3b","#858796"]
        for i, (mes, _, total, cnt) in enumerate(rows):
            pct = (total / max_val * 100) if max_val else 0
            color = colors[i % len(colors)]
            bar_h = max(int(pct * 1.1), 4)
            html += f"""
            <div style='flex:1;display:flex;flex-direction:column;align-items:center;gap:3px' title='{mes}: {currency} {total:,.2f} ({cnt} liq.)'>
              <span style='font-size:10px;color:#666;font-weight:600'>{currency}{int(total/1000)}K</span>
              <div style='width:100%;background:{color};border-radius:3px 3px 0 0;height:{bar_h}px;min-height:4px;cursor:pointer' title='{mes}: {currency} {total:,.2f}'></div>
              <span style='font-size:9px;color:#999;text-align:center;line-height:1.1'>{mes}</span>
            </div>"""
        html += "</div>"
        return html

    def action_open_dashboard(self):
        rec = self.env["ktx.expense.dashboard"].create({})
        return {
            "type": "ir.actions.act_window",
            "res_model": "ktx.expense.dashboard",
            "res_id": rec.id,
            "view_mode": "form",
            "target": "current",
        }
