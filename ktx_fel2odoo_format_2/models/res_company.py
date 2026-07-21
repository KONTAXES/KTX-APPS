# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    ktx_fel_format_style = fields.Selection(
        selection_add=[('ktx3', 'KTX 3')],
        ondelete={'ktx3': 'set default'},
    )
