# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    ktx_fel_format_style = fields.Selection(
        selection_add=[('ktx5', 'KTX 5')],
        ondelete={'ktx5': 'set default'},
    )
