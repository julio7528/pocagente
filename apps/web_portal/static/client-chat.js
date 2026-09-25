document.addEventListener("DOMContentLoaded", () => {
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
