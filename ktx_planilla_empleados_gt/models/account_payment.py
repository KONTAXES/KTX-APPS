# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class AccountPayment(models.Model):
    _inherit = "account.payment"

    ktx_pl_linea_id = fields.Many2one(
        "ktx.planilla.linea",
        string="Línea de Planilla",
        copy=False,
        index="btree_not_null",
        help="Línea de planilla que se paga con este pago.",
    )
    ktx_pl_planilla_id = fields.Many2one(
        related="ktx_pl_linea_id.planilla_id",
        string="Planilla",
        store=True,
    )
    ktx_pl_liquidacion_id = fields.Many2one(
        "ktx.planilla.liquidacion",
        string="Liquidación de Prestaciones",
        copy=False,
        index="btree_not_null",
    )
    ktx_pl_es_nomina = fields.Boolean(
        compute="_compute_ktx_pl_es_nomina",
        string="Es Pago de Nómina",
    )

    @api.depends("ktx_pl_linea_id", "ktx_pl_liquidacion_id")
    def _compute_ktx_pl_es_nomina(self):
        for pago in self:
            pago.ktx_pl_es_nomina = bool(
                pago.ktx_pl_linea_id or pago.ktx_pl_liquidacion_id)

    def action_ktx_pl_recibo_nomina(self):
        """Imprime el recibo de nómina del pago (Acciones → Recibo de Nómina)."""
        lineas = self.ktx_pl_linea_id
        if lineas:
            return self.env.ref(
                "ktx_planilla_empleados_gt.action_report_recibo_nomina"
            ).report_action(lineas)
        liquidaciones = self.ktx_pl_liquidacion_id
        if liquidaciones:
            return self.env.ref(
                "ktx_planilla_empleados_gt.action_report_liquidacion"
            ).report_action(liquidaciones)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Sin recibo"),
                "message": _("Este pago no está vinculado a una planilla ni "
                             "a una liquidación de prestaciones."),
                "type": "warning",
                "sticky": False,
            },
        }
