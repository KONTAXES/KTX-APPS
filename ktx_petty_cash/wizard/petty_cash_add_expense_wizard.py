# -*- coding: utf-8 -*-
from markupsafe import Markup
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class KtxPettyCashAddExpenseLine(models.TransientModel):
    _name = "ktx.petty.cash.add.expense.line"
    _description = "Línea de Gasto Manual para Caja Chica"

    wizard_id = fields.Many2one("ktx.petty.cash.add.expense.wizard", required=True, ondelete="cascade")
    move_type = fields.Selection(
        [("manual_expense", "Gasto"), ("manual_income", "Ingreso")],
        string="Tipo", required=True, default="manual_expense",
    )
    name = fields.Char(string="Descripción", required=True)
    partner_id = fields.Many2one("res.partner", string="Contacto")
    date = fields.Date(string="Fecha", required=True, default=fields.Date.context_today)
    ref = fields.Char(string="Referencia")
    amount = fields.Monetary(string="Total", currency_field="currency_id", required=True)
    account_id = fields.Many2one(
        "account.account", string="Cuenta Contable",
        help="Cuenta de gasto (débito) o cuenta por cobrar (crédito para ingreso).",
    )
    currency_id = fields.Many2one(related="wizard_id.currency_id")


class KtxPettyCashAddExpenseWizard(models.TransientModel):
    _name = "ktx.petty.cash.add.expense.wizard"
    _description = "Agregar Gastos a Caja Chica"

    fund_id = fields.Many2one("ktx.petty.cash.fund", string="Fondo", required=True, ondelete="cascade")
    staging_ids = fields.Many2many(
        "ktx.petty.cash.staging", string="Gastos con Factura",
        domain="[('state', '=', 'pending')]",
    )
    line_ids = fields.One2many(
        "ktx.petty.cash.add.expense.line", "wizard_id",
        string="Gastos / Ingresos Manuales",
    )
    payment_date = fields.Date(string="Fecha de Pago", required=True, default=fields.Date.context_today)
    auto_approve = fields.Boolean(string="Autorizar automáticamente", default=True)
    auto_pay = fields.Boolean(string="Marcar como pagados", default=False)
    currency_id = fields.Many2one(related="fund_id.currency_id", readonly=True)
    total_amount = fields.Monetary(string="Total", compute="_compute_total", currency_field="currency_id")

    @api.depends("staging_ids.amount_pending", "line_ids.amount")
    def _compute_total(self):
        for rec in self:
            rec.total_amount = (
                sum(rec.staging_ids.mapped("amount_pending")) +
                sum(rec.line_ids.mapped("amount"))
            )

    def action_add(self):
        self.ensure_one()
        if not self.staging_ids and not self.line_ids:
            raise UserError(_("Selecciona o agrega al menos un gasto."))
        if self.fund_id.state == "closed":
            raise UserError(_("El fondo '%s' está cerrado.") % self.fund_id.name)

        new_state = "draft"
        if self.auto_approve and self.auto_pay:
            new_state = "reimbursed"
        elif self.auto_approve:
            new_state = "approved"

        # Process staging-based (invoice-linked) expenses
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
                "state": new_state,
                "account_id": payable_account.id if payable_account else False,
                "source_move_id": staging.move_id.id,
                "ref": staging.move_name,
                "staging_id": staging.id,
            })
            if new_state == "reimbursed" and self.fund_id.account_id and payable_account:
                acc_move = move._generate_accounting_entry()
                if acc_move:
                    move.accounting_move_id = acc_move.id
            if self.auto_approve:
                move.message_post(
                    body=Markup("<b>Autorizado automáticamente</b> por %s.") % self.env.user.name,
                    subtype_xmlid="mail.mt_comment",
                )
            staging.write({"state": "assigned", "petty_cash_move_id": move.id})

        # Process manual lines
        for line in self.line_ids:
            move = self.env["ktx.petty.cash.move"].create({
                "fund_id": self.fund_id.id,
                "date": line.date,
                "payment_date": self.payment_date,
                "name": line.name,
                "partner_id": line.partner_id.id if line.partner_id else False,
                "amount": line.amount,
                "move_type": line.move_type,
                "state": new_state,
                "account_id": line.account_id.id if line.account_id else False,
                "ref": line.ref,
            })
            if new_state == "reimbursed" and self.fund_id.account_id and line.account_id:
                acc_move = move._generate_accounting_entry()
                if acc_move:
                    move.accounting_move_id = acc_move.id
            if self.auto_approve:
                move.message_post(
                    body=Markup("<b>Autorizado automáticamente</b> por %s.") % self.env.user.name,
                    subtype_xmlid="mail.mt_comment",
                )

        return {"type": "ir.actions.act_window_close"}
