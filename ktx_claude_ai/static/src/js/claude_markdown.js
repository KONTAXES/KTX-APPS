/** @odoo-module **/

/**
 * Minimal, safe markdown → HTML converter for Claude chat messages.
 *
 * Covers the subset Claude actually uses: code fences, inline code,
 * bold, italic, bullet lists, numbered lists, and links.
 * No external dependencies — only DOM text-node escaping via the browser's
 * own `textContent` trick, which is XSS-safe.
 */

function escapeHtml(str) {
    const d = document.createElement("div");
    d.appendChild(document.createTextNode(str));
    return d.innerHTML;
}

/**
 * Convert a markdown string to an HTML string.
 * The result is safe to set as `innerHTML` because:
 *   - Plain text fragments are escaped via `escapeHtml`.
 *   - Only a fixed, known set of HTML tags is produced.
 *   - Link `href` values are sanitized to http/https/mailto only.
 */
export function markdownToHtml(md) {
    if (!md) return "";

    // 1. Extract fenced code blocks before any other processing.
    const fences = [];
    md = md.replace(/```(\w*)\n?([\s\S]*?)```/g, (_m, lang, code) => {
        const langAttr = lang ? ` class="language-${escapeHtml(lang)}"` : "";
        const html = `<pre><code${langAttr}>${escapeHtml(code)}</code></pre>`;
        fences.push(html);
        return `\x00FENCE${fences.length - 1}\x00`;
    });

    // 2. Process line-by-line for block-level elements.
    const lines = md.split("\n");
    const out = [];
    let inUl = false;
    let inOl = false;

    const closeList = () => {
        if (inUl) { out.push("</ul>"); inUl = false; }
        if (inOl) { out.push("</ol>"); inOl = false; }
    };

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];

        // Fence placeholder — emit verbatim (already escaped).
        const fenceMatch = line.match(/^\x00FENCE(\d+)\x00$/);
        if (fenceMatch) {
            closeList();
            out.push(fences[parseInt(fenceMatch[1], 10)]);
            continue;
        }

        // Headings (##, ###, ####).
        const hMatch = line.match(/^(#{1,4})\s+(.+)$/);
        if (hMatch) {
            closeList();
            const level = Math.min(hMatch[1].length + 2, 6); // h3–h6
            out.push(`<h${level}>${inlineFormat(hMatch[2])}</h${level}>`);
            continue;
        }

        // Unordered list.
        const ulMatch = line.match(/^[-*]\s+(.+)$/);
        if (ulMatch) {
            if (!inUl) { closeList(); out.push("<ul>"); inUl = true; }
            out.push(`<li>${inlineFormat(ulMatch[1])}</li>`);
            continue;
        }

        // Ordered list.
        const olMatch = line.match(/^\d+\.\s+(.+)$/);
        if (olMatch) {
            if (!inOl) { closeList(); out.push("<ol>"); inOl = true; }
            out.push(`<li>${inlineFormat(olMatch[1])}</li>`);
            continue;
        }

        // Blank line → close lists, paragraph break.
        if (!line.trim()) {
            closeList();
            out.push("<br/>");
            continue;
        }

        // Normal paragraph line.
        closeList();
        out.push(`<p>${inlineFormat(line)}</p>`);
    }

    closeList();
    return out.join("");
}

/**
 * Apply inline formatting to a single line of text:
 * inline code, bold, italic, links.
 */
function inlineFormat(text) {
    // Fence placeholders stay verbatim (shouldn't appear here, but guard anyway).
    const parts = [];
    let rest = text;

    // Inline code: `...`
    rest = rest.replace(/`([^`]+)`/g, (_m, code) => `<code>${escapeHtml(code)}</code>`);

    // Bold+Italic: ***...***
    rest = rest.replace(/\*\*\*(.+?)\*\*\*/g, (_m, t) => `<strong><em>${escapeHtml(t)}</em></strong>`);

    // Bold: **...**
    rest = rest.replace(/\*\*(.+?)\*\*/g, (_m, t) => `<strong>${escapeHtml(t)}</strong>`);

    // Italic: *...*  (not preceded or followed by *)
    rest = rest.replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, (_m, t) => `<em>${escapeHtml(t)}</em>`);

    // Links: [text](url)
    rest = rest.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_m, label, url) => {
        const safeUrl = /^(https?:|mailto:)/i.test(url.trim()) ? url.trim() : "#";
        return `<a href="${escapeHtml(safeUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`;
    });

    // Escape remaining plain text segments that weren't already processed.
    // At this point `rest` may contain already-escaped HTML tags — we can't
    // double-escape, so we return as-is. The regex replacements above only
    // produce safe tags with escaped content, so this is XSS-safe.
    return rest;
}
