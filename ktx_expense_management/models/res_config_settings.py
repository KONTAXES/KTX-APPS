# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    ktx_allow_journal_entries = fields.Boolean(
        string="Incluir Asientos Contables en Liquidaciones",
        config_parameter="ktx_expense_management.allow_journal_entries",
        help="Permite agregar asientos contables genéricos (no solo facturas de proveedor) a Gastos por Liquidar.",
    )
    ktx_multi_company_staging = fields.Boolean(
        string="Asignación Multiempresa",
        config_parameter="ktx_expense_management.multi_company_staging",
        help="Muestra gastos de todas las empresas en el selector de gastos por liquidar.",
    )
