# -*- coding: utf-8 -*-
import base64
from markupsafe import Markup
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class KtxPettyCashMove(models.Model):
    _name = "ktx.petty.cash.move"
    _description = "Movimiento de Caja Chica"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "payment_date desc, date desc, id desc"

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, **kwargs):
        if not self.env.su:
            multi = self.env['ir.config_parameter'].sudo().get_param(
                'ktx_petty_cash.multi_company', 'False'
            )
            if multi not in ('True', '1', 'true'):
                domain = [('company_id', 'in', self.env.companies.ids)] + list(domain)
        return super()._search(domain, offset=offset, limit=limit, order=order, **kwargs)

    fund_id = fields.Many2one(
        "ktx.petty.cash.fund", string="Fondo",
        required=True, ondelete="cascade", index=True,
    )
    date = fields.Date(
        string="Fecha", default=fields.Date.context_today, required=True,
    )
    payment_date = fields.Date(string="Fecha de Pago", tracking=True)
    name = fields.Char(string="Descripción", tracking=True)
    partner_id = fields.Many2one(
        "res.partner", string="Proveedor / Beneficiario", ondelete="restrict",
    )
    amount = fields.Monetary(
        string="Monto", required=True, currency_field="currency_id",
    )
    move_type = fields.Selection(
        [
            ("expense", "Gasto"),
            ("replenishment", "Reposición"),
            ("manual_expense", "Gasto Manual"),
            ("manual_income", "Ingreso Manual"),
        ],
        string="Tipo", required=True, default="expense", tracking=True,
    )
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("pending", "Pendiente Aprobación"),
            ("approved", "Aprobado"),
            ("reimbursed", "Reembolsado"),
            ("rejected", "Rechazado"),
            ("cancelled", "Cancelado"),
        ],
        string="Estado", default="draft", required=True, tracking=True,
    )
    fund_authorizer_id = fields.Many2one(
        "res.users",
        related="fund_id.authorizer_id",
        string="Autorizador del Fondo",
        store=False,
    )
    account_id = fields.Many2one(
        "account.account", string="Cuenta de Gasto",
        domain="[('company_ids', 'in', [company_id])]",
        ondelete="restrict",
    )
    analytic_account_id = fields.Many2one(
        "account.analytic.account", string="Centro de Costo", ondelete="set null",
    )
    ref = fields.Char(string="Referencia / Documento")
    rejection_note = fields.Text(string="Motivo de Rechazo", tracking=True)
    payment_method = fields.Selection(
        [("cash", "Efectivo"), ("transfer", "Transferencia"), ("check", "Cheque"), ("other", "Otro")],
        string="Método de Pago", tracking=True,
    )
    payment_ref = fields.Char(string="Referencia de Pago", tracking=True)

    # Source document: the invoice/journal entry being paid with petty cash
    source_move_id = fields.Many2one(
        "account.move",
        string="Documento Origen",
        help="Factura o asiento contable pagado con este fondo de caja chica.",
        domain="[('state', '=', 'posted'), ('move_type', 'in', ['in_invoice', 'in_receipt', 'entry'])]",
        ondelete="set null",
    )
    source_move_ref = fields.Char(
        string="Ref. Documento",
        related="source_move_id.ref",
        store=True, readonly=True,
    )
    source_move_partner_id = fields.Many2one(
        "res.partner",
        related="source_move_id.partner_id",
        string="Proveedor Doc.",
        store=True, readonly=True,
    )

    # Accounting entry generated when this move is reimbursed
    accounting_move_id = fields.Many2one(
        "account.move", string="Asiento Contable", readonly=True, copy=False, ondelete="set null",
    )
    replenishment_id = fields.Many2one(
        "ktx.petty.cash.replenishment", string="Reposición",
        readonly=True, ondelete="set null",
    )
    staging_id = fields.Many2one(
        "ktx.petty.cash.staging", string="Gasto por Reembolsar",
        readonly=True, copy=False, ondelete="set null",
    )
    period_closed = fields.Boolean(
        string="Período Cerrado", default=False, tracking=True,
        help="Marcado cuando se realiza el cierre mensual del período.",
    )
    period_label = fields.Char(
        string="Período",
        compute="_compute_period_label",
        store=True,
    )
    balance_after = fields.Monetary(
        string="Saldo Después",
        currency_field="currency_id",
        compute="_compute_balance_after",
    )
    debit = fields.Monetary(
        string="Débito", compute="_compute_debit_credit", currency_field="currency_id",
    )
    credit = fields.Monetary(
        string="Crédito", compute="_compute_debit_credit", currency_field="currency_id",
    )
    company_id = fields.Many2one(
        "res.company", string="Compañía",
        related="fund_id.company_id", store=True, readonly=True,
    )
    currency_id = fields.Many2one(
        "res.currency", string="Moneda",
        related="fund_id.currency_id", store=True, readonly=True,
    )
    can_approve = fields.Boolean(
        string="Puede Aprobar",
        compute="_compute_can_approve",
    )

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s - %s" % (rec.fund_id.name or "", rec.name or _("Sin descripción"))

    def _compute_can_approve(self):
        is_manager = self.env.user.has_group("ktx_petty_cash.group_petty_cash_manager")
        for rec in self:
            if rec.fund_id.authorizer_id:
                # When authorizer is set, ONLY that user can approve
                rec.can_approve = rec.fund_id.authorizer_id == self.env.user
            else:
                rec.can_approve = is_manager

    @api.depends("amount", "move_type")
    def _compute_debit_credit(self):
        for rec in self:
            if rec.move_type in ("expense", "manual_expense"):
                rec.debit = rec.amount
                rec.credit = 0.0
            else:
                rec.debit = 0.0
                rec.credit = rec.amount

    @api.depends("date", "payment_date")
    def _compute_period_label(self):
        months = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]
        for rec in self:
            d = rec.payment_date or rec.date
            if d:
                rec.period_label = "%s %s" % (months[d.month - 1], d.year)
            else:
                rec.period_label = False

    @api.depends(
        "fund_id.initial_amount",
        "fund_id.line_ids.date",
        "fund_id.line_ids.amount",
        "fund_id.line_ids.state",
        "fund_id.line_ids.move_type",
        "date", "amount", "state", "move_type",
    )
    def _compute_balance_after(self):
        self.balance_after = 0.0
        for fund in self.mapped("fund_id"):
            balance = fund.initial_amount
            sorted_moves = fund.line_ids.sorted(
                key=lambda m: (m.payment_date or m.date or fields.Date.today(), m.id)
            )
            fund_moves_in_self = self.filtered(lambda m: m.fund_id == fund)
            for move in sorted_moves:
                if move.state == "cancelled":
                    pass  # cancelled moves don't affect balance
                elif move.move_type in ("expense", "manual_expense") and move.state in ("approved", "reimbursed"):
                    balance -= move.amount
                elif move.move_type in ("replenishment", "manual_income") and move.state == "reimbursed":
                    balance += move.amount
                if move in fund_moves_in_self:
                    move.balance_after = balance

    @api.onchange("source_move_id")
    def _onchange_source_move_id(self):
        if self.source_move_id:
            move = self.source_move_id
            if not self.partner_id:
                self.partner_id = move.partner_id
            if not self.name:
                self.name = move.ref or move.name

            # Determine amount: prefer residual, fallback for journal entries
            if not self.amount or self.amount == 0:
                residual = abs(move.amount_residual)
                if residual:
                    self.amount = residual
                else:
                    # Journal entry: sum unreconciled lines with reconcilable accounts
                    unreconciled = move.line_ids.filtered(
                        lambda l: l.account_id.reconcile and not l.reconciled
                    )
                    if unreconciled:
                        self.amount = abs(sum(unreconciled.mapped("amount_residual")))
                    else:
                        # Fallback: total credit side
                        self.amount = sum(move.line_ids.mapped("credit"))

            # Determine payable account
            if not self.account_id:
                # 1. Payable account (invoices)
                payable_line = move.line_ids.filtered(
                    lambda l: l.account_id.account_type == "liability_payable"
                )
                if payable_line:
                    self.account_id = payable_line[0].account_id
                else:
                    # 2. Any unreconciled reconcilable line (journal entries)
                    unreconciled = move.line_ids.filtered(
                        lambda l: l.account_id.reconcile and not l.reconciled
                    )
                    if unreconciled:
                        self.account_id = unreconciled[0].account_id

    def action_request_approval(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Solo se pueden enviar a aprobación movimientos en borrador."))
            if rec.fund_id.state == "closed":
                raise UserError(_("El fondo '%s' está cerrado.") % rec.fund_id.name)
            authorizer = rec.fund_id.authorizer_id
            if not authorizer:
                raise UserError(_(
                    "Este fondo no tiene autorizador configurado. "
                    "Use el botón 'Aprobar' directamente."
                ))
            rec.write({"state": "pending"})
            rec.activity_schedule(
                "mail.mail_activity_data_todo",
                summary=_("Aprobación de gasto de caja chica"),
                note=_(
                    "El usuario <b>%(user)s</b> solicita aprobación del gasto <b>%(desc)s</b> "
                    "por <b>%(sym)s %(amount).2f</b> en el fondo <b>%(fund)s</b>."
                ) % {
                    "user": self.env.user.name,
                    "desc": rec.name or str(rec.id),
                    "sym": rec.currency_id.symbol or "",
                    "amount": rec.amount,
                    "fund": rec.fund_id.name or "",
                },
                user_id=authorizer.id,
            )
            rec.message_post(
                body=Markup(
                    "Solicitud de aprobación enviada a <b>%s</b> por <b>%s</b>."
                ) % (authorizer.name, self.env.user.name),
                subtype_xmlid="mail.mt_comment",
            )

    def action_approve(self):
        for rec in self:
            if rec.state not in ("draft", "pending"):
                raise UserError(_("Solo se pueden aprobar movimientos en borrador o pendientes de aprobación."))
            if rec.fund_id.state == "closed":
                raise UserError(_("El fondo '%s' está cerrado.") % rec.fund_id.name)
            if not rec.can_approve:
                raise UserError(_("No tiene permiso para aprobar este movimiento."))
            # Mark approval activities as done
            todo_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
            if todo_type:
                pending_acts = rec.activity_ids.filtered(
                    lambda a: a.activity_type_id == todo_type and a.user_id == self.env.user
                )
                for act in pending_acts:
                    try:
                        act.action_feedback(feedback=_("Aprobado"))
                    except Exception:
                        act.unlink()
            rec.write({"state": "approved"})
            rec.message_post(
                body=Markup("<b>Gasto aprobado</b> por %s.") % self.env.user.name,
                subtype_xmlid="mail.mt_comment",
            )
            rec.fund_id._check_low_balance()

    def action_reimburse(self):
        self.ensure_one()
        if self.state != "approved":
            raise UserError(_("Solo se pueden marcar como reembolsados los movimientos aprobados."))
        if self.period_closed:
            raise UserError(_("El período de este movimiento está cerrado."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Confirmar Pago"),
            "res_model": "ktx.petty.cash.reimburse.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_move_id": self.id,
                "default_amount": self.amount,
            },
        }

    def _generate_accounting_entry(self):
        """Genera el asiento contable al confirmar el pago con caja chica.

        Dr: Cuentas por Pagar (payable account from source invoice)
        Cr: Cuenta Caja Chica (fund.account_id)
        """
        self.ensure_one()
        fund = self.fund_id
        if not fund.account_id:
            return False

        # Determine payable account from source document
        payable_account = False
        if self.source_move_id:
            # 1. Standard payable account (invoices)
            payable_line = self.source_move_id.line_ids.filtered(
                lambda l: l.account_id.account_type == "liability_payable"
            )
            if payable_line:
                payable_account = payable_line[0].account_id
            else:
                # 2. Journal entry: any unreconciled reconcilable line
                unreconciled = self.source_move_id.line_ids.filtered(
                    lambda l: l.account_id.reconcile and not l.reconciled
                )
                if unreconciled:
                    payable_account = unreconciled[0].account_id

        # Fall back to account_id field if no payable found
        if not payable_account:
            payable_account = self.account_id

        # For manual entries, use account_id directly
        if self.move_type in ("manual_expense", "manual_income") and self.account_id:
            payable_account = self.account_id

        if not payable_account:
            return False

        journal = fund.journal_id
        if not journal:
            journal = self.env["account.journal"].search(
                [("type", "=", "general"), ("company_id", "=", fund.company_id.id)],
                limit=1,
            )
        if not journal:
            return False

        ref_parts = [fund.name or "", self.source_move_id.ref or (self.source_move_id.name if self.source_move_id else "") or self.ref or "", self.name or ""]
        ref = " / ".join(p for p in ref_parts if p)

        entry_date = self.payment_date or self.date

        if self.move_type == "manual_income":
            lines = [
                (0, 0, {
                    "name": ref or _("Ingreso Caja Chica"),
                    "account_id": fund.account_id.id,
                    "debit": self.amount,
                    "credit": 0.0,
                    "partner_id": self.partner_id.id if self.partner_id else False,
                }),
                (0, 0, {
                    "name": ref or _("Ingreso Caja Chica"),
                    "account_id": payable_account.id,
                    "debit": 0.0,
                    "credit": self.amount,
                    "partner_id": self.partner_id.id if self.partner_id else False,
                }),
            ]
        else:
            lines = [
                (0, 0, {
                    "name": ref or _("Gasto Caja Chica"),
                    "account_id": payable_account.id,
                    "debit": self.amount,
                    "credit": 0.0,
                    "partner_id": self.partner_id.id if self.partner_id else False,
                    "analytic_distribution": (
                        {str(self.analytic_account_id.id): 100}
                        if self.analytic_account_id else False
                    ),
                }),
                (0, 0, {
                    "name": ref or _("Gasto Caja Chica"),
                    "account_id": fund.account_id.id,
                    "debit": 0.0,
                    "credit": self.amount,
                    "partner_id": fund.custodian_id.id if fund.custodian_id else False,
                }),
            ]
        move = self.env["account.move"].create({
            "journal_id": journal.id,
            "date": entry_date or fields.Date.context_today(self),
            "ref": ref or _("Gasto Caja Chica"),
            "company_id": fund.company_id.id,
            "line_ids": lines,
        })
        move.action_post()

        # Reconcile debit line of our entry with the source invoice payable line
        if self.source_move_id and payable_account:
            invoice_payable = self.source_move_id.line_ids.filtered(
                lambda l: l.account_id == payable_account and not l.reconciled
            )
            entry_debit = move.line_ids.filtered(
                lambda l: l.account_id == payable_account and l.debit > 0
            )
            if invoice_payable and entry_debit:
                try:
                    (invoice_payable + entry_debit).reconcile()
                except Exception:
                    pass

        return move

    def action_reject(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Rechazar Gasto"),
            "res_model": "ktx.petty.cash.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_move_id": self.id},
        }

    def _delete_accounting_entry(self):
        """Elimina la póliza contable vinculada desonciliando primero.

        Cubre tres casos:
        - Registro ya eliminado externamente → limpia el campo y continúa.
        - Asiento pertenece a un account.payment → cancela vía el pago.
        - Asiento ordinario → resetea a borrador y elimina; si hay fecha
          bloqueada, crea una reversa en su lugar.
        """
        self.ensure_one()
        move = self.accounting_move_id
        if not move:
            return

        # El registro puede haber sido eliminado desde otro flujo
        if not move.exists():
            self.write({'accounting_move_id': False})
            return

        # Quitar conciliaciones en todas las líneas del asiento
        reconciled = move.line_ids.filtered('reconciled')
        if reconciled:
            reconciled.remove_move_reconcile()

        # Caso: el asiento pertenece a un pago — hay que cancelar por el pago
        # (en Odoo 19 account.move no expone payment_id; buscamos al revés)
        payment = self.env['account.payment'].search(
            [('move_id', '=', move.id)], limit=1
        )
        if payment and payment.exists():
            try:
                payment.action_draft()   # resetea pago + asiento a borrador
                payment.unlink()
            except Exception:
                # Si no se puede borrar (lock date u otro), crear reversa
                if move.exists() and move.state == 'posted':
                    reversal = move._reverse_moves(
                        default_values_list=[{
                            'ref': _('Anulación CC: %s') % (self.name or move.ref or ''),
                        }]
                    )
                    if reversal:
                        reversal.action_post()
            self.write({'accounting_move_id': False})
            return

        # Caso: asiento ordinario (no ligado a pago)
        if move.state == 'draft':
            move.unlink()
        else:
            try:
                move.button_draft()
                move.unlink()
            except Exception:
                reversal = move._reverse_moves(
                    default_values_list=[{
                        'ref': _('Anulación CC: %s') % (self.name or move.ref or ''),
                    }]
                )
                if reversal:
                    reversal.action_post()

        self.write({'accounting_move_id': False})

    def action_reset_draft(self):
        for rec in self:
            if rec.state not in ("rejected", "cancelled", "pending"):
                raise UserError(_("Solo se pueden restablecer movimientos rechazados, cancelados o pendientes."))
            # Si quedó algún asiento vinculado (datos legacy o cancel fallido), eliminarlo
            if rec.accounting_move_id:
                rec._delete_accounting_entry()
            # Cancel open activities when resetting from pending
            if rec.state == "pending":
                todo_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
                if todo_type:
                    acts = rec.activity_ids.filtered(lambda a: a.activity_type_id == todo_type)
                    acts.unlink()
            rec.write({"rejection_note": False, "state": "draft"})
            rec.message_post(
                body=Markup("Restablecido a borrador por <b>%s</b>.") % self.env.user.name,
                subtype_xmlid="mail.mt_comment",
            )

    def action_cancel(self):
        for rec in self:
            if rec.accounting_move_id:
                rec._delete_accounting_entry()
            rec.write({"state": "cancelled"})
            rec.message_post(
                body=Markup("<b>Gasto cancelado</b> por %s.") % self.env.user.name,
                subtype_xmlid="mail.mt_comment",
            )

    def unlink(self):
        for rec in self:
            if rec.state not in ("draft", "rejected", "cancelled") and rec.fund_id.state != "closed":
                raise UserError(_("Solo se pueden eliminar movimientos en borrador, rechazados o cancelados."))
            if rec.accounting_move_id:
                raise UserError(_("No se puede eliminar '%s': tiene un asiento contable vinculado. Cancele primero.") % (rec.name or rec.id))
            # Reset linked staging record so the invoice can be re-assigned
            staging = self.env["ktx.petty.cash.staging"].search([("petty_cash_move_id", "=", rec.id)], limit=1)
            if staging:
                staging.write({"state": "pending", "petty_cash_move_id": False})
                staging.message_post(
                    body=Markup("Movimiento <b>%s</b> eliminado. Gasto vuelto a estado <b>Pendiente</b>.") % (rec.name or rec.id),
                    subtype_xmlid="mail.mt_comment",
                )
        return super().unlink()

    def action_view_accounting_entry(self):
        self.ensure_one()
        if not self.accounting_move_id:
            raise UserError(_("Este movimiento no tiene asiento contable generado."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Asiento Contable"),
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.accounting_move_id.id,
        }
