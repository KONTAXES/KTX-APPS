# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    claude_enabled = fields.Boolean(
        string="Activar Claude AI",
        config_parameter="ktx_claude_ai.enabled",
        help="Interruptor general. Si está desactivado, el chat y las "
        "herramientas no funcionan.",
    )
    claude_api_key = fields.Char(
        string="API Key de Anthropic",
        config_parameter="ktx_claude_ai.api_key",
        help="Clave generada en console.anthropic.com. Se guarda en el servidor.",
    )
    claude_model = fields.Selection(
        selection=[
            ("claude-haiku-4-5", "Claude Haiku 4.5 (rápido y económico — recomendado)"),
            ("claude-sonnet-4-6", "Claude Sonnet 4.6 (equilibrado)"),
            ("claude-opus-4-8", "Claude Opus 4.8 (máxima capacidad)"),
        ],
        string="Modelo",
        default="claude-haiku-4-5",
        config_parameter="ktx_claude_ai.model",
    )
    claude_thinking = fields.Boolean(
        string="Razonamiento adaptativo",
        config_parameter="ktx_claude_ai.thinking",
        help="Permite que Claude razone antes de responder (recomendado).",
    )
    claude_max_tokens = fields.Integer(
        string="Tokens máximos por respuesta",
        config_parameter="ktx_claude_ai.max_tokens",
    )
    claude_max_steps = fields.Integer(
        string="Pasos máximos del agente",
        config_parameter="ktx_claude_ai.max_steps",
        help="Límite de iteraciones de herramientas por mensaje.",
    )
    claude_require_confirmation = fields.Boolean(
        string="Confirmar operaciones destructivas/masivas",
        config_parameter="ktx_claude_ai.require_confirmation",
    )
    claude_max_batch_size = fields.Integer(
        string="Umbral de operación masiva",
        config_parameter="ktx_claude_ai.max_batch_size",
        help="Por encima de este número de registros, escribir/eliminar/acciones "
        "requieren confirmación.",
    )
    claude_log_enabled = fields.Boolean(
        string="Registrar auditoría",
        config_parameter="ktx_claude_ai.log_enabled",
    )
    claude_log_retention_days = fields.Integer(
        string="Días de retención de bitácora",
        config_parameter="ktx_claude_ai.log_retention_days",
        help="La bitácora más antigua que este número de días se elimina "
        "automáticamente (tarea diaria). 0 = conservar siempre.",
    )
    claude_system_prompt = fields.Char(
        string="Instrucciones del sistema (opcional)",
        config_parameter="ktx_claude_ai.system_prompt",
        help="Si se deja vacío se usan instrucciones por defecto.",
    )

    # ------------------------------------------------- Conector remoto (Fase 2)
    claude_connector_enabled = fields.Boolean(
        string="Activar conector remoto",
        config_parameter="ktx_claude_ai.connector_enabled",
        help="Permite usar esta Odoo como conector personalizado desde Claude.ai "
        "web y la app de escritorio.",
    )
    claude_connector_base_url = fields.Char(
        string="URL pública (HTTPS)",
        config_parameter="ktx_claude_ai.connector_base_url",
        help="URL pública de esta Odoo. Si se deja vacío se usa web.base.url.",
    )
    claude_connector_rate_limit = fields.Integer(
        string="Límite de peticiones/min por token",
        config_parameter="ktx_claude_ai.connector_rate_limit",
    )
    claude_connector_token_ttl = fields.Integer(
        string="Vida del access token (seg)",
        config_parameter="ktx_claude_ai.connector_token_ttl",
    )
    claude_connector_url = fields.Char(
        string="URL del conector (pegar en Claude)",
        compute="_compute_connector_url",
        help="Agrega esta URL en Claude.ai → Settings → Connectors → Add custom connector.",
    )

    @api.depends("claude_connector_base_url")
    def _compute_connector_url(self):
        icp = self.env["ir.config_parameter"].sudo()
        for rec in self:
            base = (
                rec.claude_connector_base_url or icp.get_param("web.base.url") or ""
            ).rstrip("/")
            rec.claude_connector_url = (base + "/claude/mcp") if base else ""

    @api.model
    def get_values(self):
        res = super().get_values()
        params = self.env["ir.config_parameter"].sudo()
        # Defaults applied at read time for the integer/boolean parameters.
        res.update(
            claude_max_tokens=int(
                params.get_param("ktx_claude_ai.max_tokens", "8192")
            ),
            claude_max_steps=int(params.get_param("ktx_claude_ai.max_steps", "12")),
            claude_max_batch_size=int(
                params.get_param("ktx_claude_ai.max_batch_size", "50")
            ),
            claude_require_confirmation=params.get_param(
                "ktx_claude_ai.require_confirmation", "True"
            ) == "True",
            claude_thinking=params.get_param("ktx_claude_ai.thinking", "True")
            == "True",
            claude_log_enabled=params.get_param("ktx_claude_ai.log_enabled", "True")
            == "True",
            claude_log_retention_days=int(
                params.get_param("ktx_claude_ai.log_retention_days", "90")
            ),
            claude_connector_enabled=params.get_param(
                "ktx_claude_ai.connector_enabled", "False"
            ) == "True",
            claude_connector_rate_limit=int(
                params.get_param("ktx_claude_ai.connector_rate_limit", "120")
            ),
            claude_connector_token_ttl=int(
                params.get_param("ktx_claude_ai.connector_token_ttl", "3600")
            ),
        )
        return res

    def action_open_claude_models(self):
        return self.env["ir.actions.actions"]._for_xml_id(
            "ktx_claude_ai.action_claude_enabled_model"
        )

    def action_open_connector_tokens(self):
        return self.env["ir.actions.actions"]._for_xml_id(
            "ktx_claude_ai.action_claude_connector_token"
        )

    def action_register_claude_client(self):
        """Create (or reuse) an OAuth client for Claude.ai web and show a
        dialog with the client_id the user must paste in Claude.ai."""
        OAuthClient = self.env["claude.oauth.client"].sudo()
        icp = self.env["ir.config_parameter"].sudo()
        base = (
            icp.get_param("ktx_claude_ai.connector_base_url")
            or icp.get_param("web.base.url", "")
        ).rstrip("/")
        # Strip any trailing /claude/mcp in case the user pasted the full
        # connector URL into the "URL pública" field instead of the base domain.
        if base.endswith("/claude/mcp"):
            base = base[: -len("/claude/mcp")]

        # Always regenerate so the plaintext secret can be shown.
        # (Secrets are stored hashed and cannot be recovered after creation.)
        OAuthClient.search([("client_name", "=", "Claude.ai")]).unlink()
        client, secret = OAuthClient.register({
            "client_name": "Claude.ai",
            "redirect_uris": [
                "https://claude.ai/api/mcp/auth_callback",
                "https://claude.ai/api/organizations/mcp/auth_callback",
            ],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "client_secret_post",
            "scope": "odoo",
        })

        connector_url = base + "/claude/mcp"
        secret_line = (
            _("• Secreto del cliente: %(s)s") % {"s": secret}
        ) if secret else ""
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Cliente OAuth Claude.ai registrado"),
                "message": _(
                    "Pega estos datos en Claude.ai → Settings → Connectors:\n\n"
                    "• URL del conector: %(url)s\n"
                    "• OAuth Client ID: %(cid)s\n"
                    "%(secret_line)s\n\n"
                    "⚠ Guarda el secreto ahora — no se puede recuperar después."
                ) % {
                    "url": connector_url,
                    "cid": client.client_id,
                    "secret_line": secret_line,
                },
                "type": "success",
                "sticky": True,
            },
        }
