# -*- coding: utf-8 -*-
import logging
from markupsafe import Markup
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class KtxPettyCashReplenishment(models.Model):
    _name = "ktx.petty.cash.replenishment"
    _description = "Solicitud de Reposición de Caja Chica"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, **kwargs):
        if not self.env.su:
            multi = self.env['ir.config_parameter'].sudo().get_param(
                'ktx_petty_cash.multi_company', 'False'
            )
            if multi not in ('True', '1', 'true'):
                domain = [('company_id', 'in', self.env.companies.ids)] + list(domain)
        return super()._search(domain, offset=offset, limit=limit, order=order, **kwargs)

    name = fields.Char(
        string="Referencia", required=True, default="/", copy=False, tracking=True,
    )
    fund_id = fields.Many2one(
        "ktx.petty.cash.fund", string="Fondo",
        required=True, tracking=True, ondelete="restrict",
    )
    date = fields.Date(
        string="Fecha", default=fields.Date.context_today, required=True,
    )
    amount = fields.Monetary(
        string="Monto Total", currency_field="currency_id",
        compute="_compute_amount", store=True,
    )
    notes = fields.Text(string="Notas")
    journal_id = fields.Many2one(
        "account.journal", string="Diario de Pago",
        domain="[('type', 'in', ['bank','cash']), ('company_id', '=', company_id)]",
        ondelete="restrict",
    )
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("confirmed", "Confirmado"),
            ("approved", "Aprobado"),
            ("posted", "Publicado"),
            ("cancelled", "Cancelado"),
        ],
        string="Estado", default="draft", required=True, tracking=True,
    )
    move_id = fields.Many2one(
        "account.move", string="Asiento Contable",
        readonly=True, copy=False, ondelete="set null",
    )
    line_ids = fields.One2many(
        "ktx.petty.cash.move", "replenishment_id", string="Gastos a Reembolsar",
    )
    company_id = fields.Many2one(
        "res.company", string="Compañía",
        related="fund_id.company_id", store=True, readonly=True,
    )
    currency_id = fields.Many2one(
        "res.currency", string="Moneda",
        related="fund_id.currency_id", store=True, readonly=True,
    )
    approved_lines_count = fields.Integer(compute="_compute_approved_lines_count")

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name if rec.name != "/" else _("Borrador")

    @api.depends("line_ids.amount")
    def _compute_amount(self):
        for rec in self:
            rec.amount = sum(rec.line_ids.mapped("amount"))

    def _compute_approved_lines_count(self):
        for rec in self:
            rec.approved_lines_count = len(
                rec.fund_id.line_ids.filtered(
                    lambda l: l.state == "approved"
                    and l.move_type == "expense"
                    and not l.replenishment_id
                )
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("ktx.petty.cash.replenishment") or "/"
                )
        return super().create(vals_list)

    def action_confirm(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Solo se pueden confirmar solicitudes en borrador."))
            if not rec.line_ids:
                raise UserError(_("Debe agregar gastos aprobados a la reposición antes de confirmar."))
            rec.state = "confirmed"
            rec._notify_managers(_("Reposición lista para revisión"))

    def action_approve(self):
        for rec in self:
            if rec.state != "confirmed":
                raise UserError(_("Solo se pueden aprobar solicitudes confirmadas."))
            rec.state = "approved"
            rec.message_post(
                body=_("Reposición aprobada por %s.") % self.env.user.name,
                subtype_xmlid="mail.mt_note",
            )
            rec._notify_accountant(_("Reposición aprobada — pendiente de publicar"))

    def action_post(self):
        for rec in self:
            if rec.state != "approved":
                raise UserError(_("Solo se pueden publicar solicitudes aprobadas."))
            if not rec.journal_id:
                raise UserError(_("Debe seleccionar un diario de pago antes de publicar."))
            if not rec.fund_id.account_id:
                raise UserError(_(
                    "El fondo '%s' no tiene una cuenta contable configurada."
                ) % rec.fund_id.name)
            move = rec._create_journal_entry()
            rec.line_ids.filtered(lambda l: l.state == "approved").write({"state": "reimbursed"})
            rec.write({"state": "posted", "move_id": move.id})
            rec.message_post(
                body=_("Reposición publicada. Asiento: <a href='#'>%s</a>") % move.name,
                subtype_xmlid="mail.mt_note",
            )
            rec._notify_custodian(_("Reposición de caja chica realizada"))

    def action_cancel(self):
        for rec in self:
            if rec.state == "posted":
                raise UserError(_("No se puede cancelar una reposición ya publicada."))
            rec.state = "cancelled"
            rec.line_ids.write({"replenishment_id": False})
            rec.message_post(body=_("Solicitud cancelada."), subtype_xmlid="mail.mt_note")

    def action_reset_draft(self):
        for rec in self:
            if rec.state in ("confirmed", "approved", "cancelled"):
                rec.line_ids.write({"replenishment_id": False})
                rec.state = "draft"

    def action_open_move(self):
        self.ensure_one()
        if not self.move_id:
            raise UserError(_("Esta reposición no tiene asiento contable generado."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Asiento Contable"),
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.move_id.id,
        }

    def action_load_approved_expenses(self):
        """Carga automáticamente los gastos aprobados del fondo que aún no tienen reposición."""
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("Solo se pueden cargar gastos en solicitudes en borrador."))
        approved = self.fund_id.line_ids.filtered(
            lambda l: l.state == "approved"
            and l.move_type == "expense"
            and not l.replenishment_id
        )
        if not approved:
            raise UserError(_("No hay gastos aprobados pendientes de reposición en este fondo."))
        approved.write({"replenishment_id": self.id})

    def _create_journal_entry(self):
        self.ensure_one()
        fund = self.fund_id
        company = fund.company_id or self.env.company
        date = self.date or fields.Date.context_today(self)
        journal = self.journal_id

        if not journal.default_account_id:
            raise UserError(_("El diario '%s' no tiene cuenta por defecto configurada.") % journal.name)

        lines = [
            (0, 0, {
                "name": self.name,
                "account_id": fund.account_id.id,
                "debit": self.amount,
                "credit": 0.0,
                "partner_id": fund.custodian_id.id if fund.custodian_id else False,
            }),
            (0, 0, {
                "name": self.name,
                "account_id": journal.default_account_id.id,
                "debit": 0.0,
                "credit": self.amount,
                "partner_id": fund.custodian_id.id if fund.custodian_id else False,
            }),
        ]
        move = self.env["account.move"].create({
            "journal_id": journal.id,
            "date": date,
            "ref": self.name,
            "company_id": company.id,
            "line_ids": lines,
        })
        move.action_post()
        return move

    def _notify_managers(self, subject):
        managers = self.env.ref(
            "ktx_petty_cash.group_petty_cash_manager", raise_if_not_found=False
        )
        if not managers:
            return
        self.message_post(
            body=_(
                "La reposición <b>%s</b> del fondo <b>%s</b> por <b>%s %.2f</b> "
                "requiere revisión."
            ) % (
                self.name, self.fund_id.name,
                self.currency_id.symbol, self.amount,
            ),
            subtype_xmlid="mail.mt_comment",
            partner_ids=managers.users.mapped("partner_id").ids,
        )
        self.activity_schedule(
            "mail.mail_activity_data_todo",
            summary=subject,
            note=_(
                "Reposición <b>%s</b> — Fondo: <b>%s</b> — Monto: <b>%s %.2f</b>."
            ) % (self.name, self.fund_id.name, self.currency_id.symbol, self.amount),
            user_id=self.env.uid,
        )

    def _notify_accountant(self, subject):
        self.activity_schedule(
            "mail.mail_activity_data_todo",
            summary=subject,
            note=_(
                "La reposición <b>%s</b> ha sido aprobada y está lista para publicarse. "
                "Fondo: <b>%s</b> — Monto: <b>%s %.2f</b>."
            ) % (self.name, self.fund_id.name, self.currency_id.symbol, self.amount),
            user_id=self.env.uid,
        )

    def _notify_custodian(self, subject):
        if not self.fund_id.custodian_id or not self.fund_id.custodian_id.user_ids:
            return
        user = self.fund_id.custodian_id.user_ids[0]
        self.activity_schedule(
            "mail.mail_activity_data_todo",
            summary=subject,
            note=_(
                "La reposición <b>%s</b> fue publicada. Tu fondo <b>%s</b> "
                "ha sido repuesto por <b>%s %.2f</b>. Saldo actual: <b>%s %.2f</b>."
            ) % (
                self.name, self.fund_id.name,
                self.currency_id.symbol, self.amount,
                self.currency_id.symbol, self.fund_id.current_balance,
            ),
            user_id=user.id,
        )
