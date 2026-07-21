# -*- coding: utf-8 -*-
import json
import logging

import requests

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


class ClaudeApi(models.AbstractModel):
    """Thin wrapper around the Anthropic Messages API.

    Uses ``requests`` (bundled with Odoo) — no extra Python package required, so
    the module installs cleanly on Odoo Online, Odoo.sh and on-premise. Isolates
    the HTTP details so the agentic loop in ``claude.conversation`` and the
    remote connector share one client.
    """

    _name = "claude.api"
    _description = "Cliente de la API de Claude (Anthropic)"

    def _get_api_key(self):
        key = (
            self.env["ir.config_parameter"].sudo().get_param("ktx_claude_ai.api_key")
        )
        if not key:
            raise UserError(
                _("Falta la API key de Anthropic. Configúrela en Ajustes → Claude AI.")
            )
        return key

    def create_message(
        self,
        *,
        model,
        messages,
        tools=None,
        system=None,
        max_tokens=8192,
        thinking=None,
    ):
        """Call ``POST /v1/messages`` and return the response as a plain dict.

        :return: the raw API JSON — keys include ``content`` (list of blocks),
            ``stop_reason``, ``usage`` and ``model``.
        """
        payload = {"model": model, "max_tokens": max_tokens, "messages": messages}
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = tools
        if thinking:
            payload["thinking"] = thinking
        headers = {
            "x-api-key": self._get_api_key(),
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        try:
            resp = requests.post(
                ANTHROPIC_URL, headers=headers, data=json.dumps(payload), timeout=120
            )
        except requests.exceptions.RequestException as exc:
            raise UserError(
                _("No se pudo conectar con la API de Claude: %s") % exc
            ) from exc

        if resp.status_code != 200:
            detail = resp.text
            try:
                detail = (resp.json().get("error") or {}).get("message") or detail
            except ValueError:
                pass
            _logger.warning("Claude API error %s: %s", resp.status_code, detail)
            raise UserError(
                _("Error de la API de Claude (%(code)s): %(msg)s")
                % {"code": resp.status_code, "msg": detail}
            )
        return resp.json()
