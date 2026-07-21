# -*- coding: utf-8 -*-
"""Asistente "Consultar NIT": ingresa un NIT, consulta a la SAT (via
apifelcore, endpoint agencia-virtual/nombre-receptor) y muestra el nombre
oficial. Permite crear un contacto nuevo con ese nombre o actualizar uno
existente.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class KtxFel2odooNitWizard(models.TransientModel):
    _name = 'ktx.fel2odoo.nit.wizard'
    _description = 'Consultar NIT en la SAT (FEL2Odoo)'

    config_id = fields.Many2one(
        'ktx.fel2odoo.config', string='Conexion', required=True,
        default=lambda self: self.env['ktx.fel2odoo.config'].search(
            [('active', '=', True)], limit=1),
    )
    company_id = fields.Many2one(
        'res.company', related='config_id.company_id', readonly=True)
    nit = fields.Char(string='NIT', required=True,
                      help='NIT a consultar en la SAT.')
    nombre = fields.Char(string='Nombre segun SAT', readonly=True)
    partner_id = fields.Many2one(
        'res.partner', string='Contacto a actualizar',
        help='Opcional: si eliges un contacto, se actualiza su nombre con el '
             'resultado. Si lo dejas vacio, puedes crear uno nuevo.')
    state = fields.Selection(
        [('input', 'Ingreso'), ('done', 'Resultado')],
        default='input')

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_query(self):
        self.ensure_one()
        if not self.nit or not self.nit.strip():
            raise UserError(_('Ingrese un NIT.'))
        config = self.config_id or self.env['ktx.fel2odoo.config']._get_query_config(
            self.env.company)
        nombre = config._consultar_nombre_receptor(self.nit)
        if not nombre:
            raise UserError(_(
                'La SAT no devolvio un nombre para el NIT "%s". Verifiquelo.'
            ) % self.nit)
        self.write({'nombre': nombre, 'state': 'done'})
        return self._reopen()

    def action_reset(self):
        self.ensure_one()
        self.write({'nombre': False, 'state': 'input'})
        return self._reopen()

    def action_apply_to_partner(self):
        """Actualiza el nombre del contacto elegido con el resultado."""
        self.ensure_one()
        if not self.nombre:
            raise UserError(_('Primero consulte el NIT.'))
        if not self.partner_id:
            raise UserError(_('Elija un contacto a actualizar o use "Crear contacto".'))
        anterior = self.partner_id.name or ''
        self.partner_id.name = self.nombre
        self.partner_id.message_post(body=_(
            'Nombre actualizado desde la SAT (NIT %(nit)s): <b>%(nuevo)s</b> '
            '(antes: %(anterior)s)') % {
                'nit': self.nit, 'nuevo': self.nombre,
                'anterior': anterior or _('(vacio)')})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'res_id': self.partner_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_create_partner(self):
        """Crea un contacto nuevo con el nombre resuelto y el NIT consultado."""
        self.ensure_one()
        if not self.nombre:
            raise UserError(_('Primero consulte el NIT.'))
        partner = self.env['res.partner'].create({
            'name': self.nombre,
            'vat': (self.nit or '').strip(),
            'is_company': True,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'res_id': partner.id,
            'view_mode': 'form',
            'target': 'current',
        }
