# -*- coding: utf-8 -*-
import logging
from datetime import date
from dateutil.relativedelta import relativedelta
from markupsafe import escape
from odoo import api, fields, models

_logger = logging.getLogger(__name__)

_MONTHS_ES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
               'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

_QUARTERS_ES = ['1er Trimestre', '2do Trimestre', '3er Trimestre', '4to Trimestre']


def _fmt(val, symbol='Q'):
    if val is None:
        return '&#8212;'
    neg = val < 0
    return f"{'(' if neg else ''}{symbol} {abs(val):,.2f}{')' if neg else ''}"


def _first_day_of_month():
    t = date.today()
    return t.replace(day=1)


def _last_day_of_month():
    t = date.today()
    return (t.replace(day=1) + relativedelta(months=1)) - relativedelta(days=1)


def _first_day_of_quarter():
    t = date.today()
    q_month = ((t.month - 1) // 3) * 3 + 1
    return t.replace(month=q_month, day=1)


def _last_day_of_quarter():
    df = _first_day_of_quarter()
    return (df + relativedelta(months=3)) - relativedelta(days=1)


def _period_label_for(period_type, df, dt):
    if not df:
        return ''
    if period_type == 'mes':
        return f"{_MONTHS_ES[df.month - 1]} {df.year}"
    if period_type == 'trim':
        q = (df.month - 1) // 3
        return f"{_QUARTERS_ES[q]} {df.year}"
    if period_type == 'anio':
        return str(df.year)
    return f"{df} &#8212; {dt}"


class SatgtResumen(models.Model):
    _name = 'ktx.satgt.resumen'
    _description = 'Resumen Fiscal SAT GT'
    _rec_name = 'name'

    # Nombre — fija el breadcrumb como "Resumen Fiscal" en lugar de "Nuevo"
    name = fields.Char(default='Resumen Fiscal')

    # Empresas (aplica a todas las secciones)
    company_ids = fields.Many2many(
        'res.company', string='Empresas',
        default=lambda self: self.env.company,
    )

    # ── Filtros IVA (estrictamente mensual) ──────────────────────────────────
    iva_date_from = fields.Date(
        string='IVA Desde', default=lambda self: _first_day_of_month(),
    )
    iva_date_to = fields.Date(
        string='IVA Hasta', default=lambda self: _last_day_of_month(),
    )
    iva_comparison = fields.Selection([
        ('none',      'Sin comparación'),
        ('prev',      'Mes anterior'),
        ('same_year', 'Mismo mes año anterior'),
    ], string='Comparación IVA', default='none')
    iva_period_display = fields.Char(compute='_compute_iva_period_display')

    # ── Filtros ISR (mensual u opcional trimestral) ───────────────────────────
    isr_period_type = fields.Selection([
        ('mes',  'Mensual'),
        ('trim', 'Trimestral'),
    ], string='Período ISR', default='mes')
    isr_date_from = fields.Date(
        string='ISR Desde', default=lambda self: _first_day_of_month(),
    )
    isr_date_to = fields.Date(
        string='ISR Hasta', default=lambda self: _last_day_of_month(),
    )
    isr_comparison = fields.Selection([
        ('none',      'Sin comparación'),
        ('prev',      'Período anterior'),
        ('same_year', 'Mismo período año anterior'),
    ], string='Comparación ISR', default='none')
    isr_period_display = fields.Char(compute='_compute_isr_period_display')

    # ── Secciones HTML ───────────────────────────────────────────────────────
    html_iva    = fields.Html(compute='_compute_html_iva',    sanitize=False)
    html_isr    = fields.Html(compute='_compute_html_isr',    sanitize=False)
    html_iso    = fields.Html(compute='_compute_html_iso',    sanitize=False)
    html_extras = fields.Html(compute='_compute_html_extras', sanitize=False)

    # ── Computed displays ────────────────────────────────────────────────────

    @api.depends('iva_date_from', 'iva_date_to')
    def _compute_iva_period_display(self):
        for rec in self:
            rec.iva_period_display = _period_label_for('mes', rec.iva_date_from, rec.iva_date_to)

    @api.depends('isr_date_from', 'isr_date_to', 'isr_period_type')
    def _compute_isr_period_display(self):
        for rec in self:
            rec.isr_period_display = _period_label_for(
                rec.isr_period_type, rec.isr_date_from, rec.isr_date_to
            )

    # ── Compute HTML ─────────────────────────────────────────────────────────

    @api.depends('company_ids', 'iva_date_from', 'iva_date_to', 'iva_comparison')
    def _compute_html_iva(self):
        for rec in self:
            rec.html_iva = rec._build_iva_html()

    @api.depends('company_ids', 'isr_date_from', 'isr_date_to', 'isr_period_type', 'isr_comparison')
    def _compute_html_isr(self):
        for rec in self:
            rec.html_isr = rec._build_isr_html()

    @api.depends('company_ids')
    def _compute_html_iso(self):
        for rec in self:
            rec.html_iso = rec._build_iso_html()

    @api.depends('company_ids')
    def _compute_html_extras(self):
        for rec in self:
            rec.html_extras = rec._build_extras_html()

    # ── Helpers de query ─────────────────────────────────────────────────────

    def _get_companies(self):
        return self.company_ids or self.env.company

    def _get_tax_ids_for_category(self, company, category):
        configs = self.env['ktx.satgt.tax.config'].search([
            ('company_id', '=', company.id),
            ('category', '=', category),
        ])
        return configs.mapped('tax_id').ids

    def _sum_tax_lines(self, company, category, date_from, date_to, move_types=None):
        tax_ids = self._get_tax_ids_for_category(company, category)
        if not tax_ids:
            return 0.0
        domain = [
            ('move_id.state', '=', 'posted'),
            ('date', '>=', date_from), ('date', '<=', date_to),
            ('company_id', '=', company.id),
            ('tax_line_id', 'in', tax_ids),
        ]
        if move_types:
            domain.append(('move_id.move_type', 'in', move_types))
        lines = self.env['account.move.line'].search(domain)
        return abs(sum(lines.mapped('balance')))

    def _sum_account_balance(self, account, date_to):
        if not account:
            return 0.0
        lines = self.env['account.move.line'].search([
            ('account_id', '=', account.id),
            ('move_id.state', '=', 'posted'),
            ('date', '<=', date_to),
        ])
        return sum(lines.mapped('balance'))

    def _sum_sales_net(self, company, date_from, date_to):
        lines = self.env['account.move.line'].search([
            ('move_id.state', '=', 'posted'),
            ('move_id.move_type', 'in', ['out_invoice', 'out_refund']),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('company_id', '=', company.id),
            ('tax_ids', '!=', False),
            ('account_id.account_type', 'in', ['income', 'income_other']),
        ])
        return abs(sum(lines.mapped('balance')))

    def _sum_account_type(self, company, account_types, date_from, date_to):
        lines = self.env['account.move.line'].search([
            ('move_id.state', '=', 'posted'),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('company_id', '=', company.id),
            ('account_id.account_type', 'in', account_types),
        ])
        return abs(sum(lines.mapped('balance')))

    # ── HTML helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _tbl_header(cols):
        ths = ''.join(
            f"<th style='padding:6px 10px;text-align:{'right' if i > 0 else 'left'};"
            f"border:1px solid #d4e9f3;color:#0369a1;white-space:nowrap;'>{escape(str(c))}</th>"
            for i, c in enumerate(cols)
        )
        return f"<thead><tr style='background:#f0f9ff;'>{ths}</tr></thead>"

    @staticmethod
    def _tbl_row(cells, bold=False, bg='#ffffff', color='#1f2937'):
        style_td = f"padding:5px 10px;border:1px solid #e2e8f0;color:{color};"
        tds = ''.join(
            f"<td style='{style_td}text-align:{'right' if i > 0 else 'left'};"
            f"{'font-weight:700;' if bold else ''}'>{escape(str(c))}</td>"
            for i, c in enumerate(cells)
        )
        return f"<tr style='background:{bg};'>{tds}</tr>"

    def _section_title(self, title, subtitle=''):
        sub = (
            f"<span style='font-size:12px;color:#93c5fd;margin-left:8px;'>{subtitle}</span>"
            if subtitle else ''
        )
        return (
            f"<div style='margin:4px 0 8px;padding:8px 14px;background:#1d4ed8;"
            f"border-radius:6px;display:inline-block;'>"
            f"<span style='color:#fff;font-weight:700;font-size:14px;'>{title}</span>{sub}</div>"
        )

    # ── IVA ──────────────────────────────────────────────────────────────────

    def _build_iva_html(self):
        companies = self._get_companies()
        df, dt = self.iva_date_from, self.iva_date_to
        if not df or not dt:
            return ''
        period = _period_label_for('mes', df, dt)
        prev_day = df - relativedelta(days=1)

        data = []
        for c in companies:
            iva_ventas  = self._sum_tax_lines(c, 'iva_ventas',   df, dt, ['out_invoice', 'out_refund'])
            iva_compras = self._sum_tax_lines(c, 'iva_compras',  df, dt, ['in_invoice',  'in_refund'])
            iva_ret     = self._sum_tax_lines(c, 'iva_retencion', df, dt)
            iva_rem_ant = abs(self._sum_account_balance(c.ktx_iva_rem_account_id, prev_day))
            a_favor     = iva_compras + iva_ret + iva_rem_ant
            diferencia  = iva_ventas - a_favor
            data.append({
                'company':    c,
                'iva_ventas': iva_ventas,
                'iva_compras':iva_compras,
                'iva_ret':    iva_ret,
                'iva_rem_ant':iva_rem_ant,
                'a_favor':    a_favor,
                'credito':    max(-diferencia, 0.0),
                'por_pagar':  max(diferencia, 0.0),
            })

        sym   = companies[0].currency_id.symbol if companies else 'Q'
        multi = len(companies) > 1
        col_names = [''] + ([c.name for c in companies] if multi else ['Importe'])

        html  = self._section_title('IVA', period)
        html += (
            "<table style='width:100%;border-collapse:collapse;font-size:13px;'>"
            + self._tbl_header(col_names) + "<tbody>"
        )
        for label, key, bold, bg in [
            ('IVA Ventas',               'iva_ventas',  False, '#ffffff'),
            ('IVA Compras',              'iva_compras', False, '#f8fafc'),
            ('IVA Retenciones',          'iva_ret',     False, '#ffffff'),
            ('Remanente Mes Anterior',   'iva_rem_ant', False, '#f8fafc'),
            ('Total a Favor',            'a_favor',     True,  '#f0f9ff'),
        ]:
            vals = [_fmt(d[key], sym) for d in data]
            html += self._tbl_row([label] + vals, bold=bold, bg=bg)

        html += (
            "<tr><td colspan='{}' style='border-top:2px solid #1d4ed8;padding:0;'></td></tr>"
            .format(len(companies) + 1)
        )
        cred_vals, pagar_vals = [], []
        for d in data:
            if d['credito'] > 0:
                cred_vals.append(_fmt(d['credito'], sym)); pagar_vals.append('&#8212;')
            else:
                cred_vals.append('&#8212;'); pagar_vals.append(_fmt(d['por_pagar'], sym))

        html += self._tbl_row(
            ['Crédito (Remanente)'] + cred_vals, bold=False, bg='#dcfce7', color='#166534'
        )
        has_deuda = any(d['por_pagar'] > 0 for d in data)
        html += self._tbl_row(
            ['IVA Por Pagar'] + pagar_vals, bold=True,
            bg='#fef2f2' if has_deuda else '#ffffff',
            color='#991b1b' if has_deuda else '#1f2937',
        )
        html += "</tbody></table>"
        return html

    # ── ISR ──────────────────────────────────────────────────────────────────

    def _build_isr_html(self):
        companies = self._get_companies()
        df, dt = self.isr_date_from, self.isr_date_to
        if not df or not dt:
            return ''
        period = _period_label_for(self.isr_period_type, df, dt)
        html_parts = []

        for c in companies:
            regime = c.ktx_isr_regime
            if not regime and c.ktx_iva_regime == 'pequeno':
                html_parts.append(
                    f"<div style='font-size:13px;color:#64748b;padding:8px 0;'>"
                    f"<b>{c.name}</b>: Pequeño Contribuyente &#8212; no aplica ISR.</div>"
                )
                continue
            if not regime:
                html_parts.append(
                    f"<div style='font-size:13px;color:#f59e0b;padding:8px 0;'>"
                    f"<b>{c.name}</b>: Régimen ISR no configurado.</div>"
                )
                continue
            sym = c.currency_id.symbol or 'Q'
            if regime == 'opcional':
                html_parts.append(self._build_isr_opcional_html(c, sym, df, dt))
            else:
                html_parts.append(self._build_isr_utilidades_html(c, sym, df, dt))

        if not html_parts:
            return ''
        return self._section_title('ISR', period) + ''.join(html_parts)

    def _build_isr_opcional_html(self, company, sym, df, dt):
        ventas   = self._sum_sales_net(company, df, dt)
        ret_isr  = self._sum_tax_lines(company, 'isr_retencion', df, dt)
        base_5   = min(ventas, 150000.0)
        base_7   = max(ventas - 150000.0, 0.0)
        isr_bruto = base_5 * 0.05 + base_7 * 0.07
        a_pagar  = max(isr_bruto - ret_isr, 0.0)

        header = (
            f"<div style='font-size:12px;font-weight:700;color:#1d4ed8;padding:6px 0;'>"
            f"{escape(company.name)} &#8212; ISR Opcional Simplificado</div>"
        )
        rows = [
            ('Ventas Netas del Período',  _fmt(ventas, sym),    False, '#ffffff'),
            ('Tasa ISR',                  '5% / 7%',            False, '#f8fafc'),
            ('ISR Bruto',                 _fmt(isr_bruto, sym), False, '#ffffff'),
            ('(-) Retenciones ISR',       _fmt(ret_isr, sym),   False, '#f8fafc'),
            ('ISR Por Pagar',             _fmt(a_pagar, sym),   True,
             '#fef2f2' if a_pagar > 0 else '#f0f9ff'),
        ]
        tbl = (
            "<table style='width:100%;border-collapse:collapse;font-size:13px;margin-bottom:12px;'>"
            + self._tbl_header(['Concepto', 'Importe']) + "<tbody>"
        )
        for label, val, bold, bg in rows:
            tbl += self._tbl_row([label, val], bold=bold, bg=bg,
                                  color='#991b1b' if bold and a_pagar > 0 else '#1f2937')
        tbl += "</tbody></table>"
        return header + tbl

    def _build_isr_utilidades_html(self, company, sym, df, dt):
        ventas = self._sum_account_type(
            company, ['income', 'income_other'], df, dt)
        gastos = self._sum_account_type(
            company, ['expense', 'expense_depreciation', 'expense_direct_cost'], df, dt)
        gnd = 0.0
        gnd_accounts = self.env['account.account'].search([
            ('company_ids', 'in', [company.id]),
            ('ktx_non_deductible', '=', True),
        ])
        if gnd_accounts:
            gnd_lines = self.env['account.move.line'].search([
                ('account_id', 'in', gnd_accounts.ids),
                ('move_id.state', '=', 'posted'),
                ('date', '>=', df), ('date', '<=', dt),
                ('company_id', '=', company.id),
            ])
            gnd = abs(sum(gnd_lines.mapped('balance')))

        base      = ventas - gastos + gnd
        isr_bruto = max(base * 0.25, 0.0)
        ret_isr   = self._sum_tax_lines(company, 'isr_retencion', df, dt)
        a_pagar   = max(isr_bruto - ret_isr, 0.0)

        header = (
            f"<div style='font-size:12px;font-weight:700;color:#1d4ed8;padding:6px 0;'>"
            f"{escape(company.name)} &#8212; ISR Sobre Utilidades</div>"
        )
        rows = [
            ('Ingresos del Período',              _fmt(ventas, sym),    False, '#ffffff'),
            ('(-) Gastos Deducibles',             _fmt(gastos, sym),    False, '#f8fafc'),
            ('(+) Gastos No Deducibles (GND)',    _fmt(gnd, sym),       False, '#ffffff'),
            ('Base Imponible',                    _fmt(base, sym),      True,  '#f0f9ff'),
            ('ISR 25%',                           _fmt(isr_bruto, sym), False, '#ffffff'),
            ('(-) Retenciones ISR',               _fmt(ret_isr, sym),   False, '#f8fafc'),
            ('ISR Por Pagar',                     _fmt(a_pagar, sym),   True,
             '#fef2f2' if a_pagar > 0 else '#f0f9ff'),
        ]
        tbl = (
            "<table style='width:100%;border-collapse:collapse;font-size:13px;margin-bottom:12px;'>"
            + self._tbl_header(['Concepto', 'Importe']) + "<tbody>"
        )
        for label, val, bold, bg in rows:
            tbl += self._tbl_row([label, val], bold=bold, bg=bg,
                                  color='#991b1b' if bold and label == 'ISR Por Pagar' and a_pagar > 0 else '#1f2937')
        tbl += "</tbody></table>"
        return header + tbl

    # ── ISO ──────────────────────────────────────────────────────────────────

    def _build_iso_html(self):
        companies = self._get_companies()
        if not any(c.ktx_apply_iso for c in companies):
            return ''
        return (
            "<div style='margin:12px 0;padding:12px 16px;background:#fefce8;"
            "border:1px solid #fde68a;border-radius:6px;font-size:13px;color:#92400e;'>"
            "<b>ISO Trimestral</b> &#8212; Próximamente disponible en esta sección."
            "</div>"
        )

    # ── Extras ───────────────────────────────────────────────────────────────

    def _build_extras_html(self):
        companies = self._get_companies()
        rows = []
        for c in companies:
            for extra in c.ktx_extra_tax_ids:
                rows.append((c.name, extra.name, extra.tax_id.name if extra.tax_id else '&#8212;'))
        if not rows:
            return ''
        title = self._section_title('Impuestos Adicionales RTU')
        tbl = (
            "<table style='width:100%;border-collapse:collapse;font-size:13px;'>"
            + self._tbl_header(['Empresa', 'Descripción', 'Impuesto']) + "<tbody>"
        )
        for i, (emp, desc, tax) in enumerate(rows):
            bg = '#ffffff' if i % 2 == 0 else '#f8fafc'
            tbl += self._tbl_row([emp, desc, tax], bg=bg)
        tbl += "</tbody></table>"
        return title + tbl

    # ── Navegación IVA (mensual) ──────────────────────────────────────────────

    def _shift_iva(self, direction):
        if not self.iva_date_from:
            return
        df = self.iva_date_from + relativedelta(months=direction)
        dt = (df + relativedelta(months=1)) - relativedelta(days=1)
        self.write({'iva_date_from': df, 'iva_date_to': dt})

    def action_iva_prev(self):
        self._shift_iva(-1)

    def action_iva_next(self):
        self._shift_iva(1)

    # ── Navegación ISR ────────────────────────────────────────────────────────

    def _shift_isr(self, direction):
        if not self.isr_date_from:
            return
        if self.isr_period_type == 'mes':
            df = self.isr_date_from + relativedelta(months=direction)
            dt = (df + relativedelta(months=1)) - relativedelta(days=1)
        else:
            df = self.isr_date_from + relativedelta(months=3 * direction)
            dt = (df + relativedelta(months=3)) - relativedelta(days=1)
        self.write({'isr_date_from': df, 'isr_date_to': dt})

    def action_isr_prev(self):
        self._shift_isr(-1)

    def action_isr_next(self):
        self._shift_isr(1)

    def action_isr_set_mes(self):
        today = date.today()
        df = today.replace(day=1)
        dt = (df + relativedelta(months=1)) - relativedelta(days=1)
        self.write({'isr_period_type': 'mes', 'isr_date_from': df, 'isr_date_to': dt})

    def action_isr_set_trim(self):
        today = date.today()
        q_month = ((today.month - 1) // 3) * 3 + 1
        df = today.replace(month=q_month, day=1)
        dt = (df + relativedelta(months=3)) - relativedelta(days=1)
        self.write({'isr_period_type': 'trim', 'isr_date_from': df, 'isr_date_to': dt})

    # ── Acción de apertura (singleton por empresa) ────────────────────────────

    @api.model
    def action_open_resumen(self):
        company = self.env.company
        record = self.search(
            [('company_ids', 'in', [company.id])], order='id desc', limit=1
        )
        if not record:
            record = self.create({
                'name': 'Resumen Fiscal',
                'company_ids': [(4, company.id)],
            })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': record.id,
            'target': 'current',
        }
