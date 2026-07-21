# -*- coding: utf-8 -*-
"""Bitacora de corridas de sincronizacion FEL2Odoo."""
from odoo import fields, models


class KtxFel2odooLog(models.Model):
    _name = 'ktx.fel2odoo.log'
    _description = 'Bitacora Sincronizacion FEL2Odoo'
    _inherit = ['mail.thread']
    _order = 'create_date desc'
    _rec_name = 'create_date'

    config_id = fields.Many2one(
        'ktx.fel2odoo.config', string='Configuracion', required=True,
        ondelete='cascade', index=True,
    )
    company_id = fields.Many2one('res.company', string='Empresa', index=True)
    tipo_operacion = fields.Selection(
        [('EMITIDOS', 'Ventas (Emitidos)'), ('RECIBIDOS', 'Compras (Recibidos)')],
        string='Operacion',
    )
    date_from = fields.Date('Desde')
    date_to = fields.Date('Hasta')
    state = fields.Selection(
        [('running', 'En proceso'), ('success', 'Exito'),
         ('error', 'Error')],
        string='Estado', default='running',
    )
    docs_found = fields.Integer('Documentos encontrados')
    docs_skipped = fields.Integer('Omitidos')
    invoices_created = fields.Integer('Facturas creadas')
    invoices_confirmed = fields.Integer('Facturas confirmadas')
    session_id = fields.Many2one('ktx.import.session', string='Sesion de importacion')
    message = fields.Text('Detalle')
    raw_response = fields.Text(
        'Respuesta del proveedor', copy=False,
        help='Respuesta cruda de consultar-documentos, para diagnostico.')

    def action_open_session(self):
        self.ensure_one()
        if not self.session_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ktx.import.session',
            'res_id': self.session_id.id,
            'view_mode': 'form',
        }
