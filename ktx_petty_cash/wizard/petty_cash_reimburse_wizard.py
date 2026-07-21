# -*- coding: utf-8 -*-
from markupsafe import Markup
from odoo import fields, models, _
from odoo.exceptions import UserError


class KtxPettyCashReimburseWizard(models.TransientModel):
    _name = "ktx.petty.cash.reimburse.wizard"
    _description = "Confirmar Pago de Caja Chica"

    move_id = fields.Many2one("ktx.petty.cash.move", string="Movimiento", required=True, ondelete="cascade")
    amount = fields.Monetary(string="Monto", currency_field="currency_id", readonly=True)
    currency_id = fields.Many2one(related="move_id.currency_id", readonly=True)
    payment_method = fields.Selection(
        [("cash", "Efectivo"), ("transfer", "Transferencia"), ("check", "Cheque"), ("other", "Otro")],
        string="Método de Pago", required=True, default="cash",
    )
    payment_ref = fields.Char(string="Referencia de Pago")
    payment_date = fields.Date(string="Fecha de Pago", default=fields.Date.context_today)
    fund_name = fields.Char(related="move_id.fund_id.name", readonly=True)
    partner_name = fields.Char(related="move_id.partner_id.name", readonly=True)

    def action_confirm(self):
        self.ensure_one()
        rec = self.move_id
        if rec.state != "approved":
            raise UserError(_("El movimiento ya no está en estado Aprobado."))
        if self.payment_date:
            rec.payment_date = self.payment_date
        rec.payment_method = self.payment_method
        rec.payment_ref = self.payment_ref
        move = rec._generate_accounting_entry()
        rec.write({"state": "reimbursed", "accounting_move_id": move.id if move else False})
        method_label = dict(self._fields["payment_method"].selection).get(self.payment_method, "")
        rec.message_post(
            body=Markup("<b>Reembolsado</b> por %s. Método: %s. Ref: %s.%s") % (
                self.env.user.name,
                method_label,
                self.payment_ref or "-",
                Markup(" Asiento: <b>%s</b>") % move.name if move else "",
            ),
            subtype_xmlid="mail.mt_comment",
        )
        return {"type": "ir.actions.act_window_close"}
