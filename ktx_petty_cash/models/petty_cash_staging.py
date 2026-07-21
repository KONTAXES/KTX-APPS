# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class KtxPettyCashStaging(models.Model):
    _name = "ktx.petty.cash.staging"
    _description = "Gasto por Reembolsar (Caja Chica)"
    _inherit = ["mail.thread"]
    _order = "invoice_date desc, id desc"

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, **kwargs):
        if not self.env.su:
            multi = self.env['ir.config_parameter'].sudo().get_param(
                'ktx_petty_cash.multi_company', 'False'
            )
            if multi not in ('True', '1', 'true'):
                domain = [('company_id', 'in', self.env.companies.ids)] + list(domain)
        return super()._search(domain, offset=offset, limit=limit, order=order, **kwargs)

    move_id = fields.Many2one("account.move", string="Factura / Documento", required=True, ondelete="restrict", index=True)
    partner_id = fields.Many2one("res.partner", related="move_id.partner_id", string="Proveedor", store=True, readonly=True)
    invoice_date = fields.Date(related="move_id.invoice_date", store=True, readonly=True, string="Fecha Factura")
    move_name = fields.Char(related="move_id.name", store=True, readonly=True, string="Número")
    ref = fields.Char(related="move_id.ref", store=True, readonly=True, string="Referencia")
    currency_id = fields.Many2one(related="move_id.currency_id", store=True, readonly=True)
    amount_total = fields.Monetary(related="move_id.amount_total", store=True, readonly=True, string="Total Documento", currency_field="currency_id")
    amount_pending = fields.Monetary(string="Monto Pendiente", compute="_compute_amount_pending", store=True, currency_field="currency_id")
    state = fields.Selection([("pending", "Pendiente"), ("assigned", "Asignado")], default="pending", string="Estado", required=True, tracking=True)
    petty_cash_move_id = fields.Many2one("ktx.petty.cash.move", string="Movimiento Caja Chica", readonly=True, copy=False, ondelete="set null")
    notes = fields.Char(string="Notas / Referencia")
    company_id = fields.Many2one(related="move_id.company_id", store=True, readonly=True)
    move_type_rel = fields.Selection(related="move_id.move_type", string="Tipo Doc.", store=True, readonly=True)

    _unique_move_id = models.Constraint(
        "UNIQUE(move_id)",
        "Esta factura o asiento ya está registrado en Gastos por Reembolsar.",
    )

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.move_name or rec.ref or _("Gasto #%d") % rec.id

    @api.depends("move_id.amount_residual", "move_id.line_ids.amount_residual")
    def _compute_amount_pending(self):
        for rec in self:
            if not rec.move_id:
                rec.amount_pending = 0.0
                continue
            residual = abs(rec.move_id.amount_residual)
            if residual:
                rec.amount_pending = residual
            else:
                # Journal entries: sum unreconciled reconcilable lines
                unreconciled = rec.move_id.line_ids.filtered(
                    lambda l: l.account_id.reconcile and not l.reconciled
                )
                rec.amount_pending = abs(sum(unreconciled.mapped("amount_residual"))) if unreconciled else 0.0

    @api.constrains("move_id")
    def _check_move_valid(self):
        for rec in self:
            if rec.move_id and rec.move_id.payment_state == "paid":
                raise UserError(_("La factura '%s' ya está pagada completamente.") % rec.move_id.name)
            if rec.move_id and rec.move_id.state != "posted":
                raise UserError(_("Solo se pueden agregar documentos publicados/confirmados."))

    def action_open_source_move(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "res_model": "account.move", "view_mode": "form", "res_id": self.move_id.id}

    def action_open_petty_cash_move(self):
        self.ensure_one()
        if not self.petty_cash_move_id:
            raise UserError(_("No hay movimiento de caja chica asignado."))
        return {"type": "ir.actions.act_window", "res_model": "ktx.petty.cash.move", "view_mode": "form", "res_id": self.petty_cash_move_id.id}

    def action_assign_petty_cash(self):
        pending = self.filtered(lambda s: s.state == "pending")
        if not pending:
            raise UserError(_("Todos los gastos seleccionados ya están asignados."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Asignar a Caja Chica"),
            "res_model": "ktx.petty.cash.assign.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_staging_ids": pending.ids},
        }
