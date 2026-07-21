# -*- coding: utf-8 -*-
from markupsafe import Markup
from odoo import models, _


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_add_to_petty_cash_staging(self):
        added = []
        already = []
        skipped = []
        for record in self:
            if record.state != "posted":
                skipped.append(record.name)
                continue
            if record.payment_state == "paid":
                skipped.append(record.name)
                continue
            if record.move_type not in ("in_invoice", "in_receipt", "entry"):
                skipped.append(record.name)
                continue
            existing = self.env["ktx.petty.cash.staging"].search(
                [("move_id", "=", record.id)], limit=1
            )
            if existing:
                already.append(record.name)
                continue
            staging = self.env["ktx.petty.cash.staging"].create({"move_id": record.id})
            staging.message_post(
                body=Markup("Agregado a <b>Gastos por Reembolsar</b> por %s.") % self.env.user.name,
                subtype_xmlid="mail.mt_comment",
            )
            record.message_post(
                body=Markup("Agregado a <b>Gastos por Reembolsar (Caja Chica)</b> por %s.") % self.env.user.name,
                subtype_xmlid="mail.mt_comment",
            )
            added.append(record.name)

        parts = []
        if added:
            parts.append(_("Agregado a Gastos por Reembolsar: %s.") % ", ".join(added))
        if already:
            parts.append(_("Ya existía(n) en Gastos por Reembolsar: %s.") % ", ".join(already))
        if skipped:
            parts.append(_("Omitido(s) (pagados/no publicados/tipo no soportado): %s.") % ", ".join(skipped))

        msg = " ".join(parts) or _("Sin cambios.")
        notif_type = "success" if added else ("warning" if already else "danger")

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Pagar con Caja Chica"),
                "message": msg,
                "type": notif_type,
                "sticky": False,
            },
        }
