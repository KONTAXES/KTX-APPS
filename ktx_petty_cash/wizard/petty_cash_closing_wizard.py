# -*- coding: utf-8 -*-
import base64
import calendar
from datetime import date, timedelta
from markupsafe import Markup
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class KtxPettyCashClosingWizard(models.TransientModel):
    _name = "ktx.petty.cash.closing.wizard"
    _description = "Cierre de Caja Chica"

    fund_id = fields.Many2one(
        "ktx.petty.cash.fund", string="Fondo", required=True, ondelete="cascade",
    )
    closing_date = fields.Date(
        string="Fecha de Cierre", required=True,
        default=fields.Date.context_today,
    )
    new_fund_name = fields.Char(
        string="Nombre del Nuevo Fondo",
        help="Nombre para el nuevo fondo que se abrirá con el saldo final.",
    )
    new_fund_date_start = fields.Date(
        string="Fecha Inicio Nuevo Fondo",
        default=lambda self: fields.Date.today() + timedelta(days=1),
    )
    closing_balance = fields.Monetary(
        string="Saldo Final", related="fund_id.current_balance",
        currency_field="currency_id", readonly=True,
    )
    notes = fields.Text(string="Notas del Cierre")
    move_count = fields.Integer(string="Movimientos Abiertos", compute="_compute_move_count")
    total_amount = fields.Monetary(
        string="Total Gastos del Período", compute="_compute_move_count",
        currency_field="currency_id",
    )
    currency_id = fields.Many2one("res.currency", related="fund_id.currency_id", readonly=True)

    @api.depends("fund_id")
    def _compute_move_count(self):
        for rec in self:
            moves = rec._get_open_moves()
            rec.move_count = len(moves)
            rec.total_amount = sum(
                m.amount for m in moves if m.move_type in ("expense", "manual_expense")
            )

    @api.onchange("fund_id")
    def _onchange_fund_id(self):
        if self.fund_id:
            self.new_fund_name = self.fund_id.name

    def _get_open_moves(self):
        if not self.fund_id:
            return self.env["ktx.petty.cash.move"]
        return self.env["ktx.petty.cash.move"].search([
            ("fund_id", "=", self.fund_id.id),
            ("state", "in", ("approved", "reimbursed")),
            ("period_closed", "=", False),
        ])

    def action_close_fund(self):
        self.ensure_one()
        fund = self.fund_id
        if fund.state == "closed":
            raise UserError(_("El fondo ya está cerrado."))
        if fund.line_ids.filtered(lambda l: l.state == "draft"):
            raise UserError(_(
                "No se puede cerrar el fondo '%s' mientras tenga gastos pendientes de aprobación."
            ) % fund.name)

        moves = self._get_open_moves()
        moves.write({"period_closed": True})

        sym = fund.currency_id.symbol or ""
        closing_balance = fund.current_balance

        # Build chatter message
        items = Markup("")
        for m in moves:
            tipo = dict(self.env["ktx.petty.cash.move"]._fields["move_type"].selection).get(m.move_type, m.move_type)
            items += Markup("<li>%s — %s: <b>%s %.2f</b>%s</li>") % (
                m.date, tipo, sym, m.amount,
                Markup(" — %s") % m.name if m.name else Markup(""),
            )
        note_html = Markup("<p><b>Notas:</b> %s</p>") % self.notes if self.notes else Markup("")

        # Close current fund
        fund.state = "closed"
        fund.date_end = self.closing_date

        # Generate and attach PDF state report
        attachment_ids = []
        try:
            report = self.env.ref(
                "ktx_petty_cash.action_report_ktx_petty_cash_fund_state",
                raise_if_not_found=False,
            )
            if report:
                pdf_content, _mime = report._render_qweb_pdf(fund.ids)
                att = self.env["ir.attachment"].create({
                    "name": "Cierre_%s.pdf" % (fund.name or fund.id),
                    "type": "binary",
                    "datas": base64.b64encode(pdf_content),
                    "res_model": fund._name,
                    "res_id": fund.id,
                    "mimetype": "application/pdf",
                })
                attachment_ids = [att.id]
        except Exception:
            pass

        fund.message_post(
            body=Markup(
                "<p><b>Caja cerrada por %s</b> el %s</p>"
                "<p>Saldo final: <b>%s %.2f</b> | Movimientos cerrados: <b>%d</b> | Total gastos: <b>%s %.2f</b></p>"
                "%s%s"
            ) % (
                self.env.user.name,
                self.closing_date,
                sym, closing_balance,
                len(moves),
                sym, self.total_amount,
                Markup("<ul>%s</ul>") % items if items else Markup(""),
                note_html,
            ),
            attachment_ids=attachment_ids,
            subtype_xmlid="mail.mt_note",
            author_id=self.env.user.partner_id.id,
        )

        # Create new fund with closing balance as initial amount
        new_name = self.new_fund_name or fund.name
        new_fund = self.env["ktx.petty.cash.fund"].create({
            "name": new_name,
            "custodian_id": fund.custodian_id.id if fund.custodian_id else False,
            "authorizer_id": fund.authorizer_id.id if fund.authorizer_id else False,
            "company_id": fund.company_id.id,
            "currency_id": fund.currency_id.id,
            "initial_amount": closing_balance,
            "min_balance": fund.min_balance,
            "journal_id": fund.journal_id.id if fund.journal_id else False,
            "account_id": fund.account_id.id if fund.account_id else False,
            "chart_type": fund.chart_type,
            "date_start": self.new_fund_date_start or (self.closing_date + timedelta(days=1)),
            "state": "open",
        })
        new_fund.message_post(
            body=Markup(
                "<p>Fondo creado a partir del cierre de <b>%s</b>.</p>"
                "<p>Saldo inicial: <b>%s %.2f</b></p>"
            ) % (fund.name, sym, closing_balance),
            subtype_xmlid="mail.mt_note",
        )

        return {
            "type": "ir.actions.act_window",
            "name": _("Nuevo Fondo — %s") % new_name,
            "res_model": "ktx.petty.cash.fund",
            "view_mode": "form",
            "res_id": new_fund.id,
        }
