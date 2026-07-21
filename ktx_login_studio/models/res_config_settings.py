# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    ktx_login_studio_force_safe_mode = fields.Boolean(
        string="Modo seguro (desactivar temas y extensiones)",
        config_parameter="ktx_login_studio.force_safe_mode",
        help="Interruptor de emergencia: si se activa, TODAS las paginas de "
             "login vuelven a la apariencia 100% original de Odoo para todos "
             "los usuarios, ignorando cualquier tema o extension publicada. "
             "Utilizalo si una personalizacion deja el login inutilizable.",
    )

    def action_open_ktx_login_studio(self):
        return self.env["ir.actions.act_window"]._for_xml_id(
            "ktx_login_studio.ktx_login_theme_action")
