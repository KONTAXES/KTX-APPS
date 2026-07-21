# -*- coding: utf-8 -*-
"""
Migration 19.0.1.19.0 — SQL-based model seeding.

Rewrites the seeding to use raw SQL (INSERT ... ON CONFLICT DO UPDATE)
to guarantee all COMMON_MODELS are created/reactivated regardless of any
previous ORM-level failures.
"""
from odoo import api, SUPERUSER_ID
from odoo.addons.ktx_claude_ai.hooks import _seed_models_sql, _seed_all_models


def migrate(cr, version):
    _seed_models_sql(cr)
    env = api.Environment(cr, SUPERUSER_ID, {})
    _seed_all_models(env)
