# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.ktx_claude_ai.models.claude_api import ClaudeApi


def _ensure_enabled(env, model_name, **perms):
    """Search for an existing enabled-model record and update it, or create one.

    This avoids UniqueViolation errors when the record is already seeded by
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
class TestClaudeAgentLoop(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        params = cls.env["ir.config_parameter"].sudo()
        params.set_param("ktx_claude_ai.enabled", "True")
        params.set_param("ktx_claude_ai.log_enabled", "False")
        params.set_param("ktx_claude_ai.thinking", "False")
        params.set_param("ktx_claude_ai.api_key", "sk-ant-test")
        _ensure_enabled(
            cls.env, "res.partner",
            allow_read=True, allow_create=True,
            allow_write=False, allow_unlink=False, allow_action=False,
        )

    def test_tool_use_loop_creates_record(self):
        responses = [
            {
                "model": "claude-opus-4-8",
                "stop_reason": "tool_use",
                "usage": {"input_tokens": 10, "output_tokens": 5},
                "content": [
                    {"type": "text", "text": "Voy a crear el contacto."},
                    {
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": "odoo_create",
                        "input": {
                            "model": "res.partner",
                            "values": {"name": "Foo Claude"},
                        },
                    },
                ],
            },
            {
                "model": "claude-opus-4-8",
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 12, "output_tokens": 6},
                "content": [{"type": "text", "text": "Listo, creé a Foo Claude."}],
            },
        ]

        def fake_create_message(self, **kwargs):
            return responses.pop(0)

        conv = self.env["claude.conversation"].create({})
        with patch.object(ClaudeApi, "create_message", fake_create_message):
            new_msgs = conv.send_message("Crea un contacto llamado Foo Claude")

        # The agent loop ran two turns: created the partner and replied.
        self.assertTrue(
            self.env["res.partner"].search_count([("name", "=", "Foo Claude")])
        )
        roles = [m["role"] for m in new_msgs]
        self.assertIn("user", roles)
        self.assertIn("tool", roles)
        self.assertIn("assistant", roles)
        # Token usage accumulated on the conversation.
        self.assertEqual(conv.total_output_tokens, 11)
        # Raw replay history persisted for the next turn.
        self.assertTrue(conv.raw_messages and conv.raw_messages != "[]")
