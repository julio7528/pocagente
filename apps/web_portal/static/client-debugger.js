document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.querySelector("[data-debugger-toggle]");
  const drawer = document.querySelector("[data-debugger-drawer]");
  const status = document.querySelector("[data-debugger-status]");
  const events = document.querySelector("[data-debugger-events]");
  const summary = document.querySelector("[data-debugger-summary]");
  const scroll = document.querySelector("[data-debugger-scroll]");
  if (!toggle || !drawer || !status || !events || !summary || !scroll) return;
  const layout = drawer.closest(".client-layout");

  const storageKey = "getnet-client-debugger-open";
  let open = false;
  let payload = null;
  try {
    payload = JSON.parse(document.getElementById("client-debugger-payload")?.textContent || "null");
  } catch (_) {
    payload = null;
  }

  const syncFormInputs = () => {
    for (const input of document.querySelectorAll("[data-debugger-mode-input]")) {
      input.value = open ? "on" : "off";
    }
  };
  const clearContent = (message = "Mantenha o Debugger aberto e envie uma mensagem para registrar o processamento.") => {
    status.textContent = message;
    events.replaceChildren();
    summary.replaceChildren();
    summary.hidden = true;
  };
  const setOpen = (next) => {
    open = next;
    drawer.hidden = !open;
    layout?.classList.toggle("client-layout--debugger-open", open);
    document.body.classList.toggle("client-debugger-open", open);
    toggle.setAttribute("aria-expanded", String(open));
    syncFormInputs();
    try {
      sessionStorage.setItem(storageKey, open ? "true" : "false");
    } catch (_) { /* Browser storage may be unavailable. */ }
    if (!open) {
      payload = null;
      clearContent();
    }
  };
  const appendSummary = (label, value) => {
    if (typeof value !== "string" || !value) return;
    const row = document.createElement("div");
    const term = document.createElement("dt");
    const detail = document.createElement("dd");
    term.textContent = label;
    detail.textContent = value;
    row.append(term, detail);
    summary.append(row);
  };
  const renderPayload = (current) => {
    clearContent();
    if (!current || typeof current !== "object") return;
    status.textContent = current.state === "complete"
      ? "✓ Processamento concluído"
      : current.state === "error"
        ? "Processamento encerrado com erro controlado."
        : "Este turno não acionou o processamento automático.";
    const traceItems = Array.isArray(current.trace) ? current.trace : [];
    for (const item of traceItems) {
      if (!item || typeof item !== "object") continue;
      const entry = document.createElement("li");
      const label = document.createElement("strong");
      const line = document.createElement("div");
      const detail = document.createElement("span");
      label.textContent = typeof item.label === "string" ? item.label : "Evento";
      detail.textContent = typeof item.detail === "string" ? item.detail : "";
      entry.className = "client-debugger-event";
      line.className = "client-debugger-event-detail";
      line.append(detail);
      if (Number.isFinite(item.elapsed_ms) && item.elapsed_ms >= 0) {
        const duration = document.createElement("span");
        duration.className = "client-debugger-event-duration";
        duration.textContent = `${(item.elapsed_ms / 1000).toFixed(1)}s`;
        line.append(duration);
      }
      entry.append(label, line);
      events.append(entry);
    }
    if (traceItems.length === 0 && current.state === "complete") {
      const note = document.createElement("li");
      note.className = "client-debugger-truncated";
      note.textContent = "Nenhum evento de telemetria foi recebido para este turno.";
      events.append(note);
    }
    if (current.trace_truncated === true) {
      const note = document.createElement("li");
      note.className = "client-debugger-truncated";
      note.textContent = "O limite de eventos deste turno foi atingido.";
      events.append(note);
    }
    appendSummary("ROTA", current.route);
    appendSummary("STATUS", current.status);
    appendSummary("INTENÇÃO", current.intent);
    summary.hidden = summary.childElementCount === 0;
    requestAnimationFrame(() => { scroll.scrollTop = scroll.scrollHeight; });
  };

  let storedOpen = null;
  try { storedOpen = sessionStorage.getItem(storageKey); } catch (_) {}
  if (storedOpen === "true" || (storedOpen === null && payload)) {
    setOpen(true);
    renderPayload(payload);
  } else {
    syncFormInputs();
  }
  toggle.addEventListener("click", () => {
    const next = !open;
    setOpen(next);
    if (next && payload) renderPayload(payload);
  });

  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || !form.matches("[data-chat-form], [data-agent-retry-form]")) return;
    if (!form.checkValidity() || form.dataset.submitting === "true") return;
    open = !drawer.hidden;
    const modeInput = form.querySelector("[data-debugger-mode-input]");
    if (modeInput) modeInput.value = open ? "on" : "off";
    syncFormInputs();
    if (open) clearContent("● Processando a mensagem...");
  }, true);
});
