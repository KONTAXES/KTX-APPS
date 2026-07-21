# -*- coding: utf-8 -*-
from odoo import fields, models


class ClaudeMessage(models.Model):
    """A single rendered item in a Claude conversation (for display & audit).

    The verbatim Anthropic message array used for API replay lives on
    ``claude.conversation.raw_messages``; these records are the human-facing
    view of the exchange.
    """

    _name = "claude.message"
    _description = "Mensaje de Claude"
    _order = "id"

    conversation_id = fields.Many2one(
        "claude.conversation",
        string="Conversación",
        required=True,
        ondelete="cascade",
        index=True,
    )
    role = fields.Selection(
        [
            ("user", "Usuario"),
            ("assistant", "Claude"),
            ("thinking", "Razonamiento"),
            ("tool", "Herramienta"),
            ("error", "Error"),
        ],
        string="Rol",
        required=True,
    )
    body = fields.Text(string="Contenido")
    tool_name = fields.Char(string="Herramienta")
    tool_input = fields.Text(string="Entrada de la herramienta")
    tool_result = fields.Text(string="Resultado de la herramienta")
    tool_success = fields.Boolean(string="Herramienta exitosa", default=True)

    def _to_frontend(self):
        self.ensure_one()
        return {
            "id": self.id,
            "role": self.role,
            "body": self.body or "",
            "tool_name": self.tool_name or "",
            "tool_input": self.tool_input or "",
            "tool_result": self.tool_result or "",
            "tool_success": self.tool_success,
        }
