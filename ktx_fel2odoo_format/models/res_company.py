# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    ktx_fel_format_enabled = fields.Boolean(
        'Formato FEL GT (KTX)', default=False,
        help='Activa el boton "Imprimir FEL" en las facturas de '
             'venta que tengan un XML de DTE FEL adjunto. Genera un PDF con '
             'formato de factura (datos, items, totales, QR de verificacion '
             'de la SAT) a partir de ese XML.'
    )

    ktx_fel_format_accent_color = fields.Char(
        'Color de acento', default='#e97132',
        help='Color principal del formato (caja DTE, barras de tablas, '
             'barra de totales). Usa un color hexadecimal, ej. #e97132.')

    ktx_fel_format_paper_size = fields.Selection([
        ('carta', 'Carta (8.5 x 11 in)'),
        ('media_carta', 'Media Carta (5.5 x 8.5 in)'),
        ('ticket', 'Ticket (impresora termica, 72mm)'),
    ], string='Tamano de papel', default='carta', required=True,
        help='Tamano de pagina en el que se genera el PDF del Formato FEL GT.')

    ktx_fel_format_style = fields.Selection([
        ('ktx1', 'KTX 1'),
    ], string='Formato/Apariencia', default='ktx1', required=True,
        help='Diseno visual de la factura. Con el tiempo se iran agregando '
             'mas apariencias (KTX2, KTX3...) ademas de esta.')

    @api.constrains('ktx_fel_format_style', 'ktx_fel_format_paper_size')
    def _check_ktx_fel_format_ticket_only_ktx1(self):
        # El tamano Ticket (impresora termica, una sola columna estilo POS)
        # solo esta implementado para la apariencia KTX 1. Las demas
        # apariencias son de pagina completa (Carta / Media Carta).
        for company in self:
            if (company.ktx_fel_format_paper_size == 'ticket'
                    and company.ktx_fel_format_style != 'ktx1'):
                raise ValidationError(_(
                    'El tamano de papel "Ticket" solo esta disponible con la '
                    'apariencia KTX 1. Para la apariencia "%s" elija Carta o '
                    'Media Carta.') % company.ktx_fel_format_style)

    ktx_fel_format_logo_position = fields.Selection([
        ('left', 'Izquierda'),
        ('right', 'Derecha'),
    ], string='Posicion del logo', default='left', required=True,
        help='En que lado del encabezado se muestra el logo grande.')

    ktx_fel_format_logo_source = fields.Selection([
        ('default', 'Logo de la empresa (el mismo de Odoo)'),
        ('custom', 'Otro logo (subido aqui)'),
    ], string='Logo a usar', default='default', required=True)

    ktx_fel_format_logo = fields.Binary(
        'Logo personalizado', attachment=True,
        help='Se usa en vez del logo de la empresa cuando "Logo a usar" esta '
             'en "Otro logo". Se recomienda una imagen cuadrada o apaisada, '
             'fondo transparente.')
    ktx_fel_format_logo_filename = fields.Char('Nombre del archivo (logo)')

    ktx_fel_format_side_image = fields.Binary(
        'Imagen lateral', attachment=True,
        help='Opcional. Si se sube, se muestra como un panel lateral que '
             'ocupa el alto de la pagina (como una foto decorativa). Si no '
             'se sube ninguna, no se reserva espacio y la factura usa todo '
             'el ancho de la pagina.')
    ktx_fel_format_side_image_filename = fields.Char('Nombre del archivo (imagen lateral)')

    ktx_fel_format_background_image = fields.Binary(
        'Imagen de fondo (marca de agua)', attachment=True,
        help='Opcional. Si se sube, se muestra de fondo cubriendo toda la '
             'pagina, muy tenue (aclarada), como marca de agua. Para que '
             'encaje bien sin deformarse, usa una imagen con la misma '
             'proporcion de una hoja carta (8.5 x 11 in, proporcion '
             '1:1.294): se ajusta al tamano de la pagina recortando el '
             'sobrante solo si la proporcion no coincide exactamente. Si no '
             'se sube ninguna, la pagina queda blanca.')
    ktx_fel_format_background_filename = fields.Char('Nombre del archivo (fondo)')

    ktx_fel_format_show_footer = fields.Boolean(
        'Mostrar membrete/pie de pagina', default=False,
        help='Agrega un pie de pagina con una descripcion adicional y/o '
             'redes sociales, debajo del detalle de la factura.')
    ktx_fel_format_footer_description = fields.Text(
        'Descripcion adicional',
        help='Texto libre que se muestra en el pie de pagina (por ejemplo, '
             'un eslogan, horario de atencion, o alguna leyenda de la '
             'empresa).')
    ktx_fel_format_social_website = fields.Char('Sitio web')
    ktx_fel_format_social_phone = fields.Char('Telefono')
    ktx_fel_format_social_email = fields.Char('Correo de contacto')
    ktx_fel_format_social_facebook = fields.Char('Facebook')
    ktx_fel_format_social_instagram = fields.Char('Instagram')
    ktx_fel_format_social_x = fields.Char('X / Twitter')

    def _ktx_fel_format_effective_logo(self):
        """Binary del logo a usar en el reporte segun la configuracion:
        el personalizado si se eligio y existe, si no el de la empresa."""
        self.ensure_one()
        if self.ktx_fel_format_logo_source == 'custom' and self.ktx_fel_format_logo:
            return self.ktx_fel_format_logo
        return self.logo
