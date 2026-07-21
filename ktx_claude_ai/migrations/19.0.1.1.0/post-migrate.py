# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID
from odoo.addons.ktx_claude_ai.hooks import _seed_models


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _seed_models(env, update_existing=False)
