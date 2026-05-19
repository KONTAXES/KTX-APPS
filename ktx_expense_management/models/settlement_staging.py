# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class SettlementStaging(models.Model):
    _name = "ktx.settlement.staging"
    _description = "Gasto por Liquidar"
    _order = "invoice_date desc, id desc"
    _rec_name = "move_id"
    _check_company_auto = True

    move_id = fields.Many2one(
        comodel_name="account.move",
        string="Factura / Asiento",
        ondelete="restrict",
        index=True,
    )
    move_type = fields.Selection(
        string="Tipo",
        related="move_id.move_type",
        store=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Proveedor / Contacto",
        related="move_id.partner_id",
        store=True,
        readonly=True,
    )
    invoice_date = fields.Date(
        string="Fecha",
        related="move_id.invoice_date",
        store=True,
        readonly=True,
    )
    ref = fields.Char(
        string="Referencia / Serie",
        related="move_id.ref",
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Moneda",
        related="move_id.currency_id",
        store=True,
        readonly=True,
    )
    amount_total = fields.Monetary(
        string="Total",
        related="move_id.amount_total",
        currency_field="currency_id",
        store=True,
        readonly=True,
    )
    amount_residual = fields.Monetary(
        string="Pendiente de Pago",
        related="move_id.amount_residual",
        currency_field="currency_id",
        store=True,
        readonly=True,
    )
    move_state = fields.Selection(
        string="Estado Documento",
        related="move_id.state",
        store=True,
        readonly=True,
    )
    state = fields.Selection(
        selection=[
            ("pending", "Pendiente"),
            ("in_settlement", "En Liquidación"),
            ("done", "Liquidado"),
        ],
        string="Estado",
        default="pending",
        required=True,
        tracking=True,
        index=True,
    )
    state_color = fields.Integer(compute="_compute_state_color")
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Compañía",
        related="move_id.company_id",
        store=True,
        readonly=True,
    )

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, **kwargs):
        """Apply company filter unless multi-company staging is enabled."""
        if not self.env.su:
            multi = self.env["ir.config_parameter"].sudo().get_param(
                "ktx_expense_management.multi_company_staging", "False"
            )
            if multi not in ("True", "1", "true"):
                domain = [("company_id", "in", self.env.companies.ids)] + list(domain)
        return super()._search(domain, offset=offset, limit=limit, order=order, **kwargs)

    @api.constrains("move_id")
    def _check_unique_move_id(self):
        for rec in self:
            if not rec.move_id:
                continue
            duplicate = self.search([
                ("move_id", "=", rec.move_id.id),
                ("id", "!=", rec.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    _("Este documento ya fue agregado al staging de liquidaciones.")
                )

    @api.depends("state")
    def _compute_state_color(self):
        _map = {"pending": 3, "in_settlement": 1, "done": 10}
        for rec in self:
            rec.state_color = _map.get(rec.state, 0)

    def unlink(self):
        for rec in self:
            if not rec.move_id:
                continue
            if rec.state == "in_settlement":
                raise UserError(
                    _("No se puede eliminar «%s» porque está incluido en una liquidación activa. "
                      "Elimine la línea desde la liquidación primero.")
                    % (rec.move_id.name or rec.ref or "")
                )
            if rec.state == "done":
                raise UserError(
                    _("No se puede eliminar «%s» porque ya fue liquidado y pagado.")
                    % (rec.move_id.name or rec.ref or "")
                )
        return super().unlink()

    @api.depends("move_id.name", "move_id.ref", "partner_id.name")
    def _compute_display_name(self):
        for rec in self:
            if rec.move_id:
                name = rec.move_id.name or rec.move_id.ref or _("Sin nombre")
                if rec.partner_id:
                    name = f"{name} - {rec.partner_id.name}"
            else:
                name = _("Nuevo Gasto")
            rec.display_name = name

    def action_create_settlement(self):
        """Crea una nueva liquidación con los gastos seleccionados (solo pendientes)."""
        eligible = self.filtered(lambda r: r.state == "pending")
        if not eligible:
            raise UserError(
                _("Seleccione al menos un gasto en estado 'Pendiente' para crear una liquidación.")
            )

        # Detectar si hay registros ya en uso activo para advertir al usuario
        already_used = self - eligible
        if already_used:
            _logger.warning(
                "Se omitieron %d gasto(s) ya en uso: %s",
                len(already_used),
                ", ".join(already_used.mapped("move_id.name")),
            )

        # Validar que todos los gastos sean de la misma empresa (solo si multi-empresa está desactivado)
        multi = self.env["ir.config_parameter"].sudo().get_param(
            "ktx_expense_management.multi_company_staging", "False"
        )
        companies = eligible.mapped("company_id")
        if multi not in ("True", "1", "true") and len(companies) > 1:
            raise UserError(
                _("Los gastos seleccionados pertenecen a diferentes empresas (%s). "
                  "Seleccione gastos de una sola empresa.")
                % ", ".join(companies.mapped("name"))
            )

        # Crear la liquidación en borrador (usando la empresa del staging)
        settlement = self.env["ktx.settlement"].create({
            "date": fields.Date.context_today(self),
            "company_id": companies[0].id if companies else self.env.company.id,
        })

        # Crear las líneas usando el saldo pendiente de la factura
        for staging in eligible:
            residual = staging.move_id.amount_residual if staging.move_id else 0.0
            self.env["ktx.settlement.line"].create({
                "settlement_id": settlement.id,
                "staging_id": staging.id,
                "amount_to_pay": residual if residual > 0 else staging.amount_total,
            })

        return {
            "type": "ir.actions.act_window",
            "res_model": "ktx.settlement",
            "view_mode": "form",
            "res_id": settlement.id,
            "target": "current",
        }

    def action_create_vendor_receipt(self):
        """Abre un nuevo recibo/factura de proveedor para agregar al staging."""
        # Remove empty shell records created by clicking "New" without a move
        empty = self.filtered(lambda r: not r.move_id)
        if empty:
            empty.sudo().unlink()
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_move_type": "in_invoice",
                "default_invoice_date": fields.Date.context_today(self),
                "ktx_auto_staging": True,
            },
        }
