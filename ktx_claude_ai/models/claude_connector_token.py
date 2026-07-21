# -*- coding: utf-8 -*-
import secrets

from odoo import _, api, fields, models

from .claude_oauth import sha256


class ClaudeConnectorToken(models.Model):
    """Static bearer token for the remote connector.

    Simpler alternative to OAuth, for Claude Desktop or the Anthropic Messages
    API ``mcp_servers`` parameter (where Dynamic Client Registration / OAuth is
    not used). The token is generated once, shown once, and stored hashed.
    Actions run with this token execute as ``user_id``.
    """

    _name = "claude.connector.token"
    _description = "Token estático del conector de Claude"
    _order = "create_date desc"

    name = fields.Char(required=True)
    token_hash = fields.Char(index=True, copy=False, readonly=True)
    token_preview = fields.Char(string="Token (vista previa)", readonly=True)
    user_id = fields.Many2one(
        "res.users", string="Ejecutar como", required=True,
        default=lambda s: s.env.user, ondelete="cascade",
        help="Las acciones realizadas con este token usan los permisos de este usuario.",
    )
    active = fields.Boolean(default=True)
    expiry_date = fields.Datetime(string="Caduca el", help="Vacío = no caduca.")
    last_used = fields.Datetime(readonly=True)
    request_count = fields.Integer(default=0, readonly=True)

    @api.model
    def _mint(self, name, user_id=None):
        """Create a token and return (record, plaintext_token)."""
        raw = "ckx_" + secrets.token_urlsafe(32)
        rec = self.create({
            "name": name,
            "user_id": user_id or self.env.uid,
            "token_hash": sha256(raw),
            "token_preview": "…" + raw[-6:],
        })
        return rec, raw

    def action_generate(self):
        """(Re)generate the secret for this token and show it once."""
        self.ensure_one()
        raw = "ckx_" + secrets.token_urlsafe(32)
        self.write({"token_hash": sha256(raw), "token_preview": "…" + raw[-6:]})
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Token generado"),
                "message": _("Cópialo ahora; no se volverá a mostrar:\n\n%s") % raw,
                "type": "warning",
                "sticky": True,
            },
        }

    @api.model
    def find_valid_token(self, raw):
        """Return the res.users for a valid static token, else None."""
        if not raw:
            return None
        rec = self.sudo().search(
            [("token_hash", "=", sha256(raw)), ("active", "=", True)], limit=1
        )
        if not rec:
            return None
        if rec.expiry_date and rec.expiry_date < fields.Datetime.now():
            return None
        rec.write({
            "last_used": fields.Datetime.now(),
            "request_count": rec.request_count + 1,
        })
        user = rec.user_id
        return user if (user and user.active) else None
