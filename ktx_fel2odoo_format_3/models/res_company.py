# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    ktx_fel_format_style = fields.Selection(
        selection_add=[('ktx4', 'KTX 4')],
        ondelete={'ktx4': 'set default'},
    )
