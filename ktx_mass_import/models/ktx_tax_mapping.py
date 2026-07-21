# -*- coding: utf-8 -*-
from odoo import api, fields, models

NOMBRES_CORTOS = [
    ('IVA', 'IVA'),
    ('PETROLEO', 'Petroleo y Combustibles'),
    ('TURISMO HOSPEDAJE', 'Turismo Hospedaje'),
    ('TURISMO PASAJES', 'Turismo Pasajes'),
    ('TIMBRE DE PRENSA', 'Timbre de Prensa'),
    ('BOMBEROS', 'Bomberos'),
    ('TASA MUNICIPAL', 'Tasa Municipal'),
    ('BEBIDAS ALCOHOLICAS', 'Bebidas Alcoholicas'),
    ('TABACO', 'Tabaco'),
    ('CEMENTO', 'Cemento'),
    ('BEBIDAS NO ALCOHOLICAS', 'Bebidas No Alcoholicas'),
    ('TARIFA PORTUARIA', 'Tarifa Portuaria'),
]


class KtxTaxMapping(models.Model):
    _name = 'ktx.tax.mapping'
    _description = 'Mapeo de Impuestos SAT FEL a Odoo'
    _order = 'nombre_corto, codigo_unidad_gravable'
    _rec_name = 'display_name'

    nombre_corto = fields.Selection(
        NOMBRES_CORTOS, string='Tipo Impuesto SAT', required=True,
        help='NombreCorto del XML FEL segun catalogo SAT'
    )
    codigo_unidad_gravable = fields.Integer(
        'Codigo UG', required=True,
        help='CodigoUnidadGravable del XML FEL'
    )
    descripcion = fields.Char(
        'Descripcion SAT',
        help='Descripcion oficial del catalogo SAT'
    )
    tasa_referencia = fields.Char(
        'Tasa/Monto Referencia',
        help='Tasa o monto de referencia segun catalogo SAT'
    )
    # company_dependent: el catalogo es global (una fila por tipo SAT) pero cada
    # empresa guarda SU PROPIO impuesto en esa misma fila. Nunca se mezclan los
    # impuestos entre empresas y no se duplican registros del catalogo.
    tax_id = fields.Many2one(
        'account.tax', string='Impuesto Compras (esta empresa)',
        company_dependent=True,
        domain="[('type_tax_use', 'in', ['purchase', 'all'])]",
        help='Impuesto de compras de la empresa activa para este tipo SAT. '
             'Se aplica al importar facturas de proveedores.'
    )
    tax_id_sale = fields.Many2one(
        'account.tax', string='Impuesto Ventas (esta empresa)',
        company_dependent=True,
        domain="[('type_tax_use', 'in', ['sale', 'all'])]",
        help='Impuesto de ventas de la empresa activa para este tipo SAT. '
             'Se aplica al importar facturas de clientes.'
    )
    product_id = fields.Many2one(
        'product.template', string='Producto por Defecto',
        help='Producto Odoo a usar para lineas con este tipo de impuesto'
    )
    active = fields.Boolean(default=True)
    display_name = fields.Char(compute='_compute_display_name', store=True)

    _unique_mapping = models.Constraint(
        'UNIQUE(nombre_corto, codigo_unidad_gravable)',
        'Ya existe un mapeo para este NombreCorto y CodigoUnidadGravable.',
    )

    @api.depends('nombre_corto', 'codigo_unidad_gravable', 'descripcion')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s - UG%s%s' % (
                rec.nombre_corto or '',
                rec.codigo_unidad_gravable,
                (' (%s)' % rec.descripcion) if rec.descripcion else '',
            )
