# -*- coding: utf-8 -*-
"""Pide el motivo de anulacion antes de anular una factura ante la SAT.

El endpoint /agencia-virtual/anular-documento exige una observacion. El
motivo es OPCIONAL en el wizard: si se deja vacio se envia el generico
"Anular documento"; si se escribe algo, se envia exactamente eso.
"""
from odoo import _, fields, models


class KtxFel2odooCancelWizard(models.TransientModel):
    _name = 'ktx.fel2odoo.cancel.wizard'
    _description = 'Anular factura FEL2Odoo ante la SAT'

    move_id = fields.Many2one(
        'account.move', string='Factura', required=True, readonly=True)
    fel2odoo_uuid = fields.Char(related='move_id.fel2odoo_uuid', readonly=True)
    motivo = fields.Char(
        'Motivo de anulacion',
        help='Si se deja vacio se enviara el motivo generico "Anular documento".')

    def action_confirm(self):
        self.ensure_one()
        move = self.move_id
        motivo_final = (self.motivo or '').strip() or _('Anular documento')
        Config = self.env['ktx.fel2odoo.config']
        config = Config._get_emision_config(move.company_id)
        config.with_company(move.company_id)._anular_documento(move, motivo_final)
        move.write({'fel2odoo_state': 'anulado'})
        move.message_post(body=_(
            'Factura anulada ante la SAT por FEL2Odoo. Motivo: %s') % motivo_final)
        # Con el estado ya en 'anulado', el override de button_cancel de este
        # modulo ya no intercepta: se completa la cancelacion normal de Odoo.
        if move.state != 'cancel':
            move.button_cancel()
        return config._notify(
            _('Factura anulada'),
            _('Factura %s anulada ante la SAT y cancelada en Odoo.') % move.name, 'success')
