# -*- coding: utf-8 -*-
import base64
from odoo import api, fields, models, _
from ..utils.amount_in_words import amount_to_words_es

_MONTHS_ES = {
    1: 'ENERO', 2: 'FEBRERO', 3: 'MARZO', 4: 'ABRIL',
    5: 'MAYO', 6: 'JUNIO', 7: 'JULIO', 8: 'AGOSTO',
    9: 'SEPTIEMBRE', 10: 'OCTUBRE', 11: 'NOVIEMBRE', 12: 'DICIEMBRE',
}


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    ktx_non_negotiable = fields.Boolean(
        string='No Negociable',
        default=False,
        help='Imprime "NO NEGOCIABLE" en el cuerpo del cheque.',
    )
    ktx_is_check_journal = fields.Boolean(
        compute='_compute_ktx_is_check_journal',
        store=False,
    )

    @api.depends('journal_id', 'payment_method_line_id')
    def _compute_ktx_is_check_journal(self):
        for payment in self:
            method_line = payment.payment_method_line_id
            if not method_line or not method_line.payment_method_id:
                payment.ktx_is_check_journal = False
                continue
            code = (method_line.payment_method_id.code or '').lower()
            name = (method_line.name or '').lower()
            payment.ktx_is_check_journal = 'check' in code or 'cheque' in name

    def _ktx_check_fname(self):
        parts = ['Cheque']
        ref = self.memo or self.ref
        if ref:
            parts.append(ref)
        if self.partner_id.name:
            parts.append(self.partner_id.name)
        return ' '.join(parts) + '.pdf'

    def action_ktx_save_check(self):
        """Genera el PDF, lo adjunta al chatter y notifica al usuario."""
        self.ensure_one()
        pdf_content, _mime = self.env['ir.actions.report']._render_qweb_pdf(
            'ktx_check_print.action_report_ktx_check_letter',
            self.ids,
        )
        attachment = self.env['ir.attachment'].create({
            'name': self._ktx_check_fname(),
            'type': 'binary',
            'datas': base64.b64encode(pdf_content),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })
        self.message_post(
            body=_('Cheque Voucher adjuntado'),
            attachment_ids=attachment.ids,
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Cheque adjuntado'),
                'message': _('El PDF fue generado y adjuntado al chatter.'),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_ktx_print_check(self):
        """Abre el diálogo de impresión del cheque en el navegador."""
        self.ensure_one()
        return self.env.ref(
            'ktx_check_print.action_report_ktx_check_letter'
        ).report_action(self)

    def action_ktx_open_check_wizard(self):
        self.ensure_one()
        wizard = self.env['ktx.check.print.wizard'].create({
            'payment_id': self.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Imprimir Cheque Voucher'),
            'res_model': 'ktx.check.print.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _ktx_get_amount_in_words(self):
        self.ensure_one()
        return amount_to_words_es(self.amount)

    def _ktx_get_date_formatted(self):
        """Returns 'CIUDAD DE GUATEMALA, 5 DE MAYO DE 2026'"""
        self.ensure_one()
        if not self.date:
            return ''
        city = (self.company_id.city or 'GUATEMALA').upper()
        d = self.date
        return '{}, {} DE {} DE {}'.format(city, d.day, _MONTHS_ES[d.month], d.year)

    def _ktx_get_exchange_rate(self):
        """Returns the exchange rate used for this payment (company_currency / payment_currency)."""
        self.ensure_one()
        company_currency = self.company_id.currency_id
        if not self.currency_id or self.currency_id == company_currency:
            return 1.0
        if self.move_id:
            lines = self.move_id.line_ids.filtered(
                lambda l: l.currency_id
                and l.currency_id != company_currency
                and l.amount_currency
            )
            if lines:
                line = lines[0]
                try:
                    return abs(line.balance / line.amount_currency)
                except ZeroDivisionError:
                    pass
        return 1.0

    def _ktx_get_bank_display(self):
        """Returns 'BANKNAME  ACCOUNT_NUMBER' for the voucher header."""
        self.ensure_one()
        bank_name = ''
        acc_number = ''
        if self.journal_id.bank_account_id:
            acc_number = self.journal_id.bank_account_id.acc_number or ''
            if self.journal_id.bank_account_id.bank_id:
                bank_name = self.journal_id.bank_account_id.bank_id.name or ''
        if not bank_name:
            bank_name = self.journal_id.name or ''
        return '{} {}'.format(bank_name, acc_number).strip()
