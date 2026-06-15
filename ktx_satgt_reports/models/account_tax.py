# -*- coding: utf-8 -*-
from odoo import api, fields, models

SAT_BOOK_CATEGORIES = [
    ('iva_ventas',          'IVA Ventas'),
    ('iva_compras',         'IVA Compras'),
    ('iva_retencion',       'IVA Retencion Recibida'),
    ('isr_retencion',       'ISR Retencion Recibida'),
    ('pequeno_cont',        'Pequeno Contribuyente'),
    ('local_grav_bienes',   'Local - Gravada Bienes'),
    ('local_grav_serv',     'Local - Gravada Servicios'),
    ('local_exe_bienes',    'Local - Exenta Bienes'),
    ('local_exe_serv',      'Local - Exenta Servicios'),
    ('import_grav_bienes',  'Importacion - Gravada Bienes'),
    ('import_grav_serv',    'Importacion - Gravada Servicios'),
    ('import_exe_bienes',   'Importacion - Exenta Bienes'),
    ('import_exe_serv',     'Importacion - Exenta Servicios'),
    ('no_afecto',           'No Afecto / Sin Clasificacion'),
]


class AccountTax(models.Model):
    _inherit = 'account.tax'

    ktx_satgt_category = fields.Selection(
        SAT_BOOK_CATEGORIES,
        string='Categoría SAT GT (legacy)',
        help='Clasificación legacy. Los switches de abajo tienen prioridad cuando '
             '"Incluir en Libros SAT" está activo.',
    )

    # ── Switches granulares para libros SAT GT ────────────────────────────────
    ktx_include_in_report = fields.Boolean(
        string='Incluir en Libros SAT',
        help='Activo: este impuesto determina la columna del libro de compras/ventas. '
             'Si ningún impuesto de la línea tiene este switch, se usa la clasificación legacy.',
    )
    ktx_is_import = fields.Boolean(
        string='Importación / Exportación',
        help='Activo = columnas Importación/Exportación. Inactivo = columnas Local.',
    )
    ktx_is_exento = fields.Boolean(
        string='Exento / No Gravado',
        help='Activo = columna Exenta. Inactivo = columna Gravada.',
    )
    ktx_is_iva = fields.Boolean(
        string='Es IVA (12%)',
        help='El monto cobrado por este impuesto va a la columna IVA del libro.',
    )
    ktx_is_combustible = fields.Boolean(
        string='Es Combustible / IPCN',
        help='Impuesto de distribución de combustibles. El monto va a la columna '
             'Exenta del libro (no genera crédito fiscal).',
    )
    ktx_is_pequeno = fields.Boolean(
        string='Pequeño Contribuyente',
        help='Las facturas con este impuesto van íntegramente a la columna '
             'Pequeño Contribuyente.',
    )
    ktx_is_otro = fields.Boolean(
        string='Otro Impuesto (no IVA)',
        help='Otros cargos adicionales (timbres, tasas, etc.). El monto va a la '
             'columna Exenta del libro.',
    )


class KtxSatgtTaxConfig(models.Model):
    _name = 'ktx.satgt.tax.config'
    _description = 'Categorias SAT GT - Configuracion de Impuestos'
    _order = 'company_id, category'

    company_id = fields.Many2one(
        'res.company', string='Empresa', required=True,
        default=lambda self: self.env.company,
        ondelete='cascade',
    )
    category = fields.Selection(SAT_BOOK_CATEGORIES, string='Categoria SAT GT', required=True)
    tax_id = fields.Many2one(
        'account.tax', string='Impuesto', required=True,
        domain="[('company_id', '=', company_id)]",
        ondelete='cascade', index=True,
    )

    @api.model
    def action_auto_detect(self):
        from ..hooks import auto_detect_sat_categories
        total = auto_detect_sat_categories(self.env, update_existing=True)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Auto-deteccion completada',
                'message': (f'Se procesaron {total} impuestos.'
                            if total else 'No hay cambios pendientes.'),
                'type': 'success' if total else 'info',
                'sticky': False,
            },
        }
