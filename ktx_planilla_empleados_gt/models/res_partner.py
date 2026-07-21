# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    ktx_pl_account_gasto_id = fields.Many2one(
        "account.account",
        string="Cuenta Gasto Sueldo",
        company_dependent=True,
        help="Cuenta de gasto de sueldos y salarios específica para este "
             "contacto/empleado. Si se deja vacía se usa la configurada en "
             "los ajustes de Planilla GT.",
    )
    ktx_pl_account_pagar_id = fields.Many2one(
        "account.account",
        string="Cuenta Sueldo por Pagar",
        company_dependent=True,
        help="Cuenta de pasivo de sueldos por pagar específica para este "
             "contacto/empleado. Si se deja vacía se usa la configurada en "
             "los ajustes de Planilla GT.",
    )
