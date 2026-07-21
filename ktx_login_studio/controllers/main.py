# -*- coding: utf-8 -*-
import base64
from urllib.parse import urlencode

from markupsafe import Markup

from odoo import http
from odoo.http import request

FONT_MAP = {
    "system-ui": 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    "Inter": '"Inter", sans-serif',
    "Roboto": '"Roboto", sans-serif',
    "Open Sans": '"Open Sans", sans-serif',
    "Lato": '"Lato", sans-serif',
    "Poppins": '"Poppins", sans-serif',
    "Georgia": "Georgia, serif",
}


class KtxLoginStudioController(http.Controller):
    _ALLOWED_IMAGE_FIELDS = {"company_logo", "favicon", "background_image"}

    @staticmethod
    def _safe_int(value, default=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _font_css(self, theme_dict):
        if theme_dict.get("font_family") == "custom" and theme_dict.get("custom_font_css_name"):
            return '"%s", sans-serif' % theme_dict["custom_font_css_name"]
        return FONT_MAP.get(theme_dict.get("font_family"), FONT_MAP["system-ui"])

    @staticmethod
    def _font_face_css(theme):
        if (theme.font_family == "custom" and theme.custom_font_asset_id
                and theme.custom_font_asset_id.state == "published" and theme.custom_font_css_name):
            return "@font-face { font-family: '%s'; src: url('%s'); font-display: swap; }" % (
                theme.custom_font_css_name, theme.custom_font_asset_id.get_public_url(),
            )
        return ""

    def _build_background_css(self, cfg):
        bg_type = cfg.get("background_type")
        if bg_type == "solid":
            return "background: %s !important;" % (cfg.get("background_color") or "#f8f9fa")
        if bg_type == "gradient":
            return "background: linear-gradient(%s, %s, %s) !important;" % (
                cfg.get("gradient_direction") or "to bottom right",
                cfg.get("gradient_start") or "#714B67",
                cfg.get("gradient_end") or "#2B124C",
            )
        if bg_type == "animated_gradient":
            return (
                "background: linear-gradient(-45deg, %s, %s, %s) !important; "
                "background-size: 400%% 400%% !important; "
                "animation: ktxGradientAnim 15s ease infinite !important;"
            ) % (
                cfg.get("gradient_start") or "#714B67",
                cfg.get("gradient_end") or "#2B124C",
                cfg.get("primary_color") or "#714B67",
            )
        if bg_type == "image":
            return (
                "background: url('/ktx_login_studio/image/background_image?theme_id=%s') "
                "no-repeat center center fixed !important; background-size: cover !important;"
            ) % cfg.get("theme_id")
        if bg_type == "video":
            # The <video> element (see login_templates.xml) is what actually
            # shows; this is just the base colour behind it while it loads.
            return "background: %s !important;" % (cfg.get("background_color") or "#000000")
        return ""

    _CARD_SHADOW_CSS = {
        "none": "none",
        "soft": "0 4px 12px rgba(0, 0, 0, 0.06)",
        "medium": "0 10px 30px rgba(0, 0, 0, 0.08)",
        "strong": "0 20px 50px rgba(0, 0, 0, 0.28)",
    }

    def _inline_style(self, cfg):
        return """
        @keyframes ktxGradientAnim {
            0%% { background-position: 0%% 50%%; }
            50%% { background-position: 100%% 50%%; }
            100%% { background-position: 0%% 50%%; }
        }
        :root {
            --ktx-primary: %(primary_color)s;
            --ktx-secondary: %(secondary_color)s;
            --ktx-overlay-color: %(background_overlay_color)s;
            --ktx-overlay-opacity: %(background_overlay_opacity)s;
            --ktx-font: %(font_css)s;
            --ktx-text-color: %(text_color)s;
            --ktx-link-color: %(link_color)s;
            --ktx-card-bg: %(card_background_color)s;
            --ktx-card-width: %(card_width)spx;
            --ktx-card-shadow: %(card_shadow)s;
            --ktx-logo-height: %(logo_max_height)spx;
            --ktx-glass-blur: %(glassmorphism_blur)spx;
            --ktx-glass-opacity: %(glassmorphism_opacity)s;
            --ktx-input-radius: %(input_border_radius)spx;
            --ktx-btn-radius: %(button_border_radius)spx;
            --ktx-btn-color: %(button_color)s;
            --ktx-btn-text: %(button_text_color)s;
        }
        %(font_face_css)s
        .ktx-login-wrap.ktx-template-centered, .ktx-login-wrap.ktx-template-fullbleed { %(bg_css)s }
        .ktx-login-wrap.ktx-template-split .ktx-split-aside { %(bg_css)s }
        %(custom_css)s
        """ % {
            "font_face_css": cfg.get("font_face_css") or "",
            "primary_color": cfg.get("primary_color") or "#714B67",
            "secondary_color": cfg.get("secondary_color") or "#FFFFFF",
            "background_overlay_color": cfg.get("background_overlay_color") or "#000000",
            "background_overlay_opacity": cfg.get("background_overlay_opacity") or "0.3",
            "font_css": self._font_css(cfg),
            "text_color": cfg.get("text_color") or "#212529",
            "link_color": cfg.get("link_color") or cfg.get("primary_color") or "#714B67",
            "card_background_color": cfg.get("card_background_color") or "#FFFFFF",
            "card_width": cfg.get("card_width") or "400",
            "card_shadow": self._CARD_SHADOW_CSS.get(cfg.get("card_shadow") or "medium", self._CARD_SHADOW_CSS["medium"]),
            "logo_max_height": cfg.get("logo_max_height") or "80",
            "glassmorphism_blur": cfg.get("glassmorphism_blur") or "10",
            "glassmorphism_opacity": cfg.get("glassmorphism_opacity") or "0.2",
            "input_border_radius": cfg.get("input_border_radius") or "6",
            "button_border_radius": cfg.get("button_border_radius") or "6",
            "button_color": cfg.get("button_color") or "#714B67",
            "button_text_color": cfg.get("button_text_color") or "#FFFFFF",
            "bg_css": self._build_background_css(cfg),
            "custom_css": cfg.get("custom_css") or "",
        }

    # ------------------------------------------------------------------
    # Live preview (backend, authenticated) used by the Login Studio widget
    # ------------------------------------------------------------------
    @http.route("/ktx_login_studio/preview", type="http", auth="user")
    def preview(self, page="login", theme_id=None, **kwargs):
        if not request.env.user.has_group("base.group_system"):
            return request.not_found()
        theme = request.env["ktx.login.theme"].sudo().browse(self._safe_int(theme_id))
        if not theme.exists():
            return request.not_found()

        cfg = {
            "theme_id": theme.id,
            "template": kwargs.get("template", theme.template),
            "render_mode": kwargs.get("render_mode", theme.render_mode),
            "tagline": kwargs.get("tagline", theme.tagline or ""),
            "primary_color": kwargs.get("primary_color", theme.primary_color),
            "secondary_color": kwargs.get("secondary_color", theme.secondary_color),
            "background_type": kwargs.get("background_type", theme.background_type),
            "background_color": kwargs.get("background_color", theme.background_color),
            "gradient_start": kwargs.get("gradient_start", theme.gradient_start),
            "gradient_end": kwargs.get("gradient_end", theme.gradient_end),
            "gradient_direction": kwargs.get("gradient_direction", theme.gradient_direction),
            "background_overlay_color": kwargs.get("background_overlay_color", theme.background_overlay_color),
            "background_overlay_opacity": kwargs.get(
                "background_overlay_opacity", str(theme.background_overlay_opacity)),
            "has_background_video": bool(theme.background_video),
            "font_family": kwargs.get("font_family", theme.font_family),
            "custom_font_css_name": kwargs.get("custom_font_css_name", theme.custom_font_css_name),
            "text_color": kwargs.get("text_color", theme.text_color),
            "link_color": kwargs.get("link_color", theme.link_color),
            "card_width": kwargs.get("card_width", str(theme.card_width)),
            "card_shadow": kwargs.get("card_shadow", theme.card_shadow),
            "logo_max_height": kwargs.get("logo_max_height", str(theme.logo_max_height)),
            "input_border_radius": kwargs.get("input_border_radius", str(theme.input_border_radius)),
            "button_border_radius": kwargs.get("button_border_radius", str(theme.button_border_radius)),
            "button_color": kwargs.get("button_color", theme.button_color),
            "button_text_color": kwargs.get("button_text_color", theme.button_text_color),
            "show_database_domain": (
                kwargs.get("show_database_domain") == "true" if "show_database_domain" in kwargs
                else theme.show_database_domain),
            "hide_website_header": (
                kwargs.get("hide_website_header") == "true" if "hide_website_header" in kwargs
                else theme.hide_website_header),
            "db": request.db,
            "host": request.httprequest.host,
            "show_powered_by_odoo": (
                kwargs.get("show_powered_by_odoo") == "true" if "show_powered_by_odoo" in kwargs
                else theme.show_powered_by_odoo),
            "split_alignment": kwargs.get("split_alignment", theme.split_alignment or "left"),
            "card_background_color": kwargs.get("card_background_color", theme.card_background_color),
            "glassmorphism": (
                kwargs.get("glassmorphism") == "true" if "glassmorphism" in kwargs
                else theme.glassmorphism),
            "glassmorphism_blur": kwargs.get("glassmorphism_blur", str(theme.glassmorphism_blur)),
            "glassmorphism_opacity": kwargs.get("glassmorphism_opacity", str(theme.glassmorphism_opacity)),
            "custom_footer_text": kwargs.get("custom_footer_text", theme.custom_footer_text or ""),
            "login_welcome_title": kwargs.get("login_welcome_title", theme.login_welcome_title or ""),
            "login_welcome_subtitle": kwargs.get("login_welcome_subtitle", theme.login_welcome_subtitle or ""),
            "terms_url": kwargs.get("terms_url", theme.terms_url or ""),
            "privacy_url": kwargs.get("privacy_url", theme.privacy_url or ""),
            "terms_label": kwargs.get("terms_label", theme.terms_label or "Terms of Service"),
            "privacy_label": kwargs.get("privacy_label", theme.privacy_label or "Privacy Policy"),
            "custom_body_class": kwargs.get("custom_body_class", theme.custom_body_class or ""),
            "custom_css": kwargs.get("custom_css", theme.custom_css or ""),
            "custom_header_html": theme.get_header_html(),
            "custom_footer_html": theme.get_footer_html(),
            "company_logo": bool(theme.company_logo),
            "is_preview": True,
            "page": page,
            "name": theme.name,
            "show_portal_name": (
                kwargs.get("show_portal_name") == "true" if "show_portal_name" in kwargs
                else theme.show_portal_name),
            "card_entrance_animation": kwargs.get("card_entrance_animation", theme.card_entrance_animation),
            "ambient_glow": (
                kwargs.get("ambient_glow") == "true" if "ambient_glow" in kwargs
                else theme.ambient_glow),
            "ambient_glow_color": kwargs.get("ambient_glow_color", theme.ambient_glow_color),
            "ambient_glow_intensity": kwargs.get("ambient_glow_intensity", theme.ambient_glow_intensity),
            "input_style": kwargs.get("input_style", theme.input_style),
            "input_focus_glow": (
                kwargs.get("input_focus_glow") == "true" if "input_focus_glow" in kwargs
                else theme.input_focus_glow),
            "input_icons": (
                kwargs.get("input_icons") == "true" if "input_icons" in kwargs
                else theme.input_icons),
            "button_hover_effect": kwargs.get("button_hover_effect", theme.button_hover_effect),
        }
        cfg["font_face_css"] = self._font_face_css(theme)
        # Markup, not a plain str: this is server-generated CSS text embedded
        # via t-out inside a <style> tag. t-out HTML-escapes plain strings
        # (quotes in font-family values, etc.), and browsers never decode
        # HTML entities inside <style>/<script>, so an escaped value would
        # just be invalid, broken CSS on arrival.
        cfg["inline_style"] = Markup(self._inline_style(cfg))

        head_assets = theme.asset_ids.filtered(
            lambda a: a.active and a.state == "published" and a.target == "head"
            and a.scope in ("all", page)
        ).sorted("sequence")
        body_assets = theme.asset_ids.filtered(
            lambda a: a.active and a.state == "published" and a.target == "body_end"
            and a.scope in ("all", page)
        ).sorted("sequence")

        # Rendered as a fully self-contained mock page (not through
        # web.login_layout / website.layout): when the website module is
        # installed it extends web.login_layout to wrap the real page in
        # website.layout, which expects a large amount of frontend context
        # (lang, editable, translatable, frontend_languages...) normally
        # only populated by the website module's own request dispatch. This
        # preview is admin-only and cosmetic, so it renders its own minimal
        # markup with the same theme CSS instead of fighting that pipeline.
        qcontext = {"ktx": cfg, "ktx_head_assets": head_assets, "ktx_body_assets": body_assets}
        return request.render("ktx_login_studio.preview_page", qcontext)

    # ------------------------------------------------------------------
    # Short, human-typeable personal login link (".../web/login/<slug>"),
    # e.g. "/web/login/gutrust" instead of a long random token. Redirects to
    # the real login route rather than duplicating any rendering logic, so
    # it reuses the exact same, already-working resolution -- but the
    # token itself travels in the "ktx_t" cookie (the same one the login
    # page's own script sets, see get_set_cookie_script), never in the
    # visible URL/query string, so a screenshot or shared browser history
    # of the resulting address bar never exposes it.
    # ------------------------------------------------------------------
    @http.route("/web/login/<string:slug>", type="http", auth="public", csrf=False)
    def login_by_slug(self, slug, **kwargs):
        theme = request.env["ktx.login.theme"].sudo().get_by_slug(slug)
        if not theme:
            return request.not_found()
        target = "/web/login%s" % (("?" + urlencode(kwargs)) if kwargs else "")
        response = request.redirect(target)
        response.set_cookie("ktx_t", theme.access_token, max_age=86400, path="/", samesite="Lax")
        return response

    # ------------------------------------------------------------------
    # Public, cached CSS for a specific published theme
    # ------------------------------------------------------------------
    @http.route("/ktx_login_studio/theme.css", type="http", auth="public")
    def theme_css(self, **kwargs):
        theme_id = self._safe_int(kwargs.get("theme_id"), 0)
        theme = request.env["ktx.login.theme"].sudo().browse(theme_id)
        if not theme.exists() or theme.state != "published" or not theme.active:
            return request.make_response("", headers=[("Content-Type", "text/css")])

        cfg = {
            "theme_id": theme.id,
            "primary_color": theme.primary_color,
            "secondary_color": theme.secondary_color,
            "background_overlay_color": theme.background_overlay_color,
            "background_overlay_opacity": theme.background_overlay_opacity,
            "font_family": theme.font_family,
            "custom_font_css_name": theme.custom_font_css_name,
            "text_color": theme.text_color,
            "link_color": theme.link_color,
            "card_background_color": theme.card_background_color,
            "card_width": theme.card_width,
            "card_shadow": theme.card_shadow,
            "logo_max_height": theme.logo_max_height,
            "glassmorphism_blur": theme.glassmorphism_blur,
            "glassmorphism_opacity": theme.glassmorphism_opacity,
            "input_border_radius": theme.input_border_radius,
            "button_border_radius": theme.button_border_radius,
            "button_color": theme.button_color,
            "button_text_color": theme.button_text_color,
            "background_type": theme.background_type,
            "background_color": theme.background_color,
            "gradient_start": theme.gradient_start,
            "gradient_end": theme.gradient_end,
            "gradient_direction": theme.gradient_direction,
            "custom_css": theme.custom_css or "",
            "font_face_css": self._font_face_css(theme),
        }
        css = self._inline_style(cfg)
        return request.make_response(css, headers=[
            ("Content-Type", "text/css"),
            ("Cache-Control", "public, max-age=120"),
        ])

    # ------------------------------------------------------------------
    # Branding images (logo / background image)
    # ------------------------------------------------------------------
    @http.route("/ktx_login_studio/image/<string:field>", type="http", auth="public")
    def get_image(self, field, **kwargs):
        if field not in self._ALLOWED_IMAGE_FIELDS:
            return request.not_found()
        theme_id = self._safe_int(kwargs.get("theme_id"), 0)
        theme = request.env["ktx.login.theme"].sudo().browse(theme_id)
        if not theme.exists() or not getattr(theme, field, False):
            return request.not_found()
        return request.env["ir.binary"]._get_stream_from(theme, field).get_response()

    # ------------------------------------------------------------------
    # Background video uploaded directly on the theme (Colores y Fondo tab).
    # Streamed via ir.binary so the browser can request byte ranges and
    # start playback before the whole file downloads.
    # ------------------------------------------------------------------
    @http.route("/ktx_login_studio/background_video", type="http", auth="public")
    def get_background_video(self, **kwargs):
        theme_id = self._safe_int(kwargs.get("theme_id"), 0)
        theme = request.env["ktx.login.theme"].sudo().browse(theme_id)
        if not theme.exists() or not theme.background_video:
            return request.not_found()
        return request.env["ir.binary"]._get_stream_from(
            theme, "background_video", filename=theme.background_video_filename or "background.mp4",
        ).get_response()

    # ------------------------------------------------------------------
    # Stable, theme-independent logo/favicon URLs: resolve to whichever
    # theme is currently active for this browser -- the visitor's own
    # personal theme (via the "ktx_t" query param or, more commonly since
    # these two URLs are meant to be hardcoded with no query string at all,
    # the "ktx_t" cookie set once that personal theme first resolved),
    # falling back to the published DEFAULT theme -- so a "HTML 100%
    # personalizado" design's own CSS/HTML can hardcode these two paths
    # once and never need updating after re-uploading a logo, and a
    # personal theme's own logo/favicon is used instead of the default
    # theme's whenever one is configured. No manual copy-pasting of a
    # generated asset URL into the design's CSS either way.
    # ------------------------------------------------------------------
    def _current_theme(self, kwargs):
        token = kwargs.get("ktx_t") or request.cookies.get("ktx_t")
        return request.env["ktx.login.theme"].sudo().get_current(token)

    @http.route("/ktx_login_studio/active_logo", type="http", auth="public")
    def get_active_logo(self, **kwargs):
        theme = self._current_theme(kwargs)
        if not theme.company_logo:
            # Personal theme with no logo of its own: fall back to the
            # default theme's logo instead of a broken image.
            theme = request.env["ktx.login.theme"].sudo().get_default()
        if not theme or not theme.company_logo:
            return request.not_found()
        return request.env["ir.binary"]._get_stream_from(theme, "company_logo").get_response()

    @http.route("/ktx_login_studio/active_favicon", type="http", auth="public")
    def get_active_favicon(self, **kwargs):
        theme = self._current_theme(kwargs)
        if not theme.favicon:
            theme = request.env["ktx.login.theme"].sudo().get_default()
        if not theme or not theme.favicon:
            return request.not_found()
        return request.env["ir.binary"]._get_stream_from(theme, "favicon").get_response()

    # ------------------------------------------------------------------
    # Uploaded extensions (CSS/JS/font/image/video) -- served as static
    # bytes only, never interpreted server-side.
    # ------------------------------------------------------------------
    @http.route(
        '/ktx_login_studio/asset/<int:asset_id>-<string:checksum>/<string:filename>',
        type="http", auth="public", csrf=False,
    )
    def get_asset(self, asset_id, checksum, filename, **kwargs):
        asset = request.env["ktx.login.asset"].sudo().browse(asset_id)
        if (not asset.exists() or not asset.active or asset.state != "published"
                or asset.checksum != checksum or not asset.datas):
            return request.not_found()

        content = base64.b64decode(asset.datas)
        return request.make_response(content, headers=[
            ("Content-Type", asset.mimetype or "application/octet-stream"),
            ("Cache-Control", "public, max-age=31536000, immutable"),
            ("X-Content-Type-Options", "nosniff"),
        ])
