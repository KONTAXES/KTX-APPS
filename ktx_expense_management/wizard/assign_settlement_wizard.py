# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AssignSettlementWizard(models.TransientModel):
    _name = "ktx.settlement.assign.wizard"
    _description = "Asignar Documentos a una Liquidación Existente"

    kind = fields.Selection(
        selection=[("expense", "Gasto"), ("sale", "Venta")],
        string="Clase",
        required=True,
    )
    staging_ids = fields.Many2many(
        comodel_name="ktx.settlement.staging",
        string="Documentos a Asignar",
        readonly=True,
    )
    staging_count = fields.Integer(
        string="Documentos Seleccionados",
        compute="_compute_staging_count",
    )
    settlement_id = fields.Many2one(
        comodel_name="ktx.settlement",
        string="Liquidación Destino",
        required=True,
        domain="[('kind', '=', kind), ('state', 'in', ['draft', 'confirmed'])]",
        help="Solo se listan liquidaciones ABIERTAS (borrador o por autorizar) de la misma clase.",
    )

    @api.depends("staging_ids")
    def _compute_staging_count(self):
        for rec in self:
            rec.staging_count = len(rec.staging_ids)

    @api.model
    def default_get(self, fields_list):
        result = super().default_get(fields_list)
        staging_ids = self.env.context.get("default_staging_ids") or []
        if staging_ids and "staging_ids" in fields_list:
            result["staging_ids"] = [(6, 0, staging_ids)]
        return result

    def action_assign(self):
        self.ensure_one()
        settlement = self.settlement_id
        if not settlement:
            raise UserError(_("Seleccione una liquidación destino."))
        if settlement.state not in ("draft", "confirmed"):
            raise UserError(
                _("Solo se pueden agregar documentos a liquidaciones en borrador o por autorizar.")
            )
        if settlement.kind != self.kind:
            raise UserError(
                _("La liquidación seleccionada es de otra clase (gasto/venta). "
                  "Elija una del mismo tipo que los documentos.")
            )

        eligible = self.staging_ids.filtered(lambda s: s.state == "pending")
        if not eligible:
            raise UserError(
                _("Los documentos seleccionados ya no están pendientes.")
            )

        already_in = settlement.line_ids.staging_id.ids
        added = 0
        for staging in eligible:
            if staging.id in already_in:
                continue
            residual = staging.move_id.amount_residual if staging.move_id else 0.0
            self.env["ktx.settlement.line"].create({
                "settlement_id": settlement.id,
                "staging_id": staging.id,
                "amount_to_pay": residual if residual > 0 else staging.amount_total,
            })
            added += 1

        settlement.invalidate_recordset(["line_ids"])
        settlement._sync_intercompany_accounts()

        return {
            "type": "ir.actions.act_window",
            "res_model": "ktx.settlement",
            "view_mode": "form",
            "res_id": settlement.id,
            "target": "current",
        }
