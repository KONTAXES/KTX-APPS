# -*- coding: utf-8 -*-
from odoo import fields, models, api


class KtxPhraseConfig(models.Model):
    _name = 'ktx.phrase.config'
    _description = 'Configuracion de Frases y Escenarios SAT FEL'
    _order = 'tipo_frase, codigo_escenario'
    _rec_name = 'display_name'

    tipo_frase = fields.Integer(
        'Tipo Frase', required=True,
        help='TipoFrase del XML FEL (1-12 segun catalogo SAT)'
    )
    codigo_escenario = fields.Integer(
        'Codigo Escenario', required=True,
        help='CodigoEscenario del XML FEL'
    )
    descripcion = fields.Char(
        'Descripcion SAT', required=True,
        help='Descripcion oficial del catalogo SAT'
    )
    descripcion_es = fields.Char(
        'Texto en Factura',
        help='Texto personalizado a mostrar en las notas de la factura. '
             'Si esta vacio se usa la Descripcion SAT.'
    )
    tipo_regimen = fields.Char('Tipo Regimen / Categoria')
    include_in_footer = fields.Boolean(
        'Incluir en notas de factura', default=True,
        help='Si activo, el texto se agrega en el campo Notas/Narration de la factura'
    )
    # company_dependent: cada empresa asigna su propio impuesto de retencion
    # a esta frase, sin mezclarse con el de otras empresas.
    tax_id = fields.Many2one(
        'account.tax', string='Retencion Compras (esta empresa)',
        company_dependent=True,
        domain="[('type_tax_use', 'in', ['purchase', 'all'])]",
        help='Impuesto de retencion para compras (ej: ISR retencion o IVA Agente). '
             'Se aplica al importar facturas de proveedores. Cada empresa configura el suyo.'
    )
    tax_id_sale = fields.Many2one(
        'account.tax', string='Retencion Ventas (esta empresa)',
        company_dependent=True,
        domain="[('type_tax_use', 'in', ['sale', 'all'])]",
        help='Impuesto de retencion para ventas. '
             'Se aplica al importar facturas de clientes. Cada empresa configura el suyo.'
    )
    clear_taxes = fields.Boolean(
        'Limpiar todos los impuestos', default=False,
        help='Si activo, elimina TODOS los impuestos de las lineas al importar. '
             'Usar para frases de exencion de IVA (TipoFrase=4) y similares '
             'donde la SAT indica que la operacion no genera IVA.'
    )
    active = fields.Boolean(default=True)
    display_name = fields.Char(compute='_compute_display_name', store=True)

    _unique_phrase = models.Constraint(
        'UNIQUE(tipo_frase, codigo_escenario)',
        'Ya existe configuracion para este Tipo Frase y Codigo Escenario.',
    )

    @api.depends('tipo_frase', 'codigo_escenario', 'descripcion')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = 'T%d/E%d - %s' % (
                rec.tipo_frase, rec.codigo_escenario, rec.descripcion or ''
            )
