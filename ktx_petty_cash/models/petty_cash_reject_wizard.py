# -*- coding: utf-8 -*-
from markupsafe import Markup
from odoo import fields, models, _
from odoo.exceptions import UserError


class KtxPettyCashRejectWizard(models.TransientModel):
    _name = "ktx.petty.cash.reject.wizard"
    _description = "Wizard de Rechazo de Gasto"

    move_id = fields.Many2one("ktx.petty.cash.move", string="Movimiento", required=True)
    rejection_note = fields.Text(string="Motivo de Rechazo", required=True)

    def action_reject(self):
        self.ensure_one()
        if not self.rejection_note or not self.rejection_note.strip():
            raise UserError(_("Debe indicar el motivo de rechazo."))
        move = self.move_id
        move.write({"state": "rejected", "rejection_note": self.rejection_note})
        move.message_post(
            body=Markup("Gasto rechazado por <b>%s</b>.<br/><b>Motivo:</b> %s") % (
                self.env.user.name, self.rejection_note
            ),
            subtype_xmlid="mail.mt_note",
        )
        return {"type": "ir.actions.act_window_close"}
