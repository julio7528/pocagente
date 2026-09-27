document.addEventListener("DOMContentLoaded", () => {
  renderAgentFormatting();

  const transcript = document.querySelector(".client-page .transcript");
  let followLatest = true;
  if (transcript) {
    announceIncomingMessage(transcript);
    const savedScroll = restoreTranscriptScroll(transcript);
    followLatest = savedScroll?.followLatest ?? true;
    transcript.addEventListener("scroll", () => {
      followLatest = transcript.scrollHeight - transcript.scrollTop - transcript.clientHeight < 96;
    }, { passive: true });
    const observer = new MutationObserver((records) => {
      const addedMessage = records.some((record) =>
        record.target === transcript && record.addedNodes.length > 0
      );
      if (!addedMessage || !followLatest) return;
      transcript.scrollTo({ top: transcript.scrollHeight, behavior: "smooth" });
    });
    observer.observe(transcript, { childList: true });
  } else {
    clearPendingChatSend();
  }

  const expandButton = document.querySelector("[data-composer-expand]");
  const composer = expandButton?.closest(".composer");
  const textarea = composer?.querySelector("textarea");
  const resizeTextarea = () => {
    if (!textarea) return;
    const maxHeight = composer.classList.contains("is-expanded")
      ? Math.round(window.innerHeight * 0.35)
      : 192;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, maxHeight)}px`;
    textarea.style.overflowY = textarea.scrollHeight > maxHeight ? "auto" : "hidden";
  };
  textarea?.addEventListener("input", resizeTextarea);
  textarea?.addEventListener("change", resizeTextarea);
  resizeTextarea();
  expandButton?.addEventListener("click", () => {
    const expanded = composer.classList.toggle("is-expanded");
    expandButton.setAttribute("aria-expanded", String(expanded));
    expandButton.setAttribute("aria-label", expanded ? "Recolher caixa de mensagem" : "Expandir caixa de mensagem");
    expandButton.title = expanded ? "Recolher caixa de mensagem" : "Expandir caixa de mensagem";
    resizeTextarea();
    textarea?.focus();
  });

  for (const form of document.querySelectorAll("[data-chat-form], [data-agent-retry-form]")) {
    form.addEventListener("submit", (event) => {
      if (!form.checkValidity()) return;
      if (form.dataset.submitting === "true") {
        event.preventDefault();
        return;
      }
      form.dataset.submitting = "true";
      if (form.hasAttribute("data-chat-form")) {
        try { sessionStorage.setItem("getnet-chat-pending-send", String(Date.now())); } catch (_) {}
      }
      const status = form.querySelector("[data-submit-status]");
      if (status) {
        status.textContent = form.hasAttribute("data-agent-retry-form")
          ? "Tentando obter resposta…"
          : "Enviando mensagem…";
      }
      const button = form.querySelector('button[type="submit"]');
      form.setAttribute("aria-busy", "true");
      if (button) {
        button.disabled = true;
        if (form.hasAttribute("data-chat-form")) {
          button.classList.add("is-loading");
          button.setAttribute("aria-busy", "true");
          button.setAttribute("aria-label", "Enviando mensagem");
          button.title = "Enviando mensagem";
        }
      }
    });
  }

  window.addEventListener("pageshow", (event) => {
    if (!event.persisted) return;
    for (const form of document.querySelectorAll("[data-chat-form], [data-agent-retry-form]")) {
      delete form.dataset.submitting;
      form.removeAttribute("aria-busy");
      const button = form.querySelector('button[type="submit"]');
      button?.removeAttribute("aria-busy");
      button?.classList.remove("is-loading");
      if (button) {
        button.disabled = false;
        if (form.hasAttribute("data-chat-form")) {
          button.setAttribute("aria-label", "Enviar mensagem");
          button.title = "Enviar mensagem";
        }
      }
      const status = form.querySelector("[data-submit-status]");
      if (status) status.textContent = "";
    }
  });

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
        if (transcript) rememberTranscriptScroll(transcript, followLatest);
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

function announceIncomingMessage(transcript) {
  const conversationId = transcript.dataset.conversationId;
  const messages = transcript.querySelectorAll(".transcript-item[data-message-id]");
  const latestMessage = messages[messages.length - 1];
  if (!conversationId || !latestMessage) return;

  const messageId = latestMessage.dataset.messageId;
  const senderType = latestMessage.dataset.senderType;
  const storageKey = `getnet-chat-last-message:${conversationId}`;
  let previousMessageId = null;
  try { previousMessageId = sessionStorage.getItem(storageKey); } catch (_) {}
  let pendingSendAt = null;
  try {
    const value = sessionStorage.getItem("getnet-chat-pending-send");
    pendingSendAt = value ? Number(value) : null;
    sessionStorage.removeItem("getnet-chat-pending-send");
  } catch (_) {}

  const pendingAge = pendingSendAt === null ? null : Date.now() - pendingSendAt;
  const firstResponseAfterSend = !previousMessageId
    && pendingAge !== null
    && pendingAge >= 0
    && pendingAge < 5 * 60 * 1000;
  const isIncomingAgentMessage = ["AGENT", "SUPPORT_AGENT"].includes(senderType);
  const messageChanged = previousMessageId && previousMessageId !== messageId;

  if (isIncomingAgentMessage && (messageChanged || firstResponseAfterSend)) {
    latestMessage.classList.add("is-arriving");
    playArrivalPing();
  }

  try { sessionStorage.setItem(storageKey, messageId); } catch (_) {}
}

function clearPendingChatSend() {
  try { sessionStorage.removeItem("getnet-chat-pending-send"); } catch (_) {}
}

function restoreTranscriptScroll(transcript) {
  const conversationId = transcript.dataset.conversationId;
  if (!conversationId) return null;
  const storageKey = `getnet-chat-scroll:${conversationId}`;
  let saved = null;
  try {
    saved = JSON.parse(sessionStorage.getItem(storageKey) || "null");
    sessionStorage.removeItem(storageKey);
  } catch (_) {}

  if (saved && Number.isFinite(saved.scrollTop) && typeof saved.followLatest === "boolean") {
    requestAnimationFrame(() => {
      transcript.scrollTop = saved.followLatest
        ? transcript.scrollHeight
        : Math.min(saved.scrollTop, transcript.scrollHeight);
    });
    return saved;
  }

  // A newly opened conversation starts at its latest message.
  transcript.scrollTop = transcript.scrollHeight;
  requestAnimationFrame(() => { transcript.scrollTop = transcript.scrollHeight; });
  return null;
}

function rememberTranscriptScroll(transcript, followLatest) {
  const conversationId = transcript.dataset.conversationId;
  if (!conversationId) return;
  try {
    sessionStorage.setItem(`getnet-chat-scroll:${conversationId}`, JSON.stringify({
      scrollTop: transcript.scrollTop,
      followLatest,
    }));
  } catch (_) {}
}

function playArrivalPing() {
  const AudioContextType = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextType) return;

  let context;
  try { context = new AudioContextType(); } catch (_) { return; }
  const closeIfBlocked = window.setTimeout(() => {
    if (context.state !== "running") context.close().catch(() => {});
  }, 800);
  context.resume().then(() => {
    window.clearTimeout(closeIfBlocked);
    if (context.state !== "running") return;
    const start = context.currentTime;
    const tone = context.createOscillator();
    const volume = context.createGain();
    tone.type = "sine";
    tone.frequency.setValueAtTime(540, start);
    tone.frequency.exponentialRampToValueAtTime(760, start + 0.12);
    volume.gain.setValueAtTime(0.0001, start);
    volume.gain.exponentialRampToValueAtTime(0.035, start + 0.02);
    volume.gain.exponentialRampToValueAtTime(0.0001, start + 0.16);
    tone.connect(volume);
    volume.connect(context.destination);
    tone.addEventListener("ended", () => { context.close().catch(() => {}); }, { once: true });
    tone.start(start);
    tone.stop(start + 0.17);
  }).catch(() => { context.close().catch(() => {}); });
}

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
