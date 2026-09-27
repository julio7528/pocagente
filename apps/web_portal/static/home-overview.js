(() => {
  const overview = document.querySelector("[data-home-overview]");
  if (!overview) return;

  const dialog = overview.querySelector("[data-overview-dialog]");
  const title = overview.querySelector("[data-overview-dialog-title]");
  const eyebrow = overview.querySelector("[data-overview-dialog-eyebrow]");
  const content = overview.querySelector("[data-overview-dialog-content]");
  const closeButton = overview.querySelector("[data-overview-close]");
  const detailTemplates = new Map(
    [...overview.querySelectorAll("template[data-overview-detail]")].map((template) => [
      template.dataset.overviewDetail,
      template,
    ]),
  );

  if (!dialog || !title || !eyebrow || !content || !closeButton) return;

  let returnFocusTarget = null;

  overview.querySelectorAll("[data-overview-open]").forEach((trigger) => {
    trigger.addEventListener("click", () => {
      const detail = detailTemplates.get(trigger.dataset.overviewOpen);
      if (!detail || typeof dialog.showModal !== "function") return;

      returnFocusTarget = trigger;
      title.textContent = trigger.dataset.overviewTitle || "Detalhes";
      eyebrow.textContent = "Visão geral da POC";
      content.replaceChildren(detail.content.cloneNode(true));
      dialog.showModal();
      closeButton.focus();
    });
  });

  closeButton.addEventListener("click", () => dialog.close());

  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });

  dialog.addEventListener("close", () => {
    const trigger = returnFocusTarget;
    returnFocusTarget = null;
    if (trigger?.isConnected) window.requestAnimationFrame(() => trigger.focus());
  });
})();
