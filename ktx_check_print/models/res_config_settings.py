# -*- coding: utf-8 -*-
from odoo import fields, models

_POS_PARAM = 'ktx_check_print.pos.{}.{}'

# (field_name, param_key, default_value)
_POS_FIELDS = [
    ('ktx_check_height',      'height',      70.0),
    ('ktx_check_date_top',    'date_top',    25.0),
    ('ktx_check_date_left',   'date_left',   20.0),
    ('ktx_check_amount_top',  'amount_top',  25.0),
    ('ktx_check_amount_left', 'amount_left', 150.0),
    ('ktx_check_payee_top',   'payee_top',   31.0),
    ('ktx_check_payee_left',  'payee_left',  20.0),
    ('ktx_check_words_top',   'words_top',   38.0),
    ('ktx_check_words_left',  'words_left',  20.0),
    ('ktx_check_nonneg_top',  'nonneg_top',  48.0),
    ('ktx_check_nonneg_left', 'nonneg_left', 20.0),
]


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Columnas reales existentes (ya en BD desde instalación anterior)
    ktx_check_paper_format = fields.Selection(
        selection=[
            ('letter', 'Carta Bond (8.5" × 11")'),
            ('continuous', 'Papel Continuo (9.5" × 11")'),
        ],
        string='Formato de Papel de Cheque',
        default='letter',
    )
    ktx_check_appearance = fields.Selection(
        selection=[
            ('classic', 'Clásico'),
            ('modern', 'Moderno'),
            ('minimal', 'Minimalista'),
        ],
        string='Apariencia del Cheque',
        default='classic',
    )
    ktx_check_margin_top = fields.Float(
        string='Margen Superior (mm)',
        default=5.0,
        help='Distancia desde el borde superior de la hoja al número de cheque.',
    )
    ktx_check_margin_left = fields.Float(
        string='Margen Izquierdo (mm)',
        default=5.0,
    )
    ktx_check_margin_right = fields.Float(
        string='Margen Derecho (mm)',
        default=5.0,
    )
    ktx_check_blank_height = fields.Float(
        string='Altura Área en Blanco (mm)',
        default=70.0,
        help=(
            'Espacio en blanco debajo del monto en letras, '
            'correspondiente al cuerpo del cheque físico. '
            'Ajuste hasta que el voucher quede en la posición correcta.'
        ),
    )

    # ── Posiciones de impresión — store=False para no crear columnas nuevas ──
    # Almacenadas vía ir.config_parameter keyed por empresa.
    ktx_check_height = fields.Float(
        string='Altura sección cheque (mm)', default=70.0,
        compute='_compute_ktx_check_positions',
        inverse='_inverse_ktx_check_positions',
        store=False,
    )
    ktx_check_date_top = fields.Float(
        string='Fecha — superior (mm)', default=25.0,
        compute='_compute_ktx_check_positions',
        inverse='_inverse_ktx_check_positions',
        store=False,
    )
    ktx_check_date_left = fields.Float(
        string='Fecha — izquierda (mm)', default=20.0,
        compute='_compute_ktx_check_positions',
        inverse='_inverse_ktx_check_positions',
        store=False,
    )
    ktx_check_amount_top = fields.Float(
        string='Monto numérico — superior (mm)', default=25.0,
        compute='_compute_ktx_check_positions',
        inverse='_inverse_ktx_check_positions',
        store=False,
    )
    ktx_check_amount_left = fields.Float(
        string='Monto numérico — izquierda (mm)', default=150.0,
        compute='_compute_ktx_check_positions',
        inverse='_inverse_ktx_check_positions',
        store=False,
    )
    ktx_check_payee_top = fields.Float(
        string='Beneficiario — superior (mm)', default=31.0,
        compute='_compute_ktx_check_positions',
        inverse='_inverse_ktx_check_positions',
        store=False,
    )
    ktx_check_payee_left = fields.Float(
        string='Beneficiario — izquierda (mm)', default=20.0,
        compute='_compute_ktx_check_positions',
        inverse='_inverse_ktx_check_positions',
        store=False,
    )
    ktx_check_words_top = fields.Float(
        string='Monto en letras — superior (mm)', default=38.0,
        compute='_compute_ktx_check_positions',
        inverse='_inverse_ktx_check_positions',
        store=False,
    )
    ktx_check_words_left = fields.Float(
        string='Monto en letras — izquierda (mm)', default=20.0,
        compute='_compute_ktx_check_positions',
        inverse='_inverse_ktx_check_positions',
        store=False,
    )
    ktx_check_nonneg_top = fields.Float(
        string='NO NEGOCIABLE — superior (mm)', default=48.0,
        compute='_compute_ktx_check_positions',
        inverse='_inverse_ktx_check_positions',
        store=False,
    )
    ktx_check_nonneg_left = fields.Float(
        string='NO NEGOCIABLE — izquierda (mm)', default=20.0,
        compute='_compute_ktx_check_positions',
        inverse='_inverse_ktx_check_positions',
        store=False,
    )

    def _compute_ktx_check_positions(self):
        get = self.env['ir.config_parameter'].sudo().get_param
        for company in self:
            for fname, pkey, default in _POS_FIELDS:
                raw = get(_POS_PARAM.format(pkey, company.id))
                company[fname] = float(raw) if raw else default

    def _inverse_ktx_check_positions(self):
        set_param = self.env['ir.config_parameter'].sudo().set_param
        for company in self:
            for fname, pkey, _default in _POS_FIELDS:
                set_param(_POS_PARAM.format(pkey, company.id), str(company[fname]))
