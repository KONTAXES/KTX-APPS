# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ClaudeRequestLog(models.Model):
    """Unified audit trail of every tool Claude executes.

    Written for actions originating from the in-Odoo chat and (phase 2) from
    the remote connector, so the activity history is unified regardless of the
    surface used.
    """

    _name = "claude.request.log"
    _description = "Bitácora de Claude AI"
    _order = "create_date desc"
    _rec_name = "tool_name"

    user_id = fields.Many2one(
        "res.users", string="Usuario", index=True, ondelete="set null"
    )
    source = fields.Selection(
        [("odoo_chat", "Chat en Odoo"), ("connector", "Conector remoto")],
        string="Origen",
        default="odoo_chat",
        index=True,
    )
    tool_name = fields.Char(string="Herramienta", index=True)
    model_name = fields.Char(string="Modelo de Odoo", index=True)
    operation = fields.Char(string="Operación")
    record_ids = fields.Char(string="IDs afectados")
    success = fields.Boolean(string="Éxito", default=True)
    error_message = fields.Text(string="Mensaje de error")
    duration_ms = fields.Integer(string="Duración (ms)")
    input_tokens = fields.Integer(string="Tokens de entrada")
    output_tokens = fields.Integer(string="Tokens de salida")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("user_id", self.env.uid)
        return super().create(vals_list)
