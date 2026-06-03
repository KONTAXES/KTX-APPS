# -*- coding: utf-8 -*-
from odoo import fields, models


class KtxPettyCashCompanyAccount(models.Model):
    _name = "ktx.petty.cash.company.account"
    _description = "Cuenta Intercompañía - Caja Chica"

    fund_id = fields.Many2one("ktx.petty.cash.fund", string="Fondo", required=True, ondelete="cascade")
    company_id = fields.Many2one("res.company", string="Compañía", required=True, ondelete="cascade")
    account_id = fields.Many2one(
        "account.account", string="Cuenta Contable", required=True, ondelete="restrict",
        domain="[('account_type', 'in', ['liability_payable', 'asset_receivable'])]",
    )
