# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.tools import html_escape

_logger = logging.getLogger(__name__)


class CheckPrintWizard(models.TransientModel):
    _name = 'ktx.check.print.wizard'
    _description = 'Asistente de Impresión de Cheque'

    payment_id = fields.Many2one(
        comodel_name='account.payment',
        string='Pago',
        required=True,
        ondelete='cascade',
    )
    preview_html = fields.Html(
        string='Vista Previa',
        compute='_compute_preview_html',
        sanitize=False,
    )

    @api.depends('payment_id')
    def _compute_preview_html(self):
        for rec in self:
            if not rec.payment_id:
                rec.preview_html = ''
                continue
            rec.preview_html = rec._build_preview_html()

    def _build_preview_html(self):
        p = self.payment_id
        symbol = p.currency_id.symbol or 'Q'
        amount_str = '{:,.2f}'.format(p.amount)
        date_str = html_escape(p._ktx_get_date_formatted())
        amount_words = html_escape(p._ktx_get_amount_in_words())
        partner_name = html_escape((p.partner_id.name or '').upper())
        check_num = html_escape(p.payment_reference or p.name or '')
        company = p.company_id
        bank_display = html_escape(p._ktx_get_bank_display())
        exch_rate = p._ktx_get_exchange_rate()
        memo_val = html_escape(getattr(p, 'memo', '') or getattr(p, 'ref', '') or '')
        created_by = html_escape(p.create_uid.name or '')

        # Accounting lines from the journal entry
        move_lines = []
        total_debit = 0.0
        total_credit = 0.0
        if p.move_id:
            for line in p.move_id.line_ids:
                move_lines.append({
                    'account': html_escape(line.account_id.code or ''),
                    'name': html_escape(line.account_id.name or ''),
                    'debit': line.debit,
                    'credit': line.credit,
                })
                total_debit += line.debit
                total_credit += line.credit

        # Build table rows for accounting lines (minimum 4 rows for appearance)
        line_rows = ''
        for ml in move_lines:
            d_str = '{:,.2f}'.format(ml['debit']) if ml['debit'] else '&nbsp;'
            c_str = '{:,.2f}'.format(ml['credit']) if ml['credit'] else '&nbsp;'
            line_rows += (
                '<tr>'
                '<td style="border:1px solid #ccc;padding:3px 6px;">{}</td>'
                '<td style="border:1px solid #ccc;padding:3px 6px;">{}</td>'
                '<td style="border:1px solid #ccc;padding:3px 6px;text-align:right;">{}</td>'
                '<td style="border:1px solid #ccc;padding:3px 6px;text-align:right;">{}</td>'
                '</tr>'
            ).format(ml['account'], ml['name'], d_str, c_str)
        blank_needed = max(0, 4 - len(move_lines))
        for _ in range(blank_needed):
            line_rows += (
                '<tr>'
                '<td style="border:1px solid #ccc;padding:6px;">&nbsp;</td>'
                '<td style="border:1px solid #ccc;padding:6px;">&nbsp;</td>'
                '<td style="border:1px solid #ccc;padding:6px;">&nbsp;</td>'
                '<td style="border:1px solid #ccc;padding:6px;">&nbsp;</td>'
                '</tr>'
            )

        non_neg_html = (
            '<div style="text-align:right;font-weight:bold;margin-top:4px;">'
            'NO NEGOCIABLE</div>'
        ) if p.ktx_non_negotiable else ''

        # Company logo
        logo_html = ''
        if company.logo:
            logo_html = (
                '<img src="/web/image/res.company/{}/logo" '
                'style="max-height:50px;max-width:110px;"/>'
            ).format(company.id)

        company_name = html_escape(company.name or '')
        company_street = html_escape(company.street or '')
        company_phone = html_escape(company.phone or '')

        return '''
<div style="font-family:Arial,Helvetica,sans-serif;font-size:9pt;max-width:700px;margin:0 auto;">

  <!-- SECCIÓN CHEQUE -->
  <div style="border:2px solid #555;border-radius:8px;padding:10px 16px 8px 16px;
              margin-bottom:10px;background:#fff;">
    <div style="font-weight:bold;font-size:13pt;letter-spacing:1px;margin-bottom:8px;">
      {check_num}
    </div>
    <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px;">
      <span>{date_str}</span>
      <span style="font-weight:bold;font-size:11pt;">****{symbol}{amount_str}**</span>
    </div>
    <div style="font-weight:bold;font-style:italic;text-align:center;
                margin-bottom:8px;font-size:10pt;">
      **{partner_name}**
    </div>
    <div style="font-weight:bold;margin-bottom:6px;">
      **{amount_words}**
    </div>
    {non_neg_html}
    <div style="height:30px;"></div>
  </div>

  <!-- SECCIÓN VOUCHER -->
  <div style="border:1px solid #bbb;border-radius:8px;overflow:hidden;">

    <!-- Encabezado empresa -->
    <div style="display:flex;justify-content:space-between;align-items:flex-start;
                padding:8px 12px;border-bottom:1px solid #ddd;">
      <div style="font-size:9pt;line-height:1.5;">
        <strong>{company_name}</strong><br/>
        {company_street}<br/>
        {company_phone}
      </div>
      <div>{logo_html}</div>
    </div>

    <!-- Banco / Cheque No. -->
    <table style="width:100%;border-collapse:collapse;">
      <tr>
        <td style="border:1px solid #ccc;padding:4px 8px;width:60%;font-size:9pt;">
          {bank_display}
        </td>
        <td style="border:1px solid #ccc;padding:4px 8px;font-size:9pt;">
          <strong>Cheque No.: {check_num}</strong>
        </td>
      </tr>
      <tr>
        <td colspan="2" style="border:1px solid #ccc;padding:4px 8px;font-size:9pt;">
          <strong>Paguese a:</strong> {partner_name}
        </td>
      </tr>
      <tr>
        <td style="border:1px solid #ccc;padding:4px 8px;font-size:9pt;">
          <strong>Fecha:</strong> {date_str}
        </td>
        <td style="border:1px solid #ccc;padding:4px 8px;font-size:9pt;">
          <strong>Tasa de Cambio:</strong> {exch_rate:.5f}
        </td>
      </tr>
    </table>

    <!-- Póliza contable -->
    <table style="width:100%;border-collapse:collapse;font-size:9pt;">
      <thead>
        <tr style="background:#e0e0e0;">
          <th style="border:1px solid #ccc;padding:4px 6px;text-align:left;width:14%;">CUENTA</th>
          <th style="border:1px solid #ccc;padding:4px 6px;text-align:left;">DESCRIPCION</th>
          <th style="border:1px solid #ccc;padding:4px 6px;text-align:right;width:14%;">DEBE</th>
          <th style="border:1px solid #ccc;padding:4px 6px;text-align:right;width:14%;">HABER</th>
        </tr>
      </thead>
      <tbody>{line_rows}</tbody>
      <tfoot>
        <tr style="font-weight:bold;background:#f0f0f0;">
          <td colspan="2"
              style="border:1px solid #ccc;padding:4px 6px;text-align:right;">TOTALES</td>
          <td style="border:1px solid #ccc;padding:4px 6px;text-align:right;">
            {total_debit}
          </td>
          <td style="border:1px solid #ccc;padding:4px 6px;text-align:right;">
            {total_credit}
          </td>
        </tr>
      </tfoot>
    </table>

    <!-- Memo/concepto -->
    <div style="border:1px solid #ccc;padding:5px 8px;font-size:9pt;min-height:22px;">
      {memo_val}
    </div>

    <!-- Firmas -->
    <table style="width:100%;border-collapse:collapse;font-size:8pt;">
      <thead>
        <tr style="background:#e0e0e0;">
          <th style="border:1px solid #ccc;padding:3px 4px;">Hecho Por</th>
          <th style="border:1px solid #ccc;padding:3px 4px;">Revisado Por</th>
          <th style="border:1px solid #ccc;padding:3px 4px;">Aprobado Por</th>
          <th style="border:1px solid #ccc;padding:3px 4px;">Recibí Conforme</th>
          <th style="border:1px solid #ccc;padding:3px 4px;">Fecha</th>
          <th style="border:1px solid #ccc;padding:3px 4px;">Operado</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td style="border:1px solid #ccc;padding:10px 4px;">{created_by}</td>
          <td style="border:1px solid #ccc;padding:10px 4px;">&nbsp;</td>
          <td style="border:1px solid #ccc;padding:10px 4px;">&nbsp;</td>
          <td style="border:1px solid #ccc;padding:10px 4px;">&nbsp;</td>
          <td style="border:1px solid #ccc;padding:10px 4px;">&nbsp;</td>
          <td style="border:1px solid #ccc;padding:10px 4px;">&nbsp;</td>
        </tr>
      </tbody>
    </table>

  </div>
</div>
'''.format(
            check_num=check_num,
            date_str=date_str,
            symbol=html_escape(symbol),
            amount_str=html_escape(amount_str),
            partner_name=partner_name,
            amount_words=amount_words,
            non_neg_html=non_neg_html,
            company_name=company_name,
            company_street=company_street,
            company_phone=company_phone,
            logo_html=logo_html,
            bank_display=bank_display,
            exch_rate=exch_rate,
            line_rows=line_rows,
            total_debit='{:,.2f}'.format(total_debit),
            total_credit='{:,.2f}'.format(total_credit),
            memo_val=memo_val,
            created_by=created_by,
        )

    def _get_report_ref(self):
        company = self.payment_id.company_id or self.env.company
        fmt = company.ktx_check_paper_format or 'letter'
        if fmt == 'continuous':
            return 'ktx_check_print.action_report_ktx_check_continuous'
        return 'ktx_check_print.action_report_ktx_check_letter'

    def action_download_pdf(self):
        self.ensure_one()
        return self.env.ref(self._get_report_ref()).report_action(self.payment_id)

    def action_print(self):
        self.ensure_one()
        return self.env.ref(self._get_report_ref()).report_action(self.payment_id)
