# -*- coding: utf-8 -*-
from markupsafe import Markup
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class KtxPettyCashFundReplenishmentWizard(models.TransientModel):
    _name = "ktx.petty.cash.fund.replenishment.wizard"
    _description = "Asistente de Reposición de Fondos"

    fund_id = fields.Many2one("ktx.petty.cash.fund", required=True, ondelete="cascade")
    fund_balance = fields.Monetary(related="fund_id.current_balance", currency_field="currency_id", readonly=True)
    currency_id = fields.Many2one(related="fund_id.currency_id", readonly=True)

    journal_id = fields.Many2one(
        "account.journal", string="Diario Bancario", required=True,
        domain="[('type', 'in', ['bank', 'cash'])]",
    )
    payment_method_line_id = fields.Many2one(
        "account.payment.method.line", string="Método de Pago",
        domain="[('journal_id', '=', journal_id), ('payment_type', '=', 'outbound')]",
    )
    partner_id = fields.Many2one("res.partner", string="A nombre de")
    amount = fields.Monetary(string="Importe", required=True, currency_field="currency_id")
    date = fields.Date(string="Fecha", required=True, default=fields.Date.context_today)
    memo = fields.Char(string="Memo / Comunicación")
    payment_ref = fields.Char(string="Referencia de Pago", help="N° cheque, referencia transferencia, etc.")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        fund_id = res.get("fund_id")
        if fund_id:
            fund = self.env["ktx.petty.cash.fund"].browse(fund_id)
            if fund.custodian_id:
                res["partner_id"] = fund.custodian_id.id
        return res

    @api.onchange("fund_id")
    def _onchange_fund_id(self):
        if self.fund_id and self.fund_id.custodian_id:
            self.partner_id = self.fund_id.custodian_id

    @api.onchange("journal_id")
    def _onchange_journal_id(self):
        self.payment_method_line_id = False
        if self.journal_id:
            methods = self.journal_id.outbound_payment_method_line_ids
            if methods:
                self.payment_method_line_id = methods[0]

    def action_confirm(self):
        self.ensure_one()
        fund = self.fund_id
        if fund.state == "closed":
            raise UserError(_("El fondo '%s' está cerrado.") % fund.name)
        if self.amount <= 0:
            raise UserError(_("El importe debe ser mayor que cero."))
        if not fund.account_id:
            raise UserError(_("El fondo no tiene cuenta contable configurada."))

        memo = self.memo or (_("Reposición Caja Chica: %s") % fund.name)

        # Create payment: Dr Petty Cash (destination) / Cr Outstanding (transitoria del diario)
        # Bank reconciliation will handle: Dr Outstanding / Cr Bank (standard Odoo flow)
        payment_vals = {
            "payment_type": "outbound",
            "partner_type": "supplier",
            "partner_id": self.partner_id.id if self.partner_id else False,
            "journal_id": self.journal_id.id,
            "destination_account_id": fund.account_id.id,
            "amount": self.amount,
            "date": self.date,
        }
        if self.payment_method_line_id:
            payment_vals["payment_method_line_id"] = self.payment_method_line_id.id

        # Detect which memo/communication field exists on account.payment in this version
        payment_fields = self.env["account.payment"].fields_get()
        # Odoo 16: communication / Odoo 17+: memo / some versions: payment_reference
        for candidate in ("memo", "communication", "payment_reference"):
            if candidate in payment_fields:
                payment_vals[candidate] = self.memo or memo
                break

        payment = self.env["account.payment"].create(payment_vals)
        payment.action_post()

        # Write ref on the underlying move after posting (survives action_post)
        ref_val = self.payment_ref or memo
        if ref_val:
            payment.move_id.write({"ref": ref_val})
            # Also update all move lines name for clarity
            payment.move_id.line_ids.filtered(lambda l: not l.name or l.name == "/").write(
                {"name": memo}
            )

        method_label = (
            self.payment_method_line_id.name if self.payment_method_line_id else _("Manual")
        )

        # Create petty cash replenishment move linked to the payment's journal entry
        self.env["ktx.petty.cash.move"].create({
            "fund_id": fund.id,
            "date": self.date,
            "payment_date": self.date,
            "name": memo,
            "partner_id": self.partner_id.id if self.partner_id else False,
            "amount": self.amount,
            "move_type": "replenishment",
            "payment_method": "transfer",
            "payment_ref": self.payment_ref,
            "state": "reimbursed",
            "accounting_move_id": payment.move_id.id,
            "ref": self.payment_ref,
        })

        fund.message_post(
            body=Markup(
                "<b>Fondos agregados:</b> %s %.2f<br/>"
                "Método: %s | Ref: %s | Fecha: %s<br/>"
                "Pago: <b>%s</b> | Por: %s"
            ) % (
                self.currency_id.symbol or "",
                self.amount,
                method_label,
                self.payment_ref or "-",
                self.date,
                payment.name,
                self.env.user.name,
            ),
            subtype_xmlid="mail.mt_comment",
        )

        return {
            "type": "ir.actions.act_window",
            "res_model": "account.payment",
            "view_mode": "form",
            "res_id": payment.id,
        }
