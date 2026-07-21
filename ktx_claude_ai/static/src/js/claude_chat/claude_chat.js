/** @odoo-module **/

import { Component, useState, useRef, onWillStart, onMounted, onPatched, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { markdownToHtml } from "../claude_markdown";

const safeMarkup = typeof markup === "function" ? markup : (s) => s;

export class ClaudeChatAction extends Component {
    static template = "ktx_claude_ai.ClaudeChat";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.threadRef = useRef("thread");
        this.state = useState({
            conversations: [],
            activeId: null,
            messages: [],
            draft: "",
            loading: false,
        });

        onWillStart(async () => {
            await this.loadConversations();
            if (this.state.conversations.length) {
                await this.selectConversation(this.state.conversations[0].id);
            } else {
                await this.newConversation();
            }
        });
        onMounted(() => this.scrollToBottom());
        onPatched(() => this.scrollToBottom());
    }

    scrollToBottom() {
        const el = this.threadRef.el;
        if (el) {
            el.scrollTop = el.scrollHeight;
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
    }

    async newConversation() {
        const conv = await this.orm.call(
            "claude.conversation", "create_conversation", []
        );
        await this.loadConversations();
        this.state.activeId = conv.id;
        this.state.messages = [];
    }

    async deleteConversation() {
        if (!this.state.activeId) return;
        if (!window.confirm(_t("¿Eliminar esta conversación?"))) return;
        try {
            await this.orm.call(
                "claude.conversation", "delete_conversation", [[this.state.activeId]]
            );
            await this.loadConversations();
            if (this.state.conversations.length) {
                await this.selectConversation(this.state.conversations[0].id);
            } else {
                await this.newConversation();
            }
        } catch (e) {
            this.notification.add(_t("No se pudo eliminar la conversación."), { type: "danger" });
        }
    }

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
        if (!text || this.state.loading) {
            return;
        }
        if (!this.state.activeId) {
            await this.newConversation();
        }
        this.state.draft = "";
        this.state.loading = true;
        this.state.messages.push({
            id: `tmp-${Date.now()}`, role: "user", body: text,
            tool_name: "", tool_input: "", tool_result: "", tool_success: true,
        });
        try {
            const result = await this.orm.call(
                "claude.conversation", "send_message", [[this.state.activeId], text]
            );
            const newMessages = result.messages || result;
            this.state.messages = this.state.messages.filter(
                (m) => typeof m.id !== "string"
            );
            this.state.messages.push(...newMessages.map((m) => this._enrichMessage(m)));
            await this.loadConversations();
        } catch (error) {
            this.state.messages = this.state.messages.filter(
                (m) => typeof m.id !== "string"
            );
            this.notification.add(
                error.data && error.data.message ? error.data.message : _t("Error al contactar a Claude."),
                { type: "danger" }
            );
        } finally {
            this.state.loading = false;
        }
    }

    get activeName() {
        const c = this.state.conversations.find((c) => c.id === this.state.activeId);
        return c ? c.name : _t("Claude");
    }
}

registry.category("actions").add("ktx_claude_ai.chat", ClaudeChatAction);
