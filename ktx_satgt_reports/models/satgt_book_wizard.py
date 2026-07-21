# -*- coding: utf-8 -*-
import logging
import re
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)

_MONTHS_ES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
               'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

_REFUND_TYPES = frozenset({'in_refund', 'out_refund'})

_RETENTION_WORDS = ('retenci', 'retencion', 'ret ', 'isr', 'renta')
_PC_WORDS        = ('peque', 'cuota', 'contribuy', 'regimen esp', 'régimen esp')
_EXENTA_WORDS    = ('exent', 'libre', 'exenci', 'no grav', 'no afect')

_EMPTY_ROW = {
    'local_grav_bienes':  0.0,
    'local_grav_serv':    0.0,
    'local_exe_bienes':   0.0,
    'local_exe_serv':     0.0,
    'import_grav_bienes': 0.0,
    'import_grav_serv':   0.0,
    'import_exe_bienes':  0.0,
    'import_exe_serv':    0.0,
    'pequeno_cont':       0.0,
    'iva':                0.0,
    'total':              0.0,
}


def _first_day(self=None):
    t = date.today()
    return t.replace(day=1)


def _last_day(self=None):
    t = date.today()
    return (t.replace(day=1) + relativedelta(months=1)) - relativedelta(days=1)


def _is_iva_tax(tax):
    name = (tax.name or '').lower()
    return (tax.amount_type == 'percent' and tax.amount == 12
            and not any(w in name for w in _RETENTION_WORDS))


def _is_pequeno_tax(tax):
    name = (tax.name or '').lower()
    if any(w in name for w in _PC_WORDS):
        return True
    grp = (tax.tax_group_id.name or '').lower() if tax.tax_group_id else ''
    if any(w in grp for w in _PC_WORDS):
        return True
    if (tax.amount_type == 'percent' and tax.amount == 5
            and not any(w in name for w in _RETENTION_WORDS)):
        return True
    # 0% tax sin palabras de retención ni de exención → probable PC (cuota informativa)
    if (tax.amount_type == 'percent' and tax.amount == 0
            and not any(w in name for w in list(_RETENTION_WORDS) + list(_EXENTA_WORDS))):
        return True
    return False


def _fmt(v):
    """Format amount with comma thousands separator and period decimal."""
    if not v:
        return ''
    return '{:,.2f}'.format(abs(v))


class SatgtBookWizard(models.TransientModel):
    _name = 'ktx.satgt.book.wizard'
    _description = 'Generador de Libros SAT GT'

    book_type = fields.Selection([
        ('compras', 'Libro de Compras y Servicios'),
        ('ventas',  'Libro de Ventas y Servicios'),
        ('diario',  'Libro Diario'),
        ('mayor',   'Libro Mayor'),
    ], string='Libro / Reporte', required=True, default='compras')

    company_ids = fields.Many2many(
        'res.company', string='Empresas',
        default=lambda self: self.env.company,
    )
    period_type = fields.Selection([
        ('mes',          'Mes'),
        ('trim',         'Trimestre'),
        ('anio',         'Año'),
        ('personalizado', 'Personalizado'),
    ], string='Periodo', default='mes')
    date_from   = fields.Date(string='Desde', required=True, default=_first_day)
    date_to     = fields.Date(string='Hasta', required=True, default=_last_day)
    folio_start = fields.Integer(string='No. de Folio Inicial', default=1)

    journal_ids = fields.Many2many(
        'account.journal', string='Diarios',
        help='Filtrar por diarios específicos. Vacío = todos los del tipo correspondiente.',
    )
    account_ids = fields.Many2many(
        'account.account', string='Cuentas Contables',
        help='Filtrar por cuentas contables. Vacío = todas las cuentas.',
    )
    use_company_currency = fields.Boolean(
        string='Usar moneda de la empresa', default=True,
    )
    period_label = fields.Char(
        string='Período', compute='_compute_period_label', store=False,
    )

    col_nit    = fields.Boolean('NIT',      default=True)
    col_serie  = fields.Boolean('Serie DTE', default=True)
    col_numero = fields.Boolean('Numero DTE', default=True)
    col_iva    = fields.Boolean('IVA',       default=True)

    orientation = fields.Selection([
        ('portrait',  'Vertical (Retrato)'),
        ('landscape', 'Horizontal (Paisaje)'),
    ], string='Orientación', default='portrait')

    margin_top    = fields.Float(string='Margen Superior (mm)',  default=10.0)
    margin_bottom = fields.Float(string='Margen Inferior (mm)',  default=10.0)
    margin_left   = fields.Float(string='Margen Izquierdo (mm)', default=10.0)
    margin_right  = fields.Float(string='Margen Derecho (mm)',   default=10.0)

    preview_html = fields.Html(sanitize=False, readonly=True)

    @api.depends('period_type', 'date_from', 'date_to')
    def _compute_period_label(self):
        for rec in self:
            pt = rec.period_type or 'mes'
            if pt == 'mes' and rec.date_from:
                rec.period_label = f"{_MONTHS_ES[rec.date_from.month - 1]}  {rec.date_from.year}"
            elif pt == 'trim' and rec.date_from:
                q = (rec.date_from.month - 1) // 3 + 1
                rec.period_label = f"Trimestre {q}  —  {rec.date_from.year}"
            elif pt == 'anio' and rec.date_from:
                rec.period_label = str(rec.date_from.year)
            else:
                rec.period_label = rec._period_str()

    @api.depends('book_type')
    def _compute_display_name(self):
        labels = dict(self._fields['book_type'].selection)
        for rec in self:
            rec.display_name = labels.get(rec.book_type, 'Libro')

    @api.onchange('period_type')
    def _onchange_period_type(self):
        today = date.today()
        pt = self.period_type
        if pt == 'mes':
            self.date_from = today.replace(day=1)
            self.date_to = (today.replace(day=1) + relativedelta(months=1)) - relativedelta(days=1)
        elif pt == 'trim':
            q_start = ((today.month - 1) // 3) * 3 + 1
            self.date_from = today.replace(month=q_start, day=1)
            self.date_to = (self.date_from + relativedelta(months=3)) - relativedelta(days=1)
        elif pt == 'anio':
            self.date_from = today.replace(month=1, day=1)
            self.date_to = today.replace(month=12, day=31)

    def action_preview(self):
        self.ensure_one()
        if self.book_type in ('compras', 'ventas'):
            self.preview_html = self._build_preview_html()
        else:
            self.preview_html = (
                "<div style='padding:24px;text-align:center;color:#64748b;font-size:14px;'>"
                "Este reporte estara disponible proximamente.</div>"
            )
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ktx.satgt.book.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }

    def action_print_pdf(self):
        self.ensure_one()
        company = self.company_ids[:1] or self.env.company
        if self.book_type in ('compras', 'ventas') and company.ktx_iva_regime == 'pequeno':
            report = self.env.ref('ktx_satgt_reports.action_report_libro_pc')
            return report.with_context(satgt_folio_start=self.folio_start or 1).report_action(self)
        report_map = {
            'compras': 'ktx_satgt_reports.action_report_libro_compras',
            'ventas':  'ktx_satgt_reports.action_report_libro_ventas',
            'diario':  'ktx_satgt_reports.action_report_libro_diario',
            'mayor':   'ktx_satgt_reports.action_report_libro_mayor',
        }
        report_ref = report_map.get(self.book_type)
        if not report_ref:
            raise UserError(_('La impresión PDF no está disponible para este tipo de libro.'))
        report = self.env.ref(report_ref)
        if self.book_type in ('diario', 'mayor'):
            report = report.with_context(satgt_folio_start=self.folio_start or 1)
        return report.report_action(self)

    # ── Datos ─────────────────────────────────────────────────────────────────

    def _build_import_doc_map(self, move_ids):
        if 'ktx.import.document' not in self.env:
            return {}
        docs = self.env['ktx.import.document'].search([('invoice_id', 'in', list(move_ids))])
        return {d.invoice_id.id: d for d in docs}

    def _line_amount(self, line):
        sign = -1 if line.move_id.move_type in _REFUND_TYPES else 1
        if self.use_company_currency:
            return sign * abs(line.balance)
        return sign * abs(line.price_subtotal)

    def _tax_amount(self, tl):
        sign = -1 if tl.move_id.move_type in _REFUND_TYPES else 1
        if self.use_company_currency:
            return sign * abs(tl.balance)
        return sign * abs(tl.amount_currency)

    def _get_book_lines(self):
        is_compras  = self.book_type == 'compras'
        move_types  = ['in_invoice', 'in_refund'] if is_compras else ['out_invoice', 'out_refund']
        iva_cat     = 'iva_compras' if is_compras else 'iva_ventas'
        company_ids = self.company_ids.ids or [self.env.company.id]

        # Build tax→category map: ktx_satgt_category on tax takes priority over config model
        configs     = self.env['ktx.satgt.tax.config'].search([('company_id', 'in', company_ids)])
        tax_cat_map = {cfg.tax_id.id: cfg.category for cfg in configs}
        for tax in self.env['account.tax'].search([('ktx_satgt_category', '!=', False)]):
            tax_cat_map[tax.id] = tax.ktx_satgt_category

        domain = [
            ('move_type', 'in', move_types),
            ('state', '=', 'posted'),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('company_id', 'in', company_ids),
        ]
        if self.journal_ids:
            domain.append(('journal_id', 'in', self.journal_ids.ids))
        moves = self.env['account.move'].search(domain, order='invoice_date, date, name')
        moves = moves.sorted(key=lambda m: (m.invoice_date or m.date or fields.Date.today(), m.name or ''))

        # Only include moves where at least one invoice line has a configured tax
        def _has_configured_tax(m):
            return any(
                t.ktx_include_in_report or t.id in tax_cat_map
                for line in m.invoice_line_ids.filtered(lambda l: l.display_type == 'product')
                for t in line.tax_ids
            )
        moves = moves.filtered(_has_configured_tax)

        imp_doc_map = self._build_import_doc_map(moves.ids)

        lines  = []
        totals = dict(_EMPTY_ROW)
        for i, move in enumerate(moves, 1):
            row = self._classify_move(move, iva_cat, tax_cat_map, imp_doc_map)
            row['no'] = i
            lines.append(row)
            for k in totals:
                totals[k] += row.get(k, 0.0)

        return lines, totals

    def _classify_move(self, move, iva_cat, tax_cat_map, imp_doc_map=None):
        row = dict(_EMPTY_ROW)
        imp_doc_map = imp_doc_map or {}

        imp_doc = imp_doc_map.get(move.id)
        if imp_doc:
            serie  = getattr(imp_doc, 'serie', '') or ''
            numero = (getattr(imp_doc, 'numero_autorizacion', None)
                      or move.ref or move.name or '')
        else:
            serie  = (getattr(move, 'fe_serie', None)
                      or getattr(move, 'numero_serie', None) or '')
            numero = (getattr(move, 'fe_number', None)
                      or move.ref or move.name or '')

        row.update({
            'no':       0,
            'dia':      (move.invoice_date or move.date).day if (move.invoice_date or move.date) else '',
            'serie':    serie,
            'numero':   numero,
            'nit':      (move.partner_id.vat or '').replace('-', '') if move.partner_id else 'CF',
            'partner':  move.partner_id.name if move.partner_id else 'Consumidor Final',
            'currency': move.currency_id.symbol or 'Q',
        })

        IMPORT_CATS = {'import_grav_bienes', 'import_grav_serv',
                       'import_exe_bienes',  'import_exe_serv'}
        IVA_CATS    = {'iva_compras', 'iva_ventas'}

        for line in move.invoice_line_ids.filtered(lambda l: l.display_type == 'product'):
            amount = self._line_amount(line)
            is_svc = bool(line.product_id and line.product_id.type == 'service')
            sfx    = '_serv' if is_svc else '_bienes'
            lt     = list(line.tax_ids)

            # ── New boolean-flag classification (takes priority) ──────────────
            flag_taxes = [t for t in lt if t.ktx_include_in_report]
            if flag_taxes:
                is_pequeno = any(t.ktx_is_pequeno    for t in flag_taxes)
                is_import  = any(t.ktx_is_import     for t in flag_taxes)
                is_exento  = any(t.ktx_is_exento     for t in flag_taxes)
                if is_pequeno:
                    row['pequeno_cont'] += amount
                elif is_exento:
                    prefix = 'import' if is_import else 'local'
                    row[f'{prefix}_exe{sfx}'] += amount
                else:
                    prefix = 'import' if is_import else 'local'
                    row[f'{prefix}_grav{sfx}'] += amount
                continue

            # ── Legacy category-map + heuristic fallback ──────────────────────
            cats = {tax_cat_map.get(t.id) for t in lt if t.id in tax_cat_map}
            cats.discard(None)

            import_cats_found = cats & IMPORT_CATS
            if import_cats_found:
                cat = next(iter(import_cats_found))
                row[cat] += amount
            elif cats & IVA_CATS:
                row['local_grav' + sfx] += amount
            elif 'pequeno_cont' in cats:
                row['pequeno_cont'] += amount
            elif cats & {'local_grav_bienes', 'local_grav_serv'}:
                cat = next(iter(cats & {'local_grav_bienes', 'local_grav_serv'}))
                row[cat] += amount
            elif cats & {'local_exe_bienes', 'local_exe_serv'}:
                if any(_is_pequeno_tax(t) for t in lt):
                    row['pequeno_cont'] += amount
                else:
                    cat = next(iter(cats & {'local_exe_bienes', 'local_exe_serv'}))
                    row[cat] += amount
            else:
                # No configured tax found for this line (neither new flags nor legacy category)
                # Skip: do not include in book
                continue

        for tl in move.line_ids.filtered(lambda l: l.tax_line_id):
            tax = tl.tax_line_id
            amt = self._tax_amount(tl)
            if tax.ktx_include_in_report:
                if tax.ktx_is_iva:
                    row['iva'] += amt
                elif tax.ktx_is_combustible or tax.ktx_is_otro:
                    prefix = 'import' if tax.ktx_is_import else 'local'
                    # Determine bienes/servicios from the invoice lines that carry this tax
                    src_lines = move.invoice_line_ids.filtered(
                        lambda l, t=tax: l.display_type == 'product' and t in l.tax_ids
                    )
                    all_svc = bool(src_lines) and all(
                        l.product_id and l.product_id.type == 'service'
                        for l in src_lines
                    )
                    sfx = '_serv' if all_svc else '_bienes'
                    row[f'{prefix}_exe{sfx}'] += amt
            else:
                cat = tax_cat_map.get(tax.id)
                if cat in IVA_CATS or (cat is None and _is_iva_tax(tax)):
                    row['iva'] += amt
                elif cat in IMPORT_CATS:
                    row[cat] += amt

        row['total'] = sum(row[k] for k in _EMPTY_ROW if k != 'total')
        return row

    # ── Folios ────────────────────────────────────────────────────────────────

    _PAGE_H_MM    = 215.9
    _CO_HDR_MM    = 25.0  # company header block (first folio only)
    _FOLIO_HDR_MM =  3.0  # "FOLIO No. X" label (non-first folios)
    _COL_HDR_MM   = 12.0  # 3-row column header
    _TFOOT_MM     =  4.5  # subtotals footer row
    # Row height: 3.5mm per text line + 1.0mm cell padding.
    # Proveedor column fits ~50 chars on one line at this page width.
    _CHARS_PER_LINE = 50
    _MM_PER_LINE    =  3.5
    _ROW_PADDING_MM =  1.0

    def _row_height_mm(self, row):
        name  = row.get('partner', '') or ''
        lines = max(1, -(-len(name) // self._CHARS_PER_LINE))
        return lines * self._MM_PER_LINE + self._ROW_PADDING_MM

    def _folio_avail_mm(self, first=False):
        mt    = self.margin_top    or 10.0
        mb    = self.margin_bottom or 10.0
        avail = self._PAGE_H_MM - mt - mb - self._COL_HDR_MM - self._TFOOT_MM
        if first:
            avail -= self._CO_HDR_MM
        else:
            avail -= self._FOLIO_HDR_MM
        return max(avail, 20.0)

    def _get_folios(self, lines, totals):
        if not lines:
            return []
        folios  = []
        running = dict(_EMPTY_ROW)
        i = 0
        while i < len(lines):
            avail   = self._folio_avail_mm(first=not folios)
            chunk   = []
            used_mm = 0.0
            while i < len(lines):
                rh = self._row_height_mm(lines[i])
                if used_mm + rh > avail and chunk:
                    break
                chunk.append(lines[i])
                used_mm += rh
                i += 1
            for r in chunk:
                for k in running:
                    running[k] += r.get(k, 0.0)
            is_last = i >= len(lines)
            folios.append({
                'lines':     chunk,
                'subtotals': totals if is_last else dict(running),
                'label':     'Totales' if is_last else 'Sub-Totales',
                'is_last':   is_last,
                'folio_no':  self.folio_start + len(folios),
            })
        return folios

    def _period_str(self):
        if not self.date_from or not self.date_to:
            return ''
        return (f"{self.date_from.strftime('%d/%m/%Y')}"
                f" al {self.date_to.strftime('%d/%m/%Y')}")

    def _build_preview_html(self):
        lines, totals = self._get_book_lines()
        if not lines:
            return ("<div style='padding:24px;text-align:center;color:#64748b;'>"
                    "Sin movimientos en el periodo seleccionado.</div>")

        is_compras  = self.book_type == 'compras'
        partner_lbl = 'Proveedor' if is_compras else 'Cliente / Comprador'
        title       = ('LIBRO DE COMPRAS Y SERVICIOS' if is_compras
                       else 'LIBRO DE VENTAS Y SERVICIOS')

        TH  = "padding:4px 6px;text-align:right;white-space:nowrap;border:1px solid #1e4f7a;"
        THL = "padding:4px 6px;white-space:nowrap;border:1px solid #1e4f7a;"

        th = "<thead><tr style='background:#0369a1;color:#fff;font-size:10px;'>"
        for c in ['No.', 'Dia']:
            th += f"<th style='{THL}'>{c}</th>"
        if self.col_serie:
            th += f"<th style='{THL}'>Serie DTE</th>"
        if self.col_numero:
            th += f"<th style='{THL}'>Numero DTE</th>"
        if self.col_nit:
            th += f"<th style='{THL}'>NIT</th>"
        th += f"<th style='{THL}'>{partner_lbl}</th>"
        for c in ['LOCAL Grav.Bienes', 'LOCAL Grav.Serv.',
                  'LOCAL Exen.Bienes', 'LOCAL Exen.Serv.', 'Peq.Contrib.']:
            th += f"<th style='{TH}'>{c}</th>"
        if self.col_iva:
            th += f"<th style='{TH}'>IVA</th>"
        th += f"<th style='{TH}'>Total</th></tr></thead>"

        html = (
            f"<div style='font-family:Arial,sans-serif;overflow-x:auto;'>"
            f"<div style='font-weight:700;font-size:14px;margin-bottom:4px;'>{title}</div>"
            f"<div style='color:#64748b;margin-bottom:12px;font-size:11px;'>"
            f"Periodo: {self._period_str()} | Folio: {self.folio_start} | {len(lines)} registros</div>"
            f"<table style='border-collapse:collapse;width:100%;font-size:10px;'>{th}<tbody>"
        )

        for idx, r in enumerate(lines):
            bg  = '#ffffff' if idx % 2 == 0 else '#f8fafc'
            td  = f"<tr style='background:{bg};'>"
            td += f"<td style='padding:3px 5px;border:1px solid #e2e8f0;'>{r['no']}</td>"
            td += f"<td style='padding:3px 5px;border:1px solid #e2e8f0;text-align:center;'>{r['dia']}</td>"
            if self.col_serie:
                td += f"<td style='padding:3px 5px;border:1px solid #e2e8f0;'>{r['serie']}</td>"
            if self.col_numero:
                td += f"<td style='padding:3px 5px;border:1px solid #e2e8f0;'>{r['numero']}</td>"
            if self.col_nit:
                td += f"<td style='padding:3px 5px;border:1px solid #e2e8f0;'>{r['nit']}</td>"
            td += f"<td style='padding:3px 5px;border:1px solid #e2e8f0;max-width:120px;overflow:hidden;'>{r['partner']}</td>"
            for k in ['local_grav_bienes', 'local_grav_serv',
                      'local_exe_bienes', 'local_exe_serv', 'pequeno_cont']:
                td += f"<td style='padding:3px 5px;border:1px solid #e2e8f0;text-align:right;'>{_fmt(r[k])}</td>"
            if self.col_iva:
                td += f"<td style='padding:3px 5px;border:1px solid #e2e8f0;text-align:right;'>{_fmt(r['iva'])}</td>"
            td += f"<td style='padding:3px 5px;border:1px solid #e2e8f0;text-align:right;font-weight:600;'>{_fmt(r['total'])}</td></tr>"
            html += td

        span = 2 + (1 if self.col_serie else 0) + (1 if self.col_numero else 0) \
                  + (1 if self.col_nit else 0) + 1
        tr_t = (f"<tr style='background:#0369a1;color:#fff;font-weight:700;'>"
                f"<td colspan='{span}' style='padding:4px 6px;border:1px solid #1e4f7a;'>TOTALES</td>")
        for k in ['local_grav_bienes', 'local_grav_serv',
                  'local_exe_bienes', 'local_exe_serv', 'pequeno_cont']:
            tr_t += f"<td style='padding:4px 6px;border:1px solid #1e4f7a;text-align:right;'>{_fmt(totals[k])}</td>"
        if self.col_iva:
            tr_t += f"<td style='padding:4px 6px;border:1px solid #1e4f7a;text-align:right;'>{_fmt(totals['iva'])}</td>"
        tr_t += f"<td style='padding:4px 6px;border:1px solid #1e4f7a;text-align:right;'>{_fmt(totals['total'])}</td></tr>"
        html += tr_t + "</tbody></table></div>"
        return html

    def _month_name(self):
        return _MONTHS_ES[self.date_from.month - 1] if self.date_from else ''

    def _year_str(self):
        return str(self.date_from.year) if self.date_from else ''

    def _get_resumen(self, lines, totals):
        is_compras = self.book_type == 'compras'
        prefix = 'COMPRAS' if is_compras else 'VENTAS'
        imp    = 'IMPORTACION' if is_compras else 'EXPORTACION'

        def _iva(base):
            return round(base * 0.12, 2) if base else 0.0

        lgb = totals.get('local_grav_bienes', 0.0)
        lgs = totals.get('local_grav_serv', 0.0)
        leb = totals.get('local_exe_bienes', 0.0)
        les = totals.get('local_exe_serv', 0.0)
        igb = totals.get('import_grav_bienes', 0.0)
        igs = totals.get('import_grav_serv', 0.0)
        ieb = totals.get('import_exe_bienes', 0.0)
        ies = totals.get('import_exe_serv', 0.0)
        peq = totals.get('pequeno_cont', 0.0)

        rows = []
        if lgb:
            rows.append({'label': f'{prefix} GRAVADAS BIENES',     'grav': lgb, 'exe': 0,   'iva': _iva(lgb), 'total': lgb + _iva(lgb)})
        if lgs:
            rows.append({'label': f'{prefix} GRAVADAS SERVICIOS',  'grav': lgs, 'exe': 0,   'iva': _iva(lgs), 'total': lgs + _iva(lgs)})
        if leb:
            rows.append({'label': f'{prefix} EXENTAS BIENES',      'grav': 0,   'exe': leb, 'iva': 0,          'total': leb})
        if les:
            rows.append({'label': f'{prefix} EXENTAS SERVICIOS',   'grav': 0,   'exe': les, 'iva': 0,          'total': les})
        if igb:
            rows.append({'label': f'{imp} GRAVADA BIENES',          'grav': igb, 'exe': 0,   'iva': _iva(igb), 'total': igb + _iva(igb)})
        if igs:
            rows.append({'label': f'{imp} GRAVADA SERVICIOS',       'grav': igs, 'exe': 0,   'iva': _iva(igs), 'total': igs + _iva(igs)})
        if ieb:
            rows.append({'label': f'{imp} EXENTA BIENES',           'grav': 0,   'exe': ieb, 'iva': 0,          'total': ieb})
        if ies:
            rows.append({'label': f'{imp} EXENTA SERVICIOS',        'grav': 0,   'exe': ies, 'iva': 0,          'total': ies})
        if peq:
            rows.append({'label': 'PEQUEÑO CONTRIBUYENTE',          'grav': 0,   'exe': peq, 'iva': 0,          'total': peq})

        rows.append({
            'label': 'Totales',
            'grav':  lgb + lgs + igb + igs,
            'exe':   leb + les + ieb + ies + peq,
            'iva':   totals.get('iva', 0.0),
            'total': totals.get('total', 0.0),
            'is_total': True,
        })
        return rows

    def action_prev_period(self):
        self._shift_period(-1)
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'view_mode': 'form', 'res_id': self.id,
                'views': [(False, 'form')], 'target': 'new'}

    def action_next_period(self):
        self._shift_period(1)
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'view_mode': 'form', 'res_id': self.id,
                'views': [(False, 'form')], 'target': 'new'}

    def _shift_period(self, delta):
        if not self.date_from:
            return
        if self.period_type == 'mes':
            new_from = (self.date_from + relativedelta(months=delta)).replace(day=1)
            new_to   = (new_from + relativedelta(months=1)) - relativedelta(days=1)
        elif self.period_type == 'trim':
            new_from = (self.date_from + relativedelta(months=3 * delta)).replace(day=1)
            new_to   = (new_from + relativedelta(months=3)) - relativedelta(days=1)
        else:
            new_from = self.date_from.replace(year=self.date_from.year + delta, month=1, day=1)
            new_to   = new_from.replace(month=12, day=31)
        self.date_from = new_from
        self.date_to   = new_to

    def _get_pc_book_lines(self):
        """Return (compras_lines, ventas_lines, compras_total, ventas_total) for PC regime."""
        company_ids = self.company_ids.ids or [self.env.company.id]

        def _fetch(move_types):
            domain = [
                ('move_type', 'in', move_types),
                ('state', '=', 'posted'),
                ('date', '>=', self.date_from),
                ('date', '<=', self.date_to),
                ('company_id', 'in', company_ids),
            ]
            moves = self.env['account.move'].search(domain, order='invoice_date, date, name')
            moves = moves.sorted(
                key=lambda m: (m.invoice_date or m.date or fields.Date.today(), m.name or '')
            )
            imp_doc_map = self._build_import_doc_map(moves.ids)
            lines = []
            for i, move in enumerate(moves, 1):
                imp_doc = imp_doc_map.get(move.id)
                if imp_doc:
                    serie  = getattr(imp_doc, 'serie', '') or ''
                    numero = (getattr(imp_doc, 'numero_autorizacion', None)
                              or move.ref or move.name or '')
                else:
                    serie  = (getattr(move, 'fe_serie', None)
                              or getattr(move, 'numero_serie', None) or '')
                    numero = (getattr(move, 'fe_number', None)
                              or move.ref or move.name or '')
                lines.append({
                    'no':      i,
                    'dia':     (move.invoice_date or move.date).day
                               if (move.invoice_date or move.date) else '',
                    'serie':   serie,
                    'numero':  numero,
                    'nit':     (move.partner_id.vat or '').replace('-', '')
                               if move.partner_id else 'CF',
                    'partner': move.partner_id.name if move.partner_id else 'Consumidor Final',
                    'total':   (-1 if move.move_type in _REFUND_TYPES else 1) * abs(move.amount_total),
                })
            return lines

        c_lines = _fetch(['in_invoice', 'in_refund'])
        v_lines = _fetch(['out_invoice', 'out_refund'])
        return (
            c_lines,
            v_lines,
            sum(r['total'] for r in c_lines),
            sum(r['total'] for r in v_lines),
        )

    def _get_diario_lines(self):
        company_ids = self.company_ids.ids or [self.env.company.id]
        domain = [
            ('state', '=', 'posted'),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('company_id', 'in', company_ids),
        ]
        if self.journal_ids:
            domain.append(('journal_id', 'in', self.journal_ids.ids))
        moves = self.env['account.move'].search(domain, order='date, name')
        entries = []
        total_debit = total_credit = 0.0
        entry_no = 0
        for move in moves:
            move_lines = []
            for aml in move.line_ids.filtered(lambda l: l.display_type not in ('line_section', 'line_note')):
                if self.account_ids and aml.account_id.id not in self.account_ids.ids:
                    continue
                move_lines.append({
                    'account_code': aml.account_id.code or '',
                    'account_name': aml.account_id.name or '',
                    'partner':      aml.partner_id.name or '',
                    'label':        aml.name or '',
                    'debit':        aml.debit,
                    'credit':       aml.credit,
                })
            if not move_lines:
                continue
            # Debit lines first, then credit lines
            move_lines.sort(key=lambda l: (0 if l['debit'] > 0 else 1))
            entry_no += 1
            md = sum(l['debit'] for l in move_lines)
            mc = sum(l['credit'] for l in move_lines)
            total_debit += md
            total_credit += mc
            entries.append({
                'no':           entry_no,
                'date':         move.date,
                'name':         move.name or '',
                'ref':          move.ref or '',
                'serie':        getattr(move, 'fe_serie', None) or getattr(move, 'numero_serie', None) or '',
                'ref_doc':      (getattr(move, 'fe_number', None)
                                 or getattr(move, 'l10n_gt_dte_number', None)
                                 or getattr(move, 'numero_serie', None)
                                 or move.ref or ''),
                'narration':    re.sub('<[^>]+>', ' ', move.narration or '').replace('\n', ' ').strip()[:120],
                'lines':        move_lines,
                'entry_debit':  md,
                'entry_credit': mc,
            })
        return entries, total_debit, total_credit

    def _get_mayor_lines(self):
        company_ids = self.company_ids.ids or [self.env.company.id]
        domain = [
            ('move_id.state', '=', 'posted'),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('company_id', 'in', company_ids),
            ('display_type', 'not in', ['line_section', 'line_note']),
        ]
        if self.account_ids:
            domain.append(('account_id', 'in', self.account_ids.ids))
        if self.journal_ids:
            domain.append(('journal_id', 'in', self.journal_ids.ids))
        amls = self.env['account.move.line'].search(domain, order='account_id, date, id')

        accounts = {}
        for aml in amls:
            acc = aml.account_id
            if acc.id not in accounts:
                ob_lines = self.env['account.move.line'].search([
                    ('account_id', '=', acc.id),
                    ('move_id.state', '=', 'posted'),
                    ('date', '<', self.date_from),
                    ('company_id', 'in', company_ids),
                ])
                accounts[acc.id] = {
                    'code': acc.code or '',
                    'name': acc.name or '',
                    'opening': sum(ob_lines.mapped('balance')),
                    'lines': [],
                }
            accounts[acc.id]['lines'].append(aml)

        company_currency = self.env.company.currency_id
        result = []
        for acc_id, data in sorted(accounts.items(), key=lambda x: x[1]['code']):
            running = data['opening']
            rows = []
            for i, aml in enumerate(data['lines'], 1):
                running += aml.balance
                is_foreign = aml.currency_id and aml.currency_id != company_currency
                move = aml.move_id
                ref_doc = (
                    getattr(move, 'fe_number', None)
                    or getattr(move, 'l10n_gt_dte_number', None)
                    or getattr(move, 'numero_serie', None)
                    or move.ref
                    or ''
                )
                rows.append({
                    'no':             i,
                    'date':           aml.date,
                    'ref':            move.name or '',
                    'ref_doc':        ref_doc,
                    'label':          aml.name or '',
                    'partner':        aml.partner_id.name or '',
                    'debit':          aml.debit,
                    'credit':         aml.credit,
                    'balance':        running,
                    'amount_foreign': abs(aml.amount_currency) if is_foreign else 0.0,
                    'currency_sym':   aml.currency_id.symbol if is_foreign else '',
                })
            result.append({
                'account_code':  data['code'],
                'account_name':  data['name'],
                'opening':       data['opening'],
                'lines':         rows,
                'total_debit':   sum(l['debit']  for l in rows),
                'total_credit':  sum(l['credit'] for l in rows),
                'closing':       running,
            })
        return result

    def _get_mayor_folios(self):
        accounts      = self._get_mayor_lines()
        ROWS_PER_PAGE = 35
        global_folio  = self.folio_start
        grand_debit   = 0.0
        grand_credit  = 0.0

        for acc in accounts:
            lines = acc.pop('lines')
            acc['folios'] = []
            cum_debit  = 0.0
            cum_credit = 0.0
            for idx, start in enumerate(range(0, max(len(lines), 1), ROWS_PER_PAGE)):
                chunk          = lines[start:start + ROWS_PER_PAGE]
                is_last        = (start + ROWS_PER_PAGE) >= len(lines)
                partial_debit  = sum(l['debit']  for l in chunk)
                partial_credit = sum(l['credit'] for l in chunk)
                prev_cum_d = cum_debit
                prev_cum_c = cum_credit
                cum_debit  += partial_debit
                cum_credit += partial_credit
                acc['folios'].append({
                    'folio_no':        idx + 1,
                    'global_folio':    global_folio,
                    'is_first':        idx == 0,
                    'is_last':         is_last,
                    'needs_page_break': idx > 0,
                    'lines':           chunk,
                    'partial_debit':   partial_debit,
                    'partial_credit':  partial_credit,
                    'cum_debit':       cum_debit,
                    'cum_credit':      cum_credit,
                    'prev_cum_debit':  prev_cum_d,
                    'prev_cum_credit': prev_cum_c,
                    'prev_balance':    (lines[start - 1]['balance'] if start > 0
                                        else acc['opening']),
                })
                global_folio += 1
            grand_debit  += acc['total_debit']
            grand_credit += acc['total_credit']

        return accounts, grand_debit, grand_credit

    def _get_diario_folios(self):
        entries, total_debit, total_credit = self._get_diario_lines()
        # Per-page row capacities. First page carries the full company header (~35 mm),
        # continuation pages have a compact 1-line header. Spacer rows (~5 px) are
        # excluded from the entry_rows count to avoid overcounting.
        FIRST_PAGE_CAP = 60
        CONT_PAGE_CAP  = 72
        global_folio = self.folio_start
        folios       = []
        cur_entries  = []
        cur_rows     = 0

        def _cap(is_first):
            return FIRST_PAGE_CAP if is_first else CONT_PAGE_CAP

        for entry in entries:
            # 1 header row + N detail lines + 1 total row (spacer is tiny, not counted)
            entry_rows = len(entry['lines']) + 2
            is_first   = (global_folio == self.folio_start)
            if cur_entries and (cur_rows + entry_rows) > _cap(is_first):
                folios.append({'entries': cur_entries})
                global_folio += 1
                cur_entries  = []
                cur_rows     = 0
            cur_entries.append(entry)
            cur_rows += entry_rows

        if cur_entries:
            folios.append({'entries': cur_entries})

        # Second pass: assign folio numbers, is_first/is_last flags and
        # cumulative carry-over subtotals (viene de / pasa a página siguiente).
        cum_debit = cum_credit = 0.0
        n = len(folios)
        for i, folio in enumerate(folios):
            page_debit  = sum(e['entry_debit']  for e in folio['entries'])
            page_credit = sum(e['entry_credit'] for e in folio['entries'])
            folio['folio_no']     = self.folio_start + i
            folio['is_first']     = (i == 0)
            folio['is_last']      = (i == n - 1)
            folio['carry_debit']  = cum_debit      # comes from previous page
            folio['carry_credit'] = cum_credit
            cum_debit  += page_debit
            cum_credit += page_credit
            folio['cum_debit']    = cum_debit      # passes to next page
            folio['cum_credit']   = cum_credit

        return folios, total_debit, total_credit

    def _export_excel_diario(self):
        import io, base64
        try:
            import xlsxwriter
        except ImportError:
            raise UserError(_('xlsxwriter no está instalado. Ejecute: pip install xlsxwriter'))

        entries, total_debit, total_credit = self._get_diario_lines()
        company  = self.env.company
        filename = 'Libro_Diario_%s_%s.xlsx' % (self.date_from, self.date_to)

        output = io.BytesIO()
        wb     = xlsxwriter.Workbook(output, {'in_memory': True})
        ws     = wb.add_worksheet('LIBRO DIARIO')

        NCOLS   = 9
        NAVY    = '#1e3a5f'
        WHITE   = '#FFFFFF'
        BASE    = {'border': 1, 'font_size': 8, 'valign': 'vcenter'}

        def _f(**kw):
            d = dict(BASE); d.update(kw); return wb.add_format(d)

        f_co    = wb.add_format({'bold': True, 'font_size': 11, 'align': 'center', 'valign': 'vcenter'})
        f_title = wb.add_format({'bold': True, 'font_size': 13, 'align': 'center', 'valign': 'vcenter'})
        f_meta  = wb.add_format({'align': 'center', 'font_size': 8, 'valign': 'vcenter'})
        f_hdr   = _f(bold=True, bg_color=NAVY, font_color=WHITE, align='center', valign='vcenter', text_wrap=True)
        f_entry = _f(bold=True, bg_color='#e8f0fe', align='left', valign='vcenter')
        f_ctr   = _f(align='center', valign='vcenter')
        f_txt   = _f(align='left', valign='vcenter')
        f_num   = _f(align='right', valign='vcenter', num_format='#,##0.00')
        f_tot_l = _f(bold=True, bg_color=NAVY, font_color=WHITE, align='left', valign='vcenter')
        f_tot_n = _f(bold=True, bg_color=NAVY, font_color=WHITE, align='right', valign='vcenter', num_format='#,##0.00')
        f_cert  = wb.add_format({'font_size': 8, 'text_wrap': True, 'valign': 'vcenter'})
        f_sig_n = wb.add_format({'bold': True, 'align': 'center', 'top': 2, 'valign': 'vcenter', 'font_size': 8})
        f_sig_r = wb.add_format({'align': 'center', 'font_size': 8, 'valign': 'vcenter'})

        ws.set_column(0, 0, 6)   # No. Asiento
        ws.set_column(1, 1, 10)  # Fecha
        ws.set_column(2, 2, 15)  # Referencia
        ws.set_column(3, 3, 10)  # Cuenta
        ws.set_column(4, 4, 28)  # Nombre Cuenta
        ws.set_column(5, 5, 30)  # Descripción
        ws.set_column(6, 6, 22)  # Contacto
        ws.set_column(7, 7, 12)  # Debe
        ws.set_column(8, 8, 12)  # Haber

        ws.set_paper(1); ws.set_default_row(10)

        row = 0
        ws.merge_range(row, 0, row, NCOLS - 1, company.name, f_co); row += 1
        if company.street:
            ws.merge_range(row, 0, row, NCOLS - 1, company.street, f_meta); row += 1
        if company.vat:
            ws.merge_range(row, 0, row, NCOLS - 1, 'NIT: ' + company.vat, f_meta); row += 1
        ws.merge_range(row, 0, row, NCOLS - 1, 'LIBRO DIARIO', f_title); row += 1
        period_str = ''
        if self.date_from and self.date_to:
            period_str = 'Período: %s al %s' % (self.date_from.strftime('%d/%m/%Y'), self.date_to.strftime('%d/%m/%Y'))
        ws.merge_range(row, 0, row, NCOLS - 1, period_str, f_meta); row += 2

        # Column headers: 9 columns
        for col, lbl in enumerate(['No.Asiento', 'Fecha', 'Referencia', 'Cuenta', 'Nombre Cuenta', 'Descripción', 'Contacto', 'Debe', 'Haber']):
            ws.write(row, col, lbl, f_hdr)
        row += 1

        for entry in entries:
            # Entry header row
            ws.merge_range(row, 0, row, 6,
                           '%s | %s | %s' % (entry['name'], str(entry['date']), entry['ref']),
                           f_entry)
            ws.write(row, 7, entry['entry_debit'],  f_num)
            ws.write(row, 8, entry['entry_credit'], f_num)
            row += 1
            for ln in entry['lines']:
                ws.write(row, 0, entry['no'],        f_ctr)
                ws.write(row, 1, str(entry['date']), f_ctr)
                ws.write(row, 2, entry['ref'],       f_txt)
                ws.write(row, 3, ln['account_code'], f_txt)
                ws.write(row, 4, ln['account_name'], f_txt)
                ws.write(row, 5, ln['label'],        f_txt)
                ws.write(row, 6, ln['partner'],      f_txt)
                ws.write(row, 7, ln['debit']  or '', f_num)
                ws.write(row, 8, ln['credit'] or '', f_num)
                row += 1

        ws.merge_range(row, 0, row, 6, 'TOTALES', f_tot_l)
        ws.write(row, 7, total_debit,  f_tot_n)
        ws.write(row, 8, total_credit, f_tot_n)
        row += 2

        mes  = self._month_name()
        anio = self._year_str()
        df   = self.date_from.strftime('%d') if self.date_from else '__'
        dt   = self.date_to.strftime('%d')   if self.date_to   else '__'
        cert = (
            'EL INFRASCRITO PERITO CONTADOR %(name)s REGISTRADO ANTE LA '
            'SUPERINTENDENCIA DE ADMINISTRACIÓN TRIBUTARIA -SAT- CON EL NÚMERO DE '
            'REGISTRO %(nit)s, CERTIFICA: QUE LOS REGISTROS CONTENIDOS EN EL PRESENTE '
            'LIBRO DIARIO, PROPIEDAD DE LA EMPRESA %(co)s, CORRESPONDIENTES A LA FECHA DEL '
            '%(df)s AL %(dt)s DEL MES %(mes)s DEL AÑO %(anio)s, PRESENTAN INFORMACIÓN '
            'RAZONABLE Y OBJETIVA SEGÚN LOS MOVIMIENTOS REALIZADOS.'
        ) % {
            'name': (company.ktx_contador_id.name or '___________________________').upper(),
            'nit':  (company.ktx_contador_id.vat  or '_______________').upper(),
            'co': company.name.upper(), 'df': df, 'dt': dt, 'mes': mes, 'anio': anio,
        }
        ws.merge_range(row, 0, row + 1, NCOLS - 1, cert, f_cert)
        ws.set_row(row, 50); row += 4

        sc1, sc2 = 1, 6
        ws.write(row,     sc1, company.ktx_contador_id.name  or '___________________________', f_sig_n)
        ws.write(row + 1, sc1, 'Perito Contador', f_sig_r)
        ws.write(row + 2, sc1, 'NIT: %s' % (company.ktx_contador_id.vat  or '_______________'), f_sig_r)
        ws.write(row,     sc2, company.ktx_rep_legal_id.name or '___________________________', f_sig_n)
        ws.write(row + 1, sc2, 'Representante Legal', f_sig_r)
        ws.write(row + 2, sc2, 'NIT: %s' % (company.ktx_rep_legal_id.vat or '_______________'), f_sig_r)

        wb.close()
        xls_data   = base64.b64encode(output.getvalue()).decode()
        attachment = self.env['ir.attachment'].create({
            'name': filename, 'type': 'binary', 'datas': xls_data,
            'res_model': self._name, 'res_id': self.id,
        })
        return {
            'type':   'ir.actions.act_url',
            'url':    '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }

    def _export_excel_mayor(self):
        import io, base64
        try:
            import xlsxwriter
        except ImportError:
            raise UserError(_('xlsxwriter no está instalado. Ejecute: pip install xlsxwriter'))

        accounts = self._get_mayor_lines()
        company  = self.env.company
        filename = 'Libro_Mayor_%s_%s.xlsx' % (self.date_from, self.date_to)

        output = io.BytesIO()
        wb     = xlsxwriter.Workbook(output, {'in_memory': True})
        ws     = wb.add_worksheet('LIBRO MAYOR')

        NCOLS   = 9
        NAVY    = '#1e3a5f'
        WHITE   = '#FFFFFF'
        BASE    = {'border': 1, 'font_size': 8, 'valign': 'vcenter'}

        def _f(**kw):
            d = dict(BASE); d.update(kw); return wb.add_format(d)

        f_co    = wb.add_format({'bold': True, 'font_size': 11, 'align': 'center', 'valign': 'vcenter'})
        f_title = wb.add_format({'bold': True, 'font_size': 13, 'align': 'center', 'valign': 'vcenter'})
        f_meta  = wb.add_format({'align': 'center', 'font_size': 8, 'valign': 'vcenter'})
        f_hdr   = _f(bold=True, bg_color=NAVY, font_color=WHITE, align='center', valign='vcenter', text_wrap=True)
        f_acc   = _f(bold=True, bg_color='#dbeafe', align='left', valign='vcenter')
        f_clo   = _f(bold=True, bg_color='#fef3c7', align='left', valign='vcenter')
        f_clo_n = _f(bold=True, bg_color='#fef3c7', align='right', valign='vcenter', num_format='#,##0.00')
        f_ctr   = _f(align='center', valign='vcenter')
        f_txt   = _f(align='left', valign='vcenter')
        f_num   = _f(align='right', valign='vcenter', num_format='#,##0.00')
        f_for   = _f(align='right', valign='vcenter', num_format='#,##0.00', font_color='#0369a1')
        f_cert  = wb.add_format({'font_size': 8, 'text_wrap': True, 'valign': 'vcenter'})
        f_sig_n = wb.add_format({'bold': True, 'align': 'center', 'top': 2, 'valign': 'vcenter', 'font_size': 8})
        f_sig_r = wb.add_format({'align': 'center', 'font_size': 8, 'valign': 'vcenter'})

        # 9 cols: No. | Fecha | Póliza | Ref.Doc | Descripción | Contacto | Dólares | Debe | Haber | Saldo
        ws.set_column(0, 0, 5)   # No.
        ws.set_column(1, 1, 10)  # Fecha
        ws.set_column(2, 2, 16)  # Póliza
        ws.set_column(3, 3, 16)  # Ref. Documento
        ws.set_column(4, 4, 26)  # Descripción
        ws.set_column(5, 5, 22)  # Contacto
        ws.set_column(6, 6, 10)  # Dólares
        ws.set_column(7, 7, 12)  # Debe
        ws.set_column(8, 8, 12)  # Haber
        ws.set_column(9, 9, 14)  # Saldo
        NCOLS = 10

        ws.set_landscape(); ws.set_paper(1); ws.set_default_row(10)

        row = 0
        ws.merge_range(row, 0, row, NCOLS - 1, company.name, f_co); row += 1
        if company.street:
            ws.merge_range(row, 0, row, NCOLS - 1, company.street, f_meta); row += 1
        if company.vat:
            ws.merge_range(row, 0, row, NCOLS - 1, 'NIT: ' + company.vat, f_meta); row += 1
        ws.merge_range(row, 0, row, NCOLS - 1, 'LIBRO MAYOR', f_title); row += 1
        period_str = ''
        if self.date_from and self.date_to:
            period_str = 'Período: %s al %s' % (self.date_from.strftime('%d/%m/%Y'), self.date_to.strftime('%d/%m/%Y'))
        ws.merge_range(row, 0, row, NCOLS - 1, period_str, f_meta); row += 2

        for acc in accounts:
            # Account header
            ws.merge_range(row, 0, row, 6,
                           '%s — %s  |  Saldo Inicial: %s' % (
                               acc['account_code'], acc['account_name'],
                               '{:,.2f}'.format(acc['opening'])),
                           f_acc)
            ws.write(row, 7, acc['total_debit'],  f_num)
            ws.write(row, 8, acc['total_credit'], f_num)
            ws.write(row, 9, acc['closing'],      f_num)
            row += 1

            # Column sub-headers
            for col, lbl in enumerate(['No.', 'Fecha', 'Póliza', 'Ref. Documento',
                                       'Descripción', 'Contacto', 'Dólares', 'Debe', 'Haber', 'Saldo']):
                ws.write(row, col, lbl, f_hdr)
            row += 1

            for ln in acc['lines']:
                ws.write(row, 0, ln['no'],          f_ctr)
                ws.write(row, 1, str(ln['date']),   f_ctr)
                ws.write(row, 2, ln['ref'],          f_txt)
                ws.write(row, 3, ln['ref_doc'],      f_txt)
                ws.write(row, 4, ln['label'],        f_txt)
                ws.write(row, 5, ln['partner'],      f_txt)
                ws.write(row, 6, ln['amount_foreign'] or '', f_for)
                ws.write(row, 7, ln['debit']  or '', f_num)
                ws.write(row, 8, ln['credit'] or '', f_num)
                ws.write(row, 9, ln['balance'],      f_num)
                row += 1

            # Closing row
            ws.merge_range(row, 0, row, 6, 'SALDO FINAL: %s' % acc['account_name'], f_clo)
            ws.write(row, 7, acc['total_debit'],  f_clo_n)
            ws.write(row, 8, acc['total_credit'], f_clo_n)
            ws.write(row, 9, acc['closing'],      f_clo_n)
            row += 2

        mes  = self._month_name()
        anio = self._year_str()
        df   = self.date_from.strftime('%d') if self.date_from else '__'
        dt   = self.date_to.strftime('%d')   if self.date_to   else '__'
        cert = (
            'EL INFRASCRITO PERITO CONTADOR %(name)s REGISTRADO ANTE LA '
            'SUPERINTENDENCIA DE ADMINISTRACIÓN TRIBUTARIA -SAT- CON EL NÚMERO DE '
            'REGISTRO %(nit)s, CERTIFICA: QUE LOS REGISTROS CONTENIDOS EN EL PRESENTE '
            'LIBRO MAYOR, PROPIEDAD DE LA EMPRESA %(co)s, CORRESPONDIENTES A LA FECHA DEL '
            '%(df)s AL %(dt)s DEL MES %(mes)s DEL AÑO %(anio)s, PRESENTAN INFORMACIÓN '
            'RAZONABLE Y OBJETIVA SEGÚN LOS MOVIMIENTOS REALIZADOS.'
        ) % {
            'name': (company.ktx_contador_id.name or '___________________________').upper(),
            'nit':  (company.ktx_contador_id.vat  or '_______________').upper(),
            'co': company.name.upper(), 'df': df, 'dt': dt, 'mes': mes, 'anio': anio,
        }
        ws.merge_range(row, 0, row + 1, NCOLS - 1, cert, f_cert)
        ws.set_row(row, 50); row += 4

        sc1, sc2 = 2, 7
        ws.write(row,     sc1, company.ktx_contador_id.name  or '___________________________', f_sig_n)
        ws.write(row + 1, sc1, 'Perito Contador', f_sig_r)
        ws.write(row + 2, sc1, 'NIT: %s' % (company.ktx_contador_id.vat  or '_______________'), f_sig_r)
        ws.write(row,     sc2, company.ktx_rep_legal_id.name or '___________________________', f_sig_n)
        ws.write(row + 1, sc2, 'Representante Legal', f_sig_r)
        ws.write(row + 2, sc2, 'NIT: %s' % (company.ktx_rep_legal_id.vat or '_______________'), f_sig_r)

        wb.close()
        xls_data   = base64.b64encode(output.getvalue()).decode()
        attachment = self.env['ir.attachment'].create({
            'name': filename, 'type': 'binary', 'datas': xls_data,
            'res_model': self._name, 'res_id': self.id,
        })
        return {
            'type':   'ir.actions.act_url',
            'url':    '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }

    def action_export_excel(self):
        import io, base64
        try:
            import xlsxwriter
        except ImportError:
            raise UserError(_('xlsxwriter no está instalado. Ejecute: pip install xlsxwriter'))

        self.ensure_one()
        if self.book_type == 'diario':
            return self._export_excel_diario()
        if self.book_type == 'mayor':
            return self._export_excel_mayor()
        if self.book_type not in ('compras', 'ventas'):
            raise UserError(_('La exportación Excel no está disponible para este tipo de libro.'))

        lines, totals = self._get_book_lines()
        resumen       = self._get_resumen(lines, totals)
        company       = self.env.company
        mes           = self._month_name()
        anio          = self._year_str()
        is_compras    = self.book_type == 'compras'
        book_name     = 'LIBRO DE COMPRAS Y SERVICIOS' if is_compras else 'LIBRO DE VENTAS Y SERVICIOS'
        imp_label     = 'IMPORTACION' if is_compras else 'EXPORTACION'
        partner_label = 'Proveedor' if is_compras else 'Cliente'
        filename      = 'Libro_%s_%s_%s.xlsx' % (
            'Compras' if is_compras else 'Ventas', self.date_from, self.date_to)

        output = io.BytesIO()
        wb     = xlsxwriter.Workbook(output, {'in_memory': True})
        ws     = wb.add_worksheet(book_name[:31])

        NCOLS   = 17
        NAVY    = '#1e3a5f'
        NAVY_DK = '#162d4a'
        WHITE   = '#FFFFFF'
        BASE    = {'border': 1, 'font_size': 8, 'valign': 'vcenter'}

        def _f(**kw):
            d = dict(BASE); d.update(kw); return wb.add_format(d)

        f_co    = wb.add_format({'bold': True, 'font_size': 11, 'align': 'center', 'valign': 'vcenter'})
        f_title = wb.add_format({'bold': True, 'font_size': 13, 'align': 'center', 'valign': 'vcenter'})
        f_meta  = wb.add_format({'align': 'center', 'font_size': 8, 'valign': 'vcenter'})
        f_hdr   = _f(bold=True, bg_color=NAVY, font_color=WHITE, align='center', valign='vcenter', text_wrap=True)
        f_sec   = _f(bold=True, bg_color=NAVY_DK, font_color=WHITE, align='center', valign='vcenter', text_wrap=True)
        f_ctr   = _f(align='center', valign='vcenter')
        f_txt   = _f(align='left', valign='vcenter')
        f_num   = _f(align='right', valign='vcenter', num_format='#,##0.00')
        f_tot_l = _f(bold=True, bg_color=NAVY, font_color=WHITE, align='left', valign='vcenter')
        f_tot_n = _f(bold=True, bg_color=NAVY, font_color=WHITE, align='right', valign='vcenter', num_format='#,##0.00')
        f_rh    = wb.add_format({'bold': True, 'bg_color': NAVY, 'font_color': WHITE, 'align': 'center', 'border': 1, 'valign': 'vcenter', 'font_size': 8})
        f_rl    = wb.add_format({'align': 'left',  'border': 1, 'valign': 'vcenter', 'font_size': 8})
        f_rn    = wb.add_format({'align': 'right', 'border': 1, 'num_format': '#,##0.00', 'valign': 'vcenter', 'font_size': 8})
        f_rtl   = wb.add_format({'bold': True, 'bg_color': NAVY, 'font_color': WHITE, 'align': 'left',  'border': 1, 'valign': 'vcenter', 'font_size': 8})
        f_rtn   = wb.add_format({'bold': True, 'bg_color': NAVY, 'font_color': WHITE, 'align': 'right', 'border': 1, 'num_format': '#,##0.00', 'valign': 'vcenter', 'font_size': 8})
        f_cert  = wb.add_format({'font_size': 8, 'text_wrap': True, 'valign': 'vcenter'})
        f_sig_n = wb.add_format({'bold': True, 'align': 'center', 'top': 2, 'valign': 'vcenter', 'font_size': 8})
        f_sig_r = wb.add_format({'align': 'center', 'font_size': 8, 'valign': 'vcenter'})

        ws.set_column(0, 0, 4);   ws.set_column(1, 1, 4);   ws.set_column(2, 2, 7)
        ws.set_column(3, 3, 11);  ws.set_column(4, 4, 9);   ws.set_column(5, 5, 14)
        ws.set_column(6, 13, 9);  ws.set_column(14, 14, 8); ws.set_column(15, 15, 9)
        ws.set_column(16, 16, 11)

        row = 0
        ws.set_landscape(); ws.set_paper(1); ws.fit_to_pages(1, 0); ws.set_default_row(10)

        ws.merge_range(row, 0, row, NCOLS - 1, company.name, f_co); row += 1
        if company.street:
            ws.merge_range(row, 0, row, NCOLS - 1, company.street, f_meta); row += 1
        if company.vat:
            ws.merge_range(row, 0, row, NCOLS - 1, 'NIT: ' + company.vat, f_meta); row += 1
        ws.merge_range(row, 0, row, NCOLS - 1, book_name, f_title); row += 1
        ws.merge_range(row, 0, row, NCOLS - 1,
                       'Mes: %s   Año: %s   Cantidad de %ss: %d' % (mes, anio, partner_label, len(lines)),
                       f_meta); row += 2

        r0, r1, r2 = row, row + 1, row + 2
        for col, lbl in [(0,'No.'),(1,'Día'),(2,'Serie'),(3,'Número'),
                         (4,'NIT'),(5,partner_label),
                         (14,'Pequeño\nContrib.'),(15,'IVA'),(16,'Total')]:
            ws.merge_range(r0, col, r2, col, lbl, f_hdr)
        ws.merge_range(r0, 6,  r0, 9,  'LOCAL',     f_sec)
        ws.merge_range(r0, 10, r0, 13, imp_label,   f_sec)
        ws.merge_range(r1, 6,  r1, 7,  'Gravada',   f_sec)
        ws.merge_range(r1, 8,  r1, 9,  'Exenta',    f_sec)
        ws.merge_range(r1, 10, r1, 11, 'Gravada',   f_sec)
        ws.merge_range(r1, 12, r1, 13, 'Exenta',    f_sec)
        for c in range(6, 14):
            ws.write(r2, c, 'Bienes' if (c - 6) % 2 == 0 else 'Servicios', f_hdr)
        ws.set_row(r0, 16); ws.set_row(r1, 12); ws.set_row(r2, 12)
        row += 3

        NUM_KEYS = ['local_grav_bienes','local_grav_serv','local_exe_bienes','local_exe_serv',
                    'import_grav_bienes','import_grav_serv','import_exe_bienes','import_exe_serv',
                    'pequeno_cont','iva','total']
        CTR_COLS = {0, 1, 2, 3, 4}
        for line in lines:
            ws.set_row(row, 10)
            for col, key in enumerate(['no','dia','serie','numero','nit','partner'] + NUM_KEYS):
                val = line.get(key, '')
                if col in CTR_COLS:
                    ws.write(row, col, val, f_ctr)
                elif col == 5:
                    ws.write(row, col, val, f_txt)
                elif val:
                    ws.write(row, col, val, f_num)
                else:
                    ws.write(row, col, '', f_num)
            row += 1

        ws.merge_range(row, 0, row, 5, 'TOTALES', f_tot_l)
        for col, key in enumerate(NUM_KEYS, 6):
            ws.write(row, col, totals.get(key, 0), f_tot_n)
        row += 2

        ws.merge_range(row, 0, row, 4, 'RESUMEN',
                       wb.add_format({'bold': True, 'font_size': 11, 'align': 'center'}))
        row += 1
        for col, lbl in enumerate(['Clasificacion','Gravado','No Gravado','IVA','Total']):
            ws.write(row, col, lbl, f_rh)
        row += 1
        for rs in resumen:
            is_tot = rs.get('is_total')
            fl, fn = (f_rtl, f_rtn) if is_tot else (f_rl, f_rn)
            ws.write(row, 0, rs['label'], fl)
            ws.write(row, 1, rs['grav']  or '', fn if rs['grav']  else fl)
            ws.write(row, 2, rs['exe']   or '', fn if rs['exe']   else fl)
            ws.write(row, 3, rs['iva']   or '', fn if rs['iva']   else fl)
            ws.write(row, 4, rs['total'], fn)
            row += 1
        row += 1

        df  = self.date_from.strftime('%d') if self.date_from else '__'
        dt  = self.date_to.strftime('%d')   if self.date_to   else '__'
        cert = (
            'EL INFRASCRITO PERITO CONTADOR %(name)s REGISTRADO ANTE LA '
            'SUPERINTENDENCIA DE ADMINISTRACIÓN TRIBUTARIA -SAT- CON EL NÚMERO DE '
            'REGISTRO %(nit)s, CERTIFICA: QUE LOS REGISTROS CONTENIDOS EN EL PRESENTE '
            '%(book)s, PROPIEDAD DE LA EMPRESA %(co)s, CORRESPONDIENTES A LA FECHA DEL '
            '%(df)s AL %(dt)s DEL MES %(mes)s DEL AÑO %(anio)s, PRESENTAN INFORMACIÓN '
            'RAZONABLE Y OBJETIVA SEGÚN LOS MOVIMIENTOS REALIZADOS.'
        ) % {
            'name': (company.ktx_contador_id.name or '___________________________').upper(),
            'nit':  (company.ktx_contador_id.vat  or '_______________').upper(),
            'book': book_name, 'co': company.name.upper(),
            'df': df, 'dt': dt, 'mes': mes, 'anio': anio,
        }
        ws.merge_range(row, 0, row + 1, NCOLS - 1, cert, f_cert)
        ws.set_row(row, 50); row += 4

        sc1, sc2 = 3, 12
        ws.write(row,     sc1, company.ktx_contador_id.name  or '___________________________', f_sig_n)
        ws.write(row + 1, sc1, 'Perito Contador', f_sig_r)
        ws.write(row + 2, sc1, 'NIT: %s' % (company.ktx_contador_id.vat  or '_______________'), f_sig_r)
        ws.write(row,     sc2, company.ktx_rep_legal_id.name or '___________________________', f_sig_n)
        ws.write(row + 1, sc2, 'Representante Legal', f_sig_r)
        ws.write(row + 2, sc2, 'NIT: %s' % (company.ktx_rep_legal_id.vat or '_______________'), f_sig_r)

        wb.close()
        xls_data   = base64.b64encode(output.getvalue()).decode()
        attachment = self.env['ir.attachment'].create({
            'name': filename, 'type': 'binary', 'datas': xls_data,
            'res_model': self._name, 'res_id': self.id,
        })
        return {
            'type':   'ir.actions.act_url',
            'url':    '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }
