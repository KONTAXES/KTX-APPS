# -*- coding: utf-8 -*-
import re
import secrets

from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class KtxLoginTheme(models.Model):
    """A full authentication (login/signup/reset) look-and-feel configuration.

    Two kinds of theme coexist:

    - A single default theme (``is_default`` True) applied to every visitor
      who doesn't have a personal theme -- reachable at plain ``/web/login``,
      no link/token needed. Administrator-only, no per-user/per-company
      distinction.
    - Optional personal themes (``user_ids`` set) that override the default
      one only for the specific users assigned to them, reached either via a
      shareable personal link (``login_url``) or automatically once the
      visitor is identified by email. Still admin-only to configure.

    Several themes can exist (drafts, seasonal variants, A/B candidates);
    only one default theme and only one personal theme per user can be
    ``published`` at a time (see ``_check_single_published`` and
    ``action_publish``), and ``get_default``/``get_by_token``/
    ``get_active_for_user`` always degrade gracefully to "no theme" (= stock
    Odoo login) instead of raising, so a bad configuration can never lock
    anyone out.
    """

    _name = "ktx.login.theme"
    _description = "Login Studio - Theme"
    _inherit = ["mail.thread"]
    _order = "sequence, id"

    name = fields.Char(required=True, default="Tema de Login", tracking=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    state = fields.Selection(
        [("draft", "Borrador"), ("published", "Publicado")],
        default="draft", required=True, tracking=True,
        help="Solo el tema Publicado se usa en el login real. Puedes "
             "preparar y previsualizar temas en Borrador sin ningun riesgo.",
    )
    user_ids = fields.Many2many(
        "res.users", string="Usuarios",
        help="Usuarios que veran este tema -- via su enlace de acceso "
             "personal, o automaticamente si su correo ya aparece en la "
             "pantalla de login -- sin afectar al resto. No aplica si "
             "\"Login predeterminado\" esta activo (ese tema se usa para "
             "todos, sin necesidad de asignar usuarios).",
    )
    is_default = fields.Boolean(
        string="Login predeterminado", default=False, tracking=True,
        help="Este tema se usa directamente en /web/login (y en registro/"
             "recuperar contrasena) sin necesidad de ningun enlace ni "
             "token, para cualquier visitante que no tenga un tema "
             "personal propio. Solo un tema puede ser el predeterminado a "
             "la vez. Al activarlo se desactiva la configuracion de enlace "
             "personalizado, ya que no hace falta.",
    )

    # ------------------------------------------------------------------
    # Personal access link (only meaningful when user_ids is set)
    # ------------------------------------------------------------------
    access_token = fields.Char(
        default=lambda self: secrets.token_urlsafe(16), copy=False, readonly=True, required=True,
    )
    slug = fields.Char(
        string="Enlace corto",
        help="Enlace facil de escribir y recordar, por ejemplo 'gutrust' "
             "para que el acceso sea .../web/login/gutrust en vez de un "
             "token largo. Solo letras, numeros, guiones (-) y guiones "
             "bajos (_). Opcional: si lo dejas vacio se usa el enlace con "
             "token de todas formas.",
    )
    login_url = fields.Char(
        string="Enlace de acceso personalizado", compute="_compute_login_url",
        help="Comparte este enlace con los usuarios asignados arriba: "
             "siempre les mostrara este tema al iniciar sesion, sin importar "
             "el tema global de la base de datos.",
    )

    @api.depends("slug", "access_token", "is_default")
    def _compute_login_url(self):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        for record in self:
            if record.is_default:
                record.login_url = "%s/web/login" % base_url
            elif record.slug:
                record.login_url = "%s/web/login/%s" % (base_url, record.slug)
            else:
                record.login_url = "%s/web/login?ktx_t=%s" % (base_url, record.access_token or "")

    _access_token_uniq = models.Constraint(
        "unique(access_token)", "El token de acceso debe ser unico.",
    )
    _slug_uniq = models.Constraint(
        "unique(slug)", "Ese enlace corto ya esta en uso por otro tema.",
    )

    # "totp" is a real Odoo core route (/web/login/totp, two-factor auth);
    # a theme using that slug would be silently unreachable since a static
    # route always wins over our dynamic one, so it's rejected up front
    # instead of leaving a confusing dead link.
    _RESERVED_SLUGS = {"totp"}

    @api.constrains("slug")
    def _check_slug_format(self):
        for record in self:
            if not record.slug:
                continue
            if not re.match(r"^[a-zA-Z0-9_-]+$", record.slug):
                raise ValidationError(
                    "El enlace corto solo puede contener letras, numeros, "
                    "guiones (-) y guiones bajos (_), sin espacios ni simbolos."
                )
            if record.slug in record._RESERVED_SLUGS:
                raise ValidationError(
                    "'%s' esta reservado por Odoo (autenticacion de dos "
                    "factores) y no se puede usar como enlace corto."
                    % record.slug
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("slug"):
                vals["slug"] = vals["slug"].strip().lower()
            if vals.get("is_default"):
                vals["user_ids"] = [(5, 0, 0)]
                vals["slug"] = False
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("slug"):
            vals["slug"] = vals["slug"].strip().lower()
        if vals.get("is_default"):
            vals["user_ids"] = [(5, 0, 0)]
            vals["slug"] = False
        return super().write(vals)

    # ------------------------------------------------------------------
    # Layout engine
    # ------------------------------------------------------------------
    render_mode = fields.Selection(
        [("styled", "Tema visual (colores, fondos, tipografias)"),
         ("custom", "HTML 100% personalizado (desactiva la apariencia por defecto)")],
        default="styled", required=True, tracking=True,
        help="'HTML 100% personalizado' reemplaza toda la cabecera, marca y pie de "
             "pagina de Odoo por tu propio HTML/CSS. El formulario de login en si "
             "(campos, boton, CSRF) nunca se toca, para que el acceso jamas se rompa.",
    )
    template = fields.Selection(
        [("centered", "Tarjeta Centrada"),
         ("split", "Pantalla Dividida"),
         ("fullbleed", "Fondo a Pantalla Completa")],
        default="centered", required=True,
    )
    split_alignment = fields.Selection(
        [("left", "Imagen a la Izquierda"), ("right", "Imagen a la Derecha")],
        default="left",
    )
    custom_body_class = fields.Char(
        string="Clases CSS adicionales en <body>",
        help="Clases extra para enganchar tus propios CSS/JS avanzados.",
    )

    # ------------------------------------------------------------------
    # Card & effects
    # ------------------------------------------------------------------
    card_background_color = fields.Char(default="#FFFFFF")
    card_width = fields.Integer(
        string="Ancho de la tarjeta (px)", default=400,
        help="Ancho maximo de la tarjeta de login. En pantallas pequenas "
             "siempre se adapta al 100%.",
    )
    card_shadow = fields.Selection(
        [("none", "Sin sombra"), ("soft", "Suave"),
         ("medium", "Media"), ("strong", "Pronunciada")],
        string="Sombra de la tarjeta", default="medium", required=True,
    )
    glassmorphism = fields.Boolean(string="Efecto Glassmorphism")
    glassmorphism_blur = fields.Integer(string="Desenfoque (px)", default=10)
    glassmorphism_opacity = fields.Float(string="Opacidad de la tarjeta", default=0.2)
    card_entrance_animation = fields.Selection(
        [("none", "Ninguna"), ("fade", "Aparecer (fade)"),
         ("slide_up", "Deslizar hacia arriba"), ("zoom", "Acercamiento (zoom)"),
         ("bounce", "Rebote")],
        string="Animacion de entrada", default="fade", required=True,
    )
    ambient_glow = fields.Boolean(
        string="Resplandor ambiental",
        help="Halo de luz difuminado detras de la tarjeta, tipo spotlight.",
    )
    ambient_glow_color = fields.Char(string="Color del resplandor", default="#7c3aed")
    ambient_glow_intensity = fields.Selection(
        [("soft", "Suave"), ("medium", "Media"), ("strong", "Intensa")],
        default="medium", required=True,
    )

    # ------------------------------------------------------------------
    # Branding
    # ------------------------------------------------------------------
    company_logo = fields.Binary(string="Logo")
    logo_max_height = fields.Integer(
        string="Alto maximo del logo (px)", default=80,
        help="Tamano del logo dentro de la tarjeta o el panel lateral.",
    )
    favicon = fields.Binary(string="Favicon")
    tagline = fields.Char(string="Eslogan")
    show_portal_name = fields.Boolean(
        string='Mostrar "Accede al portal de: <nombre>"', default=False,
        help='Muestra la frase "Accede al portal de: <nombre>" encima del '
             'formulario, usando el nombre de este tema (campo Nombre, '
             'arriba). En modo "HTML 100% personalizado" no se muestra '
             'automaticamente: usa el texto {{ktx_portal_name}} en la '
             'Cabecera o el Pie de Pagina para insertarlo donde quieras.',
    )

    # ------------------------------------------------------------------
    # Colors & background
    # ------------------------------------------------------------------
    primary_color = fields.Char(default="#714B67", required=True)
    secondary_color = fields.Char(default="#FFFFFF", required=True)
    background_type = fields.Selection(
        [("solid", "Color Solido"), ("gradient", "Degradado"),
         ("animated_gradient", "Degradado Animado"), ("image", "Imagen"),
         ("video", "Video")],
        default="solid", required=True,
    )
    background_color = fields.Char(default="#f8f9fa")
    gradient_start = fields.Char(default="#714B67")
    gradient_end = fields.Char(default="#2B124C")
    gradient_direction = fields.Selection(
        [("to right", "Hacia la derecha"), ("to bottom", "Hacia abajo"),
         ("to bottom right", "Diagonal inferior derecha"),
         ("to bottom left", "Diagonal inferior izquierda")],
        default="to bottom right",
    )
    background_image = fields.Binary(string="Imagen de Fondo")
    background_video = fields.Binary(
        string="Video de Fondo", attachment=True,
        help="Sube aqui un video corto y ligero (recomendado .mp4 o .webm, "
             "que son los que reproducen todos los navegadores; idealmente "
             "menos de 10 MB y en bucle). Se reproduce automaticamente, en "
             "silencio y en bucle como fondo, sin necesidad de la pestana "
             "Extensiones ni de Claude Design.",
    )
    background_video_filename = fields.Char(string="Nombre del video")
    background_video_asset_id = fields.Many2one(
        "ktx.login.asset", string="Video de Fondo (Extension)",
        domain="[('theme_id', '=', id), ('asset_type', '=', 'video'), ('state', '=', 'published')]",
        help="Alternativa avanzada: usa un video ya subido en la pestana "
             "Extensiones. Si subes un video directamente arriba, ese tiene "
             "prioridad sobre este.",
    )
    background_overlay_color = fields.Char(
        string="Color de superposicion", default="#000000",
        help="Capa de color por encima de la imagen o el video de fondo "
             "(para oscurecer o tintar y que el texto se lea mejor). Su "
             "intensidad se controla con la opacidad de abajo.",
    )
    background_overlay_opacity = fields.Float(default=0.3)

    # ------------------------------------------------------------------
    # Typography
    # ------------------------------------------------------------------
    font_family = fields.Selection(
        [("Inter", "Inter"), ("Roboto", "Roboto"), ("Open Sans", "Open Sans"),
         ("Lato", "Lato"), ("Poppins", "Poppins"), ("Georgia", "Georgia"),
         ("system-ui", "Predeterminada del sistema"), ("custom", "Fuente personalizada (subida)")],
        default="Inter", required=True,
    )
    custom_font_asset_id = fields.Many2one(
        "ktx.login.asset", string="Fuente Subida (.woff2)",
        domain="[('theme_id', '=', id), ('asset_type', '=', 'font'), ('state', '=', 'published')]",
    )
    custom_font_css_name = fields.Char(
        string="Nombre CSS de la fuente",
        help='font-family exacto declarado dentro del archivo de fuente, ej. "Acme Sans".',
    )
    text_color = fields.Char(default="#212529", required=True)
    link_color = fields.Char(
        string="Color de enlaces", default="#714B67",
        help='Color de los enlaces del formulario ("Restablecer contrasena", '
             '"No tienes cuenta?", terminos, etc.).',
    )
    input_border_radius = fields.Integer(default=6)
    button_border_radius = fields.Integer(default=6)
    button_color = fields.Char(default="#714B67", required=True)
    button_text_color = fields.Char(default="#FFFFFF", required=True)

    # ------------------------------------------------------------------
    # Input fields & button interaction
    # ------------------------------------------------------------------
    input_style = fields.Selection(
        [("outlined", "Con borde"), ("filled", "Relleno"), ("underline", "Solo linea inferior")],
        default="outlined", required=True,
    )
    input_focus_glow = fields.Boolean(
        string="Resplandor al enfocar campos", default=True,
    )
    input_icons = fields.Boolean(
        string="Iconos en los campos", default=False,
        help="Muestra un icono de correo y de candado dentro de los campos de acceso.",
    )
    button_hover_effect = fields.Selection(
        [("none", "Ninguno"), ("scale", "Escala"), ("glow", "Resplandor"),
         ("shine", "Brillo deslizante")],
        default="scale", required=True,
    )

    # ------------------------------------------------------------------
    # Footer / legal / content
    # ------------------------------------------------------------------
    hide_website_header = fields.Boolean(
        string="Ocultar menu y pie de pagina del sitio web", default=False,
        help="Oculta la barra de navegacion (logo, enlaces, redes sociales) "
             "y el pie de pagina nativo de Odoo (\"Con la tecnologia de "
             "Odoo...\") unicamente en las paginas de login, registro y "
             "recuperacion de contrasena, para que el tema ocupe toda la "
             "pantalla. El resto del sitio web no se ve afectado.",
    )
    show_database_domain = fields.Boolean(
        string="Mostrar dominio de la base de datos", default=True,
        help="Muestra el dominio de esta base de datos (texto plano, sin enlace "
             "para cambiar de base de datos), en vez del enlace 'Administrar "
             "bases de datos' de Odoo.",
    )
    show_powered_by_odoo = fields.Boolean(default=True)
    custom_footer_text = fields.Char()
    login_welcome_title = fields.Char()
    login_welcome_subtitle = fields.Char()
    terms_url = fields.Char(string="URL Terminos de Servicio")
    privacy_url = fields.Char(string="URL Politica de Privacidad")
    terms_label = fields.Char(default="Terminos de Servicio")
    privacy_label = fields.Char(default="Politica de Privacidad")

    # ------------------------------------------------------------------
    # Custom HTML chrome (only used when render_mode == 'custom')
    # ------------------------------------------------------------------
    custom_header_html = fields.Html(
        string="HTML de Cabecera", sanitize=False,
        help="Reemplaza por completo el bloque de marca/cabecera. El formulario "
             "de acceso real siempre se renderiza despues, intacto. Puedes "
             "escribir {{ktx_portal_name}} en cualquier parte y se reemplaza "
             "por el campo Nombre de este tema (util para una frase como "
             "\"Accede al portal de: {{ktx_portal_name}}\").",
    )
    custom_footer_html = fields.Html(
        string="HTML de Pie de Pagina", sanitize=False,
        help="Igual que la Cabecera: tambien admite el texto "
             "{{ktx_portal_name}}.",
    )
    custom_css = fields.Text(
        string="CSS Adicional (en linea)",
        help="Se inyecta despues de todas las hojas de estilo y extensiones. "
             "Para JavaScript, usa la pestana Extensiones (los .js no se aceptan aqui).",
    )

    # ------------------------------------------------------------------
    # Signup / reset password (delegates to auth_signup system parameters)
    # ------------------------------------------------------------------
    auth_signup_uninvited = fields.Selection(
        [("b2b", "Solo por Invitacion (B2B)"), ("b2c", "Registro Libre (B2C)")],
        compute="_compute_auth_settings", inverse="_inverse_auth_signup_uninvited",
    )
    auth_signup_reset_password = fields.Boolean(
        string="Permitir Recuperar Contrasena",
        compute="_compute_auth_settings", inverse="_inverse_auth_signup_reset_password",
    )

    # ------------------------------------------------------------------
    # Extensions (assets)
    # ------------------------------------------------------------------
    asset_ids = fields.One2many("ktx.login.asset", "theme_id", string="Extensiones")
    asset_count = fields.Integer(compute="_compute_asset_count")
    max_asset_size_mb = fields.Integer(
        string="Tamano maximo por archivo (MB)", default=3,
    )

    _background_overlay_opacity_range = models.Constraint(
        "CHECK(background_overlay_opacity >= 0 AND background_overlay_opacity <= 1)",
        "La opacidad de superposicion debe estar entre 0 y 1.",
    )
    _glassmorphism_opacity_range = models.Constraint(
        "CHECK(glassmorphism_opacity >= 0 AND glassmorphism_opacity <= 1)",
        "La opacidad de la tarjeta debe estar entre 0 y 1.",
    )
    _glassmorphism_blur_non_negative = models.Constraint(
        "CHECK(glassmorphism_blur >= 0)", "El desenfoque debe ser positivo o cero.",
    )
    _max_asset_size_positive = models.Constraint(
        "CHECK(max_asset_size_mb > 0)", "El tamano maximo debe ser mayor a cero.",
    )

    def _compute_asset_count(self):
        real_ids = [rec.id for rec in self if isinstance(rec.id, int)]
        counts = self.env["ktx.login.asset"]._read_group(
            [("theme_id", "in", real_ids)], ["theme_id"], ["__count"],
        ) if real_ids else []
        mapped = {theme.id: count for theme, count in counts}
        for record in self:
            record.asset_count = mapped.get(record.id, 0)

    def _compute_auth_settings(self):
        get_param = self.env["ir.config_parameter"].sudo().get_param
        for record in self:
            record.auth_signup_uninvited = get_param("auth_signup.invitation_scope", "b2b")
            record.auth_signup_reset_password = get_param("auth_signup.reset_password", "False").lower() == "true"

    def _inverse_auth_signup_uninvited(self):
        for record in self:
            self.env["ir.config_parameter"].sudo().set_param(
                "auth_signup.invitation_scope", record.auth_signup_uninvited)

    def _inverse_auth_signup_reset_password(self):
        for record in self:
            self.env["ir.config_parameter"].sudo().set_param(
                "auth_signup.reset_password", str(record.auth_signup_reset_password))

    @api.constrains("state", "is_default", "user_ids")
    def _check_single_published(self):
        for record in self:
            if record.state != "published":
                continue
            if record.is_default:
                other = self.search([
                    ("state", "=", "published"), ("is_default", "=", True),
                    ("id", "!=", record.id),
                ], limit=1)
                if other:
                    raise ValidationError(
                        "Ya hay un tema predeterminado publicado (%s). "
                        "Publica este tema para reemplazarlo automaticamente "
                        "en su lugar." % other.name
                    )
            elif record.user_ids:
                other = self.search([
                    ("state", "=", "published"), ("user_ids", "in", record.user_ids.ids),
                    ("id", "!=", record.id),
                ], limit=1)
                if other:
                    shared = other.user_ids & record.user_ids
                    raise ValidationError(
                        "%s ya tiene un tema personal publicado (%s). Publica "
                        "este tema para reemplazarlo automaticamente en su "
                        "lugar." % (shared[:1].name, other.name)
                    )

    def action_publish(self):
        self.ensure_one()
        domain = [("state", "=", "published"), ("id", "!=", self.id)]
        domain += [("is_default", "=", True)] if self.is_default else [("user_ids", "in", self.user_ids.ids)]
        others = self.search(domain)
        others.write({"state": "draft"})
        self.write({"state": "published"})
        if self.is_default:
            self.message_post(body="Tema publicado como predeterminado para todos los visitantes del login.")
        elif self.user_ids:
            self.message_post(body="Tema publicado para: %s." % ", ".join(self.user_ids.mapped("name")))
        else:
            self.message_post(body="Tema publicado.")

    def action_unpublish(self):
        self.write({"state": "draft"})

    def action_save(self):
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_view_assets(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Extensiones - %s" % self.name,
            "res_model": "ktx.login.asset",
            "view_mode": "list,form",
            "domain": [("theme_id", "=", self.id)],
            "context": {"default_theme_id": self.id},
        }

    def _render_custom_html(self, html):
        """Substitute the small set of {{ktx_*}} text placeholders a
        custom_header_html/custom_footer_html author can use, then return
        the result marked safe for unescaped QWeb output. Not a general
        templating engine on purpose: just plain string substitution of a
        known token, so a design can write e.g. "Accede al portal de:
        {{ktx_portal_name}}" once and have it work for every theme without
        hardcoding a name that will go stale.
        """
        # str(), not Markup.replace(): Markup's own .replace() re-escapes
        # the replacement value, which would double-escape the name.
        html = str(html or "")
        html = html.replace("{{ktx_portal_name}}", str(escape(self.name or "")))
        return Markup(html)

    def get_header_html(self):
        """Return the custom header HTML marked safe for unescaped QWeb
        output. Only meaningful when ``render_mode == 'custom'``; content is
        authored exclusively by Settings-level admins (see security.xml)."""
        self.ensure_one()
        return self._render_custom_html(self.custom_header_html)

    def get_footer_html(self):
        self.ensure_one()
        return self._render_custom_html(self.custom_footer_html)

    def get_set_cookie_script(self):
        """Return an inline <script> body (marked safe) that remembers this
        theme's access_token in a "ktx_t" cookie, so a personal theme keeps
        showing when the visitor navigates to /web/signup or
        /web/reset_password even if the query string doesn't carry the
        token through. access_token is generated by secrets.token_urlsafe
        (base64 urlsafe alphabet only), so it never needs JS/HTML escaping.
        """
        self.ensure_one()
        return Markup(
            'document.cookie = "ktx_t=%s; path=/; max-age=86400; SameSite=Lax";'
            % self.access_token
        )

    @api.model
    def get_default(self):
        """Return the published theme marked as "Login predeterminado", or
        an empty recordset if none is published (=> caller must render
        stock Odoo). This is the catch-all fallback: it never returns a
        personal theme, even if one happens to be published too.
        """
        return self.search(
            [("state", "=", "published"), ("active", "=", True), ("is_default", "=", True)],
            order="sequence, id", limit=1,
        )

    @api.model
    def get_by_token(self, token):
        """Resolve a theme from its shareable personal-link token (see
        ``login_url``). Lets a specific user get their own login look via a
        link, without the login page needing to know who they are beforehand.
        """
        if not token:
            return self.browse()
        return self.search(
            [("access_token", "=", token), ("state", "=", "published"), ("active", "=", True)],
            limit=1,
        )

    @api.model
    def get_by_slug(self, slug):
        """Resolve a theme from its short, human-typed link (/web/login/<slug>).
        """
        if not slug:
            return self.browse()
        return self.search(
            [("slug", "=", slug.strip().lower()), ("state", "=", "published"), ("active", "=", True)],
            limit=1,
        )

    @api.model
    def get_user_by_login(self, login):
        """Best-effort user lookup for a not-yet-authenticated visitor who
        is already identified by email (e.g. from an invitation link, or a
        failed-login retry where Odoo re-fills the login field). Used so
        their own personal theme shows up automatically in that case.
        """
        if not login:
            return self.env["res.users"].browse()
        return self.env["res.users"].sudo().search([("login", "=", login)], limit=1)

    @api.model
    def get_current(self, token=None):
        """Resolve whichever theme is currently active for this browser: a
        personal theme via its ``ktx_t`` token (query string or the "ktx_t"
        cookie set once a personal link/email-match resolves -- see
        ``get_set_cookie_script``), falling back to the published default
        theme. Used by routes that serve a fixed, theme-independent URL
        (``/active_logo``, ``/active_favicon``) and therefore don't have
        access to the full login-page context (the "login" QWeb variable)
        to run the complete priority chain used in ``login_layout_studio``
        -- only the token/cookie is available to them.
        """
        return self.get_by_token(token) or self.get_default()

    @api.model
    def get_active_for_user(self, user):
        """Return the published personal theme assigned to ``user``, or an
        empty recordset if none is published for them (=> caller falls back
        to get_default). ``user`` may be an empty recordset.
        """
        if not user:
            return self.browse()
        return self.search(
            [("user_ids", "in", user.ids), ("state", "=", "published"), ("active", "=", True)],
            limit=1,
        )
