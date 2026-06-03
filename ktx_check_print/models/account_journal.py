# -*- coding: utf-8 -*-
from odoo import fields, models

KTX_BANK_FORMATS = [
    ('none', 'Sin formato específico'),
    ('promerica_gt', 'Bancos de Guatemala'),
]

_PARAM = 'ktx_check_print.bank_format.{}'


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    # store=False → no new column on account_journal, no UndefinedColumn on restart
    ktx_check_bank_format = fields.Selection(
        KTX_BANK_FORMATS,
        string='Formato de Cheque KTX',
        compute='_compute_ktx_check_bank_format',
        inverse='_inverse_ktx_check_bank_format',
        store=False,
    )

    def _compute_ktx_check_bank_format(self):
        get = self.env['ir.config_parameter'].sudo().get_param
        for journal in self:
            journal.ktx_check_bank_format = get(
                _PARAM.format(journal.id), 'none'
            )

    def _inverse_ktx_check_bank_format(self):
        set_param = self.env['ir.config_parameter'].sudo().set_param
        for journal in self:
            set_param(
                _PARAM.format(journal.id),
                journal.ktx_check_bank_format or 'none',
            )
