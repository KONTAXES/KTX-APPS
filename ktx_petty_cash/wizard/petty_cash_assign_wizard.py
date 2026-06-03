# -*- coding: utf-8 -*-
from markupsafe import Markup
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class KtxPettyCashAssignWizard(models.TransientModel):
    _name = "ktx.petty.cash.assign.wizard"
    _description = "Asignar Pago a Caja Chica"

    staging_ids = fields.Many2many("ktx.petty.cash.staging", string="Gastos por Reembolsar")
    fund_id = fields.Many2one("ktx.petty.cash.fund", string="Fondo de Caja Chica", required=True, domain="[('state', '=', 'open')]")
    payment_date = fields.Date(string="Fecha de Pago", required=True, default=fields.Date.context_today)
    currency_id = fields.Many2one(related="fund_id.currency_id", readonly=True)
    fund_balance = fields.Monetary(related="fund_id.current_balance", string="Saldo Disponible", currency_field="currency_id", readonly=True)
    total_amount = fields.Monetary(string="Total a Pagar", compute="_compute_total", currency_field="currency_id")
    items_count = fields.Integer(compute="_compute_total")

    @api.depends("staging_ids.amount_pending")
    def _compute_total(self):
        for rec in self:
            rec.total_amount = sum(rec.staging_ids.mapped("amount_pending"))
            rec.items_count = len(rec.staging_ids)

    def action_assign(self):
        self.ensure_one()
        if not self.staging_ids:
            raise UserError(_("No hay gastos seleccionados para asignar."))
        if self.fund_id.state == "closed":
            raise UserError(_("El fondo '%s' está cerrado.") % self.fund_id.name)

        moves_created = self.env["ktx.petty.cash.move"]
        for staging in self.staging_ids.filtered(lambda s: s.state == "pending"):
            payable_account = False
            if staging.move_id:
                payable_line = staging.move_id.line_ids.filtered(
                    lambda l: l.account_id.account_type == "liability_payable"
                )
                if payable_line:
                    payable_account = payable_line[0].account_id

            move = self.env["ktx.petty.cash.move"].create({
                "fund_id": self.fund_id.id,
                "date": staging.invoice_date or self.payment_date,
                "payment_date": self.payment_date,
                "name": staging.notes or staging.ref or staging.move_name,
                "partner_id": staging.partner_id.id if staging.partner_id else False,
                "amount": staging.amount_pending,
                "move_type": "expense",
                "state": "draft",
                "account_id": payable_account.id if payable_account else False,
                "source_move_id": staging.move_id.id,
                "ref": staging.move_name,
                "staging_id": staging.id,
            })
            staging.write({"state": "assigned", "petty_cash_move_id": move.id})
            staging.message_post(
                body=Markup("Asignado al fondo <b>%s</b> — movimiento <b>%s</b> creado por %s.") % (
                    self.fund_id.name, move.name or move.id, self.env.user.name
                ),
                subtype_xmlid="mail.mt_comment",
            )
            move.message_post(
                body=Markup("Gasto creado desde <b>%s</b> y asignado al fondo <b>%s</b> por %s.") % (
                    staging.move_name or staging.move_id.name, self.fund_id.name, self.env.user.name
                ),
                subtype_xmlid="mail.mt_comment",
            )
            moves_created |= move

        if len(moves_created) == 1:
            return {"type": "ir.actions.act_window", "res_model": "ktx.petty.cash.move", "view_mode": "form", "res_id": moves_created.id}
        return {"type": "ir.actions.act_window", "name": _("Movimientos Creados"), "res_model": "ktx.petty.cash.move", "view_mode": "list,form", "domain": [("id", "in", moves_created.ids)]}
