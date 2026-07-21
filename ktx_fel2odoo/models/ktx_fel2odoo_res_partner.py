# -*- coding: utf-8 -*-
"""Boton inteligente "NIT FEL2ODOO" en el contacto.

Consulta a la SAT (via apifelcore, endpoint agencia-virtual/nombre-receptor) el
nombre oficial asociado al NIT del contacto y actualiza su nombre. Es un
boton EXPLICITO (no un onchange sobre el campo NIT/vat) para no interferir con
otros modulos que ya reaccionan a ese campo.
"""
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    ktx_fel_nit_button_visible = fields.Boolean(
        string='Mostrar boton NIT FEL2Odoo',
        compute='_compute_ktx_fel_nit_button_visible',
        help='True si hay una conexion FEL2Odoo activa para la empresa con el '
             'boton "NIT FEL2ODOO" habilitado.')

    @api.depends('company_id')
    @api.depends_context('company')
    def _compute_ktx_fel_nit_button_visible(self):
        # sudo: la visibilidad la puede evaluar cualquier usuario que edite el
        # contacto (ventas, etc.), aunque no tenga acceso al modelo de conexion.
        Config = self.env['ktx.fel2odoo.config'].sudo()
        for partner in self:
            company = partner.company_id or self.env.company
            partner.ktx_fel_nit_button_visible = bool(Config.search_count([
                ('company_id', '=', company.id),
                ('active', '=', True),
                ('enable_nit_button', '=', True),
            ]))

    def action_ktx_fel_consultar_nit(self):
        """Consulta el nombre oficial del NIT del contacto y lo actualiza."""
        self.ensure_one()
        nit = (self.vat or '').strip()
        if not nit:
            raise UserError(_(
                'Este contacto no tiene NIT (campo NIF/RFC). Ingreselo primero '
                'y vuelva a pulsar "NIT FEL2ODOO".'))
        company = self.company_id or self.env.company
        config = self.env['ktx.fel2odoo.config']._get_query_config(company)
        nombre = config._consultar_nombre_receptor(nit)
        if not nombre:
            raise UserError(_(
                'La SAT no devolvio un nombre para el NIT "%s". Verifique '
                'que este bien escrito.') % nit)

        anterior = self.name or ''
        if nombre == anterior:
            return self._ktx_fel_nit_notification(
                _('El nombre ya coincide con el registrado en la SAT: %s') % nombre,
                'info')
        self.name = nombre
        self.message_post(body=_(
            'Nombre actualizado desde la SAT (NIT %(nit)s): '
            '<b>%(nuevo)s</b> (antes: %(anterior)s)') % {
                'nit': nit,
                'nuevo': nombre,
                'anterior': anterior or _('(vacio)'),
            })
        return self._ktx_fel_nit_notification(
            _('Nombre actualizado a: %s') % nombre, 'success')

    def _ktx_fel_nit_notification(self, message, ntype):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Consulta NIT FEL2Odoo'),
                'message': message,
                'type': ntype,
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
