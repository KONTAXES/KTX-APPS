# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


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
class TestClaudeDispatcher(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["ir.config_parameter"].sudo().set_param(
            "ktx_claude_ai.enabled", "True"
        )
        cls.env["ir.config_parameter"].sudo().set_param(
            "ktx_claude_ai.log_enabled", "False"
        )
        cls.dispatcher = cls.env["claude.tool.dispatcher"]
        cls.Enabled = cls.env["claude.enabled.model"]
        cls.partner_model = cls.env.ref("base.model_res_partner")
        # Enable res.partner: read/create/write/action (no unlink).
        _ensure_enabled(
            cls.env, "res.partner",
            allow_read=True, allow_create=True, allow_write=True,
            allow_unlink=False, allow_action=True, allowed_methods="toggle_active",
        )

    def test_create_and_write(self):
        res = self.dispatcher.execute_tool(
            "odoo_create",
            {"model": "res.partner", "values": {"name": "Acme Claude"}},
        )
        self.assertTrue(res.get("created"))
        partner = self.env["res.partner"].browse(res["id"])
        self.assertEqual(partner.name, "Acme Claude")

        res2 = self.dispatcher.execute_tool(
            "odoo_write",
            {"model": "res.partner", "ids": [partner.id], "values": {"phone": "123"}},
        )
        self.assertEqual(res2.get("count"), 1)
        self.assertEqual(partner.phone, "123")

    def test_operation_not_enabled(self):
        # unlink is disabled for res.partner.
        partner = self.env["res.partner"].create({"name": "ToKeep"})
        res = self.dispatcher.execute_tool(
            "odoo_unlink", {"model": "res.partner", "ids": [partner.id], "confirm": True}
        )
        self.assertIn("error", res)
        self.assertTrue(partner.exists())

    def test_model_not_enabled(self):
        res = self.dispatcher.execute_tool(
            "odoo_search", {"model": "ir.config_parameter", "domain": []}
        )
        self.assertIn("error", res)

    def test_unlink_confirmation_flow(self):
        # Enable unlink for this test.
        rec = self.Enabled.search([("model_name", "=", "res.partner")], limit=1)
        rec.allow_unlink = True
        partner = self.env["res.partner"].create({"name": "ToDelete"})
        # Without confirm → confirmation required, record kept.
        res = self.dispatcher.execute_tool(
            "odoo_unlink", {"model": "res.partner", "ids": [partner.id]}
        )
        self.assertEqual(res.get("status"), "confirmation_required")
        self.assertTrue(partner.exists())
        # With confirm → deleted.
        res2 = self.dispatcher.execute_tool(
            "odoo_unlink",
            {"model": "res.partner", "ids": [partner.id], "confirm": True},
        )
        self.assertEqual(res2.get("count"), 1)
        self.assertFalse(partner.exists())

    def test_action_allowlist(self):
        partner = self.env["res.partner"].create({"name": "Toggle", "active": True})
        # Disallowed method rejected.
        res = self.dispatcher.execute_tool(
            "odoo_action",
            {"model": "res.partner", "ids": [partner.id], "method": "unlink"},
        )
        self.assertIn("error", res)
        # Allowed method runs.
        res2 = self.dispatcher.execute_tool(
            "odoo_action",
            {"model": "res.partner", "ids": [partner.id], "method": "toggle_active"},
        )
        self.assertEqual(res2.get("method"), "toggle_active")
        self.assertFalse(partner.active)

    def test_mass_guard(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "ktx_claude_ai.max_batch_size", "1"
        )
        p1 = self.env["res.partner"].create({"name": "M1"})
        p2 = self.env["res.partner"].create({"name": "M2"})
        res = self.dispatcher.execute_tool(
            "odoo_write",
            {"model": "res.partner", "ids": [p1.id, p2.id], "values": {"phone": "9"}},
        )
        self.assertEqual(res.get("status"), "confirmation_required")
        # Confirm proceeds.
        res2 = self.dispatcher.execute_tool(
            "odoo_write",
            {
                "model": "res.partner",
                "ids": [p1.id, p2.id],
                "values": {"phone": "9"},
                "confirm": True,
            },
        )
        self.assertEqual(res2.get("count"), 2)

    def test_odoo_count(self):
        self.env["res.partner"].create({"name": "CountMe1"})
        self.env["res.partner"].create({"name": "CountMe2"})
        res = self.dispatcher.execute_tool(
            "odoo_count",
            {"model": "res.partner", "domain": [["name", "like", "CountMe"]]},
        )
        self.assertFalse(res.get("error"))
        self.assertGreaterEqual(res.get("count", 0), 2)
        # Empty domain returns all partners.
        res2 = self.dispatcher.execute_tool(
            "odoo_count", {"model": "res.partner"}
        )
        self.assertGreater(res2.get("count", 0), 0)

    def test_odoo_get_url(self):
        partner = self.env["res.partner"].create({"name": "URLTest"})
        res = self.dispatcher.execute_tool(
            "odoo_get_url",
            {"model": "res.partner", "id": partner.id},
        )
        self.assertFalse(res.get("error"))
        url = res.get("url", "")
        self.assertIn("res.partner", url)
        self.assertIn(str(partner.id), url)
        self.assertIn("form", url)

    def test_context_aware_system_prompt(self):
        partner = self.env["res.partner"].create({"name": "CtxPartner"})
        conv = self.env["claude.conversation"].create({})
        prompt = conv._build_system_prompt_with_record("res.partner", partner.id)
        self.assertIn("CtxPartner", prompt)
        self.assertIn("res.partner", prompt)
        # Without context returns base prompt.
        base = conv._build_system_prompt_with_record(None, None)
        self.assertNotIn("CtxPartner", base)

    def test_delete_conversation(self):
        conv = self.env["claude.conversation"].create({})
        conv_id = conv.id
        conv.delete_conversation()
        self.assertFalse(self.env["claude.conversation"].browse(conv_id).exists())
