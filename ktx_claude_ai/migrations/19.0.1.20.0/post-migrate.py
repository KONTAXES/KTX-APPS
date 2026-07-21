# -*- coding: utf-8 -*-
"""
Migration 19.0.1.20.0 — Add company_id to claude.conversation.

Adds the ``company_id`` column to ``claude_conversation`` so each
conversation can be scoped to a specific company. Existing conversations
are set to the admin user's default company.
"""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    # Add column if not already present (safe to run multiple times)
    cr.execute("""
        ALTER TABLE claude_conversation
        ADD COLUMN IF NOT EXISTS company_id INTEGER
            REFERENCES res_company(id) ON DELETE SET NULL;
    """)

    # Back-fill existing conversations: set to the company of the conversation owner,
    # falling back to the first company in the system.
    cr.execute("""
        UPDATE claude_conversation cc
        SET company_id = COALESCE(
            (SELECT rp.company_id
               FROM res_users ru
               JOIN res_partner rp ON rp.id = ru.partner_id
              WHERE ru.id = cc.user_id
              LIMIT 1),
            (SELECT id FROM res_company ORDER BY id LIMIT 1)
        )
        WHERE company_id IS NULL;
    """)

    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.ktx_claude_ai.hooks import _seed_models_sql, _seed_all_models
    _seed_models_sql(cr)
    _seed_all_models(env)
