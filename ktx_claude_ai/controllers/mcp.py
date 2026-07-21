# -*- coding: utf-8 -*-
"""Remote MCP endpoint for Claude.ai (web) and Claude Desktop.

Implements the MCP "Streamable HTTP" transport as a JSON-RPC 2.0 endpoint at
``/claude/mcp``. Authentication is by Bearer token (an OAuth 2.1 access token or
a static connector token); tool calls are routed to the shared
``claude.tool.dispatcher`` running as the authenticated Odoo user, so the same
permissions and audit trail as the in-Odoo chat apply.
"""
import json
import logging

from odoo import http
from odoo.http import request

from .utils import (
    base_url,
    check_rate_limit,
    extract_bearer,
    json_response,
    jsonrpc_error,
    jsonrpc_result,
)

_logger = logging.getLogger(__name__)

# Latest MCP protocol version we target; we echo the client's requested version
# when present (we support it).
PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "Odoo Claude Connector", "version": "19.0.1.0.0"}


class ClaudeMcpController(http.Controller):

    def _authenticate(self):
        raw = extract_bearer()
        if not raw:
            return None
        user = request.env["claude.oauth.token"].sudo()._validate(raw)
        if not user:
            user = request.env["claude.connector.token"].sudo().find_valid_token(raw)
        return user

    @http.route(
        "/claude/mcp",
        type="http", auth="none", methods=["POST"], csrf=False, cors="*",
    )
    def mcp(self, **kw):
        icp = request.env["ir.config_parameter"].sudo()
        if icp.get_param("ktx_claude_ai.connector_enabled", "False") != "True":
            return json_response({"error": "connector_disabled"}, status=503)

        user = self._authenticate()
        if not user:
            return json_response(
                {"error": "invalid_token"},
                status=401,
                headers=[(
                    "WWW-Authenticate",
                    'Bearer resource_metadata="%s/.well-known/oauth-protected-resource"'
                    % base_url(),
                )],
            )

        # Set the authenticated user on the request's default environment.
        # auth="none" leaves request.env.user empty; without this, Odoo's
        # cursor flush calls _recompute_all() in the userless env and any
        # computed field that calls self.env.user.has_group() raises
        # "Expected singleton: res.users()".
        request.update_env(user=user.id)

        rate = int(icp.get_param("ktx_claude_ai.connector_rate_limit", "120") or 0)
        if not check_rate_limit(user.id, rate):
            return json_response(
                jsonrpc_error(None, -32000, "Rate limit exceeded"), status=429
            )

        try:
            payload = json.loads(request.httprequest.get_data(as_text=True) or "{}")
        except ValueError:
            return json_response(jsonrpc_error(None, -32700, "Parse error"), status=400)

        if isinstance(payload, list):  # JSON-RPC batch
            responses = [
                r for r in (self._handle_one(m, user) for m in payload) if r is not None
            ]
            return json_response(responses)

        response = self._handle_one(payload, user)
        if response is None:  # notification → no body
            return request.make_response(
                "", status=202, headers=[("Content-Type", "application/json")]
            )
        return json_response(response)

    # ----------------------------------------------------------- dispatch
    def _handle_one(self, msg, user):
        if not isinstance(msg, dict):
            return jsonrpc_error(None, -32600, "Invalid Request")
        method = msg.get("method")
        params = msg.get("params") or {}
        req_id = msg.get("id")
        is_notification = "id" not in msg

        if method == "initialize":
            return jsonrpc_result(req_id, {
                "protocolVersion": params.get("protocolVersion") or PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
            })
        if method and method.startswith("notifications/"):
            return None
        if method == "ping":
            return jsonrpc_result(req_id, {})
        if method == "tools/list":
            return jsonrpc_result(req_id, {"tools": self._mcp_tools()})
        if method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments") or {}
            # Set allowed_company_ids so Odoo multi-company record rules apply
            # correctly (e.g. res.company visibility is restricted to the user's
            # own companies, and documents from other companies are not exposed).
            result = (
                request.env["claude.tool.dispatcher"]
                .with_user(user)
                .with_context(
                    allowed_company_ids=user.company_ids.ids,
                    force_company=user.company_id.id,
                )
                .execute_tool(name, arguments, source="connector")
            )
            return jsonrpc_result(req_id, {
                "content": [{
                    "type": "text",
                    "text": json.dumps(result, default=str, ensure_ascii=False),
                }],
                "isError": bool(result.get("error")),
            })
        if method == "resources/list":
            return jsonrpc_result(req_id, {"resources": []})
        if method == "prompts/list":
            return jsonrpc_result(req_id, {"prompts": []})
        if is_notification:
            return None
        return jsonrpc_error(req_id, -32601, "Method not found: %s" % method)

    def _mcp_tools(self):
        """Adapt the dispatcher's Anthropic-format schemas to MCP tool shape
        (``input_schema`` → ``inputSchema``)."""
        schemas = request.env["claude.tool.dispatcher"].sudo()._get_tool_schemas()
        return [{
            "name": s["name"],
            "description": s.get("description", ""),
            "inputSchema": s.get("input_schema", {"type": "object", "properties": {}}),
        } for s in schemas]
