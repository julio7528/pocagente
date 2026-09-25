document.addEventListener("DOMContentLoaded", () => {
  renderAgentFormatting();

  for (const form of document.querySelectorAll("[data-chat-form], [data-agent-retry-form]")) {
    form.addEventListener("submit", (event) => {
      if (!form.checkValidity()) return;
      if (form.dataset.submitting === "true") {
        event.preventDefault();
        return;
      }
      form.dataset.submitting = "true";
      const status = form.querySelector("[data-submit-status]");
      if (status) {
        status.textContent = form.hasAttribute("data-agent-retry-form")
          ? "Tentando obter resposta…"
          : "Enviando mensagem…";
      }
      const button = form.querySelector('button[type="submit"]');
      if (button) button.disabled = true;
    });
  }

  const liveRegion = document.querySelector("[data-live-poll-url]");
  if (!liveRegion) return;
  let failures = 0;
  let timer;
  const poll = async () => {
    if (document.hidden) {
      timer = window.setTimeout(poll, 12000);
      return;
    }
    try {
      const response = await fetch(liveRegion.dataset.livePollUrl, {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      });
      if (!response.ok) throw new Error("poll unavailable");
      const payload = await response.json();
      failures = 0;
      if (payload.version !== liveRegion.dataset.liveVersion) {
        window.location.reload();
        return;
      }
    } catch (_) {
      failures = Math.min(failures + 1, 4);
    }
    timer = window.setTimeout(poll, Math.min(12000 * (2 ** failures), 60000));
  };
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
      window.clearTimeout(timer);
      poll();
    }
  });
  timer = window.setTimeout(poll, 12000);
});

function renderAgentFormatting() {
  const tokenPattern = /\*\*[^*\n]+\*\*|\*[^*\n]+\*|\[[^\]\n]+\]\(https?:\/\/[^\s)]+\)/g;
  for (const element of document.querySelectorAll('[data-response-format="markdown"]')) {
    const source = (element.textContent || "").replace(/\r\n?/g, "\n").trim();
    if (!source) continue;

    const fragment = document.createDocumentFragment();
    const blocks = source.split(/\n[\t ]*\n+/);
    for (const block of blocks) {
      const lines = block.split("\n");
      const unorderedItems = lines.map((line) => line.match(/^\s*[-*]\s+(.+)$/));
      const orderedItems = lines.map((line) => line.match(/^\s*(\d+)[.)]\s+(.+)$/));

      if (unorderedItems.every(Boolean)) {
        const list = document.createElement("ul");
        for (const item of unorderedItems) {
          const entry = document.createElement("li");
          appendInlineFormatting(entry, item[1]);
          list.append(entry);
        }
        fragment.append(list);
        continue;
      }

      if (orderedItems.every(Boolean)) {
        const list = document.createElement("ol");
        const firstNumber = Number(orderedItems[0][1]);
        if (firstNumber > 1) list.start = firstNumber;
        for (const item of orderedItems) {
          const entry = document.createElement("li");
          appendInlineFormatting(entry, item[2]);
          list.append(entry);
        }
        fragment.append(list);
        continue;
      }

      const paragraph = document.createElement("p");
      lines.forEach((line, index) => {
        if (index) paragraph.append(document.createElement("br"));
        appendInlineFormatting(paragraph, line);
      });
      fragment.append(paragraph);
    }

    element.replaceChildren(fragment);
    element.classList.add("message-body--formatted");
  }

  function appendInlineFormatting(parent, text) {
    let cursor = 0;
    for (const match of text.matchAll(tokenPattern)) {
      if (match.index > cursor) {
        parent.append(document.createTextNode(text.slice(cursor, match.index)));
      }
      const token = match[0];
      if (token.startsWith("**") && token.endsWith("**")) {
        const strong = document.createElement("strong");
        strong.textContent = token.slice(2, -2);
        parent.append(strong);
      } else if (token.startsWith("*") && token.endsWith("*")) {
        const emphasis = document.createElement("em");
        emphasis.textContent = token.slice(1, -1);
        parent.append(emphasis);
      } else {
        const markdownLink = token.match(/^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/);
        const href = markdownLink ? safeHttpLink(markdownLink[2]) : null;
        if (href) {
          const link = document.createElement("a");
          link.className = "message-link";
          link.href = href;
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          link.textContent = markdownLink[1];
          parent.append(link);
        } else {
          parent.append(document.createTextNode(token));
        }
      }
      cursor = match.index + token.length;
    }
    if (cursor < text.length) {
      parent.append(document.createTextNode(text.slice(cursor)));
    }
  }

  function safeHttpLink(value) {
    if (!value || /\s|[\u0000-\u001f]/.test(value)) return null;
    try {
      const parsed = new URL(value);
      if (!["http:", "https:"].includes(parsed.protocol) || !parsed.hostname || parsed.username || parsed.password) {
        return null;
      }
      return parsed.href;
    } catch (_) {
      return null;
    }
  }
}
