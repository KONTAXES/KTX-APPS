# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import UserError


class SettlementRejectWizard(models.TransientModel):
    _name = "ktx.settlement.reject.wizard"
    _description = "Asistente de Rechazo de Liquidación"

    settlement_id = fields.Many2one(
        comodel_name="ktx.settlement",
        string="Liquidación",
        required=True,
        readonly=True,
    )
    rejection_note = fields.Text(
        string="Motivo de Rechazo",
        required=True,
    )

    def action_confirm_reject(self):
        self.ensure_one()
        if not self.rejection_note or not self.rejection_note.strip():
            raise UserError(_("Debe ingresar un motivo de rechazo."))
        self.settlement_id.action_do_reject(self.rejection_note.strip())
        return {"type": "ir.actions.act_window_close"}
