# -*- coding: utf-8 -*-
from odoo import _, fields, models


class ClaudeModelSelectionWizard(models.TransientModel):
    """Quickly enable several Odoo models for Claude in one step."""

    _name = "claude.model.selection.wizard"
    _description = "Habilitar modelos para Claude"

    model_ids = fields.Many2many(
        "ir.model",
        string="Modelos a habilitar",
        help="Se crearán como modelos habilitados (solo lectura por defecto).",
    )
    allow_read = fields.Boolean(string="Lectura", default=True)
    allow_create = fields.Boolean(string="Creación", default=False)
    allow_write = fields.Boolean(string="Modificación", default=False)
    allow_unlink = fields.Boolean(string="Eliminación", default=False)
    allow_action = fields.Boolean(string="Acciones de estado", default=False)

    def action_enable(self):
        self.ensure_one()
        Enabled = self.env["claude.enabled.model"]
        created = 0
        for model in self.model_ids:
            if Enabled.search_count([("model_id", "=", model.id)]):
                continue
            Enabled.create({
                "model_id": model.id,
                "allow_read": self.allow_read,
                "allow_create": self.allow_create,
                "allow_write": self.allow_write,
                "allow_unlink": self.allow_unlink,
                "allow_action": self.allow_action,
            })
            created += 1
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Modelos habilitados"),
                "message": _("Se habilitaron %s modelo(s) para Claude.") % created,
                "type": "success",
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
