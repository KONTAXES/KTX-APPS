# -*- coding: utf-8 -*-
from odoo import api, fields, models


class KtxPettyCashDashboard(models.TransientModel):
    _name = "ktx.petty.cash.dashboard"
    _description = "Tablero de Caja Chica"

    company_currency_id = fields.Many2one("res.currency", compute="_compute_kpis")
    total_funds = fields.Integer(compute="_compute_kpis")
    total_balance = fields.Monetary(compute="_compute_kpis", currency_field="company_currency_id")
    moves_pending = fields.Integer(compute="_compute_kpis")
    replenishments_pending = fields.Integer(compute="_compute_kpis")
    total_spent_month = fields.Monetary(compute="_compute_kpis", currency_field="company_currency_id")
    funds_low_balance = fields.Integer(compute="_compute_kpis")

    top_funds_html = fields.Html(compute="_compute_charts", sanitize=False)
    monthly_html = fields.Html(compute="_compute_charts", sanitize=False)
    expense_by_partner_html = fields.Html(compute="_compute_charts", sanitize=False)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "Tablero de Caja Chica"

    def _compute_kpis(self):
        for rec in self:
            company = self.env.company
            rec.company_currency_id = company.currency_id
            cid = company.id
            Fund = self.env["ktx.petty.cash.fund"]
            funds = Fund.search([("company_id", "=", cid), ("state", "=", "open")])
            rec.total_funds = len(funds)
            rec.total_balance = sum(funds.mapped("current_balance"))
            rec.moves_pending = self.env["ktx.petty.cash.move"].search_count([
                ("company_id", "=", cid), ("state", "=", "draft"),
                ("move_type", "=", "expense"),
            ])
            rec.replenishments_pending = self.env["ktx.petty.cash.replenishment"].search_count([
                ("company_id", "=", cid), ("state", "in", ("confirmed", "approved")),
            ])
            today = fields.Date.today()
            first_month = today.replace(day=1)
            rec.total_spent_month = sum(
                self.env["ktx.petty.cash.move"].search([
                    ("company_id", "=", cid),
                    ("move_type", "=", "expense"),
                    ("state", "in", ("approved", "reimbursed")),
                    ("date", ">=", first_month),
                ]).mapped("amount")
            )
            rec.funds_low_balance = len([
                f for f in funds if f.min_balance and f.current_balance < f.min_balance
            ])

    def _compute_charts(self):
        for rec in self:
            rec.top_funds_html = rec._build_top_funds_html()
            rec.monthly_html = rec._build_monthly_html()
            rec.expense_by_partner_html = rec._build_expense_by_partner_html()

    def _build_top_funds_html(self):
        cid = self.env.company.id
        self.env.cr.execute("""
            SELECT f.name, f.current_balance, f.initial_amount, f.min_balance
            FROM ktx_petty_cash_fund f
            WHERE f.company_id = %s AND f.state = 'open'
            ORDER BY f.current_balance DESC
            LIMIT 8
        """, (cid,))
        rows = self.env.cr.fetchall()
        if not rows:
            return "<p class='text-muted text-center py-3'>Sin fondos activos</p>"
        currency = self.env.company.currency_id.symbol or "Q"
        colors = ["#4e73df","#1cc88a","#36b9cc","#f6c23e","#e74a3b","#858796","#5a5c69","#2e59d9"]
        html = "<div style='padding:4px 0'>"
        for i, (name, balance, initial, min_bal) in enumerate(rows):
            pct = (balance / initial * 100) if initial else 0
            pct = max(0, min(100, pct))
            color = colors[i % len(colors)]
            if min_bal and balance < min_bal:
                status = "⚠️"
                bar_color = "#e74a3b"
            else:
                status = "✅"
                bar_color = color
            html += f"""
            <div style='margin-bottom:12px'>
              <div style='display:flex;justify-content:space-between;margin-bottom:3px'>
                <span style='font-size:13px;font-weight:500'>{status} {name}</span>
                <span style='font-size:13px;color:{color};font-weight:600'>{currency} {balance:,.2f}</span>
              </div>
              <div style='background:#e9ecef;border-radius:4px;height:10px'>
                <div style='width:{pct:.1f}%;background:{bar_color};height:10px;border-radius:4px'></div>
              </div>
              <div style='font-size:10px;color:#999;margin-top:2px'>{pct:.1f}% del fondo inicial</div>
            </div>"""
        html += "</div>"
        return html

    def _build_monthly_html(self):
        cid = self.env.company.id
        self.env.cr.execute("""
            SELECT TO_CHAR(date, 'Mon YY') as mes,
                   DATE_TRUNC('month', date) as mes_date,
                   SUM(amount) as total,
                   COUNT(*) as cnt
            FROM ktx_petty_cash_move
            WHERE move_type = 'expense'
              AND state IN ('approved', 'reimbursed')
              AND date >= CURRENT_DATE - INTERVAL '12 months'
              AND company_id = %s
            GROUP BY mes, mes_date
            ORDER BY mes_date
        """, (cid,))
        rows = self.env.cr.fetchall()
        if not rows:
            return "<p class='text-muted text-center py-3'>Sin datos de los últimos 12 meses</p>"
        max_val = max(r[2] for r in rows) or 1
        currency = self.env.company.currency_id.symbol or "Q"
        colors = ["#4e73df","#1cc88a","#36b9cc","#f6c23e","#e74a3b","#858796"]
        html = "<div style='display:flex;align-items:flex-end;gap:6px;height:120px;padding:0 4px'>"
        for i, (mes, _, total, cnt) in enumerate(rows):
            pct = (total / max_val * 100) if max_val else 0
            color = colors[i % len(colors)]
            bar_h = max(int(pct * 1.1), 4)
            html += f"""
            <div style='flex:1;display:flex;flex-direction:column;align-items:center;gap:3px'
                 title='{mes}: {currency} {total:,.2f} ({cnt} mov.)'>
              <span style='font-size:10px;color:#666;font-weight:600'>{currency}{int(total/1000)}K</span>
              <div style='width:100%;background:{color};border-radius:3px 3px 0 0;
                          height:{bar_h}px;min-height:4px'></div>
              <span style='font-size:9px;color:#999;text-align:center'>{mes}</span>
            </div>"""
        html += "</div>"
        return html

    def _build_expense_by_partner_html(self):
        cid = self.env.company.id
        self.env.cr.execute("""
            SELECT COALESCE(rp.name, 'Sin proveedor') as partner, SUM(m.amount) as total
            FROM ktx_petty_cash_move m
            LEFT JOIN res_partner rp ON rp.id = m.partner_id
            WHERE m.move_type = 'expense'
              AND m.state IN ('approved', 'reimbursed')
              AND m.company_id = %s
            GROUP BY rp.name
            ORDER BY total DESC
            LIMIT 8
        """, (cid,))
        rows = self.env.cr.fetchall()
        if not rows:
            return "<p class='text-muted text-center py-3'>Sin datos</p>"
        max_val = rows[0][1] or 1
        currency = self.env.company.currency_id.symbol or "Q"
        colors = ["#1cc88a","#4e73df","#f6c23e","#36b9cc","#e74a3b","#858796","#2e59d9","#5a5c69"]
        html = "<div style='padding:4px 0'>"
        for i, (partner, total) in enumerate(rows):
            pct = (total / max_val * 100) if max_val else 0
            color = colors[i % len(colors)]
            html += f"""
            <div style='margin-bottom:10px'>
              <div style='display:flex;justify-content:space-between;margin-bottom:3px'>
                <span style='font-size:13px;font-weight:500'>{partner}</span>
                <span style='font-size:13px;color:{color};font-weight:600'>{currency} {total:,.2f}</span>
              </div>
              <div style='background:#e9ecef;border-radius:4px;height:10px'>
                <div style='width:{pct:.1f}%;background:{color};height:10px;border-radius:4px'></div>
              </div>
            </div>"""
        html += "</div>"
        return html

    def action_open_dashboard(self):
        rec = self.env["ktx.petty.cash.dashboard"].create({})
        return {
            "type": "ir.actions.act_window",
            "res_model": "ktx.petty.cash.dashboard",
            "res_id": rec.id,
            "view_mode": "form",
            "target": "current",
        }
