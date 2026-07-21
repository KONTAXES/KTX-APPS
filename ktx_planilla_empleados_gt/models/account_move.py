# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    ktx_pl_linea_id = fields.Many2one(
        "ktx.planilla.linea",
        string="Línea de Planilla",
        copy=False,
        readonly=True,
        index="btree_not_null",
        help="Línea de planilla que generó esta partida contable.",
    )
    ktx_pl_planilla_id = fields.Many2one(
        related="ktx_pl_linea_id.planilla_id",
        string="Planilla",
        store=True,
    )
