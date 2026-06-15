# -*- coding: utf-8 -*-
from datetime import date
from dateutil.relativedelta import relativedelta
from markupsafe import escape
from odoo import api, fields, models

_MONTHS_ES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
              'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
_QUARTERS_ES = ['1er Trimestre', '2do Trimestre', '3er Trimestre', '4to Trimestre']


def _first_day(self=None):
    t = date.today()
    return t.replace(day=1)


def _last_day(self=None):
    t = date.today()
    return (t.replace(day=1) + relativedelta(months=1)) - relativedelta(days=1)


def _first_day_of_quarter(self=None):
    t = date.today()
    q_month = ((t.month - 1) // 3) * 3 + 1
    return t.replace(month=q_month, day=1)


class SatgtDeclWizard(models.TransientModel):
    _name = 'ktx.satgt.decl.wizard'
    _description = 'Declaración Sombra SAT GT'
    _rec_name = 'name'

    name = fields.Char(default='Declaración Sombra', readonly=True)

    company_id = fields.Many2one(
        'res.company', string='Empresa',
        default=lambda s: s.env.company, required=True,
    )

    # ── Computed company regime flags (for invisible conditions in view) ──────
    company_iva_regime = fields.Char(
        compute='_compute_company_regime', store=False,
    )
    company_isr_regime = fields.Char(
        compute='_compute_company_regime', store=False,
    )
    company_apply_iso = fields.Boolean(
        compute='_compute_company_regime', store=False,
    )

    @api.depends('company_id')
    def _compute_company_regime(self):
        for rec in self:
            co = rec.company_id
            rec.company_iva_regime = co.ktx_iva_regime or 'general'
            rec.company_isr_regime = co.ktx_isr_regime or False
            rec.company_apply_iso  = co.ktx_apply_iso or False

    # ── IVA period (shared by IVA General and IVA Pequeño Contribuyente) ─────
    iva_period_type = fields.Selection([
        ('mes',          'Mes'),
        ('personalizado', 'Personalizado'),
    ], string='Tipo Período IVA', default='mes')
    iva_date_from = fields.Date(string='Desde', default=_first_day)
    iva_date_to   = fields.Date(string='Hasta',  default=_last_day)
    iva_period_label = fields.Char(
        compute='_compute_iva_period_label', store=False,
    )

    @api.depends('iva_period_type', 'iva_date_from', 'iva_date_to')
    def _compute_iva_period_label(self):
        for rec in self:
            rec.iva_period_label = rec._label_mes(rec.iva_date_from)

    @api.onchange('iva_period_type')
    def _onchange_iva_period_type(self):
        if self.iva_period_type == 'mes':
            self.iva_date_from, self.iva_date_to = self._month_range(date.today())

    def action_iva_prev(self):
        if self.iva_date_from:
            new_from = (self.iva_date_from - relativedelta(months=1)).replace(day=1)
            self.iva_date_from, self.iva_date_to = self._month_range(new_from)
        return self._reload()

    def action_iva_next(self):
        if self.iva_date_from:
            new_from = (self.iva_date_from + relativedelta(months=1)).replace(day=1)
            self.iva_date_from, self.iva_date_to = self._month_range(new_from)
        return self._reload()

    # ── ISR Mensual period ───────────────────────────────────────────────────
    isr_men_period_type = fields.Selection([
        ('mes',          'Mes'),
        ('personalizado', 'Personalizado'),
    ], string='Tipo Período ISR Mensual', default='mes')
    isr_men_date_from = fields.Date(string='Desde', default=_first_day)
    isr_men_date_to   = fields.Date(string='Hasta',  default=_last_day)
    isr_men_period_label = fields.Char(
        compute='_compute_isr_men_period_label', store=False,
    )

    @api.depends('isr_men_period_type', 'isr_men_date_from', 'isr_men_date_to')
    def _compute_isr_men_period_label(self):
        for rec in self:
            rec.isr_men_period_label = rec._label_mes(rec.isr_men_date_from)

    @api.onchange('isr_men_period_type')
    def _onchange_isr_men_period_type(self):
        if self.isr_men_period_type == 'mes':
            self.isr_men_date_from, self.isr_men_date_to = self._month_range(date.today())

    def action_isr_men_prev(self):
        if self.isr_men_date_from:
            new_from = (self.isr_men_date_from - relativedelta(months=1)).replace(day=1)
            self.isr_men_date_from, self.isr_men_date_to = self._month_range(new_from)
        return self._reload()

    def action_isr_men_next(self):
        if self.isr_men_date_from:
            new_from = (self.isr_men_date_from + relativedelta(months=1)).replace(day=1)
            self.isr_men_date_from, self.isr_men_date_to = self._month_range(new_from)
        return self._reload()

    # ── ISR Trimestral ────────────────────────────────────────────────────────
    isr_trim_quarter = fields.Selection([
        ('1', '1er Trimestre (Ene–Mar)'),
        ('2', '2do Trimestre (Ene–Jun, acumulado)'),
        ('3', '3er Trimestre (Ene–Sep, acumulado)'),
    ], string='Trimestre ISR', default=lambda s: str(((date.today().month - 1) // 3) or 1))
    isr_trim_year = fields.Integer(
        string='Año ISR', default=lambda s: date.today().year,
    )
    isr_trim_label = fields.Char(
        compute='_compute_isr_trim_label', store=False,
    )
    isr_trim_incentivos = fields.Float(
        string='Incentivos Fiscales',
        digits=(16, 2), default=0.0,
    )

    @api.depends('isr_trim_quarter', 'isr_trim_year')
    def _compute_isr_trim_label(self):
        labels = {'1': '1er Trim', '2': '2do Trim (acum.)', '3': '3er Trim (acum.)'}
        for rec in self:
            q = rec.isr_trim_quarter or '1'
            rec.isr_trim_label = f"{labels.get(q, q)} {rec.isr_trim_year or ''}"

    def action_isr_trim_prev(self):
        q = int(self.isr_trim_quarter or 1)
        if q > 1:
            self.isr_trim_quarter = str(q - 1)
        else:
            self.isr_trim_quarter = '3'
            self.isr_trim_year = (self.isr_trim_year or date.today().year) - 1
        return self._reload()

    def action_isr_trim_next(self):
        q = int(self.isr_trim_quarter or 1)
        if q < 3:
            self.isr_trim_quarter = str(q + 1)
        else:
            self.isr_trim_quarter = '1'
            self.isr_trim_year = (self.isr_trim_year or date.today().year) + 1
        return self._reload()

    # ── ISR Anual ─────────────────────────────────────────────────────────────
    isr_anual_year = fields.Integer(
        string='Año Fiscal', default=lambda s: date.today().year,
    )
    isr_anual_label = fields.Char(
        compute='_compute_isr_anual_label', store=False,
    )
    isr_anual_incentivos = fields.Float(
        string='Incentivos Fiscales',
        digits=(16, 2), default=0.0,
    )

    @api.depends('isr_anual_year')
    def _compute_isr_anual_label(self):
        for rec in self:
            rec.isr_anual_label = f"Año {rec.isr_anual_year or ''}"

    def action_isr_anual_prev(self):
        self.isr_anual_year = (self.isr_anual_year or date.today().year) - 1
        return self._reload()

    def action_isr_anual_next(self):
        self.isr_anual_year = (self.isr_anual_year or date.today().year) + 1
        return self._reload()

    # ── ISO Trimestral ────────────────────────────────────────────────────────
    iso_quarter = fields.Selection([
        ('1', '1er Trimestre (Ene–Mar)'),
        ('2', '2do Trimestre (Abr–Jun)'),
        ('3', '3er Trimestre (Jul–Sep)'),
        ('4', '4to Trimestre (Oct–Dic)'),
    ], string='Trimestre ISO', default=lambda s: str(((date.today().month - 1) // 3) + 1))
    iso_year = fields.Integer(
        string='Año ISO', default=lambda s: date.today().year,
    )
    iso_label = fields.Char(
        compute='_compute_iso_label', store=False,
    )

    @api.depends('iso_quarter', 'iso_year')
    def _compute_iso_label(self):
        labels = {
            '1': '1er Trim (Ene–Mar)',
            '2': '2do Trim (Abr–Jun)',
            '3': '3er Trim (Jul–Sep)',
            '4': '4to Trim (Oct–Dic)',
        }
        for rec in self:
            q = rec.iso_quarter or '1'
            rec.iso_label = f"{labels.get(q, q)} {rec.iso_year or ''}"

    def action_iso_prev(self):
        q = int(self.iso_quarter or 1)
        if q > 1:
            self.iso_quarter = str(q - 1)
        else:
            self.iso_quarter = '4'
            self.iso_year = (self.iso_year or date.today().year) - 1
        return self._reload()

    def action_iso_next(self):
        q = int(self.iso_quarter or 1)
        if q < 4:
            self.iso_quarter = str(q + 1)
        else:
            self.iso_quarter = '1'
            self.iso_year = (self.iso_year or date.today().year) + 1
        return self._reload()

    # ── Computed HTML fields per section ──────────────────────────────────────
    html_iva_general = fields.Html(
        compute='_compute_html_iva', sanitize=False,
    )
    html_iva_pc = fields.Html(
        compute='_compute_html_iva', sanitize=False,
    )

    @api.depends('company_id', 'iva_date_from', 'iva_date_to')
    def _compute_html_iva(self):
        for rec in self:
            rec.html_iva_general = rec._html_iva_general()
            rec.html_iva_pc      = rec._html_iva_pc()

    html_isr_mensual = fields.Html(
        compute='_compute_html_isr_men', sanitize=False,
    )

    @api.depends('company_id', 'isr_men_date_from', 'isr_men_date_to')
    def _compute_html_isr_men(self):
        for rec in self:
            rec.html_isr_mensual = rec._html_isr_mensual()

    html_isr_trim = fields.Html(
        compute='_compute_html_isr_trim', sanitize=False,
    )

    @api.depends('company_id', 'isr_trim_quarter', 'isr_trim_year', 'isr_trim_incentivos')
    def _compute_html_isr_trim(self):
        for rec in self:
            rec.html_isr_trim = rec._html_isr_trim()

    html_isr_anual = fields.Html(
        compute='_compute_html_isr_anual', sanitize=False,
    )

    @api.depends('company_id', 'isr_anual_year', 'isr_anual_incentivos')
    def _compute_html_isr_anual(self):
        for rec in self:
            rec.html_isr_anual = rec._html_isr_anual()

    html_iso_trim = fields.Html(
        compute='_compute_html_iso', sanitize=False,
    )

    @api.depends('company_id', 'iso_quarter', 'iso_year')
    def _compute_html_iso(self):
        for rec in self:
            rec.html_iso_trim = rec._html_iso_trim()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _reload(self):
        # Returning a falsy value makes the web client re-read the current
        # record in place, preserving the active notebook page. The non-stored
        # computed HTML fields recompute automatically on reload.
        return False

    @staticmethod
    def _month_range(d):
        first = d.replace(day=1)
        last  = (first + relativedelta(months=1)) - relativedelta(days=1)
        return first, last

    def _label_mes(self, d):
        if not d:
            return ''
        return f"{_MONTHS_ES[d.month - 1]} {d.year}"

    def _quarter_range(self, year, quarter):
        """Return (date_from, date_to) for the cumulative ISR quarter (always starts Jan 1)."""
        end_month = quarter * 3
        date_from = date(year, 1, 1)
        date_to   = (date(year, end_month, 1) + relativedelta(months=1)) - relativedelta(days=1)
        return date_from, date_to

    def _iso_quarter_range(self, year, quarter):
        """Return (date_from, date_to) for an independent ISO quarter."""
        start_month = (quarter - 1) * 3 + 1
        date_from   = date(year, start_month, 1)
        date_to     = (date_from + relativedelta(months=3)) - relativedelta(days=1)
        return date_from, date_to

    def _sum_tax_cat(self, category, date_from, date_to, move_types=None):
        configs  = self.env['ktx.satgt.tax.config'].search([
            ('company_id', '=', self.company_id.id), ('category', '=', category),
        ])
        tax_ids = configs.mapped('tax_id').ids
        if not tax_ids:
            return 0.0
        domain = [
            ('move_id.state', '=', 'posted'),
            ('date', '>=', date_from), ('date', '<=', date_to),
            ('company_id', '=', self.company_id.id),
            ('tax_line_id', 'in', tax_ids),
        ]
        if move_types:
            domain.append(('move_id.move_type', 'in', move_types))
        lines = self.env['account.move.line'].search(domain)
        return abs(sum(lines.mapped('balance')))

    def _sum_account_type(self, account_types, date_from, date_to):
        lines = self.env['account.move.line'].search([
            ('move_id.state', '=', 'posted'),
            ('date', '>=', date_from), ('date', '<=', date_to),
            ('company_id', '=', self.company_id.id),
            ('account_id.account_type', 'in', account_types),
        ])
        return abs(sum(lines.mapped('balance')))

    def _account_balance(self, account, date_to, date_from=None):
        """Accumulated posted balance of an account up to date_to (optionally
        from date_from). Returns the signed balance."""
        if not account:
            return 0.0
        domain = [
            ('move_id.state', '=', 'posted'),
            ('account_id', '=', account.id),
            ('company_id', '=', self.company_id.id),
            ('date', '<=', date_to),
        ]
        if date_from:
            domain.append(('date', '>=', date_from))
        lines = self.env['account.move.line'].search(domain)
        return sum(lines.mapped('balance'))

    def _sum_non_deductible(self, date_from, date_to):
        """Sum of postings in accounts flagged as non-deductible (ktx_non_deductible)."""
        lines = self.env['account.move.line'].search([
            ('move_id.state', '=', 'posted'),
            ('date', '>=', date_from), ('date', '<=', date_to),
            ('company_id', '=', self.company_id.id),
            ('account_id.ktx_non_deductible', '=', True),
        ])
        return abs(sum(lines.mapped('balance')))

    def _fmt(self, val):
        sym = (self.company_id.currency_id.symbol or 'Q') if self.company_id else 'Q'
        if val is None:
            return '—'
        neg = val < 0
        return f"{'(' if neg else ''}{sym} {abs(val):,.2f}{')' if neg else ''}"

    def _field_row(self, no, label, value, highlight=False):
        bg    = '#fef2f2' if highlight and isinstance(value, (int, float)) and value > 0 else '#ffffff'
        color = '#991b1b' if highlight and isinstance(value, (int, float)) and value > 0 else '#1f2937'
        val_str = self._fmt(value) if isinstance(value, (int, float)) else value
        return (
            f"<tr style='background:{bg};'>"
            f"<td style='padding:6px 10px;border:1px solid #e2e8f0;color:#64748b;width:60px;'>{no}</td>"
            f"<td style='padding:6px 10px;border:1px solid #e2e8f0;'>{label}</td>"
            f"<td style='padding:6px 10px;border:1px solid #e2e8f0;text-align:right;"
            f"font-weight:700;color:{color};'>{val_str}</td>"
            "</tr>"
        )

    def _decl_header(self, title, date_from, date_to, form_ref=''):
        company  = self.company_id
        ref_text = (f"&#160;<span style='color:#94a3b8;font-size:11px;'>{form_ref}</span>"
                    if form_ref else '')
        return (
            f"<div style='background:#0f172a;color:#fff;padding:16px 20px;"
            f"border-radius:8px 8px 0 0;margin-bottom:0;'>"
            f"<div style='font-size:16px;font-weight:800;'>{title}{ref_text}</div>"
            f"<div style='font-size:12px;color:#94a3b8;margin-top:4px;'>"
            f"{escape(company.name)} &bull; NIT: {escape(company.vat or '—')} &bull; "
            f"Período: {date_from} al {date_to}</div>"
            "</div>"
            "<table style='width:100%;border-collapse:collapse;font-size:13px;"
            "border:1px solid #e2e8f0;'>"
            "<thead><tr style='background:#f0f9ff;'>"
            "<th style='padding:6px 10px;border:1px solid #d4e9f3;color:#0369a1;width:60px;'>No.</th>"
            "<th style='padding:6px 10px;border:1px solid #d4e9f3;color:#0369a1;'>Concepto</th>"
            "<th style='padding:6px 10px;border:1px solid #d4e9f3;color:#0369a1;"
            "text-align:right;'>Valor</th>"
            "</tr></thead><tbody>"
        )

    def _stub(self, label):
        return (
            f"<div style='padding:32px;text-align:center;color:#64748b;font-size:14px;'>"
            f"<b>{label}</b><br/>Próximamente disponible.</div>"
        )

    # ── IVA General ───────────────────────────────────────────────────────────

    def _section_header(self, no, title, cols=3):
        return (
            f"<tr style='background:#0369a1;color:#fff;'>"
            f"<td style='padding:5px 10px;border:1px solid #1e4f7a;font-weight:700;"
            f"font-size:12px;' colspan='{cols}'>{no} — {title}</td>"
            "</tr>"
        )

    def _three_col_row(self, no, label, base_val, tax_val,
                       base_lbl='BASE', tax_lbl='IVA', highlight=False):
        bg    = '#fef2f2' if highlight else '#ffffff'
        color = '#991b1b' if highlight else '#1f2937'
        def _fv(v):
            if v is None or v == '':
                return '—'
            if isinstance(v, str):
                return v          # already formatted string, return as-is
            neg = v < 0
            return f"{'(' if neg else ''}{abs(v):,.2f}{')' if neg else ''}"
        return (
            f"<tr style='background:{bg};'>"
            f"<td style='padding:5px 10px;border:1px solid #e2e8f0;color:#64748b;width:40px;'>{no}</td>"
            f"<td style='padding:5px 10px;border:1px solid #e2e8f0;color:{color};'>{label}</td>"
            f"<td style='padding:5px 10px;border:1px solid #e2e8f0;text-align:right;font-weight:700;color:{color};'>{_fv(base_val)}</td>"
            f"<td style='padding:5px 10px;border:1px solid #e2e8f0;text-align:right;font-weight:700;color:{color};'>{_fv(tax_val)}</td>"
            "</tr>"
        )

    def _decl_header_4col(self, title, date_from, date_to, form_ref='', col3='BASE', col4='DÉBITO'):
        company  = self.company_id
        ref_text = (f"&#160;<span style='color:#94a3b8;font-size:11px;'>{form_ref}</span>"
                    if form_ref else '')
        return (
            f"<div style='background:#0f172a;color:#fff;padding:16px 20px;"
            f"border-radius:8px 8px 0 0;margin-bottom:0;'>"
            f"<div style='font-size:16px;font-weight:800;'>{title}{ref_text}</div>"
            f"<div style='font-size:12px;color:#94a3b8;margin-top:4px;'>"
            f"{escape(company.name)} &bull; NIT: {escape(company.vat or '—')} &bull; "
            f"Período: {date_from} al {date_to}</div>"
            "</div>"
            "<table style='width:100%;border-collapse:collapse;font-size:13px;"
            "border:1px solid #e2e8f0;'>"
            "<thead><tr style='background:#f0f9ff;'>"
            "<th style='padding:6px 10px;border:1px solid #d4e9f3;color:#0369a1;width:40px;'>No.</th>"
            "<th style='padding:6px 10px;border:1px solid #d4e9f3;color:#0369a1;'>Concepto</th>"
            f"<th style='padding:6px 10px;border:1px solid #d4e9f3;color:#0369a1;text-align:right;width:120px;'>{col3}</th>"
            f"<th style='padding:6px 10px;border:1px solid #d4e9f3;color:#0369a1;text-align:right;width:120px;'>{col4}</th>"
            "</tr></thead><tbody>"
        )

    def _subtotal_row(self, label, base_val, tax_val):
        def _fv(v):
            if v is None or v == '':
                return '—'
            if isinstance(v, str):
                return v
            return f"{abs(v):,.2f}"
        return (
            f"<tr style='background:#1e3a5f;color:#fff;'>"
            f"<td style='padding:5px 10px;border:1px solid #1e4f7a;' colspan='2'>"
            f"<b>{label}</b></td>"
            f"<td style='padding:5px 10px;border:1px solid #1e4f7a;text-align:right;font-weight:700;'>{_fv(base_val)}</td>"
            f"<td style='padding:5px 10px;border:1px solid #1e4f7a;text-align:right;font-weight:700;'>{_fv(tax_val)}</td>"
            "</tr>"
        )

    def _sum_book_lines_by_category(self, book_type, df, dt):
        """Aggregate compras/ventas book lines by category for SAT-2237."""
        is_compras  = (book_type == 'compras')
        move_types  = ['in_invoice', 'in_refund'] if is_compras else ['out_invoice', 'out_refund']
        iva_cat     = 'iva_compras' if is_compras else 'iva_ventas'
        company_ids = [self.company_id.id]

        configs     = self.env['ktx.satgt.tax.config'].search([
            ('company_id', 'in', company_ids),
        ])
        tax_cat_map = {cfg.tax_id.id: cfg.category for cfg in configs}

        domain = [
            ('move_type', 'in', move_types),
            ('state', '=', 'posted'),
            ('date', '>=', df),
            ('date', '<=', dt),
            ('company_id', 'in', company_ids),
        ]
        moves = self.env['account.move'].search(domain)

        totals = {
            'local_grav_bienes': 0.0, 'local_grav_serv': 0.0,
            'local_exe_bienes':  0.0, 'local_exe_serv':  0.0,
            'import_grav_bienes': 0.0, 'import_grav_serv': 0.0,
            'import_exe_bienes':  0.0, 'import_exe_serv':  0.0,
            'pequeno_cont': 0.0, 'fuel': 0.0,
            'iva': 0.0,
        }

        IMPORT_CATS = {'import_grav_bienes', 'import_grav_serv',
                       'import_exe_bienes',  'import_exe_serv'}
        EXE_CATS    = {'local_exe_bienes', 'local_exe_serv',
                       'import_exe_bienes', 'import_exe_serv'}
        IVA_CATS    = {'iva_compras', 'iva_ventas'}
        fuel_tax_ids = set(self.company_id.ktx_fuel_tax_ids.ids)

        def _is_iva(tax):
            name = (tax.name or '').lower()
            return (tax.amount_type == 'percent' and tax.amount == 12
                    and not any(w in name for w in ('retenci', 'retencion', 'ret ', 'isr', 'renta')))

        _refund_types = frozenset({'in_refund', 'out_refund'})

        for move in moves:
            sign = -1 if move.move_type in _refund_types else 1
            for line in move.invoice_line_ids.filtered(lambda l: l.display_type == 'product'):
                cats   = {tax_cat_map.get(t.id) for t in line.tax_ids if t.id in tax_cat_map}
                cats.discard(None)
                amount = sign * abs(line.balance)
                is_svc = bool(line.product_id and line.product_id.type == 'service')
                sfx    = '_serv' if is_svc else '_bienes'

                # 1) Pequeño Contribuyente (new boolean flag or legacy category)
                is_pc = ('pequeno_cont' in cats) or any(
                    t.ktx_is_pequeno for t in line.tax_ids if t.ktx_include_in_report
                )
                if is_pc:
                    totals['pequeno_cont'] += amount
                    continue
                # 2) Combustibles (configured fuel taxes) — only for compras
                if is_compras and fuel_tax_ids and (set(line.tax_ids.ids) & fuel_tax_ids):
                    totals['fuel'] += amount
                    continue
                # 3) Importación (explicit category)
                import_cats = cats & IMPORT_CATS
                if import_cats:
                    cat = next(iter(import_cats))
                    if cat in totals:
                        totals[cat] += amount
                    continue
                # 4) Exenta local (explicit category)
                exe_cats = cats & EXE_CATS
                if exe_cats:
                    totals['local_exe' + sfx] += amount
                    continue
                # 5) Gravada local (explicit IVA category or detected 12% IVA)
                if cats & IVA_CATS:
                    totals['local_grav' + sfx] += amount
                else:
                    lt = list(line.tax_ids)
                    if any(_is_iva(t) for t in lt):
                        totals['local_grav' + sfx] += amount
                    else:
                        totals['local_exe' + sfx] += amount

            for tl in move.line_ids.filtered(lambda l: l.tax_line_id):
                tax = tl.tax_line_id
                cat = tax_cat_map.get(tax.id)
                if cat in IVA_CATS or (cat is None and _is_iva(tax)):
                    totals['iva'] += sign * abs(tl.balance)

        return totals

    def _html_iva_general(self):
        if not self.company_id or not self.iva_date_from:
            return ''
        df, dt = self.iva_date_from, self.iva_date_to

        ventas  = self._sum_book_lines_by_category('ventas',  df, dt)
        compras = self._sum_book_lines_by_category('compras', df, dt)

        # Remanente período anterior: saldo de las cuentas al cierre del mes previo.
        prev_day        = df - relativedelta(days=1)
        rem_ant         = abs(self._account_balance(self.company_id.ktx_iva_rem_account_id, prev_day))
        ret_anterior    = abs(self._account_balance(self.company_id.ktx_iva_ret_account_id, prev_day))

        # Retenciones del período = suma de cargos al DEBE en la cuenta de
        # retenciones IVA durante el mes a declarar.
        iva_ret_account = self.company_id.ktx_iva_ret_account_id
        if iva_ret_account:
            ret_lines = self.env['account.move.line'].search([
                ('move_id.state', '=', 'posted'),
                ('account_id', '=', iva_ret_account.id),
                ('company_id', '=', self.company_id.id),
                ('date', '>=', df), ('date', '<=', dt),
            ])
            iva_ret = sum(ret_lines.mapped('debit'))
        else:
            iva_ret = 0.0

        # IVA exenciones = suma de cargos al DEBE en la cuenta de exenciones
        # (IVA conforme constancias de exención recibidas) durante el período.
        exencion_account = self.company_id.ktx_iva_exencion_account_id
        if exencion_account:
            exc_lines = self.env['account.move.line'].search([
                ('move_id.state', '=', 'posted'),
                ('account_id', '=', exencion_account.id),
                ('company_id', '=', self.company_id.id),
                ('date', '>=', df), ('date', '<=', dt),
            ])
            iva_exenciones = sum(exc_lines.mapped('debit'))
        else:
            iva_exenciones = 0.0

        # Saldos al cierre del período actual (crédito/retenciones que pasan al siguiente)
        rem_siguiente   = abs(self._account_balance(self.company_id.ktx_iva_rem_account_id, dt))
        ret_siguiente   = abs(self._account_balance(self.company_id.ktx_iva_ret_account_id, dt))

        # Section 3 — Débito fiscal por operaciones locales
        exe_ventas      = ventas['local_exe_bienes'] + ventas['local_exe_serv']
        grav_bienes_v   = ventas['local_grav_bienes']
        grav_serv_v     = ventas['local_grav_serv']
        debito_bienes   = round(grav_bienes_v * 0.12, 2)
        debito_serv     = round(grav_serv_v   * 0.12, 2)
        subtotal3_base  = grav_bienes_v + grav_serv_v + exe_ventas
        subtotal3_deb   = debito_bienes + debito_serv

        # Section 5 — Crédito fiscal por operaciones locales
        # Compras que no generan crédito fiscal = exentas locales + importación exentas
        no_credito      = (compras['local_exe_bienes'] + compras['local_exe_serv']
                           + compras['import_exe_bienes'] + compras['import_exe_serv'])
        pequeno_compras = compras['pequeno_cont']
        fuel_compras    = compras['fuel']
        grav_bienes_c   = compras['local_grav_bienes']   # ya excluye combustibles
        grav_serv_c     = compras['local_grav_serv']
        debito_fuel     = round(fuel_compras  * 0.12, 2)
        credito_bienes  = round(grav_bienes_c * 0.12, 2)
        credito_serv    = round(grav_serv_c   * 0.12, 2)
        subtotal5_base  = (no_credito + pequeno_compras + fuel_compras
                           + grav_bienes_c + grav_serv_c)
        subtotal5_cred  = credito_bienes + credito_serv + debito_fuel + rem_ant + iva_exenciones

        # Section 7 — Determinación
        diferencia      = subtotal3_deb - subtotal5_cred
        imp_a_pagar_det = max(diferencia, 0.0)
        saldo_imp       = imp_a_pagar_det
        ret_periodo     = iva_ret
        imp_final       = max(saldo_imp - ret_anterior - ret_periodo, 0.0)

        html = self._decl_header_4col(
            'Declaración Sombra — IVA General', df, dt, 'Formulario SAT-2237',
            col3='BASE', col4='DÉBITO / CRÉDITO',
        )

        # Section 3
        html += self._section_header('Sección 3', 'DÉBITO FISCAL POR OPERACIONES LOCALES', cols=4)
        html += self._three_col_row('3.1', 'Ventas exentas y servicios exentos', exe_ventas, 0.0)
        html += self._three_col_row('3.2', 'Ventas gravadas — Bienes', grav_bienes_v, debito_bienes)
        html += self._three_col_row('3.3', 'Servicios gravados', grav_serv_v, debito_serv)
        html += self._subtotal_row('SUBTOTAL DÉBITO', subtotal3_base, subtotal3_deb)

        # Section 5
        html += self._section_header('Sección 5', 'CRÉDITO FISCAL POR OPERACIONES LOCALES', cols=4)
        html += self._three_col_row('5.1', 'Compras que no generan crédito fiscal (exentas)', no_credito, 0.0)
        html += self._three_col_row('5.2', 'Compras a Pequeños Contribuyentes', pequeno_compras, 0.0)
        html += self._three_col_row('5.3', 'Compras de combustibles', fuel_compras, debito_fuel)
        html += self._three_col_row('5.4', 'Otras compras de bienes', grav_bienes_c, credito_bienes)
        html += self._three_col_row('5.5', 'Servicios adquiridos', grav_serv_c, credito_serv)
        html += self._three_col_row('5.6', 'Remanente crédito fiscal período anterior', rem_ant, rem_ant)
        html += self._three_col_row('5.7', 'IVA conforme constancias de exención recibidas', iva_exenciones, iva_exenciones)
        html += self._subtotal_row('SUBTOTAL CRÉDITO', subtotal5_base, subtotal5_cred)

        # Section 7
        html += self._section_header('Sección 7', 'DETERMINACIÓN DEL IMPUESTO', cols=4)
        html += self._three_col_row('7.1', 'Crédito fiscal para el período siguiente', rem_siguiente, rem_siguiente)
        html += self._three_col_row('7.2', 'Impuesto a pagar (Débito − Crédito)', imp_a_pagar_det, imp_a_pagar_det, highlight=(imp_a_pagar_det > 0))
        html += self._three_col_row('7.3', 'SALDO DEL IMPUESTO', '', saldo_imp)
        html += self._three_col_row('7.4', 'Remanente retenciones IVA período anterior', '', ret_anterior)
        html += self._three_col_row('7.5', '(-) Retenciones IVA del período', '', ret_periodo)
        html += self._three_col_row('7.6', 'Saldo retenciones siguiente período', '', ret_siguiente)
        html += self._subtotal_row('IMPUESTO A PAGAR', '', imp_final)

        html += "</tbody></table>"
        return html

    # ── IVA Pequeño Contribuyente ─────────────────────────────────────────────

    def _html_iva_pc(self):
        if not self.company_id or not self.iva_date_from:
            return ''
        df, dt = self.iva_date_from, self.iva_date_to
        ventas_lines = self.env['account.move.line'].search([
            ('move_id.state', '=', 'posted'),
            ('move_id.move_type', 'in', ['out_invoice', 'out_refund']),
            ('date', '>=', df), ('date', '<=', dt),
            ('company_id', '=', self.company_id.id),
            ('account_id.account_type', 'in', ['income', 'income_other']),
        ])
        total_ventas = abs(sum(ventas_lines.mapped('balance')))
        iva_pc       = total_ventas * 0.05

        html  = self._decl_header('Declaración Sombra — IVA Pequeño Contribuyente', df, dt)
        html += self._field_row(1, 'Total Ventas del período', total_ventas)
        html += self._field_row(2, 'Tasa IVA Pequeño Contribuyente', '5%')
        html += self._field_row(3, 'IVA Por Pagar (1 × 5%)', iva_pc, highlight=True)
        html += "</tbody></table>"
        return html

    # ── ISR Mensual (Opcional Simplificado) ───────────────────────────────────

    def _html_isr_mensual(self):
        if not self.company_id or not self.isr_men_date_from:
            return ''
        df, dt = self.isr_men_date_from, self.isr_men_date_to

        # ── Sección 1: Ingresos ──────────────────────────────────────────────
        # Ingresos afectos: cuentas de tipo income/income_other que NO están
        # marcadas como exentas de ISR.
        afectos_lines = self.env['account.move.line'].search([
            ('move_id.state', '=', 'posted'),
            ('move_id.move_type', 'in', ['out_invoice', 'out_refund']),
            ('date', '>=', df), ('date', '<=', dt),
            ('company_id', '=', self.company_id.id),
            ('account_id.account_type', 'in', ['income', 'income_other']),
            ('account_id.ktx_isr_exento', '=', False),
        ])
        ingresos_afectos = abs(sum(afectos_lines.mapped('balance')))

        # Ingresos exentos: mismas condiciones pero con ktx_isr_exento = True
        exentos_lines = self.env['account.move.line'].search([
            ('move_id.state', '=', 'posted'),
            ('move_id.move_type', 'in', ['out_invoice', 'out_refund']),
            ('date', '>=', df), ('date', '<=', dt),
            ('company_id', '=', self.company_id.id),
            ('account_id.account_type', 'in', ['income', 'income_other']),
            ('account_id.ktx_isr_exento', '=', True),
        ])
        ingresos_exentos = abs(sum(exentos_lines.mapped('balance')))
        base_imponible   = max(ingresos_afectos - ingresos_exentos, 0.0)

        # ── Sección 2: Determinación del ISR ────────────────────────────────
        # Tasa: 5% hasta Q30,000/mes, 7% sobre el excedente.
        UMBRAL = 30_000.0
        base_5    = min(base_imponible, UMBRAL)
        base_7    = max(base_imponible - UMBRAL, 0.0)
        isr_5     = round(base_5 * 0.05, 2)
        isr_7     = round(base_7 * 0.07, 2)
        isr_det   = isr_5 + isr_7

        # ── Sección 3: Retenciones disponibles ──────────────────────────────
        # Remanente anterior = saldo final del mes previo (acumulado hasta el
        # día anterior al inicio del período).
        # Retenciones del período = suma de cargos al DEBE de la cuenta durante
        # el mes a declarar (cada retención que se practicó y se registró).
        prev_day      = df - relativedelta(days=1)
        remanente_ant = abs(self._account_balance(self.company_id.ktx_isr_ret_account_id, prev_day))
        ret_account   = self.company_id.ktx_isr_ret_account_id
        if ret_account:
            ret_lines   = self.env['account.move.line'].search([
                ('move_id.state', '=', 'posted'),
                ('account_id', '=', ret_account.id),
                ('company_id', '=', self.company_id.id),
                ('date', '>=', df), ('date', '<=', dt),
            ])
            ret_periodo = sum(ret_lines.mapped('debit'))
        else:
            ret_periodo = 0.0
        total_ret = remanente_ant + ret_periodo

        # ── Sección 4: Resultado ─────────────────────────────────────────────
        isr_a_pagar   = max(isr_det - total_ret, 0.0)
        excedente_ret = max(total_ret - isr_det, 0.0)

        html = self._decl_header(
            'Declaración Sombra — ISR Mensual', df, dt,
            'Opcional Simplificado s/ Ingresos',
        )

        # Sección 1
        html += (
            "<tr style='background:#0369a1;color:#fff;'>"
            "<td colspan='3' style='padding:5px 10px;border:1px solid #1e4f7a;"
            "font-weight:700;font-size:12px;'>Sección 1 — INGRESOS DEL PERÍODO</td></tr>"
        )
        html += self._field_row('1.1', 'Ingresos afectos al ISR', ingresos_afectos)
        html += self._field_row('1.2', '(-) Ingresos exentos del ISR', ingresos_exentos)
        html += self._field_row('1.3', '(=) Base Imponible', base_imponible)

        # Sección 2
        html += (
            "<tr><td colspan='3' style='border-top:2px solid #0369a1;padding:0;'></td></tr>"
            "<tr style='background:#0369a1;color:#fff;'>"
            "<td colspan='3' style='padding:5px 10px;border:1px solid #1e4f7a;"
            "font-weight:700;font-size:12px;'>Sección 2 — DETERMINACIÓN DEL IMPUESTO</td></tr>"
        )
        html += self._field_row('2.1', f'Base gravada al 5% (hasta Q{UMBRAL:,.0f})', base_5)
        html += self._field_row('2.2', 'ISR al 5%', isr_5)
        html += self._field_row('2.3', f'Base gravada al 7% (sobre Q{UMBRAL:,.0f})', base_7)
        html += self._field_row('2.4', 'ISR al 7%', isr_7)
        html += self._field_row('2.5', 'ISR Determinado (2.2 + 2.4)', isr_det)

        # Sección 3
        html += (
            "<tr><td colspan='3' style='border-top:2px solid #0369a1;padding:0;'></td></tr>"
            "<tr style='background:#0369a1;color:#fff;'>"
            "<td colspan='3' style='padding:5px 10px;border:1px solid #1e4f7a;"
            "font-weight:700;font-size:12px;'>Sección 3 — RETENCIONES DISPONIBLES</td></tr>"
        )
        html += self._field_row(
            '3.1',
            f'Remanente retenciones período anterior (saldo al {prev_day.strftime("%d/%m/%Y")})',
            remanente_ant,
        )
        html += self._field_row('3.2', 'Retenciones practicadas en el período', ret_periodo)
        html += self._field_row('3.3', 'Total retenciones disponibles (3.1 + 3.2)', total_ret)

        # Sección 4
        html += (
            "<tr><td colspan='3' style='border-top:2px solid #0369a1;padding:0;'></td></tr>"
            "<tr style='background:#0369a1;color:#fff;'>"
            "<td colspan='3' style='padding:5px 10px;border:1px solid #1e4f7a;"
            "font-weight:700;font-size:12px;'>Sección 4 — RESULTADO</td></tr>"
        )
        if isr_a_pagar > 0:
            html += self._field_row('4.1', 'ISR A PAGAR', isr_a_pagar, highlight=True)
            html += self._field_row('4.2', 'Excedente de retenciones período siguiente', 0.0)
        else:
            html += self._field_row('4.1', 'ISR A PAGAR', 0.0)
            html += self._field_row(
                '4.2',
                'Excedente de retenciones para aplicar en período siguiente',
                excedente_ret,
                highlight=False,
            )

        html += "</tbody></table>"
        return html

    # ── ISR Trimestral (Sobre Utilidades, acumulado) ──────────────────────────

    def _html_isr_trim(self):
        if not self.company_id or not self.isr_trim_quarter:
            return ''
        q    = int(self.isr_trim_quarter)
        year = self.isr_trim_year or date.today().year
        df, dt = self._quarter_range(year, q)

        renta_bruta = self._sum_account_type(['income', 'income_other'], df, dt)
        gastos      = self._sum_account_type(
            ['expense', 'expense_depreciation', 'expense_direct_cost'], df, dt,
        )
        ret_isr          = self._sum_tax_cat('isr_retencion', df, dt)
        # Valores obtenidos de las cuentas contables configuradas
        gnd              = self._sum_non_deductible(df, dt)
        iso_acreditar    = abs(self._account_balance(self.company_id.ktx_iso_trim_account_id, dt))
        incentivos       = self.isr_trim_incentivos or 0.0
        # ISR acumulado del trimestre anterior = saldo de la cuenta ISR
        # trimestral al cierre del trimestre previo (día anterior a df... pero
        # como el período es acumulado desde el 1-ene, el trimestre anterior
        # termina el día anterior al inicio del trimestre actual).
        prev_q_end       = date(year, (q - 1) * 3, 1) + relativedelta(months=1) - relativedelta(days=1) if q > 1 else None
        prev             = abs(self._account_balance(self.company_id.ktx_isr_trim_account_id, prev_q_end)) if prev_q_end else 0.0

        renta_neta       = renta_bruta - gastos
        renta_imponible  = max(renta_neta + gnd, 0.0)
        perdida_fiscal   = max(-(renta_neta + gnd), 0.0)
        isr_calculado    = renta_imponible * 0.25
        isr_trimestre    = max(isr_calculado - prev, 0.0)
        valor_favor_perd = max(prev - isr_calculado, 0.0)

        # Section 5 — Liquidación
        subtotal_liq     = max(isr_trimestre - iso_acreditar, 0.0)
        imp_final        = max(subtotal_liq - incentivos, 0.0)

        html = self._decl_header(
            f'Declaración Sombra — ISR Trimestral T{q}', df, dt, 'SAT-1361',
        )

        # Section 3
        html += (
            "<tr style='background:#0369a1;color:#fff;'>"
            "<td colspan='3' style='padding:5px 10px;border:1px solid #1e4f7a;"
            "font-weight:700;font-size:12px;'>Sección 3 — DETERMINACIÓN DEL IMPUESTO</td></tr>"
        )
        html += self._field_row('3.1', f'Renta bruta acumulada (Ene–{dt.strftime("%b")})', renta_bruta)
        html += self._field_row('3.2', '(-) Rentas sujetas a retención definitiva', 0.0)
        html += self._field_row('3.3', '(-) Costos y gastos acumulados', gastos)
        html += self._field_row('3.4', '(+) Costos y gastos retención definitiva', 0.0)
        html += self._field_row('3.5', '(+) Costos y gastos no deducibles', gnd)
        if renta_imponible > 0:
            html += self._field_row('3.6', '(=) Renta Imponible acumulada', renta_imponible)
        else:
            html += self._field_row('3.6', '(=) Pérdida Fiscal acumulada', perdida_fiscal)
        html += self._field_row('3.7', 'Impuesto Sobre la Renta (25%)', isr_calculado)
        html += self._field_row('3.8', '(-) ISR acumulado trimestre anterior', prev)
        html += self._field_row('3.9', 'Impuesto determinado en este trimestre', isr_trimestre)
        html += self._field_row('3.10', 'Valor a favor por pérdida en el trimestre', valor_favor_perd)

        # Section 5 — Liquidación
        html += (
            "<tr><td colspan='3' style='border-top:2px solid #0369a1;padding:0;'></td></tr>"
            "<tr style='background:#0369a1;color:#fff;'>"
            "<td colspan='3' style='padding:5px 10px;border:1px solid #1e4f7a;"
            "font-weight:700;font-size:12px;'>Sección 5 — LIQUIDACIÓN</td></tr>"
        )
        html += self._field_row('5.1', 'Impuesto a pagar', isr_trimestre)
        html += self._field_row('5.2', 'Saldo ISO períodos anteriores', iso_acreditar)
        html += self._field_row('5.3', '(-) Acreditamiento ISO', iso_acreditar)
        html += self._field_row('5.4', 'Sub-total', subtotal_liq)
        html += self._field_row('5.5', '(-) Incentivos Fiscales', incentivos)
        html += self._field_row('5.6', 'IMPUESTO A PAGAR', imp_final, highlight=True)

        html += "</tbody></table>"
        return html

    # ── ISR Anual ─────────────────────────────────────────────────────────────

    def _html_isr_anual(self):
        if not self.company_id or not self.isr_anual_year:
            return ''
        regime = self.company_id.ktx_isr_regime or 'opcional'
        if regime == 'opcional':
            return self._html_isr_anual_opcional()
        return self._html_isr_anual_utilidades()

    def _html_isr_anual_opcional(self):
        year = self.isr_anual_year
        df   = date(year, 1, 1)
        dt   = date(year, 12, 31)

        # Ingresos afectos y exentos (misma lógica que ISR mensual pero anual)
        afectos_lines = self.env['account.move.line'].search([
            ('move_id.state', '=', 'posted'),
            ('move_id.move_type', 'in', ['out_invoice', 'out_refund']),
            ('date', '>=', df), ('date', '<=', dt),
            ('company_id', '=', self.company_id.id),
            ('account_id.account_type', 'in', ['income', 'income_other']),
            ('account_id.ktx_isr_exento', '=', False),
        ])
        ingresos_afectos = abs(sum(afectos_lines.mapped('balance')))

        exentos_lines = self.env['account.move.line'].search([
            ('move_id.state', '=', 'posted'),
            ('move_id.move_type', 'in', ['out_invoice', 'out_refund']),
            ('date', '>=', df), ('date', '<=', dt),
            ('company_id', '=', self.company_id.id),
            ('account_id.account_type', 'in', ['income', 'income_other']),
            ('account_id.ktx_isr_exento', '=', True),
        ])
        ingresos_exentos = abs(sum(exentos_lines.mapped('balance')))
        base_imponible   = max(ingresos_afectos - ingresos_exentos, 0.0)

        # Tasa anual: 5% hasta Q360,000 (Q30,000/mes × 12), 7% sobre el excedente.
        UMBRAL_ANUAL = 360_000.0
        base_5   = min(base_imponible, UMBRAL_ANUAL)
        base_7   = max(base_imponible - UMBRAL_ANUAL, 0.0)
        isr_5    = round(base_5 * 0.05, 2)
        isr_7    = round(base_7 * 0.07, 2)
        isr_det  = isr_5 + isr_7

        # Pagos de ISR efectuados y retenciones: mismo rango Feb→Ene+1 que las
        # declaraciones mensuales.
        df_pagos = date(year, 2, 1)
        dt_pagos = date(year + 1, 1, 31)

        # Retenciones ISR practicadas en el período = suma de cargos al DEBE
        # de la cuenta ISR Retenciones por Compensar (ktx_isr_ret_account_id)
        # en el rango Feb→Ene+1 (suma de lo declarado mensualmente).
        ret_account = self.company_id.ktx_isr_ret_account_id
        if ret_account:
            ret_lines = self.env['account.move.line'].search([
                ('move_id.state', '=', 'posted'),
                ('account_id', '=', ret_account.id),
                ('company_id', '=', self.company_id.id),
                ('date', '>=', df_pagos), ('date', '<=', dt_pagos),
            ])
            retenciones_periodo = sum(ret_lines.mapped('debit'))
        else:
            retenciones_periodo = 0.0

        saldo_segun_decl = max(isr_det - retenciones_periodo, 0.0)

        # Pagos de ISR efectuados = suma de los movimientos al HABER de la
        # cuenta ISR por Pagar desde febrero del año declarado hasta enero del
        # año siguiente (Feb año → Ene año+1).
        isr_account = self.company_id.ktx_isr_account_id
        if isr_account:
            pago_lines = self.env['account.move.line'].search([
                ('move_id.state', '=', 'posted'),
                ('account_id', '=', isr_account.id),
                ('company_id', '=', self.company_id.id),
                ('date', '>=', df_pagos), ('date', '<=', dt_pagos),
            ])
            pagos_efectuados = sum(pago_lines.mapped('credit'))
        else:
            pagos_efectuados = 0.0

        isr_a_pagar = max(saldo_segun_decl - pagos_efectuados, 0.0)
        pago_exceso = max(pagos_efectuados - saldo_segun_decl, 0.0)

        html = self._decl_header(
            f'Declaración Sombra — ISR Anual {year}', df, dt,
            'Opcional Simplificado — Liquidación Anual',
        )

        # Sección 1 — Ingresos
        html += (
            "<tr style='background:#0369a1;color:#fff;'>"
            "<td colspan='3' style='padding:5px 10px;border:1px solid #1e4f7a;"
            "font-weight:700;font-size:12px;'>Sección 1 — INGRESOS DEL AÑO</td></tr>"
        )
        html += self._field_row('1.1', 'Ingresos afectos al ISR', ingresos_afectos)
        html += self._field_row('1.2', '(-) Ingresos exentos del ISR', ingresos_exentos)
        html += self._field_row('1.3', '(=) Base Imponible', base_imponible)

        # Sección 2 — Determinación
        html += (
            "<tr><td colspan='3' style='border-top:2px solid #0369a1;padding:0;'></td></tr>"
            "<tr style='background:#0369a1;color:#fff;'>"
            "<td colspan='3' style='padding:5px 10px;border:1px solid #1e4f7a;"
            "font-weight:700;font-size:12px;'>Sección 2 — DETERMINACIÓN DEL IMPUESTO</td></tr>"
        )
        html += self._field_row('2.1', f'Base gravada al 5% (hasta Q{UMBRAL_ANUAL:,.0f})', base_5)
        html += self._field_row('2.2', 'ISR al 5%', isr_5)
        html += self._field_row('2.3', f'Base gravada al 7% (sobre Q{UMBRAL_ANUAL:,.0f})', base_7)
        html += self._field_row('2.4', 'ISR al 7%', isr_7)
        html += self._field_row('2.5', 'ISR Determinado anual (2.2 + 2.4)', isr_det)

        # Sección 3 — Retenciones practicadas según declaraciones mensuales
        html += (
            "<tr><td colspan='3' style='border-top:2px solid #0369a1;padding:0;'></td></tr>"
            "<tr style='background:#0369a1;color:#fff;'>"
            "<td colspan='3' style='padding:5px 10px;border:1px solid #1e4f7a;"
            "font-weight:700;font-size:12px;'>Sección 3 — RETENCIONES SEGÚN DECLARACIONES MENSUALES</td></tr>"
        )
        html += self._field_row(
            '3.1',
            f'(-) Retenciones ISR practicadas en el período '
            f'(Feb {year} – Ene {year + 1}, cargos al debe Cta. ISR Retenciones)',
            retenciones_periodo,
        )
        html += self._field_row(
            '3.2',
            '(=) Saldo del impuesto determinado según declaraciones mensuales',
            saldo_segun_decl,
        )

        # Sección 4 — Pagos de ISR efectuados según declaraciones mensuales
        html += (
            "<tr><td colspan='3' style='border-top:2px solid #0369a1;padding:0;'></td></tr>"
            "<tr style='background:#0369a1;color:#fff;'>"
            "<td colspan='3' style='padding:5px 10px;border:1px solid #1e4f7a;"
            "font-weight:700;font-size:12px;'>Sección 4 — PAGOS DE ISR SEGÚN DECLARACIONES MENSUALES</td></tr>"
        )
        html += self._field_row(
            '4.1',
            f'(-) Impuestos pagados en el período '
            f'(Feb {year} – Ene {year + 1}, créditos en Cuenta ISR por Pagar)',
            pagos_efectuados,
        )

        # Sección 5 — Resultado
        html += (
            "<tr><td colspan='3' style='border-top:2px solid #0369a1;padding:0;'></td></tr>"
            "<tr style='background:#0369a1;color:#fff;'>"
            "<td colspan='3' style='padding:5px 10px;border:1px solid #1e4f7a;"
            "font-weight:700;font-size:12px;'>Sección 5 — RESULTADO</td></tr>"
        )
        if isr_a_pagar > 0:
            html += self._field_row('5.1', 'ISR A PAGAR', isr_a_pagar, highlight=True)
            html += self._field_row('5.2', 'Pago en exceso / saldo a favor', 0.0)
        else:
            html += self._field_row('5.1', 'ISR A PAGAR', 0.0)
            html += self._field_row('5.2', 'Pago en exceso / saldo a favor', pago_exceso)

        html += "</tbody></table>"
        return html

    def _html_isr_anual_utilidades(self):
        year = self.isr_anual_year
        df   = date(year, 1, 1)
        dt   = date(year, 12, 31)

        ventas  = self._sum_account_type(['income', 'income_other'], df, dt)
        gastos  = self._sum_account_type(
            ['expense', 'expense_depreciation', 'expense_direct_cost'], df, dt,
        )
        ret_isr       = self._sum_tax_cat('isr_retencion', df, dt)
        gnd           = self._sum_non_deductible(df, dt)
        iso_acreditar = abs(self._account_balance(self.company_id.ktx_iso_trim_account_id, dt))
        incentivos    = self.isr_anual_incentivos or 0.0
        # Pagos trimestrales ISR = suma de cargos al DEBE de la cuenta ISR
        # Trimestral durante el año declarado (T1 + T2 + T3 acumulados).
        trim_account  = self.company_id.ktx_isr_trim_account_id
        if trim_account:
            trim_lines = self.env['account.move.line'].search([
                ('move_id.state', '=', 'posted'),
                ('account_id', '=', trim_account.id),
                ('company_id', '=', self.company_id.id),
                ('date', '>=', df), ('date', '<=', dt),
            ])
            prev = sum(trim_lines.mapped('debit'))
        else:
            prev = 0.0

        renta_neta       = ventas - gastos
        renta_imponible  = max(renta_neta + gnd, 0.0)
        perdida_fiscal   = max(-(renta_neta + gnd), 0.0)
        isr_calculado    = renta_imponible * 0.25
        saldo_iso        = max(isr_calculado - iso_acreditar, 0.0)
        isr_a_pagar      = max(saldo_iso - prev - ret_isr, 0.0)
        pago_exceso      = max(prev + ret_isr - saldo_iso, 0.0)

        html = self._decl_header(
            f'Declaración Sombra — ISR Anual {year}', df, dt, 'SAT-1411 Liquidación Definitiva',
        )

        # Section 8.1 — Ingresos
        html += (
            "<tr style='background:#0369a1;color:#fff;'>"
            "<td colspan='3' style='padding:5px 10px;border:1px solid #1e4f7a;"
            "font-weight:700;font-size:12px;'>Sección 8.1 — INGRESOS</td></tr>"
        )
        html += self._field_row('8.1', 'Ingresos brutos del año', ventas)

        # Section 8.3 — Gastos
        html += (
            "<tr style='background:#0369a1;color:#fff;'>"
            "<td colspan='3' style='padding:5px 10px;border:1px solid #1e4f7a;"
            "font-weight:700;font-size:12px;'>Sección 8.3 — GASTOS</td></tr>"
        )
        html += self._field_row('8.3', 'Total costos y gastos deducibles', gastos)

        # Section 8.4 — Determinación
        html += (
            "<tr style='background:#0369a1;color:#fff;'>"
            "<td colspan='3' style='padding:5px 10px;border:1px solid #1e4f7a;"
            "font-weight:700;font-size:12px;'>Sección 8.4 — DETERMINACIÓN RENTA IMPONIBLE</td></tr>"
        )
        html += self._field_row('8.4.1', 'Renta Neta / Pérdida Neta (Ingresos − Gastos)', renta_neta)
        html += self._field_row('8.4.2', '(+) Costos y gastos no deducibles', gnd)
        if renta_imponible > 0:
            html += self._field_row('8.4.3', '(=) Renta Imponible', renta_imponible)
        else:
            html += self._field_row('8.4.3', '(=) Pérdida Fiscal', perdida_fiscal)
        html += self._field_row('8.4.4', 'Impuesto Sobre la Renta (25%)', isr_calculado)

        # Acreditamientos
        html += (
            "<tr><td colspan='3' style='border-top:2px solid #0369a1;padding:0;'></td></tr>"
            "<tr style='background:#0369a1;color:#fff;'>"
            "<td colspan='3' style='padding:5px 10px;border:1px solid #1e4f7a;"
            "font-weight:700;font-size:12px;'>ACREDITAMIENTOS</td></tr>"
        )
        html += self._field_row('A.1', '(-) ISO / IETAAP a acreditar', iso_acreditar)
        html += self._field_row('A.2', 'SALDO DEL IMPUESTO', saldo_iso)
        html += self._field_row('A.3', '(-) Pagos trimestrales ISR (cargos debe Cta. ISR Trimestral)', prev)
        html += self._field_row('A.4', '(-) Retenciones ISR del año', ret_isr)
        if isr_a_pagar > 0:
            html += self._field_row('A.5', 'IMPUESTO SOBRE LA RENTA A PAGAR', isr_a_pagar, highlight=True)
        else:
            html += self._field_row('A.5', 'PAGO EN EXCESO (saldo a favor)', pago_exceso)

        html += "</tbody></table>"
        return html

    # ── ISO Trimestral ────────────────────────────────────────────────────────

    def _html_iso_trim(self):
        if not self.company_id or not self.iso_quarter:
            return ''
        q    = int(self.iso_quarter)
        year = self.iso_year or date.today().year
        df, dt = self._iso_quarter_range(year, q)

        activos_lines = self.env['account.move.line'].search([
            ('move_id.state', '=', 'posted'),
            ('date', '<=', dt),
            ('company_id', '=', self.company_id.id),
            ('account_id.account_type', 'in', ['asset_fixed', 'asset_non_current']),
        ])
        activos = abs(sum(activos_lines.mapped('balance')))
        ingresos = self._sum_account_type(['income', 'income_other'], df, dt)

        base_activos  = activos * 0.01 / 4
        base_ingresos = ingresos * 0.01 / 4
        iso           = max(base_activos, base_ingresos)

        html  = self._decl_header(
            f'Declaración Sombra — ISO T{q} {year}', df, dt, 'SAT-1608',
        )
        html += self._field_row(1, 'Activos Netos al cierre del trimestre', activos)
        html += self._field_row(2, 'Ingresos Brutos del trimestre', ingresos)
        html += self._field_row(3, 'Base sobre Activos (1% / 4)', base_activos)
        html += self._field_row(4, 'Base sobre Ingresos (1% / 4)', base_ingresos)
        html += self._field_row(5, 'ISO Por Pagar (mayor de 3 y 4)', iso, highlight=True)
        html += "</tbody></table>"
        return html
