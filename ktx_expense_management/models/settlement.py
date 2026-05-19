# -*- coding: utf-8 -*-
import logging
from markupsafe import Markup
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class Settlement(models.Model):
    _name = "ktx.settlement"
    _description = "Liquidación"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, name desc"
    _rec_name = "name"
    _check_company_auto = True

    name = fields.Char(
        string="Referencia",
        required=True,
        copy=False,
        default="/",
        tracking=True,
        index=True,
    )
    description = fields.Char(
        string="Descripción",
        tracking=True,
        help="Nombre descriptivo para identificar fácilmente esta liquidación.",
    )
    date = fields.Date(
        string="Fecha Liquidación",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Diario",
        tracking=True,
        ondelete="restrict",
        domain="[('type', 'in', ['general', 'purchase']), ('company_id', '=', company_id)]",
    )
    account_id = fields.Many2one(
        comodel_name="account.account",
        string="Cuenta por Pagar",
        tracking=True,
        ondelete="restrict",
        domain="[('account_type', 'in', ['liability_payable', 'liability_current']), ('company_ids', 'in', [company_id])]",
    )
    employee_id = fields.Many2one(
        comodel_name="res.partner",
        string="Empleado / Beneficiario",
        tracking=True,
        ondelete="restrict",
    )
    approver_id = fields.Many2one(
        comodel_name="res.users",
        string="Aprobador",
        tracking=True,
        ondelete="restrict",
        domain=[("share", "=", False)],
    )
    # --- Moneda y tipo de cambio ---
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Moneda",
        required=True,
        default=lambda self: self.env.company.currency_id,
        tracking=True,
        ondelete="restrict",
    )
    company_currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Moneda Compañía",
        compute="_compute_company_currency_id",
        store=False,
    )
    rate_date = fields.Date(
        string="Fecha Tipo de Cambio",
        default=fields.Date.context_today,
        tracking=True,
    )
    exchange_rate = fields.Float(
        string="Tipo de Cambio",
        digits=(16, 6),
        default=1.0,
        tracking=True,
        help="Tipo de cambio: unidades de moneda del documento por 1 unidad de moneda de liquidación.",
    )
    # --- Totales ---
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        ondelete="restrict",
    )
    intercompany_receivable_id = fields.Many2one(
        comodel_name="account.account",
        string="Cuenta por Cobrar Intercompañía",
        domain="[('account_type', 'in', ['asset_receivable', 'liability_payable', 'liability_current']), ('company_ids', 'in', [company_id])]",
        help="Cuenta de débito en el asiento de esta liquidación para gastos de otra empresa.",
        copy=False,
        ondelete="restrict",
    )
    line_ids = fields.One2many(
        comodel_name="ktx.settlement.line",
        inverse_name="settlement_id",
        string="Líneas de Liquidación",
    )
    amount_total = fields.Monetary(
        string="Total a Liquidar",
        currency_field="currency_id",
        compute="_compute_amount_total",
        store=True,
        tracking=True,
    )
    state_color = fields.Integer(compute="_compute_state_color")
    # --- Documentos relacionados ---
    move_id = fields.Many2one(
        comodel_name="account.move",
        string="Asiento Contable",
        readonly=True,
        copy=False,
        tracking=True,
        ondelete="set null",
    )
    payment_ids = fields.Many2many(
        comodel_name="account.payment",
        relation="ktx_settlement_payment_rel",
        column1="settlement_id",
        column2="payment_id",
        string="Pagos Registrados",
        readonly=True,
        copy=False,
    )
    amount_paid = fields.Monetary(
        string="Total Pagado",
        currency_field="currency_id",
        compute="_compute_payment_amounts",
        store=True,
    )
    amount_residual = fields.Monetary(
        string="Saldo Pendiente",
        currency_field="currency_id",
        compute="_compute_payment_amounts",
        store=True,
    )
    intercompany_account_ids = fields.One2many(
        comodel_name="ktx.settlement.company.account",
        inverse_name="settlement_id",
        string="Cuentas Intercompañía",
    )
    has_cross_company_lines = fields.Boolean(
        compute="_compute_has_cross_company_lines",
        store=False,
    )
    over_limit = fields.Boolean(
        compute="_compute_over_limit",
        store=False,
    )
    # --- Control de flujo ---
    state = fields.Selection(
        selection=[
            ("draft", "Borrador"),
            ("confirmed", "Por Autorizar"),
            ("approved", "Autorizada"),
            ("posted", "Publicada"),
            ("in_payment", "En Proceso de Pago"),
            ("paid", "Pagada"),
            ("rejected", "Rechazada"),
            ("cancelled", "Cancelada"),
        ],
        string="Estado",
        default="draft",
        required=True,
        tracking=True,
        copy=False,
        index=True,
    )
    rejection_note = fields.Text(
        string="Motivo de Rechazo",
        tracking=True,
        copy=False,
    )
    notes = fields.Text(
        string="Notas Internas",
    )
    forex_note = fields.Text(
        string="Diferencial Cambiario",
        readonly=True,
        copy=False,
    )

    # ------------------------------------------------------------------
    # Search override for company isolation / multi-company
    # ------------------------------------------------------------------

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, **kwargs):
        """Filter settlements by company unless multi-company mode is enabled."""
        if not self.env.su:
            multi = self.env["ir.config_parameter"].sudo().get_param(
                "ktx_expense_management.multi_company_staging", "False"
            )
            if multi not in ("True", "1", "true"):
                domain = [("company_id", "in", self.env.companies.ids)] + list(domain)
        return super()._search(domain, offset=offset, limit=limit, order=order, **kwargs)

    # ------------------------------------------------------------------
    # Computed
    # ------------------------------------------------------------------

    def _compute_company_currency_id(self):
        for rec in self:
            rec.company_currency_id = (rec.company_id or self.env.company).currency_id

    @api.depends("state")
    def _compute_state_color(self):
        _map = {
            "draft": 0, "confirmed": 2, "approved": 4,
            "posted": 7, "in_payment": 3, "paid": 10,
            "rejected": 1, "cancelled": 0,
        }
        for rec in self:
            rec.state_color = _map.get(rec.state, 0)

    @api.depends(
        "payment_ids", "payment_ids.amount", "payment_ids.currency_id",
        "payment_ids.state", "amount_total",
    )
    def _compute_payment_amounts(self):
        for rec in self:
            if not rec.payment_ids:
                rec.amount_paid = 0.0
                rec.amount_residual = rec.amount_total
                continue
            company = rec.company_id or self.env.company
            ref_date = rec.rate_date or rec.date or fields.Date.context_today(self)
            total = 0.0
            for pay in rec.payment_ids.filtered(lambda p: p.state != "cancel"):
                pay_cur = pay.currency_id or company.currency_id
                if pay_cur == rec.currency_id:
                    total += pay.amount
                else:
                    total += pay_cur._convert(
                        pay.amount, rec.currency_id, company, ref_date
                    )
            rec.amount_paid = total
            rec.amount_residual = max(0.0, rec.amount_total - total)

    def _compute_has_cross_company_lines(self):
        for rec in self:
            company = rec.company_id or self.env.company
            rec.has_cross_company_lines = any(
                l.move_id and l.move_id.company_id and l.move_id.company_id != company
                for l in rec.line_ids
            )

    def _sync_intercompany_accounts(self):
        """Auto-populates intercompany_account_ids for each foreign company found in lines."""
        for rec in self:
            settlement_company = rec.company_id or self.env.company
            foreign_companies = rec.line_ids.filtered(
                lambda l: l.move_id and l.move_id.company_id and l.move_id.company_id != settlement_company
            ).mapped("move_id.company_id")
            existing_companies = rec.intercompany_account_ids.mapped("company_id")
            for co in foreign_companies:
                if co not in existing_companies:
                    payable_account = self.env["account.account"].sudo().search([
                        ("company_ids", "in", co.ids),
                        ("account_type", "=", "liability_payable"),
                    ], limit=1)
                    vals = {
                        "settlement_id": rec.id,
                        "company_id": co.id,
                    }
                    if payable_account:
                        vals["account_id"] = payable_account.id
                    self.env["ktx.settlement.company.account"].sudo().create(vals)
            # Remove entries for companies no longer present
            stale = rec.intercompany_account_ids.filtered(lambda r: r.company_id not in foreign_companies)
            stale.unlink()

    @api.depends("line_ids.amount_in_settlement_currency")
    def _compute_amount_total(self):
        for rec in self:
            rec.amount_total = sum(rec.line_ids.mapped("amount_in_settlement_currency"))

    @api.depends("amount_total", "employee_id", "employee_id.ktx_expense_limit")
    def _compute_over_limit(self):
        for rec in self:
            limit = rec.employee_id.ktx_expense_limit if rec.employee_id else 0.0
            rec.over_limit = bool(limit > 0 and rec.amount_total > limit)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("ktx.settlement") or "/"
                )
        records = super().create(vals_list)
        records._sync_intercompany_accounts()
        return records

    def write(self, vals):
        res = super().write(vals)
        if "line_ids" in vals:
            self._sync_intercompany_accounts()
        return res

    def unlink(self):
        _SAFE_STATES = ("draft", "cancelled")
        for rec in self:
            if rec.state in ("paid", "in_payment"):
                raise UserError(
                    _("No se puede eliminar la liquidación «%s» porque tiene un pago registrado. "
                      "Cancele el pago primero.")
                    % rec.name
                )
            if rec.state == "posted":
                raise UserError(
                    _("No se puede eliminar la liquidación «%s» porque tiene un asiento contable publicado. "
                      "Use el botón «Cancelar Asiento» primero.")
                    % rec.name
                )
            if rec.state in ("confirmed", "approved"):
                raise UserError(
                    _("No se puede eliminar la liquidación «%s» en estado «%s». "
                      "Rechace o cancélela antes de eliminar.")
                    % (rec.name, dict(self._fields["state"].selection).get(rec.state, rec.state))
                )
        return super().unlink()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Onchanges
    # ------------------------------------------------------------------

    @api.onchange("company_id")
    def _onchange_company_id_clear_journal_account(self):
        """Clear journal and account when company changes so user picks from the new company."""
        company = self.company_id or self.env.company
        if self.journal_id and self.journal_id.company_id != company:
            self.journal_id = False
        if self.account_id:
            if company not in self.account_id.company_ids and self.account_id.company_ids:
                self.account_id = False

    @api.onchange("date")
    def _onchange_date_update_rate_date(self):
        """Al cambiar fecha de liquidación, sincroniza fecha de tipo de cambio."""
        if self.date and not self._origin.rate_date:
            self.rate_date = self.date

    @api.onchange("currency_id", "rate_date", "date")
    def _onchange_currency_or_rate_date(self):
        """Auto-actualiza el tipo de cambio desde las tablas de Odoo."""
        company_currency = (self.company_id or self.env.company).currency_id
        if not self.currency_id or self.currency_id == company_currency:
            self.exchange_rate = 1.0
            return
        ref_date = self.rate_date or self.date or fields.Date.context_today(self)
        try:
            rate = self.env["res.currency"]._get_conversion_rate(
                self.currency_id,
                company_currency,
                self.company_id or self.env.company,
                ref_date,
            )
            # rate = company_units per 1 foreign unit → invert for our formula
            self.exchange_rate = (1.0 / rate) if rate else 1.0
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Staging selector action
    # ------------------------------------------------------------------

    def action_open_staging_selector(self):
        """Abre el wizard de selección masiva de gastos por liquidar."""
        self.ensure_one()
        if self.state not in ("draft", "confirmed"):
            raise UserError(
                _("Solo se pueden agregar líneas a liquidaciones en borrador o confirmadas.")
            )
        return {
            "type": "ir.actions.act_window",
            "res_model": "ktx.staging.selection.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_settlement_id": self.id,
            },
        }

    def _check_state(self, expected_states, action_name):
        for rec in self:
            if rec.state not in expected_states:
                state_label = dict(self._fields["state"].selection).get(rec.state, rec.state)
                raise UserError(
                    _("No se puede ejecutar '%s' desde el estado '%s'.")
                    % (action_name, state_label)
                )

    def _send_mail_to_approver(self):
        """Crea actividad para el aprobador y mensaje en chatter."""
        self.ensure_one()
        if not self.approver_id:
            return

        # Crear actividad asignada al aprobador
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        settlement_url = "{}/odoo/liquidaciones/{}".format(base_url, self.id)
        self.activity_schedule(
            "mail.mail_activity_data_todo",
            summary=_("Autorizar liquidación %s") % self.name,
            note=Markup(
                "<p>La liquidación <strong>{ref}</strong> del {date} por "
                "<strong>{total} {currency}</strong> ({lines} línea(s)) "
                "requiere tu autorización.</p>"
                "<p><a href='{url}' style='background:#875A7B;color:white;padding:6px 14px;"
                "border-radius:4px;text-decoration:none;font-weight:600'>"
                "▶ Abrir liquidación para autorizar</a></p>"
            ).format(
                ref=self.name,
                date=self.date,
                total="{:,.2f}".format(self.amount_total),
                currency=self.currency_id.name,
                lines=len(self.line_ids),
                url=settlement_url,
            ),
            user_id=self.approver_id.id,
        )

        # Mensaje en chatter con mención
        body = Markup(
            "<p>Hola <a href='#' data-oe-model='res.users' data-oe-id='{uid}'>{name}</a>,</p>"
            "<p>La liquidación <strong>{ref}</strong> del {date} por "
            "<strong>{total} {currency}</strong> ({lines} línea(s)) "
            "requiere tu autorización.</p>"
        ).format(
            uid=self.approver_id.id,
            name=self.approver_id.name,
            ref=self.name,
            date=self.date,
            total="{:,.2f}".format(self.amount_total),
            currency=self.currency_id.name,
            lines=len(self.line_ids),
        )
        self.message_post(
            body=body,
            subtype_xmlid="mail.mt_comment",
            partner_ids=[self.approver_id.partner_id.id],
        )

    def _complete_approver_activity(self, feedback):
        """Marca como hecha la actividad pendiente del aprobador."""
        self.ensure_one()
        if not self.approver_id:
            return
        activities = self.activity_ids.filtered(
            lambda a: a.user_id == self.approver_id
                and a.activity_type_id == self.env.ref("mail.mail_activity_data_todo")
        )
        for act in activities:
            act.action_feedback(feedback=feedback)

    def _send_mail_to_creator(self, subject, message, activity_summary=None):
        """Notifica al creador con mensaje en chatter y actividad opcional."""
        self.ensure_one()
        creator = self.create_uid
        if not creator or not creator.partner_id:
            return

        body = Markup(message) if isinstance(message, str) else message

        # Crear actividad informativa para el creador si se indica resumen
        if activity_summary and creator != self.env.user:
            self.activity_schedule(
                "mail.mail_activity_data_todo",
                summary=activity_summary,
                note=body,
                user_id=creator.id,
            )

        self.message_post(
            body=body,
            subtype_xmlid="mail.mt_comment",
            partner_ids=[creator.partner_id.id],
        )

    def _get_intercompany_receivable(self):
        """Returns the intercompany receivable account from the settlement field."""
        if not self.intercompany_receivable_id:
            raise UserError(
                _("Configure la Cuenta por Cobrar Intercompañía en la pestaña «Intercompañía» de esta liquidación.")
            )
        return self.intercompany_receivable_id

    def _create_intercompany_entry(self, line):
        """Creates a mirror journal entry in the other company."""
        other_company = line.move_id.company_id
        original_payable = self._get_payable_account_from_move(line.move_id)
        if not original_payable:
            _logger.warning("Sin cuenta por pagar en %s — no se creó asiento intercompañía.", line.move_name)
            return

        ic_rec = self.intercompany_account_ids.filtered(lambda r: r.company_id == other_company)
        if not ic_rec:
            _logger.warning("Sin cuenta intercompañía para %s — no se creó asiento.", other_company.name)
            return
        payable_account = ic_rec[0].account_id

        pay_companies = payable_account.company_ids
        if pay_companies and other_company not in pay_companies:
            raise UserError(
                _("❌ Cuenta por Pagar Intercompañía incorrecta para '%s'\n\n"
                  "La cuenta '%s' no pertenece a esa empresa.\n"
                  "Corrija la cuenta en la pestaña «Intercompañía» de esta liquidación.")
                % (other_company.name, payable_account.display_name)
            )

        journal = self.env["account.journal"].sudo().search([
            ("company_id", "=", other_company.id),
            ("type", "=", "general"),
        ], limit=1)
        if not journal:
            _logger.warning("Sin diario general en %s — no se creó asiento intercompañía.", other_company.name)
            return

        ref_date = self.date or fields.Date.context_today(self)
        line_cur = line.currency_id or other_company.currency_id
        other_cur = other_company.currency_id
        amount = line.amount_to_pay if line_cur == other_cur else \
            line_cur._convert(line.amount_to_pay, other_cur, other_company, ref_date)

        settlement_company = self.company_id or self.env.company
        move_vals = {
            "journal_id": journal.id,
            "date": ref_date,
            "ref": _("Intercompañía — %s") % self.name,
            "company_id": other_company.id,
            "line_ids": [
                (0, 0, {
                    "name": line.move_name or self.name,
                    "account_id": original_payable.id,
                    "partner_id": line.partner_id.id if line.partner_id else False,
                    "debit": amount,
                    "credit": 0.0,
                }),
                (0, 0, {
                    "name": _("Intercompañía — %s") % self.name,
                    "account_id": payable_account.id,
                    "partner_id": settlement_company.partner_id.id if settlement_company.partner_id else False,
                    "debit": 0.0,
                    "credit": amount,
                }),
            ],
        }
        try:
            move = self.env["account.move"].sudo().with_company(other_company).create(move_vals)
            move.action_post()
            invoice_payable_lines = line.move_id.line_ids.filtered(
                lambda l: l.account_id == original_payable and not l.reconciled
            )
            counterpart_debit = move.line_ids.filtered(
                lambda l: l.account_id == original_payable and l.debit > 0
            )
            to_reconcile = invoice_payable_lines | counterpart_debit
            if len(to_reconcile) >= 2:
                to_reconcile.reconcile()
        except Exception as e:
            _logger.warning("No se pudo crear asiento intercompañía en %s: %s", other_company.name, e)

    def _get_payable_account_from_move(self, move):
        """Obtiene la cuenta por pagar original de la factura/asiento."""
        payable_line = move.line_ids.filtered(
            lambda l: l.account_id.account_type in (
                "liability_payable", "liability_current"
            ) and not l.reconciled
        )
        if payable_line:
            return payable_line[0].account_id
        # Fallback: primera cuenta de gasto
        expense_line = move.line_ids.filtered(
            lambda l: l.account_id.account_type in (
                "expense", "expense_depreciation", "expense_direct_cost"
            )
        )
        if expense_line:
            return expense_line[0].account_id
        # Último fallback: cuenta configurada en la liquidación
        return self.account_id

    # ------------------------------------------------------------------
    # Actions / State transitions
    # ------------------------------------------------------------------

    def action_confirm(self):
        self._check_state(["draft"], _("Confirmar"))
        for rec in self:
            if not rec.line_ids:
                raise UserError(_("No puede confirmar una liquidación sin líneas."))
            # Validate that every line has a staging_id (required at confirm, not ORM level)
            empty_lines = rec.line_ids.filtered(lambda l: not l.staging_id)
            if empty_lines:
                raise UserError(
                    _("Todas las líneas deben tener un gasto por liquidar asignado antes de confirmar.")
                )
            if not rec.journal_id:
                raise UserError(_("Debe seleccionar un diario antes de confirmar la liquidación."))
            if not rec.account_id:
                raise UserError(_("Debe seleccionar una cuenta por pagar antes de confirmar la liquidación."))
            if not rec.approver_id:
                raise UserError(
                    _("Debe seleccionar un aprobador antes de confirmar la liquidación.")
                )
            rec.state = "confirmed"
            rec._send_mail_to_approver()

    def action_approve(self):
        self._check_state(["confirmed"], _("Aprobar"))
        for rec in self:
            rec.write({"state": "approved", "rejection_note": False})
            # Completar actividad pendiente del aprobador
            rec._complete_approver_activity(
                feedback=_("Liquidación %s aprobada.") % rec.name
            )
            msg = Markup(
                "<p>✅ La liquidación <strong>{ref}</strong> fue <strong>aprobada</strong> "
                "por {approver} el {date}.</p>"
                "<p>Ya puede proceder a publicarla y registrar el pago.</p>"
            ).format(
                ref=rec.name,
                approver=self.env.user.name,
                date=fields.Date.today(),
            )
            rec._send_mail_to_creator(
                subject=_("Liquidación aprobada"),
                message=msg,
                activity_summary=_("Liquidación %s aprobada — lista para publicar") % rec.name,
            )

    def action_post(self):
        self._check_state(["approved"], _("Publicar"))
        for rec in self:
            company = rec.company_id or self.env.company
            cross_companies = rec.line_ids.filtered(
                lambda l: l.move_id and l.move_id.company_id and l.move_id.company_id != company
            ).mapped("move_id.company_id")
            if cross_companies:
                if not rec.intercompany_receivable_id:
                    raise UserError(
                        _("La liquidación incluye gastos de otra empresa.\n"
                          "Configure la Cuenta por Cobrar Intercompañía en la pestaña «Intercompañía».")
                    )
                missing = [
                    co.name for co in cross_companies
                    if not rec.intercompany_account_ids.filtered(lambda r: r.company_id == co)
                ]
                if missing:
                    raise UserError(
                        _("Faltan cuentas por pagar intercompañía para:\n%s\n\n"
                          "Agréguelas en la pestaña «Intercompañía» de esta liquidación.")
                        % "\n".join("• " + m for m in missing)
                    )
            move = rec._create_journal_entry()
            rec.write({"state": "posted", "move_id": move.id})
            rec.line_ids.staging_id.write({"state": "in_settlement"})

    def action_open_payment_wizard(self):
        """Abre el wizard de pago (permite pagos parciales desde in_payment también)."""
        self._check_state(["posted", "in_payment"], _("Registrar Pago"))
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "ktx.settlement.payment.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_settlement_id": self.id,
                "default_amount": self.amount_residual,
                "default_currency_id": self.currency_id.id,
            },
        }

    def action_reject(self):
        """Abre el wizard de rechazo para ingresar el motivo."""
        self._check_state(["confirmed", "approved"], _("Rechazar"))
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "ktx.settlement.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_settlement_id": self.id},
        }

    def action_do_reject(self, rejection_note):
        """Aplica el rechazo con la nota del wizard."""
        self.ensure_one()
        self._check_state(["confirmed", "approved"], _("Rechazar"))
        self.write({"state": "rejected", "rejection_note": rejection_note})
        # Completar actividad pendiente del aprobador
        self._complete_approver_activity(
            feedback=_("Liquidación %s rechazada. Motivo: %s") % (self.name, rejection_note or "")
        )
        msg = Markup(
            "<p>❌ La liquidación <strong>{ref}</strong> fue <strong>rechazada</strong> "
            "por {approver}.</p><p><strong>Motivo:</strong> {note}</p>"
            "<p>Puede corregirla y volver a confirmar.</p>"
        ).format(
            ref=self.name,
            approver=self.env.user.name,
            note=rejection_note or "",
        )
        self._send_mail_to_creator(
            subject=_("Liquidación rechazada"),
            message=msg,
            activity_summary=_("Liquidación %s rechazada — revisar motivo") % self.name,
        )

    def action_cancel(self):
        self._check_state(["draft", "rejected"], _("Cancelar"))
        self.write({"state": "cancelled"})

    def action_reset_draft(self):
        self._check_state(["rejected", "cancelled"], _("Restablecer a Borrador"))
        self.write({"state": "draft", "rejection_note": False})

    def action_view_journal_entry(self):
        self.ensure_one()
        if not self.move_id:
            raise UserError(_("No hay asiento contable asociado a esta liquidación."))
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.move_id.id,
        }

    def action_cancel_payment(self):
        """Revierte a Publicado: desreconcilia y elimina todos los pagos vinculados."""
        self._check_state(["paid", "in_payment"], _("Cancelar Pago(s)"))
        for rec in self:
            for payment in rec.payment_ids:
                payment_move = payment.move_id
                try:
                    if payment_move:
                        reconciled = payment_move.line_ids.filtered(lambda l: l.reconciled)
                        if reconciled:
                            reconciled.remove_move_reconcile()
                        if payment_move.state == "posted":
                            payment_move.button_draft()
                    payment.with_context(_skip_ktx_settlement_unlink=True).unlink()
                except Exception as e:
                    raise UserError(
                        _("No se pudo cancelar el pago %s: %s\n\n"
                          "Cancele el pago manualmente desde Contabilidad → Pagos.")
                        % (payment.name, str(e))
                    )
            rec.write({"state": "posted", "payment_ids": [(5,)], "forex_note": False})

    def action_cancel_move(self):
        """Revierte estado a Aprobado: cancela y elimina el asiento contable."""
        self._check_state(["posted"], _("Cancelar Asiento"))
        for rec in self:
            if rec.move_id:
                try:
                    if rec.move_id.state == "posted":
                        rec.move_id.button_draft()
                    rec.move_id.with_context(_skip_ktx_settlement_unlink=True).unlink()
                except Exception as e:
                    raise UserError(
                        _("No se puede eliminar el asiento contable: %s") % str(e)
                    )
            rec.line_ids.staging_id.write({"state": "pending"})
            rec.write({"state": "approved", "move_id": False})

    def action_view_payment(self):
        self.ensure_one()
        if not self.payment_ids:
            raise UserError(_("No hay pagos registrados para esta liquidación."))
        if len(self.payment_ids) == 1:
            return {
                "type": "ir.actions.act_window",
                "res_model": "account.payment",
                "view_mode": "form",
                "res_id": self.payment_ids[0].id,
            }
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.payment",
            "view_mode": "list,form",
            "domain": [("id", "in", self.payment_ids.ids)],
            "name": _("Pagos — %s") % self.name,
        }

    def action_download_excel(self):
        """Genera y descarga la liquidación en formato Excel editable."""
        self.ensure_one()
        try:
            import xlsxwriter
            import io
            import base64
        except ImportError:
            raise UserError(_("La biblioteca xlsxwriter no está disponible en este servidor."))

        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {"in_memory": True})
        ws = wb.add_worksheet("Liquidación")

        company = self.company_id or self.env.company
        state_labels = dict(self._fields["state"].selection)

        # Formatos
        fmt_title = wb.add_format({"bold": True, "font_size": 14, "font_color": "#007B7F"})
        fmt_subtitle = wb.add_format({"bold": True, "font_size": 11})
        fmt_label = wb.add_format({"bold": True, "bg_color": "#F0F0F0", "border": 1})
        fmt_value = wb.add_format({"border": 1})
        fmt_header = wb.add_format({"bold": True, "bg_color": "#007B7F", "font_color": "white", "border": 1, "align": "center"})
        fmt_data = wb.add_format({"border": 1, "valign": "vcenter"})
        fmt_money = wb.add_format({"border": 1, "num_format": '#,##0.00', "align": "right"})
        fmt_total_label = wb.add_format({"bold": True, "bg_color": "#E0E0E0", "border": 1, "align": "right"})
        fmt_total = wb.add_format({"bold": True, "bg_color": "#E0E0E0", "border": 1, "num_format": '#,##0.00', "align": "right"})
        fmt_section = wb.add_format({"bold": True, "font_size": 11, "bg_color": "#007B7F", "font_color": "white", "border": 1})

        ws.set_column(0, 0, 22)
        ws.set_column(1, 1, 22)
        ws.set_column(2, 2, 28)
        ws.set_column(3, 3, 14)
        ws.set_column(4, 4, 10)
        ws.set_column(5, 7, 16)

        fmt_ref = wb.add_format({"bold": True, "font_size": 18, "font_color": "#007B7F"})
        fmt_desc = wb.add_format({"font_size": 13, "font_color": "#444444"})
        fmt_state = wb.add_format({"bold": True, "font_size": 10, "font_color": "#888888"})

        # Encabezado empresa + referencia
        ws.write(0, 0, company.name, fmt_title)
        ws.write(1, 0, "LIQUIDACIÓN DE GASTOS", fmt_state)
        ws.write(2, 0, self.name or "", fmt_ref)
        if self.description:
            ws.write(3, 0, self.description, fmt_desc)
            ws.write(4, 0, "Estado: %s" % state_labels.get(self.state, self.state), fmt_subtitle)
            row_start = 6
        else:
            ws.write(3, 0, "Estado: %s" % state_labels.get(self.state, self.state), fmt_subtitle)
            row_start = 5

        # Info general
        row = row_start
        info_pairs = [
            ("Referencia", self.name or ""),
            ("Descripción", self.description or ""),
            ("Fecha", str(self.date or "")),
            ("Diario", self.journal_id.name if self.journal_id else ""),
            ("Cuenta", self.account_id.display_name if self.account_id else ""),
            ("Empleado / Beneficiario", self.employee_id.name if self.employee_id else ""),
            ("Aprobador", self.approver_id.name if self.approver_id else ""),
            ("Moneda", self.currency_id.name if self.currency_id else ""),
        ]
        if self.currency_id != (self.company_id or self.env.company).currency_id:
            info_pairs.append(("Tipo de Cambio", str(self.exchange_rate)))

        for label, value in info_pairs:
            ws.write(row, 0, label, fmt_label)
            ws.write(row, 1, value, fmt_value)
            row += 1

        # Tabla de líneas
        row += 1
        ws.merge_range(row, 0, row, 7, "LÍNEAS DE LIQUIDACIÓN", fmt_section)
        row += 1
        headers = ["Póliza", "Referencia / Serie", "Proveedor", "Fecha", "Mon.", "Total Documento", "Monto a Liquidar", "Monto Convertido"]
        for col, h in enumerate(headers):
            ws.write(row, col, h, fmt_header)
        row += 1

        for line in self.line_ids:
            ws.write(row, 0, line.move_name or "", fmt_data)
            ws.write(row, 1, line.ref or "", fmt_data)
            ws.write(row, 2, line.partner_id.name if line.partner_id else "", fmt_data)
            ws.write(row, 3, str(line.invoice_date or ""), fmt_data)
            ws.write(row, 4, line.currency_id.name if line.currency_id else "", fmt_data)
            ws.write(row, 5, line.amount_invoice, fmt_money)
            ws.write(row, 6, line.amount_to_pay, fmt_money)
            ws.write(row, 7, line.amount_in_settlement_currency, fmt_money)
            row += 1

        ws.write(row, 6, "TOTAL:", fmt_total_label)
        ws.write(row, 7, self.amount_total, fmt_total)

        # Pagos
        if self.payment_ids:
            row += 2
            ws.merge_range(row, 0, row, 7, "PAGOS REGISTRADOS", fmt_section)
            row += 1
            pay_headers = ["Referencia", "Fecha", "Contacto", "Diario", "Memo", "Monto"]
            for col, h in enumerate(pay_headers):
                ws.write(row, col, h, fmt_header)
            row += 1
            for payment in self.payment_ids:
                ws.write(row, 0, payment.name or "", fmt_data)
                ws.write(row, 1, str(payment.date or ""), fmt_data)
                ws.write(row, 2, payment.partner_id.name if payment.partner_id else "", fmt_data)
                ws.write(row, 3, payment.journal_id.name if payment.journal_id else "", fmt_data)
                ws.write(row, 4, payment.memo or "", fmt_data)
                ws.write(row, 5, payment.amount, fmt_money)
                row += 1

        # Notas / Anotaciones
        if self.notes:
            row += 2
            ws.merge_range(row, 0, row, 7, "ANOTACIONES", fmt_section)
            row += 1
            ws.merge_range(row, 0, row, 7, self.notes, fmt_value)

        wb.close()
        xlsx_data = output.getvalue()
        filename = "LIQ_%s.xlsx" % (self.name or "liquidacion").replace("/", "_")
        attachment = self.env["ir.attachment"].create({
            "name": filename,
            "type": "binary",
            "datas": base64.b64encode(xlsx_data).decode(),
            "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "res_model": self._name,
            "res_id": self.id,
        })
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/%d?download=true" % attachment.id,
            "target": "new",
        }

    # ------------------------------------------------------------------
    # Journal Entry
    # ------------------------------------------------------------------

    def _reconcile_original_invoices(self, settlement_move):
        """Reconcilia cada línea pagable de factura original con su débito específico
        en el asiento de liquidación, uno a uno, para evitar que líneas de distintas
        facturas del mismo proveedor se mezclen entre sí.
        """
        ref_date = self.rate_date or self.date or fields.Date.context_today(self)
        company = self.company_id or self.env.company
        for line in self.line_ids:
            original_move = line.move_id
            if not original_move or original_move.move_type not in ("in_invoice",):
                continue
            # Skip cross-company lines — reconciliation across companies is not allowed
            if original_move.company_id and original_move.company_id != company:
                continue

            payable_account = self._get_payable_account_from_move(original_move)
            if not payable_account:
                continue

            # Payable line(s) of this specific invoice
            invoice_payable = original_move.line_ids.filtered(
                lambda l: l.account_id == payable_account and not l.reconciled
            )
            if not invoice_payable:
                continue

            # Find the ONE debit line in the settlement move that belongs to this invoice.
            # Primary key: same account + same name (invoice number) + same partner.
            invoice_name = line.move_name or ""
            partner = line.partner_id

            def _match(l, acct=payable_account, name=invoice_name, pid=partner.id if partner else False):
                return (
                    l.account_id == acct
                    and l.debit > 0
                    and not l.reconciled
                    and l.name == name
                    and (not pid or l.partner_id.id == pid)
                )

            settlement_debit = settlement_move.line_ids.filtered(_match)

            # Fallback: same account + partner (ignore name) — take the first unreconciled
            if not settlement_debit:
                def _match_loose(l, acct=payable_account, pid=partner.id if partner else False):
                    return l.account_id == acct and l.debit > 0 and not l.reconciled and (not pid or l.partner_id.id == pid)
                settlement_debit = settlement_move.line_ids.filtered(_match_loose)[:1]

            to_reconcile = invoice_payable | settlement_debit
            if len(to_reconcile) >= 2:
                try:
                    to_reconcile.with_context(
                        ktx_settlement_date=ref_date
                    ).reconcile()
                except Exception as e:
                    _logger.warning(
                        "No se pudo reconciliar factura %s con asiento de liquidación: %s",
                        original_move.name, e,
                    )

    def _create_journal_entry(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        company_currency = company.currency_id
        ref_date = self.date or fields.Date.context_today(self)
        lines = []
        total_debit = 0.0

        # Resolve intercompany accounts once (raises early if not configured)
        cross_company_lines = [
            l for l in self.line_ids
            if l.move_id and l.move_id.company_id and l.move_id.company_id != company
        ]
        intercompany_receivable = None
        if cross_company_lines:
            intercompany_receivable = self._get_intercompany_receivable()

        for line in self.line_ids:
            line_company = line.move_id.company_id if line.move_id else company
            is_cross_company = line_company and line_company != company
            if is_cross_company:
                debit_account = intercompany_receivable
            else:
                debit_account = self._get_payable_account_from_move(line.move_id)

            # Always express debit in company currency
            line_currency = line.currency_id or company_currency
            if line_currency == company_currency:
                amount_company = line.amount_to_pay
            else:
                try:
                    amount_company = line_currency._convert(
                        line.amount_to_pay, company_currency, company, ref_date
                    )
                except Exception:
                    rate = self.exchange_rate or 1.0
                    amount_company = line.amount_to_pay / rate if rate else line.amount_to_pay

            total_debit += amount_company

            # For cross-company lines use the secondary company as partner on the receivable
            if is_cross_company:
                line_partner = line_company.partner_id.id if line_company.partner_id else False
            else:
                line_partner = line.partner_id.id if line.partner_id else False
            line_vals = {
                "name": line.move_name or line.ref or self.name,
                "partner_id": line_partner,
                "account_id": debit_account.id,
                "debit": amount_company,
                "credit": 0.0,
            }
            # Set foreign currency info when different from company currency
            if line_currency != company_currency:
                line_vals["currency_id"] = line_currency.id
                line_vals["amount_currency"] = line.amount_to_pay

            lines.append((0, 0, line_vals))

        # Credit line — exactly equals total debit to guarantee balance
        employee_partner = self.employee_id.id if self.employee_id else False
        credit_vals = {
            "name": self.name,
            "partner_id": employee_partner,
            "account_id": self.account_id.id,
            "debit": 0.0,
            "credit": total_debit,
        }
        settlement_currency = self.currency_id or company_currency
        if settlement_currency != company_currency:
            credit_vals["currency_id"] = settlement_currency.id
            credit_vals["amount_currency"] = -self.amount_total

        lines.append((0, 0, credit_vals))

        move_vals = {
            "journal_id": self.journal_id.id,
            "date": ref_date,
            "ref": self.name,
            "company_id": company.id,
            "line_ids": lines,
        }
        move = self.env["account.move"].create(move_vals)
        move.action_post()
        self._reconcile_original_invoices(move)

        # Create mirror entries in each other company for cross-company lines
        if cross_company_lines:
            for line in cross_company_lines:
                self._create_intercompany_entry(line)

        return move
