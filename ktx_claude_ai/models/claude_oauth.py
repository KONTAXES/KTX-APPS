# -*- coding: utf-8 -*-
import hashlib
import json
import secrets
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


def sha256(raw):
    return hashlib.sha256((raw or "").encode()).hexdigest()


class ClaudeOauthClient(models.Model):
    """OAuth 2.0 client registered dynamically by Claude (RFC 7591)."""

    _name = "claude.oauth.client"
    _description = "Cliente OAuth de Claude"
    _order = "create_date desc"
    _rec_name = "client_name"

    client_id = fields.Char(required=True, index=True, copy=False)
    client_secret = fields.Char(copy=False, help="Hash; solo para clientes confidenciales.")
    client_name = fields.Char()
    redirect_uris = fields.Text(help="Lista JSON de redirect_uris.")
    grant_types = fields.Char(default="authorization_code,refresh_token")
    response_types = fields.Char(default="code")
    token_endpoint_auth_method = fields.Char(default="none")
    scope = fields.Char(default="odoo")
    user_id = fields.Many2one(
        "res.users", string="Usuario personal", ondelete="cascade", index=True,
        help="Si está configurado, este cliente OAuth es exclusivo de ese usuario: "
             "solo él puede completar la autorización con este client_id.",
    )

    _client_id_uniq = models.Constraint(
        "UNIQUE(client_id)", "client_id duplicado."
    )

    def get_redirect_uris(self):
        self.ensure_one()
        try:
            return json.loads(self.redirect_uris or "[]")
        except (ValueError, TypeError):
            return []

    @api.model
    def action_my_personal_connector(self):
        """Generate (or regenerate) a personal OAuth client for the current user.

        Any Odoo user with the Claude AI / Usuario group can call this. The
        resulting client is locked to that user: only they can complete the
        OAuth authorization with it, so their Claude.ai connector sees exactly
        the same data their Odoo session would (multi-company restrictions,
        record rules, ACL — all enforced as usual).
        """
        icp = self.env["ir.config_parameter"].sudo()
        if icp.get_param("ktx_claude_ai.connector_enabled", "False") != "True":
            raise UserError(_(
                "El conector remoto no está activado. "
                "Pide al administrador que lo active en Ajustes → Claude AI → Conector remoto."
            ))

        base = (
            icp.get_param("ktx_claude_ai.connector_base_url")
            or icp.get_param("web.base.url", "")
        ).rstrip("/")
        if base.endswith("/claude/mcp"):
            base = base[: -len("/claude/mcp")]

        user = self.env.user
        # Always regenerate so the plaintext secret can be shown once.
        self.sudo().search([("user_id", "=", user.id)]).unlink()
        client, secret = self.sudo().register({
            "client_name": "Claude.ai — %s" % user.name,
            "redirect_uris": [
                "https://claude.ai/api/mcp/auth_callback",
                "https://claude.ai/api/organizations/mcp/auth_callback",
            ],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "client_secret_post",
            "scope": "odoo",
        })
        client.sudo().write({"user_id": user.id})

        connector_url = base + "/claude/mcp"
        secret_line = (_("• Secreto del cliente: %(s)s") % {"s": secret}) if secret else ""
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Tu conector personal de Claude.ai"),
                "message": _(
                    "Pega estos datos en Claude.ai → Settings → Integrations → Add connector:\n\n"
                    "• URL del conector: %(url)s\n"
                    "• OAuth Client ID: %(cid)s\n"
                    "%(secret_line)s\n\n"
                    "⚠ Guarda el secreto ahora — no se puede recuperar después.\n\n"
                    "Solo tú podrás autenticarte con este cliente. Claude solo verá "
                    "los datos de Odoo a los que tu usuario tiene acceso."
                ) % {
                    "url": connector_url,
                    "cid": client.client_id,
                    "secret_line": secret_line,
                },
                "type": "success",
                "sticky": True,
            },
        }

    @api.model
    def register(self, metadata):
        """Create a client from a Dynamic Client Registration request.

        :return: (client_record, plaintext_secret_or_None) or None on bad input.
        """
        redirect_uris = metadata.get("redirect_uris") or []
        if not isinstance(redirect_uris, list) or not redirect_uris:
            return None
        auth_method = metadata.get("token_endpoint_auth_method") or "none"
        grant_types = metadata.get("grant_types") or ["authorization_code", "refresh_token"]
        response_types = metadata.get("response_types") or ["code"]
        vals = {
            "client_id": "claude-" + secrets.token_urlsafe(24),
            "client_name": metadata.get("client_name") or "Claude",
            "redirect_uris": json.dumps(redirect_uris),
            "grant_types": ",".join(grant_types),
            "response_types": ",".join(response_types),
            "token_endpoint_auth_method": auth_method,
            "scope": metadata.get("scope") or "odoo",
        }
        secret = None
        if auth_method in ("client_secret_post", "client_secret_basic"):
            secret = secrets.token_urlsafe(32)
            vals["client_secret"] = sha256(secret)
        client = self.sudo().create(vals)
        return client, secret


class ClaudeOauthCode(models.Model):
    """Short-lived authorization code (authorization_code grant + PKCE)."""

    _name = "claude.oauth.code"
    _description = "Código de autorización OAuth de Claude"
    _order = "create_date desc"

    code = fields.Char(index=True, required=True, copy=False, help="Hash sha256 del código.")
    client_id = fields.Char(required=True, index=True)
    user_id = fields.Many2one("res.users", required=True, ondelete="cascade")
    redirect_uri = fields.Char()
    code_challenge = fields.Char()
    code_challenge_method = fields.Char(default="S256")
    scope = fields.Char()
    resource = fields.Char()
    expires_at = fields.Datetime()
    used = fields.Boolean(default=False)

    _code_uniq = models.Constraint("UNIQUE(code)", "code duplicado.")


class ClaudeOauthToken(models.Model):
    """Issued OAuth access/refresh tokens (stored hashed)."""

    _name = "claude.oauth.token"
    _description = "Token OAuth de Claude"
    _order = "create_date desc"

    access_token = fields.Char(index=True, copy=False, help="Hash sha256.")
    refresh_token = fields.Char(index=True, copy=False, help="Hash sha256.")
    client_id = fields.Char(index=True)
    user_id = fields.Many2one("res.users", ondelete="cascade")
    scope = fields.Char()
    resource = fields.Char()
    access_expires_at = fields.Datetime()
    refresh_expires_at = fields.Datetime()
    revoked = fields.Boolean(default=False)
    last_used = fields.Datetime(readonly=True)

    def _ttl_seconds(self):
        return int(
            self.env["ir.config_parameter"].sudo().get_param(
                "ktx_claude_ai.connector_token_ttl", "3600"
            ) or 3600
        )

    @api.model
    def _mint(self, client_id, user, scope, resource):
        """Mint a new access/refresh pair. Returns (access_raw, refresh_raw, ttl)."""
        access_raw = secrets.token_urlsafe(32)
        refresh_raw = secrets.token_urlsafe(32)
        now = fields.Datetime.now()
        ttl = self._ttl_seconds()
        self.sudo().create({
            "access_token": sha256(access_raw),
            "refresh_token": sha256(refresh_raw),
            "client_id": client_id,
            "user_id": user.id,
            "scope": scope,
            "resource": resource,
            "access_expires_at": now + timedelta(seconds=ttl),
            "refresh_expires_at": now + timedelta(days=30),
        })
        return access_raw, refresh_raw, ttl

    @api.model
    def _validate(self, raw_token):
        """Return the res.users for a valid bearer access token, else None."""
        if not raw_token:
            return None
        rec = self.sudo().search(
            [("access_token", "=", sha256(raw_token)), ("revoked", "=", False)], limit=1
        )
        if not rec:
            return None
        if rec.access_expires_at and rec.access_expires_at < fields.Datetime.now():
            return None
        rec.last_used = fields.Datetime.now()
        user = rec.user_id
        return user if (user and user.active) else None

    @api.model
    def _refresh(self, raw_refresh, client_id):
        """Rotate a refresh token. Returns (access_raw, refresh_raw, ttl) or None."""
        rec = self.sudo().search(
            [("refresh_token", "=", sha256(raw_refresh)), ("revoked", "=", False)], limit=1
        )
        if not rec or rec.client_id != client_id:
            return None
        if rec.refresh_expires_at and rec.refresh_expires_at < fields.Datetime.now():
            return None
        rec.revoked = True
        return self._mint(rec.client_id, rec.user_id, rec.scope, rec.resource)

    def action_revoke(self):
        self.write({"revoked": True})

    @api.model
    def _cron_gc(self):
        """Daily housekeeping: purge expired auth codes, dead tokens and old
        audit-log entries so the tables don't grow unbounded."""
        now = fields.Datetime.now()
        codes = self.env["claude.oauth.code"].sudo().search([
            "|", ("expires_at", "<", now), ("used", "=", True),
        ])
        codes.unlink()
        tokens = self.sudo().search([
            "|", ("revoked", "=", True), ("refresh_expires_at", "<", now),
        ])
        tokens.unlink()
        retention = int(
            self.env["ir.config_parameter"].sudo().get_param(
                "ktx_claude_ai.log_retention_days", "90"
            ) or 0
        )
        if retention > 0:
            cutoff = now - timedelta(days=retention)
            old_logs = self.env["claude.request.log"].sudo().search(
                [("create_date", "<", cutoff)]
            )
            old_logs.unlink()
