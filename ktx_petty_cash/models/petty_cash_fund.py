# -*- coding: utf-8 -*-
import base64
import math
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class KtxPettyCashFund(models.Model):
    _name = "ktx.petty.cash.fund"
    _description = "Fondo de Caja Chica"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "state desc, name"

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, **kwargs):
        if not self.env.su:
            multi = self.env['ir.config_parameter'].sudo().get_param(
                'ktx_petty_cash.multi_company', 'False'
            )
            if multi not in ('True', '1', 'true'):
                domain = [('company_id', 'in', self.env.companies.ids)] + list(domain)
        return super()._search(domain, offset=offset, limit=limit, order=order, **kwargs)

    name = fields.Char(string="Nombre", required=True, tracking=True)
    custodian_id = fields.Many2one(
        "res.partner", string="Custodio", tracking=True, ondelete="restrict",
    )
    company_id = fields.Many2one(
        "res.company", string="Compañía",
        default=lambda self: self.env.company, required=True, ondelete="restrict",
    )
    currency_id = fields.Many2one(
        "res.currency", string="Moneda",
        default=lambda self: self.env.company.currency_id, ondelete="restrict",
    )
    initial_amount = fields.Monetary(
        string="Monto Inicial del Fondo", currency_field="currency_id", tracking=True,
    )
    min_balance = fields.Monetary(
        string="Saldo Mínimo Alerta", currency_field="currency_id",
        help="Se crea una actividad de alerta cuando el saldo baja de este monto.",
    )
    current_balance = fields.Monetary(
        string="Saldo Actual", currency_field="currency_id",
        compute="_compute_current_balance", store=True,
    )
    total_spent = fields.Monetary(
        string="Total Gastado", currency_field="currency_id",
        compute="_compute_current_balance", store=True,
    )
    total_replenished = fields.Monetary(
        string="Total Repuesto", currency_field="currency_id",
        compute="_compute_current_balance", store=True,
    )
    pending_approval = fields.Integer(
        string="Gastos Pendientes Aprobación",
        compute="_compute_current_balance", store=True,
    )
    is_low_balance = fields.Boolean(
        string="Saldo Bajo",
        compute="_compute_current_balance", store=True,
    )
    date_start = fields.Date(string="Fecha de Inicio", tracking=True)
    date_end = fields.Date(string="Fecha de Fin", tracking=True)
    authorizer_id = fields.Many2one(
        "res.users", string="Autorizador", tracking=True,
        help="Usuario adicional que puede aprobar gastos y cerrar el fondo.",
    )
    journal_id = fields.Many2one(
        "account.journal", string="Diario",
        domain="[('company_id', '=', company_id)]", ondelete="restrict",
    )
    account_id = fields.Many2one(
        "account.account", string="Cuenta del Fondo",
        domain="[('company_ids', 'in', [company_id])]", ondelete="restrict",
    )
    state = fields.Selection(
        [("open", "Abierto"), ("closed", "Cerrado")],
        string="Estado", default="open", required=True, tracking=True,
    )
    # Configurable chart type
    chart_type = fields.Selection(
        [
            ("bar_vertical", "Barras Verticales"),
            ("bar_horizontal", "Barras Horizontales"),
            ("pie", "Pastel"),
            ("donut", "Dona"),
        ],
        string="Tipo de Gráfico",
        default="bar_vertical",
        help="Selecciona cómo se muestra el gráfico de ejecución del fondo.",
    )
    chart_html = fields.Html(
        string="Gráfico de Ejecución",
        compute="_compute_chart_html",
        sanitize=False,
    )
    line_ids = fields.One2many("ktx.petty.cash.move", "fund_id", string="Movimientos")
    replenishment_ids = fields.One2many(
        "ktx.petty.cash.replenishment", "fund_id", string="Reposiciones",
    )
    replenishment_count = fields.Integer(compute="_compute_counts")
    move_count = fields.Integer(compute="_compute_counts")

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _("Fondo sin nombre")

    @api.depends(
        "initial_amount",
        "line_ids.amount", "line_ids.move_type", "line_ids.state",
    )
    def _compute_current_balance(self):
        for rec in self:
            approved_spent = sum(
                l.amount for l in rec.line_ids
                if l.move_type in ("expense", "manual_expense")
                and l.state in ("approved", "reimbursed")
            )
            replenished = sum(
                l.amount for l in rec.line_ids
                if l.move_type in ("replenishment", "manual_income")
                and l.state == "reimbursed"
            )
            pending = sum(
                1 for l in rec.line_ids
                if l.move_type in ("expense", "manual_expense")
                and l.state in ("draft", "pending")
            )
            balance = rec.initial_amount - approved_spent + replenished
            rec.total_spent = approved_spent
            rec.total_replenished = replenished
            rec.pending_approval = pending
            rec.current_balance = balance
            rec.is_low_balance = bool(rec.min_balance and balance < rec.min_balance)

    def _compute_counts(self):
        for rec in self:
            rec.replenishment_count = len(rec.replenishment_ids)
            rec.move_count = len(rec.line_ids)

    @api.depends(
        "line_ids.amount", "line_ids.state", "line_ids.date", "line_ids.move_type",
        "chart_type", "initial_amount", "current_balance", "total_spent", "total_replenished",
    )
    def _compute_chart_html(self):
        for rec in self:
            rec.chart_html = rec._build_chart_html()

    # ──────────────────────────────────────────────────────
    # Chart generation
    # ──────────────────────────────────────────────────────

    def _get_monthly_expense_data(self):
        """Returns last 6 months of expense data as list of dicts."""
        today = fields.Date.today()
        labels = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]
        data = []
        for i in range(5, -1, -1):
            m = today - relativedelta(months=i)
            spent = sum(
                l.amount for l in self.line_ids
                if l.move_type in ("expense", "manual_expense")
                and l.state in ("approved", "reimbursed")
                and l.date and l.date.year == m.year and l.date.month == m.month
            )
            data.append({"label": labels[m.month - 1], "value": float(spent)})
        return data

    def _build_chart_html(self):
        if self.chart_type in ("bar_vertical", "bar_horizontal"):
            data = self._get_monthly_expense_data()
            max_val = max((d["value"] for d in data), default=0) or 1.0
            if self.chart_type == "bar_vertical":
                return self._chart_bar_vertical(data, max_val)
            return self._chart_bar_horizontal(data, max_val)
        return self._chart_pie_donut(donut=(self.chart_type == "donut"))

    def _chart_bar_vertical(self, data, max_val):
        n = len(data)
        w, h = 280, 130
        pad_l, pad_b, pad_t = 8, 22, 8
        area_w = w - pad_l - 8
        area_h = h - pad_b - pad_t
        bar_w = max(8, int(area_w / n) - 6)
        gap = int((area_w - bar_w * n) / (n + 1))

        bars = ""
        labels = ""
        for i, d in enumerate(data):
            bh = int(d["value"] / max_val * area_h) if max_val else 0
            x = pad_l + gap + i * (bar_w + gap)
            y = pad_t + area_h - bh
            # shadow bar
            bars += (
                f'<rect x="{x+2}" y="{y+2}" width="{bar_w}" height="{bh}" rx="3" '
                f'fill="#c4b5fd" opacity="0.4"/>'
            )
            # main bar with gradient
            grad_id = f"bg{i}"
            bars += (
                f'<defs><linearGradient id="{grad_id}" x1="0" y1="0" x2="0" y2="1">'
                f'<stop offset="0%" stop-color="#7c3aed"/>'
                f'<stop offset="100%" stop-color="#a78bfa"/>'
                f'</linearGradient></defs>'
                f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bh}" rx="3" fill="url(#{grad_id})"/>'
            )
            lx = x + bar_w // 2
            labels += (
                f'<text x="{lx}" y="{h - 5}" text-anchor="middle" '
                f'font-size="9" fill="#6b7280">{d["label"]}</text>'
            )
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'style="width:100%;max-height:130px;display:block">'
            f'{bars}{labels}</svg>'
        )

    def _chart_bar_horizontal(self, data, max_val):
        w, h = 280, 130
        bar_h = max(8, int((h - 16) / len(data)) - 5)
        area_w = w - 36 - 8
        bars = ""
        labels = ""
        for i, d in enumerate(data):
            y = 8 + i * (bar_h + 5)
            bw = int(d["value"] / max_val * area_w) if max_val else 0
            bars += (
                f'<rect x="38" y="{y+2}" width="{bw}" height="{bar_h}" rx="3" '
                f'fill="#c4b5fd" opacity="0.4"/>'
                f'<rect x="36" y="{y}" width="{bw}" height="{bar_h}" rx="3" '
                f'fill="#7c3aed" opacity="0.85"/>'
            )
            labels += (
                f'<text x="34" y="{y + bar_h - 1}" text-anchor="end" '
                f'font-size="9" fill="#6b7280">{d["label"]}</text>'
            )
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'style="width:100%;max-height:130px;display:block">'
            f'{bars}{labels}</svg>'
        )

    def _chart_pie_donut(self, donut=False):
        w, h = 260, 130
        cx, cy, r = 70, 65, 55
        inner_r = 30 if donut else 0

        total = (self.initial_amount or 0.0) + (self.total_replenished or 0.0)
        spent = min(self.total_spent or 0.0, total) if total > 0 else 0.0
        remaining = max(0.0, total - spent)

        if total <= 0:
            # Empty: full circle in gray
            circle = (
                f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#e5e7eb"/>'
            )
            if donut:
                circle += f'<circle cx="{cx}" cy="{cy}" r="{inner_r}" fill="white"/>'
            legend = (
                f'<text x="140" y="55" font-size="10" fill="#9ca3af">Sin datos</text>'
            )
            return (
                f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
                f'style="width:100%;max-height:130px;display:block">'
                f'{circle}{legend}</svg>'
            )

        pct_spent = spent / total
        angle_spent = pct_spent * 2 * math.pi

        def arc_path(cx, cy, r, start, end, cx_inner=0, cy_inner=0, r_inner=0, do_donut=False):
            x1 = cx + r * math.sin(start)
            y1 = cy - r * math.cos(start)
            x2 = cx + r * math.sin(end)
            y2 = cy - r * math.cos(end)
            large = 1 if (end - start) > math.pi else 0
            if do_donut:
                ix1 = cx + r_inner * math.sin(end)
                iy1 = cy - r_inner * math.cos(end)
                ix2 = cx + r_inner * math.sin(start)
                iy2 = cy - r_inner * math.cos(start)
                return (
                    f"M {x1:.2f},{y1:.2f} A {r},{r} 0 {large},1 {x2:.2f},{y2:.2f} "
                    f"L {ix1:.2f},{iy1:.2f} A {r_inner},{r_inner} 0 {large},0 {ix2:.2f},{iy2:.2f} Z"
                )
            return (
                f"M {cx},{cy} L {x1:.2f},{y1:.2f} A {r},{r} 0 {large},1 {x2:.2f},{y2:.2f} Z"
            )

        paths = ""
        if pct_spent >= 0.999:
            if donut:
                paths += (
                    f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#ef4444"/>'
                    f'<circle cx="{cx}" cy="{cy}" r="{inner_r}" fill="white"/>'
                )
            else:
                paths += f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#ef4444"/>'
        elif pct_spent <= 0.001:
            if donut:
                paths += (
                    f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#7c3aed" opacity="0.8"/>'
                    f'<circle cx="{cx}" cy="{cy}" r="{inner_r}" fill="white"/>'
                )
            else:
                paths += f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#7c3aed" opacity="0.8"/>'
        else:
            # remaining slice (background first)
            rem_path = arc_path(cx, cy, r, angle_spent, 2 * math.pi,
                                cx, cy, inner_r, donut)
            spent_path = arc_path(cx, cy, r, 0, angle_spent,
                                  cx, cy, inner_r, donut)
            paths += (
                f'<path d="{rem_path}" fill="#7c3aed" opacity="0.75"/>'
                f'<path d="{spent_path}" fill="#ef4444"/>'
            )
            if not donut:
                # center dot
                paths += f'<circle cx="{cx}" cy="{cy}" r="2" fill="white"/>'

        # Center label for donut
        center_text = ""
        if donut:
            pct_disp = int(pct_spent * 100)
            center_text = (
                f'<text x="{cx}" y="{cy - 6}" text-anchor="middle" '
                f'font-size="13" font-weight="bold" fill="#374151">{pct_disp}%</text>'
                f'<text x="{cx}" y="{cy + 8}" text-anchor="middle" '
                f'font-size="8" fill="#6b7280">ejecutado</text>'
            )

        sym = self.currency_id.symbol or ""
        legend = (
            f'<rect x="138" y="28" width="10" height="10" rx="2" fill="#ef4444"/>'
            f'<text x="152" y="38" font-size="9" fill="#374151">Gastado</text>'
            f'<text x="152" y="50" font-size="9" fill="#6b7280">{sym} {spent:,.2f}</text>'
            f'<rect x="138" y="62" width="10" height="10" rx="2" fill="#7c3aed" opacity="0.8"/>'
            f'<text x="152" y="72" font-size="9" fill="#374151">Disponible</text>'
            f'<text x="152" y="84" font-size="9" fill="#6b7280">{sym} {remaining:,.2f}</text>'
        )

        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'style="width:100%;max-height:130px;display:block">'
            f'{paths}{center_text}{legend}</svg>'
        )

    # ──────────────────────────────────────────────────────
    # Actions
    # ──────────────────────────────────────────────────────

    def action_close(self):
        self.ensure_one()
        if self.line_ids.filtered(lambda l: l.state in ("draft", "pending")):
            raise UserError(_(
                "No se puede cerrar el fondo '%s' mientras tenga gastos pendientes de aprobación."
            ) % self.name)
        self.write({"state": "closed"})
        # Render PDF report and attach to chatter
        attachment_ids = []
        try:
            report = self.env.ref(
                "ktx_petty_cash.action_report_ktx_petty_cash_fund_state",
                raise_if_not_found=False,
            )
            if report:
                pdf_content, _mime = report._render_qweb_pdf(self.ids)
                att = self.env["ir.attachment"].create({
                    "name": "Cierre_%s.pdf" % (self.name or self.id),
                    "type": "binary",
                    "datas": base64.b64encode(pdf_content),
                    "res_model": self._name,
                    "res_id": self.id,
                    "mimetype": "application/pdf",
                })
                attachment_ids = [att.id]
        except Exception:
            pass
        self.message_post(
            body=_("Fondo cerrado. Reporte de estado adjunto.") if attachment_ids else _("Fondo cerrado."),
            attachment_ids=attachment_ids,
            subtype_xmlid="mail.mt_comment",
        )

    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref(
            "ktx_petty_cash.action_report_ktx_petty_cash_fund_state"
        ).report_action(self)

    def action_download_excel(self):
        self.ensure_one()
        xlsx_bytes = self._build_xlsx_bytes()
        att = self.env["ir.attachment"].create({
            "name": "CajaChica_%s.xlsx" % (self.name or self.id),
            "type": "binary",
            "datas": base64.b64encode(xlsx_bytes),
            "res_model": self._name,
            "res_id": self.id,
            "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        })
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/%s?download=true" % att.id,
            "target": "self",
        }

    def _build_xlsx_bytes(self):
        """Generate a formatted XLSX (using zipfile + XML only, no external libs)."""
        import io
        import zipfile
        from xml.sax.saxutils import escape as _xml_escape

        def _x(v):
            return _xml_escape(str(v)) if v is not None else ""

        def _col(n):
            # 0-based column index → letter(s)
            s = ""
            while True:
                s = chr(ord("A") + n % 26) + s
                n = n // 26 - 1
                if n < 0:
                    break
            return s

        def _ref(row, col):
            return _col(col) + str(row)

        def _str_cell(row, col, val, xf):
            return '<c r="%s" t="inlineStr" s="%d"><is><t>%s</t></is></c>' % (
                _ref(row, col), xf, _x(val)
            )

        def _num_cell(row, col, val, xf):
            return '<c r="%s" s="%d"><v>%s</v></c>' % (
                _ref(row, col), xf, float(val or 0)
            )

        NUM_COLS = 12
        LAST_COL = _col(NUM_COLS - 1)  # 'L'

        move_type_sel = dict(self.env["ktx.petty.cash.move"]._fields["move_type"].selection)
        state_sel = dict(self.env["ktx.petty.cash.move"]._fields["state"].selection)
        method_sel = dict(self.env["ktx.petty.cash.move"]._fields["payment_method"].selection)
        fund_state_sel = dict(self._fields["state"].selection)

        moves = self.line_ids.sorted(key=lambda l: (l.payment_date or l.date or "", l.id))

        # ── Build worksheet rows and merges ──────────────────────
        rows_xml = []
        merges = []
        cur_row = 1

        # Row 1 – dark-blue title
        rows_xml.append('<row r="%d" ht="28" customHeight="1">' % cur_row)
        rows_xml.append(_str_cell(cur_row, 0, "Estado de Caja Chica", 1))
        rows_xml.append("</row>")
        merges.append("A%d:%s%d" % (cur_row, LAST_COL, cur_row))
        cur_row += 1

        # Row 2 – fund name sub-header
        rows_xml.append('<row r="%d" ht="18" customHeight="1">' % cur_row)
        rows_xml.append(_str_cell(cur_row, 0, self.name or "", 2))
        rows_xml.append("</row>")
        merges.append("A%d:%s%d" % (cur_row, LAST_COL, cur_row))
        cur_row += 1

        # Row 3 – blank spacer
        rows_xml.append('<row r="%d"/>' % cur_row)
        cur_row += 1

        # Info pairs: left block (A:B key, C:F value) + right block (G:H key, I:L value)
        info_pairs = [
            ("Compañía", self.company_id.name or ""),
            ("Estado", fund_state_sel.get(self.state, self.state)),
            ("Custodio", self.custodian_id.name or ""),
            ("Autorizador", self.authorizer_id.name or ""),
            ("Período", "%s — %s" % (self.date_start or "", self.date_end or "")),
            ("Moneda", self.currency_id.name or ""),
        ]
        for i in range(0, len(info_pairs), 2):
            rows_xml.append('<row r="%d" ht="16" customHeight="1">' % cur_row)
            k1, v1 = info_pairs[i]
            rows_xml.append(_str_cell(cur_row, 0, k1, 3))
            rows_xml.append(_str_cell(cur_row, 2, v1, 4))
            merges.append("A%d:B%d" % (cur_row, cur_row))
            merges.append("C%d:F%d" % (cur_row, cur_row))
            if i + 1 < len(info_pairs):
                k2, v2 = info_pairs[i + 1]
                rows_xml.append(_str_cell(cur_row, 6, k2, 3))
                rows_xml.append(_str_cell(cur_row, 8, v2, 4))
                merges.append("G%d:H%d" % (cur_row, cur_row))
                merges.append("I%d:%s%d" % (cur_row, LAST_COL, cur_row))
            rows_xml.append("</row>")
            cur_row += 1

        # Blank spacer
        rows_xml.append('<row r="%d"/>' % cur_row)
        cur_row += 1

        # Summary labels row
        summary = [
            ("Monto Inicial", self.initial_amount),
            ("Saldo Actual", self.current_balance),
            ("Total Gastado", self.total_spent),
            ("Total Repuesto", self.total_replenished),
        ]
        rows_xml.append('<row r="%d" ht="16" customHeight="1">' % cur_row)
        for i, (lbl, _) in enumerate(summary):
            cs = i * 3
            rows_xml.append(_str_cell(cur_row, cs, lbl, 10))
            merges.append("%s%d:%s%d" % (_col(cs), cur_row, _col(cs + 2), cur_row))
        rows_xml.append("</row>")
        cur_row += 1

        # Summary values row
        rows_xml.append('<row r="%d" ht="20" customHeight="1">' % cur_row)
        for i, (_, val) in enumerate(summary):
            cs = i * 3
            rows_xml.append(_num_cell(cur_row, cs, val, 11))
            merges.append("%s%d:%s%d" % (_col(cs), cur_row, _col(cs + 2), cur_row))
        rows_xml.append("</row>")
        cur_row += 1

        # Blank spacer
        rows_xml.append('<row r="%d"/>' % cur_row)
        cur_row += 1

        # Table header row
        headers = [
            "F. Factura", "F. Pago", "Descripción", "Tipo",
            "Proveedor/Beneficiario", "Monto", "Método Pago", "Ref. Pago",
            "Ref. Documento", "Estado", "Período", "P. Cerrado",
        ]
        rows_xml.append('<row r="%d" ht="16" customHeight="1">' % cur_row)
        for ci, h in enumerate(headers):
            rows_xml.append(_str_cell(cur_row, ci, h, 5))
        rows_xml.append("</row>")
        cur_row += 1

        # Data rows
        for idx, m in enumerate(moves):
            xf_txt = 6 if idx % 2 == 0 else 7
            xf_num = 8 if idx % 2 == 0 else 9
            rows_xml.append('<row r="%d" ht="15" customHeight="1">' % cur_row)
            cols_data = [
                (str(m.date or ""), xf_txt),
                (str(m.payment_date or ""), xf_txt),
                (m.name or "", xf_txt),
                (move_type_sel.get(m.move_type, m.move_type or ""), xf_txt),
                (m.partner_id.name if m.partner_id else "", xf_txt),
                (m.amount, xf_num),
                (method_sel.get(m.payment_method, m.payment_method or ""), xf_txt),
                (m.payment_ref or "", xf_txt),
                (m.ref or "", xf_txt),
                (state_sel.get(m.state, m.state or ""), xf_txt),
                (m.period_label or "", xf_txt),
                ("Sí" if m.period_closed else "No", xf_txt),
            ]
            for ci, (val, xf) in enumerate(cols_data):
                if ci == 5:
                    rows_xml.append(_num_cell(cur_row, ci, val, xf))
                else:
                    rows_xml.append(_str_cell(cur_row, ci, val, xf))
            rows_xml.append("</row>")
            cur_row += 1

        # ── Assemble worksheet XML ────────────────────────────────
        cols_xml = (
            "<cols>"
            '<col min="1" max="1" width="12" customWidth="1"/>'
            '<col min="2" max="2" width="12" customWidth="1"/>'
            '<col min="3" max="3" width="30" customWidth="1"/>'
            '<col min="4" max="4" width="14" customWidth="1"/>'
            '<col min="5" max="5" width="26" customWidth="1"/>'
            '<col min="6" max="6" width="14" customWidth="1"/>'
            '<col min="7" max="7" width="14" customWidth="1"/>'
            '<col min="8" max="8" width="16" customWidth="1"/>'
            '<col min="9" max="9" width="16" customWidth="1"/>'
            '<col min="10" max="10" width="14" customWidth="1"/>'
            '<col min="11" max="11" width="10" customWidth="1"/>'
            '<col min="12" max="12" width="11" customWidth="1"/>'
            "</cols>"
        )
        merge_xml = ""
        if merges:
            merge_xml = '<mergeCells count="%d">%s</mergeCells>' % (
                len(merges),
                "".join('<mergeCell ref="%s"/>' % m for m in merges),
            )
        ws_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
            ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            "<sheetViews>"
            '<sheetView workbookViewId="0"><selection activeCell="A1" sqref="A1"/></sheetView>'
            "</sheetViews>"
            + cols_xml
            + "<sheetData>"
            + "".join(rows_xml)
            + "</sheetData>"
            + merge_xml
            + "</worksheet>"
        )

        # ── Styles XML ───────────────────────────────────────────
        styles_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            "<numFmts count=\"1\">"
            '<numFmt numFmtId="164" formatCode="#,##0.00"/>'
            "</numFmts>"
            "<fonts count=\"7\">"
            "<font><sz val=\"11\"/><name val=\"Calibri\"/></font>"
            "<font><sz val=\"14\"/><b/><color rgb=\"FFFFFFFF\"/><name val=\"Calibri\"/></font>"
            "<font><sz val=\"11\"/><b/><color rgb=\"FFFFFFFF\"/><name val=\"Calibri\"/></font>"
            "<font><sz val=\"10\"/><b/><name val=\"Calibri\"/></font>"
            "<font><sz val=\"10\"/><name val=\"Calibri\"/></font>"
            "<font><sz val=\"10\"/><b/><color rgb=\"FFFFFFFF\"/><name val=\"Calibri\"/></font>"
            "<font><sz val=\"10\"/><name val=\"Calibri\"/></font>"
            "</fonts>"
            "<fills count=\"6\">"
            "<fill><patternFill patternType=\"none\"/></fill>"
            "<fill><patternFill patternType=\"gray125\"/></fill>"
            "<fill><patternFill patternType=\"solid\"><fgColor rgb=\"FF1E3A5F\"/></patternFill></fill>"
            "<fill><patternFill patternType=\"solid\"><fgColor rgb=\"FF2D6A9F\"/></patternFill></fill>"
            "<fill><patternFill patternType=\"solid\"><fgColor rgb=\"FFF0F4FA\"/></patternFill></fill>"
            "<fill><patternFill patternType=\"solid\"><fgColor rgb=\"FFEEF4FB\"/></patternFill></fill>"
            "</fills>"
            "<borders count=\"3\">"
            "<border><left/><right/><top/><bottom/><diagonal/></border>"
            "<border>"
            "<left style=\"thin\"><color rgb=\"FFB0C4DE\"/></left>"
            "<right style=\"thin\"><color rgb=\"FFB0C4DE\"/></right>"
            "<top style=\"thin\"><color rgb=\"FFB0C4DE\"/></top>"
            "<bottom style=\"thin\"><color rgb=\"FFB0C4DE\"/></bottom>"
            "<diagonal/>"
            "</border>"
            "<border>"
            "<left style=\"thin\"><color rgb=\"FFD0D0D0\"/></left>"
            "<right style=\"thin\"><color rgb=\"FFD0D0D0\"/></right>"
            "<top style=\"thin\"><color rgb=\"FFD0D0D0\"/></top>"
            "<bottom style=\"thin\"><color rgb=\"FFD0D0D0\"/></bottom>"
            "<diagonal/>"
            "</border>"
            "</borders>"
            "<cellStyleXfs count=\"1\">"
            "<xf numFmtId=\"0\" fontId=\"0\" fillId=\"0\" borderId=\"0\"/>"
            "</cellStyleXfs>"
            "<cellXfs count=\"12\">"
            # 0 default
            "<xf numFmtId=\"0\" fontId=\"0\" fillId=\"0\" borderId=\"0\" xfId=\"0\"/>"
            # 1 title: dark-blue fill, white 14pt bold, centered
            "<xf numFmtId=\"0\" fontId=\"1\" fillId=\"2\" borderId=\"0\" xfId=\"0\""
            " applyFont=\"1\" applyFill=\"1\" applyAlignment=\"1\">"
            "<alignment horizontal=\"center\" vertical=\"center\"/></xf>"
            # 2 fund-name subtitle: dark-blue fill, white 11pt bold, left
            "<xf numFmtId=\"0\" fontId=\"2\" fillId=\"2\" borderId=\"0\" xfId=\"0\""
            " applyFont=\"1\" applyFill=\"1\" applyAlignment=\"1\">"
            "<alignment horizontal=\"left\" vertical=\"center\" indent=\"1\"/></xf>"
            # 3 info-key: light-blue fill, 10pt bold, right-aligned
            "<xf numFmtId=\"0\" fontId=\"3\" fillId=\"5\" borderId=\"1\" xfId=\"0\""
            " applyFont=\"1\" applyFill=\"1\" applyBorder=\"1\" applyAlignment=\"1\">"
            "<alignment horizontal=\"right\" vertical=\"center\" indent=\"1\"/></xf>"
            # 4 info-value: white fill, 10pt, left-aligned
            "<xf numFmtId=\"0\" fontId=\"4\" fillId=\"0\" borderId=\"1\" xfId=\"0\""
            " applyFont=\"1\" applyBorder=\"1\" applyAlignment=\"1\">"
            "<alignment horizontal=\"left\" vertical=\"center\" indent=\"1\"/></xf>"
            # 5 table-header: medium-blue fill, white bold, centered
            "<xf numFmtId=\"0\" fontId=\"5\" fillId=\"3\" borderId=\"1\" xfId=\"0\""
            " applyFont=\"1\" applyFill=\"1\" applyBorder=\"1\" applyAlignment=\"1\">"
            "<alignment horizontal=\"center\" vertical=\"center\"/></xf>"
            # 6 data-normal: white, left
            "<xf numFmtId=\"0\" fontId=\"6\" fillId=\"0\" borderId=\"2\" xfId=\"0\""
            " applyFont=\"1\" applyBorder=\"1\" applyAlignment=\"1\">"
            "<alignment horizontal=\"left\" vertical=\"center\" indent=\"1\"/></xf>"
            # 7 data-alt: light-gray fill, left
            "<xf numFmtId=\"0\" fontId=\"6\" fillId=\"4\" borderId=\"2\" xfId=\"0\""
            " applyFont=\"1\" applyFill=\"1\" applyBorder=\"1\" applyAlignment=\"1\">"
            "<alignment horizontal=\"left\" vertical=\"center\" indent=\"1\"/></xf>"
            # 8 data-normal numeric
            "<xf numFmtId=\"164\" fontId=\"6\" fillId=\"0\" borderId=\"2\" xfId=\"0\""
            " applyFont=\"1\" applyBorder=\"1\" applyNumberFormat=\"1\" applyAlignment=\"1\">"
            "<alignment horizontal=\"right\" vertical=\"center\"/></xf>"
            # 9 data-alt numeric
            "<xf numFmtId=\"164\" fontId=\"6\" fillId=\"4\" borderId=\"2\" xfId=\"0\""
            " applyFont=\"1\" applyFill=\"1\" applyBorder=\"1\" applyNumberFormat=\"1\" applyAlignment=\"1\">"
            "<alignment horizontal=\"right\" vertical=\"center\"/></xf>"
            # 10 summary-label: light-blue fill, bold, centered
            "<xf numFmtId=\"0\" fontId=\"3\" fillId=\"5\" borderId=\"1\" xfId=\"0\""
            " applyFont=\"1\" applyFill=\"1\" applyBorder=\"1\" applyAlignment=\"1\">"
            "<alignment horizontal=\"center\" vertical=\"center\"/></xf>"
            # 11 summary-value: white, bold, centered, #,##0.00
            "<xf numFmtId=\"164\" fontId=\"3\" fillId=\"0\" borderId=\"1\" xfId=\"0\""
            " applyFont=\"1\" applyBorder=\"1\" applyNumberFormat=\"1\" applyAlignment=\"1\">"
            "<alignment horizontal=\"center\" vertical=\"center\"/></xf>"
            "</cellXfs>"
            "</styleSheet>"
        )

        # ── Pack into ZIP ─────────────────────────────────────────
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                "[Content_Types].xml",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                "</Types>",
            )
            zf.writestr(
                "_rels/.rels",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1"'
                ' Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"'
                ' Target="xl/workbook.xml"/>'
                "</Relationships>",
            )
            zf.writestr(
                "xl/_rels/workbook.xml.rels",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1"'
                ' Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"'
                ' Target="worksheets/sheet1.xml"/>'
                '<Relationship Id="rId2"'
                ' Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles"'
                ' Target="styles.xml"/>'
                "</Relationships>",
            )
            zf.writestr(
                "xl/workbook.xml",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
                ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                "<sheets>"
                '<sheet name="Estado Caja Chica" sheetId="1" r:id="rId1"/>'
                "</sheets>"
                "</workbook>",
            )
            zf.writestr("xl/styles.xml", styles_xml)
            zf.writestr("xl/worksheets/sheet1.xml", ws_xml)
        return buf.getvalue()

    def action_send_by_email(self):
        self.ensure_one()
        attachment_ids = []
        try:
            report = self.env.ref(
                "ktx_petty_cash.action_report_ktx_petty_cash_fund_state",
                raise_if_not_found=False,
            )
            if report:
                pdf_content, _mime = report._render_qweb_pdf(self.ids)
                att = self.env["ir.attachment"].create({
                    "name": "Estado_CajaChica_%s.pdf" % (self.name or self.id),
                    "type": "binary",
                    "datas": base64.b64encode(pdf_content),
                    "res_model": self._name,
                    "res_id": self.id,
                    "mimetype": "application/pdf",
                })
                attachment_ids = [att.id]
        except Exception:
            pass
        return {
            "type": "ir.actions.act_window",
            "res_model": "mail.compose.message",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_model": self._name,
                "default_res_ids": self.ids,
                "default_composition_mode": "comment",
                "default_attachment_ids": attachment_ids,
                "default_subject": _("Estado Fondo de Caja Chica: %s") % (self.name or ""),
            },
        }

    def action_reopen(self):
        self.ensure_one()
        self.state = "open"
        self.message_post(body=_("Fondo reabierto."), subtype_xmlid="mail.mt_note")

    def action_view_moves(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Movimientos — %s") % self.name,
            "res_model": "ktx.petty.cash.move",
            "view_mode": "list,form",
            "domain": [("fund_id", "=", self.id)],
            "context": {"default_fund_id": self.id},
        }

    def action_view_replenishments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Reposiciones — %s") % self.name,
            "res_model": "ktx.petty.cash.replenishment",
            "view_mode": "list,form",
            "domain": [("fund_id", "=", self.id)],
            "context": {"default_fund_id": self.id},
        }

    def action_add_funds(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Agregar Fondos"),
            "res_model": "ktx.petty.cash.fund.replenishment.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_fund_id": self.id},
        }

    def action_add_expense(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Agregar Movimiento"),
            "res_model": "ktx.petty.cash.add.expense.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_fund_id": self.id},
        }

    def action_open_closing_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Cierre Mensual — %s") % self.name,
            "res_model": "ktx.petty.cash.closing.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_fund_id": self.id},
        }

    def _check_low_balance(self):
        """Crea actividad de alerta si el saldo cae por debajo del mínimo."""
        ActivityType = self.env.ref("mail.mail_activity_data_warning", raise_if_not_found=False)
        if not ActivityType:
            ActivityType = self.env.ref("mail.mail_activity_data_todo")
        for rec in self:
            if not rec.min_balance or rec.current_balance >= rec.min_balance:
                continue
            already = rec.activity_ids.filtered(
                lambda a: a.activity_type_id == ActivityType
                and _("Saldo bajo") in (a.summary or "")
            )
            if already:
                continue
            user = (
                rec.custodian_id.user_ids[0]
                if rec.custodian_id and rec.custodian_id.user_ids
                else self.env.user
            )
            rec.activity_schedule(
                ActivityType.get_external_id().get(ActivityType.id) or "mail.mail_activity_data_todo",
                summary=_("Saldo bajo en fondo de caja chica"),
                note=_(
                    "El saldo actual del fondo <b>%s</b> es <b>%s %.2f</b>, "
                    "por debajo del mínimo de <b>%s %.2f</b>. "
                    "Se recomienda solicitar una reposición."
                ) % (
                    rec.name,
                    rec.currency_id.symbol, rec.current_balance,
                    rec.currency_id.symbol, rec.min_balance,
                ),
                user_id=user.id,
            )
