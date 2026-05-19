# -*- coding: utf-8 -*-
from odoo import fields, models


class SettlementCompanyAccount(models.Model):
    _name = "ktx.settlement.company.account"
    _description = "Cuenta por Pagar Intercompañía por Empresa"
    _order = "company_id"

    settlement_id = fields.Many2one(
        "ktx.settlement", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        "res.company", required=True, string="Empresa del Gasto", ondelete="cascade"
    )
    account_id = fields.Many2one(
        "account.account",
        string="Cuenta por Pagar Intercompañía",
        domain="[('account_type', 'in', ['asset_receivable', 'liability_payable', 'liability_current']), ('company_ids', 'in', [company_id])]",
        help="Cuenta que se acreditará en el asiento espejo creado en esta empresa.",
        ondelete="restrict",
    )
