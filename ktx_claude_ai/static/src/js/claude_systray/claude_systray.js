/** @odoo-module **/

import { Component, useState, useRef, onWillStart, onPatched, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { markdownToHtml } from "../claude_markdown";

const safeMarkup = typeof markup === "function" ? markup : (s) => s;

const SUPPORTED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/gif", "image/webp"];

export class ClaudeSystray extends Component {
    static template = "ktx_claude_ai.ClaudeSystray";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.threadRef = useRef("thread");
        this.fileInputRef = useRef("fileInput");

        this.state = useState({
            show: false,
            open: false,
            minimized: false,
            loaded: false,
            conversations: [],
            activeId: null,
            messages: [],
            draft: "",
            loading: false,
            totalInputTokens: 0,
            totalOutputTokens: 0,
            pendingImages: [],   // [{name, media_type, data, preview}]
            listening: false,    // microphone active
            companies: [],       // [{id, name}] — populated only when user has >1 company
            activeCompanyId: null,
            activeCompanyName: "",
        });

        this._recognition = null;

        onWillStart(async () => {
            const cfg = await this.orm.call("claude.conversation", "get_chat_config", []);
            this.state.show = !!cfg.enabled;
            if (cfg.companies && cfg.companies.length > 1) {
                this.state.companies = cfg.companies;
            }
            this.state.activeCompanyId = cfg.current_company_id || null;
            this.state.activeCompanyName = cfg.current_company_name || "";
        });
        onPatched(() => {
            if (this.state.open && !this.state.minimized) {
                this.scrollToBottom();
            }
        });
    }

    _getActiveRecord() {
        try {
            const rawHash = window.location.hash.slice(1);
            const params = Object.fromEntries(new URLSearchParams(rawHash));
            const model = params.model || null;
            const id = params.id ? parseInt(params.id, 10) : null;
            return { model, id: id > 0 ? id : null };
        } catch (_e) {
            return { model: null, id: null };
        }
    }

    // ── Panel open/close/minimize ───────────────────────────────────────────

    async toggle() {
        if (this.state.open && !this.state.minimized) {
            // Close fully
            this.state.open = false;
            this.state.minimized = false;
        } else if (this.state.minimized) {
            // Restore from minimized
            this.state.minimized = false;
        } else {
            // Open
            this.state.open = true;
            if (!this.state.loaded) {
                await this.ensureConversation();
                this.state.loaded = true;
            }
        }
    }

    minimize() {
        this.state.minimized = true;
    }

    restore() {
        this.state.minimized = false;
    }

    close() {
        this.state.open = false;
        this.state.minimized = false;
    }

    // ── Conversations ───────────────────────────────────────────────────────

    async ensureConversation() {
        await this.loadConversations();
        if (this.state.conversations.length) {
            await this.selectConversation(this.state.conversations[0].id);
        } else {
            await this.newConversation();
        }
    }

    async loadConversations() {
        this.state.conversations = await this.orm.call(
            "claude.conversation", "get_conversations", []
        );
    }

    async selectConversation(id) {
        this.state.activeId = id;
        const msgs = await this.orm.call(
            "claude.conversation", "get_messages", [[id]]
        );
        this.state.messages = msgs.map((m) => this._enrichMessage(m));
        // Fetch token stats for this conversation
        try {
            const tokens = await this.orm.call(
                "claude.conversation", "get_conversation_tokens", [[id]]
            );
            this.state.totalInputTokens = tokens.total_input_tokens || 0;
            this.state.totalOutputTokens = tokens.total_output_tokens || 0;
        } catch (_e) {
            this.state.totalInputTokens = 0;
            this.state.totalOutputTokens = 0;
        }
        // Sync company shown in selector to this conversation's company
        const conv = this.state.conversations.find((c) => c.id === id);
        if (conv && conv.company_id) {
            this.state.activeCompanyId = conv.company_id;
            this.state.activeCompanyName = conv.company_name || "";
        }
    }

    async newConversation() {
        const conv = await this.orm.call(
            "claude.conversation", "create_conversation", [],
            { company_id: this.state.activeCompanyId || false }
        );
        await this.loadConversations();
        this.state.activeId = conv.id;
        this.state.messages = [];
        this.state.totalInputTokens = 0;
        this.state.totalOutputTokens = 0;
        if (conv.company_id) {
            this.state.activeCompanyId = conv.company_id;
            this.state.activeCompanyName = conv.company_name || "";
        }
    }

    async deleteConversation() {
        if (!this.state.activeId) return;
        if (!window.confirm(_t("¿Eliminar esta conversación?"))) return;
        try {
            await this.orm.call(
                "claude.conversation", "delete_conversation", [[this.state.activeId]]
            );
            this.state.loaded = false;
            await this.ensureConversation();
            this.state.loaded = true;
        } catch (e) {
            this.notification.add(_t("No se pudo eliminar la conversación."), { type: "danger" });
        }
    }

    onConversationChange(ev) {
        const id = parseInt(ev.target.value, 10);
        if (id) {
            this.selectConversation(id);
        }
    }

    async onCompanyChange(ev) {
        const companyId = parseInt(ev.target.value, 10);
        if (!companyId || !this.state.activeId) return;
        try {
            const result = await this.orm.call(
                "claude.conversation", "set_company", [[this.state.activeId], companyId]
            );
            this.state.activeCompanyId = result.company_id;
            this.state.activeCompanyName = result.company_name || "";
            // Reload messages so the confirmation tool message is visible
            const msgs = await this.orm.call(
                "claude.conversation", "get_messages", [[this.state.activeId]]
            );
            this.state.messages = msgs.map((m) => this._enrichMessage(m));
            await this.loadConversations();
        } catch (e) {
            this.notification.add(
                e.data && e.data.message
                    ? e.data.message
                    : _t("No se pudo cambiar la empresa."),
                { type: "danger" }
            );
        }
    }

    // ── Message helpers ─────────────────────────────────────────────────────

    _enrichMessage(m) {
        if (m.role === "assistant" && m.body) {
            return { ...m, bodyHtml: safeMarkup(markdownToHtml(m.body)) };
        }
        return m;
    }

    onKeydown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.send();
        }
    }

    async send() {
        const text = (this.state.draft || "").trim();
        const images = [...this.state.pendingImages];
        if ((!text && !images.length) || this.state.loading) return;
        if (!this.state.activeId) {
            await this.newConversation();
        }
        this.state.draft = "";
        this.state.pendingImages = [];
        this.state.loading = true;

        const displayBody = text || (images.length ? _t("[imagen adjunta]") : "");
        this.state.messages.push({
            id: `tmp-${Date.now()}`, role: "user", body: displayBody,
            tool_name: "", tool_input: "", tool_result: "", tool_success: true,
        });

        const { model: activeModel, id: activeId } = this._getActiveRecord();
        const kwargs = { active_model: activeModel, active_id: activeId };
        if (images.length) {
            kwargs.images = images.map((img) => ({
                media_type: img.media_type,
                data: img.data,
            }));
        }
        try {
            const result = await this.orm.call(
                "claude.conversation", "send_message",
                [[this.state.activeId], text],
                kwargs
            );
            const newMessages = result.messages || result;
            this.state.messages = this.state.messages.filter(
                (m) => typeof m.id !== "string"
            );
            this.state.messages.push(...newMessages.map((m) => this._enrichMessage(m)));
            if (result.total_input_tokens != null) {
                this.state.totalInputTokens = result.total_input_tokens;
                this.state.totalOutputTokens = result.total_output_tokens;
            }
            await this.loadConversations();
        } catch (error) {
            this.state.messages = this.state.messages.filter(
                (m) => typeof m.id !== "string"
            );
            this.notification.add(
                error.data && error.data.message
                    ? error.data.message
                    : _t("Error al contactar a Claude."),
                { type: "danger" }
            );
        } finally {
            this.state.loading = false;
        }
    }

    scrollToBottom() {
        const el = this.threadRef.el;
        if (el) el.scrollTop = el.scrollHeight;
    }

    // ── Image attachment ────────────────────────────────────────────────────

    openFileInput() {
        const el = this.fileInputRef && this.fileInputRef.el;
        if (el) el.click();
    }

    onFileChange(ev) {
        const files = Array.from(ev.target.files || []);
        for (const file of files) {
            if (!SUPPORTED_IMAGE_TYPES.includes(file.type)) {
                this.notification.add(
                    _t("Solo se admiten imágenes (JPEG, PNG, GIF, WEBP)."),
                    { type: "warning" }
                );
                continue;
            }
            const reader = new FileReader();
            reader.onload = (e) => {
                const dataUrl = e.target.result;
                // dataUrl = "data:image/jpeg;base64,XXXX..."
                const base64 = dataUrl.split(",")[1];
                this.state.pendingImages.push({
                    name: file.name,
                    media_type: file.type,
                    data: base64,
                    preview: dataUrl,
                });
            };
            reader.readAsDataURL(file);
        }
        // Reset input so the same file can be re-selected
        ev.target.value = "";
    }

    removeImage(index) {
        this.state.pendingImages.splice(index, 1);
    }

    // ── Voice input (Web Speech API) ────────────────────────────────────────

    toggleVoice() {
        if (this.state.listening) {
            this._stopListening();
        } else {
            this._startListening();
        }
    }

    _startListening() {
        const SpeechRecognition =
            window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            this.notification.add(
                _t("Tu navegador no soporta reconocimiento de voz."),
                { type: "warning" }
            );
            return;
        }
        const rec = new SpeechRecognition();
        rec.lang = document.documentElement.lang || "es-ES";
        rec.interimResults = false;
        rec.maxAlternatives = 1;
        rec.continuous = false;

        rec.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            this.state.draft = (this.state.draft ? this.state.draft + " " : "") + transcript;
            this.state.listening = false;
        };
        rec.onerror = () => {
            this.state.listening = false;
        };
        rec.onend = () => {
            this.state.listening = false;
        };

        this._recognition = rec;
        rec.start();
        this.state.listening = true;
    }

    _stopListening() {
        if (this._recognition) {
            this._recognition.stop();
            this._recognition = null;
        }
        this.state.listening = false;
    }

    // ── Token display helpers ───────────────────────────────────────────────

    get tokenSummary() {
        const total = this.state.totalInputTokens + this.state.totalOutputTokens;
        if (!total) return "";
        return `↑${this._fmtTokens(this.state.totalInputTokens)} ↓${this._fmtTokens(this.state.totalOutputTokens)}`;
    }

    _fmtTokens(n) {
        if (n >= 1000) return (n / 1000).toFixed(1) + "k";
        return String(n);
    }
}

registry
    .category("systray")
    .add("ktx_claude_ai.systray", { Component: ClaudeSystray }, { sequence: 25 });
