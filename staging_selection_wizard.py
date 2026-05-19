# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.tools import float_compare
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SettlementPaymentWizard(models.TransientModel):
    _name = "ktx.settlement.payment.wizard"
    _description = "Asistente de Pago de Liquidación"

    settlement_id = fields.Many2one(
        comodel_name="ktx.settlement",
        string="Liquidación",
        required=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        related="settlement_id.company_id",
        string="Compañía",
        readonly=True,
    )
    journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Diario de Pago",
        required=True,
        domain="[('type', 'in', ['bank', 'cash']), ('company_id', '=', company_id)]",
    )
    payment_method_line_id = fields.Many2one(
        comodel_name="account.payment.method.line",
        string="Método de Pago",
        domain="[('journal_id', '=', journal_id)]",
    )
    payment_date = fields.Date(
        string="Fecha de Pago",
        required=True,
        default=fields.Date.context_today,
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Moneda Liquidación",
        related="settlement_id.currency_id",
        readonly=True,
    )
    journal_currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Moneda Diario",
        compute="_compute_journal_currency_id",
    )
    amount = fields.Monetary(
        string="Monto a Pagar",
        currency_field="journal_currency_id",
        required=True,
    )
    communication = fields.Char(
        string="Memo / Concepto",
    )
    payment_reference = fields.Char(
        string="Referencia de Pago",
        help="Referencia que aparecerá en el extracto bancario (número de cheque, transferencia, etc.).",
    )
    payment_difference = fields.Monetary(
        string="Diferencia",
        currency_field="currency_id",
        compute="_compute_payment_difference",
    )
    payment_difference_handling = fields.Selection(
        selection=[
            ("open", "Dejar en abierto"),
            ("reconcile", "Marcar como totalmente pagado"),
        ],
        string="Manejo de Diferencia",
        default="open",
    )
    writeoff_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Cuenta para Diferencia",
        domain="[('company_ids', 'in', [company_id])]",
    )
    writeoff_label = fields.Char(
        string="Descripción de Diferencia",
        default="Diferencia de liquidación",
    )

    @api.depends("journal_id")
    def _compute_journal_currency_id(self):
        for rec in self:
            rec.journal_currency_id = rec.journal_id.currency_id or \
                (rec.settlement_id.company_id or self.env.company).currency_id

    @api.onchange("journal_id")
    def _onchange_journal_id(self):
        self.payment_method_line_id = False
        if self.journal_id:
            methods = self.journal_id.inbound_payment_method_line_ids + \
                      self.journal_id.outbound_payment_method_line_ids
            if methods:
                self.payment_method_line_id = methods[0]

    @api.depends("amount", "settlement_id.amount_residual", "journal_currency_id", "currency_id")
    def _compute_payment_difference(self):
        for rec in self:
            rec.payment_difference = rec.settlement_id.amount_residual - rec.amount

    @api.constrains("payment_difference_handling", "writeoff_account_id")
    def _check_writeoff_account(self):
        for rec in self:
            if (
                rec.payment_difference_handling == "reconcile"
                and abs(rec.payment_difference) > 0.0
                and not rec.writeoff_account_id
            ):
                raise UserError(
                    _("Debe seleccionar una cuenta para registrar la diferencia.")
                )

    def action_pay(self):
        self.ensure_one()
        settlement = self.settlement_id

        if settlement.state not in ("posted", "in_payment"):
            raise UserError(
                _("Solo se puede registrar el pago de liquidaciones publicadas o en proceso de pago.")
            )
        if not settlement.move_id:
            raise UserError(
                _("Esta liquidación no tiene asiento contable generado.")
            )

        # Crear el pago
        employee_partner = (
            settlement.employee_id
            if settlement.employee_id
            else self.env["res.partner"].browse()
        )

        journal_currency = self.journal_id.currency_id or \
            (settlement.company_id or self.env.company).currency_id
        payment_vals = {
            "payment_type": "outbound",
            "partner_type": "supplier",
            "partner_id": employee_partner.id if employee_partner else False,
            "journal_id": self.journal_id.id,
            "date": self.payment_date,
            "amount": self.amount,
            "currency_id": journal_currency.id,
            "memo": self.communication or settlement.name,
            "company_id": settlement.company_id.id,
            "destination_account_id": settlement.account_id.id,
        }
        if self.payment_reference:
            payment_vals["payment_reference"] = self.payment_reference
        if self.payment_method_line_id:
            payment_vals["payment_method_line_id"] = self.payment_method_line_id.id
        payment = self.env["account.payment"].create(payment_vals)
        payment.action_post()

        # Reconciliar pago con asiento de la liquidación si es posible
        self._reconcile_payment_with_move(payment, settlement)

        # Manejar diferencia (write-off)
        if (
            self.payment_difference_handling == "reconcile"
            and self.writeoff_account_id
            and abs(self.payment_difference) > 0.001
        ):
            self._create_writeoff_entry(settlement, payment)

        # Registrar diferencial cambiario si existe
        forex_note = self._compute_forex_note(settlement)
        if forex_note:
            settlement.message_post(body=forex_note, subtype_xmlid="mail.mt_note")

        settlement.write({
            "payment_ids": [(4, payment.id)],
            "forex_note": forex_note or False,
            "state": "in_payment",
        })
        settlement._compute_payment_amounts()

        # Volver al formulario de la liquidación
        return {
            "type": "ir.actions.act_window",
            "res_model": "ktx.settlement",
            "view_mode": "form",
            "res_id": settlement.id,
            "target": "current",
        }

    def _reconcile_payment_with_move(self, payment, settlement):
        """Intenta reconciliar las líneas del pago con las del asiento de liquidación."""
        try:
            ref_date = settlement.rate_date or settlement.date or self.payment_date
            # Líneas de crédito del asiento de la liquidación (cuenta por pagar)
            move_payable_lines = settlement.move_id.line_ids.filtered(
                lambda l: l.account_id == settlement.account_id
                and not l.reconciled
            )
            # Líneas de débito del pago (misma cuenta por pagar)
            payment_lines = payment.move_id.line_ids.filtered(
                lambda l: l.account_id == settlement.account_id
                and not l.reconciled
            )
            lines_to_reconcile = move_payable_lines | payment_lines
            if lines_to_reconcile:
                lines_to_reconcile.with_context(ktx_settlement_date=ref_date).reconcile()
        except Exception as e:
            _logger.warning("No se pudo reconciliar automáticamente: %s", e)

    def _compute_forex_note(self, settlement):
        """Calcula y retorna una nota del diferencial cambiario si aplica."""
        company = settlement.company_id or self.env.company
        company_cur = company.currency_id
        lines_with_diff = []
        for line in settlement.line_ids:
            line_cur = line.currency_id
            if not line_cur or line_cur == company_cur:
                continue
            ref_date = settlement.rate_date or settlement.date or fields.Date.context_today(self)
            # Amount in company currency at settlement rate
            amount_at_settlement = line_cur._convert(line.amount_to_pay, company_cur, company, ref_date)
            # Amount originally recorded in the invoice payable (from the original accounting entry)
            original_lines = line.move_id.line_ids.filtered(
                lambda l: l.account_type in ("liability_payable",) and l.currency_id == line_cur
            ) if line.move_id else self.env["account.move.line"]
            if original_lines:
                original_amount_cur = sum(abs(l.amount_currency) for l in original_lines)
                original_amount_company = sum(abs(l.balance) for l in original_lines)
                if original_amount_cur and original_amount_company:
                    amount_at_invoice_rate = (line.amount_to_pay / original_amount_cur) * original_amount_company
                    diff = amount_at_settlement - amount_at_invoice_rate
                    if abs(diff) > 0.01:
                        gain_loss = _("ganancia") if diff < 0 else _("pérdida")
                        lines_with_diff.append(
                            _("  • %s %s: diferencia %s de %s %.2f %s") % (
                                line.move_name or "", line_cur.name,
                                gain_loss, company_cur.symbol, abs(diff), company_cur.name,
                            )
                        )
        if lines_with_diff:
            return _("Diferencial cambiario al registrar pago:\n") + "\n".join(lines_with_diff)
        return False

    def _create_writeoff_entry(self, settlement, payment):
        """Crea un asiento de diferencia (write-off)."""
        try:
            diff = self.payment_difference
            lines = [
                (0, 0, {
                    "name": self.writeoff_label or _("Diferencia de liquidación"),
                    "account_id": settlement.account_id.id,
                    "debit": abs(diff) if diff > 0 else 0.0,
                    "credit": abs(diff) if diff < 0 else 0.0,
                    "currency_id": self.currency_id.id,
                }),
                (0, 0, {
                    "name": self.writeoff_label or _("Diferencia de liquidación"),
                    "account_id": self.writeoff_account_id.id,
                    "debit": abs(diff) if diff < 0 else 0.0,
                    "credit": abs(diff) if diff > 0 else 0.0,
                    "currency_id": self.currency_id.id,
                }),
            ]
            writeoff_move = self.env["account.move"].create({
                "journal_id": self.journal_id.id,
                "date": self.payment_date,
                "ref": _("Diferencia - %s") % settlement.name,
                "company_id": settlement.company_id.id,
                "currency_id": self.currency_id.id,
                "line_ids": lines,
            })
            writeoff_move.action_post()
        except Exception as e:
            _logger.warning("No se pudo crear el asiento de diferencia: %s", e)
