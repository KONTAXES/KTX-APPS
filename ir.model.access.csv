# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SettlementLine(models.Model):
    _name = "ktx.settlement.line"
    _description = "Línea de Liquidación"
    _order = "sequence, id"

    settlement_id = fields.Many2one(
        comodel_name="ktx.settlement",
        string="Liquidación",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(
        string="Secuencia",
        default=10,
    )
    staging_id = fields.Many2one(
        comodel_name="ktx.settlement.staging",
        string="Gasto por Liquidar",
        ondelete="restrict",
    )
    move_id = fields.Many2one(
        comodel_name="account.move",
        string="Factura / Asiento",
        related="staging_id.move_id",
        store=True,
        readonly=True,
    )
    move_name = fields.Char(
        string="Número Póliza",
        related="staging_id.move_id.name",
        store=True,
        readonly=True,
    )
    ref = fields.Char(
        string="Referencia / Serie",
        related="staging_id.move_id.ref",
        store=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Proveedor / Contacto",
        related="staging_id.partner_id",
        store=True,
        readonly=True,
    )
    move_company_id = fields.Many2one(
        comodel_name="res.company",
        string="Empresa del Gasto",
        related="staging_id.move_id.company_id",
        store=True,
        readonly=True,
    )
    invoice_date = fields.Date(
        string="Fecha",
        related="staging_id.invoice_date",
        store=True,
        readonly=True,
    )
    # Moneda original de la factura/asiento
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Moneda Documento",
        related="staging_id.currency_id",
        store=True,
        readonly=True,
    )
    amount_invoice = fields.Monetary(
        string="Total Documento",
        related="staging_id.amount_total",
        currency_field="currency_id",
        store=True,
        readonly=True,
    )
    # Monto editable a liquidar (en moneda del documento)
    amount_to_pay = fields.Monetary(
        string="Monto a Liquidar",
        currency_field="currency_id",
        required=True,
    )
    # Moneda de la liquidación (para conversión)
    settlement_currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Moneda Liquidación",
        related="settlement_id.currency_id",
        store=True,
        readonly=True,
    )
    # Monto convertido a la moneda de la liquidación
    amount_in_settlement_currency = fields.Monetary(
        string="Monto Convertido",
        compute="_compute_amount_in_settlement_currency",
        currency_field="settlement_currency_id",
        store=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Compañía",
        related="settlement_id.company_id",
        store=True,
        readonly=True,
    )
    analytic_account_id = fields.Many2one(
        comodel_name="account.analytic.account",
        string="Centro de Costo",
        ondelete="set null",
    )

    @api.onchange("staging_id")
    def _onchange_staging_id(self):
        if self.staging_id:
            residual = self.staging_id.move_id.amount_residual if self.staging_id.move_id else 0.0
            self.amount_to_pay = residual if residual > 0 else self.staging_id.amount_total

    @api.depends("amount_to_pay", "currency_id", "settlement_currency_id", "settlement_id.exchange_rate", "settlement_id.rate_date", "settlement_id.date")
    def _compute_amount_in_settlement_currency(self):
        for line in self:
            line_cur = line.currency_id
            settlement_cur = line.settlement_currency_id
            if not line_cur or not settlement_cur or line_cur == settlement_cur:
                line.amount_in_settlement_currency = line.amount_to_pay
                continue
            company = line.settlement_id.company_id or self.env.company
            company_cur = company.currency_id
            ref_date = line.settlement_id.rate_date or line.settlement_id.date or fields.Date.context_today(self)
            rate = line.settlement_id.exchange_rate or 1.0

            if line_cur == company_cur and settlement_cur != company_cur:
                # Line in company currency, settlement in foreign: multiply by rate
                line.amount_in_settlement_currency = line.amount_to_pay * rate
            elif settlement_cur == company_cur and line_cur != company_cur:
                # Line in foreign currency, settlement in company currency:
                # use Odoo's rate tables for the line's currency (ignore settlement's exchange_rate=1)
                line.amount_in_settlement_currency = line_cur._convert(
                    line.amount_to_pay, settlement_cur, company, ref_date
                )
            else:
                # Both differ from company currency: convert via Odoo's rate engine
                line.amount_in_settlement_currency = line_cur._convert(
                    line.amount_to_pay, settlement_cur, company, ref_date
                )

    @api.constrains("staging_id", "settlement_id")
    def _check_unique_staging_per_settlement(self):
        for line in self:
            domain = [
                ("staging_id", "=", line.staging_id.id),
                ("settlement_id", "!=", line.settlement_id.id),
                ("settlement_id.state", "not in", ["rejected", "cancelled"]),
            ]
            duplicate = self.search(domain, limit=1)
            if duplicate:
                raise ValidationError(
                    _(
                        "El documento '%s' ya está siendo utilizado en otra liquidación activa."
                    )
                    % line.staging_id.move_id.name
                )

    def unlink(self):
        settlements = self.mapped("settlement_id")
        res = super().unlink()
        settlements.invalidate_recordset(["line_ids"])
        settlements._sync_intercompany_accounts()
        return res
