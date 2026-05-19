# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

VENDOR_BILL_TYPE = "in_invoice"
JOURNAL_ENTRY_TYPE = "entry"


def _journal_entries_allowed(env):
    val = env["ir.config_parameter"].sudo().get_param(
        "ktx_expense_management.allow_journal_entries", "False"
    )
    return val in ("True", "1", "true")


class AccountMove(models.Model):
    _inherit = "account.move"

    ktx_staging_id = fields.Many2one(
        comodel_name="ktx.settlement.staging",
        string="Staging Liquidación",
        compute="_compute_ktx_staging_id",
        store=False,
    )
    ktx_in_settlement = fields.Boolean(
        string="En Liquidación",
        compute="_compute_ktx_staging_id",
        store=False,
    )

    @api.depends("move_type", "state")
    def _compute_ktx_staging_id(self):
        staging_map = {}
        if self.ids:
            stagings = self.env["ktx.settlement.staging"].search(
                [("move_id", "in", self.ids)]
            )
            staging_map = {s.move_id.id: s for s in stagings}
        for rec in self:
            staging = staging_map.get(rec.id)
            rec.ktx_staging_id = staging.id if staging else False
            rec.ktx_in_settlement = bool(staging)

    def action_post(self):
        """Auto-add to staging when confirmed from the staging context."""
        res = super().action_post()
        # If bill was created from the staging module (context flag), auto-add to staging
        if self._context.get("ktx_auto_staging"):
            allow_entries = _journal_entries_allowed(self.env)
            for move in self.filtered(lambda m: m.state == "posted"):
                if move.move_type not in ("in_invoice", "in_receipt"):
                    continue
                existing = self.env["ktx.settlement.staging"].search(
                    [("move_id", "=", move.id)], limit=1
                )
                if not existing:
                    self.env["ktx.settlement.staging"].create({"move_id": move.id})
        return res

    def action_add_to_settlement(self):
        """Agrega facturas de proveedor publicadas o asientos publicados al staging."""
        allow_entries = _journal_entries_allowed(self.env)

        # Check journal entry restriction before filtering
        entry_moves = self.filtered(lambda m: m.move_type == JOURNAL_ENTRY_TYPE and m.state == "posted")
        if entry_moves and not allow_entries:
            raise UserError(
                _(
                    "La opción 'Incluir Asientos Contables en Liquidaciones' no está activada.\n"
                    "Actívela en Liquidaciones → Configuración para poder agregar asientos contables."
                )
            )

        allowed_types = (VENDOR_BILL_TYPE, JOURNAL_ENTRY_TYPE) if allow_entries else (VENDOR_BILL_TYPE,)
        eligible = self.filtered(
            lambda m: m.move_type in allowed_types and m.state == "posted"
        )
        if not eligible:
            raise UserError(
                _(
                    "Solo se pueden agregar facturas de proveedor publicadas "
                    "a una liquidación. Active 'Incluir Asientos Contables' en "
                    "Configuración para también permitir asientos contables."
                )
            )

        added = 0
        already_exists = []

        for move in eligible:
            existing = self.env["ktx.settlement.staging"].search(
                [("move_id", "=", move.id)], limit=1
            )
            if existing:
                already_exists.append(move.name or move.ref or str(move.id))
                continue
            try:
                self.env["ktx.settlement.staging"].create({"move_id": move.id})
                added += 1
            except Exception:
                self.env.cr.rollback()
                already_exists.append(move.name or move.ref or str(move.id))

        if already_exists and not added:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Documento duplicado"),
                    "message": _(
                        "El/los siguiente(s) documento(s) ya fueron agregados: %s"
                    ) % ", ".join(already_exists),
                    "type": "danger",
                    "sticky": False,
                },
            }

        if already_exists and added:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Resultado parcial"),
                    "message": _(
                        "%d documento(s) agregados correctamente. "
                        "Los siguientes ya existían: %s"
                    ) % (added, ", ".join(already_exists)),
                    "type": "warning",
                    "sticky": False,
                },
            }

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Éxito"),
                "message": _("Documentos agregados correctamente a Gastos por Liquidar."),
                "type": "success",
                "sticky": False,
            },
        }

    def unlink(self):
        if not self.env.context.get("_skip_ktx_settlement_unlink"):
            # Bloquear eliminación si la liquidación ya está pagada
            paid = self.env["ktx.settlement"].search([
                ("move_id", "in", self.ids),
                ("state", "=", "paid"),
            ])
            if paid:
                names = ", ".join(paid.mapped("name"))
                raise UserError(
                    _("No se puede eliminar el asiento porque está vinculado a la liquidación "
                      "PAGADA: %s.\nCancele el pago primero desde la liquidación.") % names
                )
            # Si está publicada (sin pago), revertir a aprobado automáticamente
            posted = self.env["ktx.settlement"].search([
                ("move_id", "in", self.ids),
                ("state", "=", "posted"),
            ])
            for settlement in posted:
                settlement.line_ids.staging_id.write({"state": "pending"})
                settlement.write({"state": "approved", "move_id": False})
        return super().unlink()


class AccountPartialReconcile(models.Model):
    _inherit = "account.partial.reconcile"

    def _prepare_exchange_difference_move_vals(self, amounts_list, company, exchange_date, **kwargs):
        """Use settlement rate_date (from context) or invoice date for forex differential entries."""
        # Settlement reconciliation passes the desired date via context
        settlement_date = self.env.context.get("ktx_settlement_date")
        if settlement_date:
            return super()._prepare_exchange_difference_move_vals(
                amounts_list, company, settlement_date, **kwargs
            )
        # Fallback: use invoice date from either reconciled move line
        invoice_date = None
        for partial in self:
            for ml in (partial.debit_move_id, partial.credit_move_id):
                if ml and ml.move_id.invoice_date:
                    invoice_date = ml.move_id.invoice_date
                    break
            if invoice_date:
                break
        return super()._prepare_exchange_difference_move_vals(
            amounts_list, company, invoice_date or exchange_date, **kwargs
        )


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def reconcile(self):
        result = super().reconcile()
        payment_ids = self.mapped("payment_id").ids
        if payment_ids:
            settlements = self.env["ktx.settlement"].search([
                ("payment_ids", "in", payment_ids),
                ("state", "=", "in_payment"),
            ])
            for settlement in settlements:
                if all(p.is_reconciled for p in settlement.payment_ids):
                    settlement.write({"state": "paid"})
        return result


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def write(self, vals):
        result = super().write(vals)
        if vals.get("is_reconciled"):
            settlements = self.env["ktx.settlement"].search([
                ("payment_ids", "in", self.ids),
                ("state", "=", "in_payment"),
            ])
            for settlement in settlements:
                if all(p.is_reconciled for p in settlement.payment_ids):
                    settlement.write({"state": "paid"})
        return result

    def unlink(self):
        if not self.env.context.get("_skip_ktx_settlement_unlink"):
            settlements = self.env["ktx.settlement"].search([
                ("payment_ids", "in", self.ids),
                ("state", "in", ["paid", "in_payment"]),
            ])
            for settlement in settlements:
                remaining = settlement.payment_ids - self
                settlement.write({"payment_ids": [(3, pid) for pid in self.ids if pid in settlement.payment_ids.ids]})
                if not remaining:
                    settlement.write({"state": "posted"})
        return super().unlink()
