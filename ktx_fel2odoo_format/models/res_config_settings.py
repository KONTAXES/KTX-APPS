# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ktx_fel_format_enabled = fields.Boolean(
        related='company_id.ktx_fel_format_enabled', readonly=False,
        string='Formato FEL GT (KTX)',
    )
    ktx_fel_format_accent_color = fields.Char(
        related='company_id.ktx_fel_format_accent_color', readonly=False)
    ktx_fel_format_paper_size = fields.Selection(
        related='company_id.ktx_fel_format_paper_size', readonly=False)
    ktx_fel_format_style = fields.Selection(
        related='company_id.ktx_fel_format_style', readonly=False)
    ktx_fel_format_logo_position = fields.Selection(
        related='company_id.ktx_fel_format_logo_position', readonly=False)
    ktx_fel_format_logo_source = fields.Selection(
        related='company_id.ktx_fel_format_logo_source', readonly=False)
    ktx_fel_format_logo = fields.Binary(
        related='company_id.ktx_fel_format_logo', readonly=False)
    ktx_fel_format_logo_filename = fields.Char(
        related='company_id.ktx_fel_format_logo_filename', readonly=False)
    ktx_fel_format_side_image = fields.Binary(
        related='company_id.ktx_fel_format_side_image', readonly=False)
    ktx_fel_format_side_image_filename = fields.Char(
        related='company_id.ktx_fel_format_side_image_filename', readonly=False)
    ktx_fel_format_background_image = fields.Binary(
        related='company_id.ktx_fel_format_background_image', readonly=False)
    ktx_fel_format_background_filename = fields.Char(
        related='company_id.ktx_fel_format_background_filename', readonly=False)
    ktx_fel_format_show_footer = fields.Boolean(
        related='company_id.ktx_fel_format_show_footer', readonly=False)
    ktx_fel_format_footer_description = fields.Text(
        related='company_id.ktx_fel_format_footer_description', readonly=False)
    ktx_fel_format_social_website = fields.Char(
        related='company_id.ktx_fel_format_social_website', readonly=False)
    ktx_fel_format_social_phone = fields.Char(
        related='company_id.ktx_fel_format_social_phone', readonly=False)
    ktx_fel_format_social_email = fields.Char(
        related='company_id.ktx_fel_format_social_email', readonly=False)
    ktx_fel_format_social_facebook = fields.Char(
        related='company_id.ktx_fel_format_social_facebook', readonly=False)
    ktx_fel_format_social_instagram = fields.Char(
        related='company_id.ktx_fel_format_social_instagram', readonly=False)
    ktx_fel_format_social_x = fields.Char(
        related='company_id.ktx_fel_format_social_x', readonly=False)

    @api.onchange('ktx_fel_format_style', 'ktx_fel_format_paper_size')
    def _onchange_ktx_fel_format_ticket(self):
        # Ticket solo existe para KTX 1. Si se elige otra apariencia con
        # Ticket seleccionado, se corrige a Carta automaticamente, de modo que
        # para las demas apariencias solo apliquen Carta y Media Carta.
        for wiz in self:
            if (wiz.ktx_fel_format_paper_size == 'ticket'
                    and wiz.ktx_fel_format_style != 'ktx1'):
                wiz.ktx_fel_format_paper_size = 'carta'
                return {'warning': {
                    'title': _('Tamano de papel ajustado'),
                    'message': _(
                        'El tamano "Ticket" solo esta disponible con la '
                        'apariencia KTX 1. Se cambio a "Carta".'),
                }}
