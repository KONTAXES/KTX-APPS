# -*- coding: utf-8 -*-
from . import models


def post_init_hook(env):
    """Crea las secuencias del modulo si no existen (auto-sanacion en install y upgrade)."""
    seq = env['ir.sequence'].sudo()
    sequences = [
        {
            'name': 'KTX Importacion Masiva FEL',
            'code': 'ktx.import.session',
            'prefix': 'IMP/%(year)s/%(month)s/',
            'padding': 4,
        },
    ]
    for vals in sequences:
        if not seq.search([('code', '=', vals['code'])], limit=1):
            seq.create({**vals, 'number_next': 1, 'number_increment': 1, 'company_id': False})
