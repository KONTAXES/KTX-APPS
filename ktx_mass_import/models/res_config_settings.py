# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ktx_allow_different_nit = fields.Boolean(
        'Permitir facturas de compra con NIT receptor diferente al de la empresa',
        config_parameter='ktx_mass_import.allow_different_nit',
        help='Si activo, se podran importar facturas de compra aunque el NIT Receptor '
             'del XML no coincida con el NIT de la empresa activa.'
    )
    ktx_allow_different_emisor_nit = fields.Boolean(
        'Permitir facturas de venta con NIT emisor diferente al de la empresa',
        config_parameter='ktx_mass_import.allow_different_emisor_nit',
        help='Si activo, se podran importar facturas de venta aunque el NIT Emisor '
             'del XML no coincida con el NIT de la empresa activa.'
    )
    ktx_default_product_bien_id = fields.Many2one(
        'product.product', string='Producto por defecto para Bienes',
        config_parameter='ktx_mass_import.default_product_bien_id'
    )
    ktx_default_product_servicio_id = fields.Many2one(
        'product.product', string='Producto por defecto para Servicios',
        config_parameter='ktx_mass_import.default_product_servicio_id'
    )
