# -*- coding: utf-8 -*-
import json

from odoo.tests import HttpCase, tagged


def _ensure_enabled(env, model_name, **perms):
    """Search for an existing enabled-model record and update it, or create one.

    Prevents UniqueViolation when a record was already seeded by
    ``data/claude_enabled_model_data.xml`` or the post_init_hook.
    """
    rec = env["claude.enabled.model"].sudo().search(
        [("model_name", "=", model_name)], limit=1
    )
    if rec:
        rec.write(perms)
    else:
        model_id = env["ir.model"].sudo().search(
            [("model", "=", model_name)], limit=1
        ).id
        rec = env["claude.enabled.model"].sudo().create(
            {"model_id": model_id, **perms}
        )
    return rec


@tagged("post_install", "-at_install")
class TestMcpConnector(HttpCase):
    def setUp(self):
        super().setUp()
        params = self.env["ir.config_parameter"].sudo()
        params.set_param("ktx_claude_ai.connector_enabled", "True")
        params.set_param("ktx_claude_ai.log_enabled", "False")
        _ensure_enabled(
            self.env, "res.partner",
            allow_read=True, allow_create=True, allow_write=False,
            allow_unlink=False, allow_action=False,
        )
        admin = self.env.ref("base.user_admin")
        _rec, self.token = self.env["claude.connector.token"].sudo()._mint("test", admin.id)

    def _rpc(self, body, token=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        return self.url_open(
            "/claude/mcp", data=json.dumps(body), headers=headers, timeout=30
        )

    def test_unauthorized(self):
        r = self._rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        self.assertEqual(r.status_code, 401)
        self.assertIn("WWW-Authenticate", r.headers)

    def test_initialize_tools_and_call(self):
        r = self._rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}, self.token)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["result"]["serverInfo"]["name"], "Odoo Claude Connector")

        r2 = self._rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, self.token)
        tools = r2.json()["result"]["tools"]
        names = [t["name"] for t in tools]
        self.assertIn("odoo_create", names)
        self.assertIn("odoo_search", names)
        self.assertIn("odoo_count", names)
        self.assertIn("odoo_get_url", names)
        # MCP tool shape uses camelCase inputSchema.
        self.assertIn("inputSchema", next(t for t in tools if t["name"] == "odoo_create"))

        r3 = self._rpc({
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {
                "name": "odoo_create",
                "arguments": {"model": "res.partner", "values": {"name": "MCP Partner"}},
            },
        }, self.token)
        result = r3.json()["result"]
        self.assertFalse(result["isError"])
        self.assertTrue(
            self.env["res.partner"].sudo().search_count([("name", "=", "MCP Partner")])
        )

    def test_permission_denied_tool(self):
        # write is not enabled for res.partner → dispatcher returns an error result.
        partner = self.env["res.partner"].sudo().create({"name": "NoWrite"})
        r = self._rpc({
            "jsonrpc": "2.0", "id": 4, "method": "tools/call",
            "params": {
                "name": "odoo_write",
                "arguments": {"model": "res.partner", "ids": [partner.id], "values": {"phone": "1"}},
            },
        }, self.token)
        self.assertTrue(r.json()["result"]["isError"])

    def test_connector_disabled(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "ktx_claude_ai.connector_enabled", "False"
        )
        r = self._rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize"}, self.token)
        self.assertEqual(r.status_code, 503)
