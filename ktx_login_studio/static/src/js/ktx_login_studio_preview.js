/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, useEffect } from "@odoo/owl";

const STYLE_FIELDS = [
    "template", "tagline", "primary_color", "secondary_color",
    "background_type", "background_color", "gradient_start", "gradient_end",
    "gradient_direction", "background_overlay_color", "background_overlay_opacity",
    "font_family", "custom_font_css_name", "text_color", "link_color",
    "card_width", "card_shadow", "logo_max_height", "input_border_radius",
    "button_border_radius", "button_color", "button_text_color",
    "show_database_domain", "show_powered_by_odoo", "split_alignment",
    "card_background_color", "glassmorphism", "glassmorphism_blur",
    "glassmorphism_opacity", "custom_footer_text", "login_welcome_title",
    "login_welcome_subtitle", "terms_url", "privacy_url", "terms_label",
    "privacy_label", "custom_body_class", "custom_css", "render_mode",
    "card_entrance_animation", "ambient_glow", "ambient_glow_color",
    "ambient_glow_intensity", "input_style", "input_focus_glow",
    "input_icons", "button_hover_effect", "hide_website_header",
    "show_portal_name",
];

const BOOL_FIELDS = new Set([
    "show_database_domain", "show_powered_by_odoo", "glassmorphism",
    "ambient_glow", "input_focus_glow", "input_icons", "hide_website_header",
    "show_portal_name",
]);

export class KtxLoginStudioPreview extends Component {
    static template = "ktx_login_studio.PreviewWidget";
    static props = ["*"];

    setup() {
        this.state = useState({ page: "login", iframeSrc: "" });
        this.debounceTimeout = null;

        useEffect(
            () => {
                const record = this.props.record;
                if (!record.resId) {
                    // Unsaved theme: no id to preview yet.
                    this.state.iframeSrc = "";
                    return;
                }
                const data = record.data;
                const params = new URLSearchParams();
                params.append("page", this.state.page);
                params.append("theme_id", record.resId);

                for (const field of STYLE_FIELDS) {
                    let val = data[field];
                    if (Array.isArray(val)) {
                        val = val[0];
                    } else if (val && typeof val === "object" && "id" in val) {
                        val = val.id;
                    }
                    if (BOOL_FIELDS.has(field)) {
                        params.append(field, val ? "true" : "false");
                    } else if (val !== undefined && val !== false && val !== "") {
                        params.append(field, val);
                    }
                }

                const newSrc = `/ktx_login_studio/preview?${params.toString()}`;
                clearTimeout(this.debounceTimeout);
                this.debounceTimeout = setTimeout(() => {
                    this.state.iframeSrc = newSrc;
                }, 250);
            },
            () => {
                const data = this.props.record.data;
                return [this.state.page, this.props.record.resId, ...STYLE_FIELDS.map((f) => data[f])];
            }
        );
    }

    setPage(page) {
        this.state.page = page;
    }
}

registry.category("view_widgets").add("ktx_login_studio_preview", {
    component: KtxLoginStudioPreview,
});
