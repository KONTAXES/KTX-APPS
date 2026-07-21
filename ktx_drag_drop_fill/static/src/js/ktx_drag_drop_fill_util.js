/** @odoo-module **/

/**
 * Shared helpers for reading a cell's text and writing to the clipboard.
 * Used by both the spreadsheet selection (Ctrl+C) and the hover copy
 * buttons, so a value copies identically whichever way you grab it.
 */

/** Extracts meaningful text from a list cell or form field container. */
export function extractCellText(el) {
    if (!el || el.classList.contains("o_handle_cell")) {
        return "";
    }

    const checkbox = el.querySelector('input[type="checkbox"]');
    if (checkbox) {
        return checkbox.checked ? "Sí" : "No";
    }

    const tags = el.querySelectorAll(".o_tag_badge_text");
    if (tags.length) {
        return Array.from(tags)
            .map((t) => t.textContent.trim())
            .filter(Boolean)
            .join(", ");
    }

    const stars = el.querySelectorAll(".fa-star, .fa-star-o");
    if (stars.length) {
        return String(el.querySelectorAll(".fa-star:not(.fa-star-o)").length);
    }

    const select = el.querySelector("select");
    if (select) {
        return select.options[select.selectedIndex]?.text.trim() || "";
    }

    const input = el.querySelector(
        'input[type="text"], input[type="number"], input:not([type]):not([type="checkbox"]):not([type="radio"]):not([type="hidden"]), textarea'
    );
    if (input) {
        const v = input.value.trim();
        if (v) {
            return v;
        }
    }

    const clone = el.cloneNode(true);
    clone.querySelectorAll(".o_ddf_copy_btn, button, .o_list_record_open_form_view").forEach((b) => b.remove());
    const badges = clone.querySelectorAll(".badge");
    if (badges.length) {
        return Array.from(badges)
            .map((b) => b.textContent.trim())
            .filter(Boolean)
            .join(", ");
    }
    return clone.textContent.replace(/\s+/g, " ").trim();
}

/** True for cells that actually hold data (text/number/tags/badges) rather
 * than a control - so the copy icon never covers a button or checkbox. */
export function cellHasCopyableContent(cell) {
    if (!cell || cell.classList.contains("o_handle_cell")) {
        return false;
    }
    if (cell.querySelector("button, .o-checkbox, input[type='checkbox'], input[type='radio']")) {
        return false;
    }
    return !!extractCellText(cell);
}

/** Copies text to the clipboard, with a legacy fallback for insecure contexts. */
export async function toClipboard(text) {
    if (!text) {
        return;
    }
    if (navigator.clipboard && window.isSecureContext) {
        try {
            await navigator.clipboard.writeText(text);
            return;
        } catch {
            /* fall through to the legacy path */
        }
    }
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.cssText = "position:fixed;top:-9999px;left:-9999px;opacity:0;";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    try {
        document.execCommand("copy");
    } catch {
        /* ignore */
    }
    document.body.removeChild(ta);
}
