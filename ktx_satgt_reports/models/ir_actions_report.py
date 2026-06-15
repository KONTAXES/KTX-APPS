# -*- coding: utf-8 -*-
from odoo import models


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _build_wkhtmltopdf_args(self, *args, **kwargs):
        command_args = super()._build_wkhtmltopdf_args(*args, **kwargs)
        folio_start = self.env.context.get('satgt_folio_start')
        if folio_start is not None and isinstance(command_args, list):
            offset = max(0, int(folio_start) - 1)
            command_args += [
                '--header-right', 'FOLIO No. [page]',
                '--header-font-size', '8',
                '--header-spacing', '3',
            ]
            if offset:
                command_args += ['--page-offset', str(offset)]
        return command_args
