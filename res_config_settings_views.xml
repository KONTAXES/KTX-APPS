# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class StagingSelectionLine(models.TransientModel):
    _name = "ktx.staging.selection.line"
    _description = "Línea de selección de gasto"
    _order = "invoice_date desc, id"

    wizard_id = fields.Many2one(
        "ktx.staging.selection.wizard", ondelete="cascade", required=True
    )
    selected = fields.Boolean(string="✓", default=False)
    # staging_id must NOT be readonly at model level so Odoo includes it in form payloads
    staging_id = fields.Many2one("ktx.settlement.staging")
    move_name = fields.Char(related="staging_id.move_id.name", string="Póliza", readonly=True)
    ref = fields.Char(related="staging_id.ref", string="Referencia", readonly=True)
    partner_id = fields.Many2one(
        related="staging_id.partner_id", string="Proveedor", readonly=True
    )
    invoice_date = fields.Date(
        related="staging_id.invoice_date", string="Fecha", readonly=True
    )
    currency_id = fields.Many2one(
        related="staging_id.currency_id", string="Moneda", readonly=True
    )
    amount_total = fields.Monetary(
        related="staging_id.amount_total",
        currency_field="currency_id",
        string="Total",
        readonly=True,
    )


class StagingSelectionWizard(models.TransientModel):
    _name = "ktx.staging.selection.wizard"
    _description = "Selección de Gastos para Liquidación"

    settlement_id = fields.Many2one(
        comodel_name="ktx.settlement",
        string="Liquidación",
        required=True,
        readonly=True,
    )
    line_ids = fields.One2many(
        comodel_name="ktx.staging.selection.line",
        inverse_name="wizard_id",
        string="Gastos Disponibles",
    )

    def _get_available_stagings(self, settlement):
        already_used = settlement.line_ids.staging_id.ids
        domain = [("state", "=", "pending"), ("id", "not in", already_used)]
        # Company filtering is handled transparently by ktx.settlement.staging._search
        # based on the multi_company config parameter.
        return self.env["ktx.settlement.staging"].search(domain)

    @api.model
    def default_get(self, fields_list):
        result = super().default_get(fields_list)
        settlement_id = self._context.get("default_settlement_id")
        if settlement_id and "line_ids" in fields_list:
            settlement = self.env["ktx.settlement"].browse(settlement_id)
            available = self._get_available_stagings(settlement)
            result["line_ids"] = [
                (0, 0, {"staging_id": s.id, "selected": False})
                for s in available
            ]
        return result

    def action_select_all(self):
        self.ensure_one()
        self.line_ids.write({"selected": True})
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_add_lines(self):
        self.ensure_one()
        settlement = self.settlement_id
        if settlement.state not in ("draft", "confirmed"):
            raise UserError(
                _("Solo se pueden agregar líneas a liquidaciones en borrador o confirmadas.")
            )
        selected = self.line_ids.filtered("selected")
        if not selected:
            raise UserError(_("Seleccione al menos un gasto para agregar."))

        already_in = settlement.line_ids.staging_id.ids
        for line in selected:
            if not line.staging_id or line.staging_id.id in already_in:
                continue
            staging = line.staging_id
            residual = staging.move_id.amount_residual if staging.move_id else 0.0
            self.env["ktx.settlement.line"].create({
                "settlement_id": settlement.id,
                "staging_id": staging.id,
                "amount_to_pay": residual if residual > 0 else staging.amount_total,
            })
        # Invalidate cache so _sync sees the newly created lines
        settlement.invalidate_recordset(["line_ids"])
        settlement._sync_intercompany_accounts()
        return {"type": "ir.actions.act_window_close"}
