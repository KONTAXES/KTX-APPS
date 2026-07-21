# -*- coding: utf-8 -*-
"""Configuracion de emision FEL2Odoo por diario de VENTAS.

Cada diario de venta decide, de forma independiente, si sus facturas se
certifican ante la SAT con el proveedor configurado en FEL2Odoo, con que
establecimiento, que tipo de documento, y si se certifica automaticamente
al confirmar o solo con el boton manual.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    ktx_fel2odoo_enabled = fields.Boolean(
        'Certificar con FEL2Odoo', default=False, tracking=True,
        help='Marca este diario de VENTAS para emitir (certificar ante la '
             'SAT) las facturas confirmadas en el, usando el proveedor '
             'configurado en FEL2Odoo. Solo aplica a diarios de tipo Venta.'
    )
    ktx_fel2odoo_establecimiento = fields.Char(
        'Codigo de establecimiento SAT', default='1',
        help='Codigo de establecimiento registrado ante la SAT para las '
             'facturas emitidas desde este diario.'
    )
    ktx_fel2odoo_tipo_documento = fields.Selection([
        ('FACT', 'Factura (FACT)'),
        ('FESP', 'Factura Especial (FESP)'),
        ('FCAM', 'Factura Cambiaria (FCAM)'),
        ('NDEB', 'Nota de Debito (NDEB)'),
        ('NCRE', 'Nota de Credito (NCRE)'),
        ('FAEX', 'Factura de Exportacion (FAEX)'),
    ], string='Tipo de documento FEL', default='FACT',
        help='Tipo de documento que se emite desde este diario. Por ahora '
             'FEL2Odoo solo puede EMITIR el tipo FACT: el proveedor no '
             'documenta como indicar otro tipo ni referenciar un documento '
             'original (necesario para NCRE/NDEB). Los demas tipos quedan '
             'pendientes de confirmar con el proveedor antes de habilitarse.'
    )
    ktx_fel2odoo_auto_certificar = fields.Boolean(
        'Certificar automaticamente al confirmar', default=False,
        help='Si esta ACTIVO, al CONFIRMAR (publicar) una factura en este '
             'diario se envia automaticamente a certificar ante la SAT. Si '
             'esta INACTIVO, debe pulsar el boton "Emitir ante la SAT '
             '(FEL2Odoo)" manualmente despues de confirmar. Si la '
             'certificacion automatica falla, la factura queda publicada '
             'igual (no se revierte); el error queda en la factura para '
             'reintentar manualmente.'
    )

    @api.constrains('ktx_fel2odoo_enabled', 'ktx_fel2odoo_tipo_documento', 'type')
    def _check_ktx_fel2odoo_scope(self):
        for journal in self:
            if not journal.ktx_fel2odoo_enabled:
                continue
            if journal.type != 'sale':
                raise ValidationError(_(
                    'FEL2Odoo solo puede certificar diarios de tipo VENTA.'))
            if journal.ktx_fel2odoo_tipo_documento != 'FACT':
                raise ValidationError(_(
                    'Por ahora FEL2Odoo solo puede EMITIR el tipo de '
                    'documento FACT (factura normal). El proveedor no '
                    'documenta como emitir "%s"; queda pendiente de '
                    'confirmar con el antes de habilitarse.'
                ) % journal.ktx_fel2odoo_tipo_documento)
