# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    ktx_expense_limit = fields.Float(
        string="Límite de Gasto",
        default=0.0,
        help="Monto máximo permitido en liquidaciones para este empleado/beneficiario. "
             "Si es 0, no se aplica ningún límite.",
    )
