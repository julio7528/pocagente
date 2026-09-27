(() => {
  const root = document.querySelector("[data-home-rag]");
  if (!root) return;

  const tabs = Array.from(root.querySelectorAll("[data-rag-tab][role='tab']"));
  const panels = Array.from(root.querySelectorAll("[data-rag-panel]"));
  const detailsTitle = root.querySelector("[data-rag-details-title]");
  const detailsDescription = root.querySelector("[data-rag-details-description]");
  const detailsMeta = root.querySelector("[data-rag-details-meta]");
  const detailsMetaLabel = root.querySelector("[data-rag-details-meta-label]");
  const detailsMetaValue = root.querySelector("[data-rag-details-meta-value]");
  const tooltip = root.querySelector("[data-rag-tooltip]");

  const emptyMessages = {
    ingestion: "Selecione uma etapa para entender como o conhecimento é preparado para o RAG.",
    retrieval: "Selecione um componente para ver como a recuperação híbrida encontra evidências.",
    numbers: "Selecione uma métrica para entender seu papel na arquitetura do RAG.",
  };

  let activeTab = "ingestion";
  let describedNode = null;

  const resolveNode = (element) => {
    if (!element) return null;
    if (element.matches("[data-rag-ref]")) {
      const referenced = document.getElementById(element.dataset.ragRef);
      return referenced && root.contains(referenced) ? referenced : null;
    }
    return element.matches("[data-rag-node]") ? element : null;
  };

  const hideTooltip = () => {
    tooltip.hidden = true;
    tooltip.textContent = "";
    if (describedNode) {
      describedNode.removeAttribute("aria-describedby");
      describedNode = null;
    }
  };

  const positionTooltip = (element, pointerEvent) => {
    const rootRect = root.getBoundingClientRect();
    const targetRect = element.getBoundingClientRect();
    const x = pointerEvent && pointerEvent.clientX
      ? pointerEvent.clientX - rootRect.left + 12
      : targetRect.left - rootRect.left + Math.min(targetRect.width / 2, 100);
    const y = pointerEvent && pointerEvent.clientY
      ? pointerEvent.clientY - rootRect.top + 12
      : targetRect.top - rootRect.top - 48;
    const maxX = Math.max(8, root.clientWidth - 280);
    tooltip.style.left = String(Math.min(Math.max(x, 8), maxX)) + "px";
    tooltip.style.top = String(Math.max(y, 8)) + "px";
  };

  const showTooltip = (element, pointerEvent) => {
    const node = resolveNode(element);
    if (!node || node.dataset.ragTab !== activeTab) return;
    const title = node.dataset.title || "";
    const description = node.dataset.description || "";
    tooltip.textContent = description ? title + ": " + description : title;
    tooltip.hidden = false;
    positionTooltip(element, pointerEvent);
    if (describedNode) describedNode.removeAttribute("aria-describedby");
    element.setAttribute("aria-describedby", tooltip.id);
    describedNode = element;
  };

  const clearSelection = () => {
    root.querySelectorAll("[data-rag-node][aria-pressed='true'], [data-rag-ref][aria-pressed='true']")
      .forEach((element) => element.setAttribute("aria-pressed", "false"));
    root.querySelectorAll(".home-rag-node.is-selected, .home-rag__mobile-flow button.is-selected, .home-rag__mobile-retrieval button.is-selected, .home-rag__chart-row.is-selected")
      .forEach((element) => element.classList.remove("is-selected"));
    root.querySelectorAll(".home-rag__edge.is-related").forEach((edge) => edge.classList.remove("is-related"));
  };

  const activateTab = (tab, moveFocus = false) => {
    activeTab = tab.dataset.ragTab;
    tabs.forEach((candidate) => {
      const selected = candidate === tab;
      candidate.setAttribute("aria-selected", String(selected));
      candidate.tabIndex = selected ? 0 : -1;
      candidate.classList.toggle("is-active", selected);
    });
    panels.forEach((panel) => {
      panel.hidden = panel.dataset.ragPanel !== activeTab;
    });
    clearSelection();
    hideTooltip();
    detailsTitle.textContent = "Explore o pipeline";
    detailsDescription.textContent = emptyMessages[activeTab];
    detailsMeta.hidden = true;
    detailsMetaLabel.textContent = "";
    detailsMetaValue.textContent = "";
    if (moveFocus) tab.focus();
  };

  const selectNode = (element) => {
    const node = resolveNode(element);
    if (!node || node.dataset.ragTab !== activeTab) return;

    clearSelection();
    node.setAttribute("aria-pressed", "true");
    node.classList.add("is-selected");
    root.querySelectorAll("[data-rag-ref]").forEach((reference) => {
      if (reference.dataset.ragRef === node.id) {
        reference.setAttribute("aria-pressed", "true");
        reference.classList.add("is-selected");
      }
    });

    const key = node.dataset.ragNode;
    root.querySelectorAll("[data-rag-edge]").forEach((edge) => {
      const connectedNodes = edge.dataset.ragEdge.split(/\s+/);
      edge.classList.toggle("is-related", connectedNodes.includes(key));
    });

    detailsTitle.textContent = node.dataset.title || "";
    detailsDescription.textContent = node.dataset.detail || node.dataset.description || "";
    detailsMetaLabel.textContent = node.dataset.metaLabel || "";
    detailsMetaValue.textContent = node.dataset.meta || "";
    detailsMeta.hidden = !node.dataset.meta;
    hideTooltip();
  };

  root.querySelector("[data-rag-tabs]").addEventListener("click", (event) => {
    const tab = event.target.closest("[data-rag-tab][role='tab']");
    if (tab) activateTab(tab);
  });

  root.querySelector("[data-rag-tabs]").addEventListener("keydown", (event) => {
    const focusedTab = event.target.closest("[role='tab']");
    const currentIndex = tabs.indexOf(focusedTab);
    if (currentIndex < 0) return;

    let nextIndex = currentIndex;
    if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % tabs.length;
    else if (event.key === "ArrowLeft") nextIndex = (currentIndex + tabs.length - 1) % tabs.length;
    else if (event.key === "Home") nextIndex = 0;
    else if (event.key === "End") nextIndex = tabs.length - 1;
    else return;

    event.preventDefault();
    activateTab(tabs[nextIndex], true);
  });

  root.addEventListener("click", (event) => {
    const target = event.target.closest("[data-rag-node], [data-rag-ref]");
    if (target) selectNode(target);
  });

  root.addEventListener("keydown", (event) => {
    const target = event.target.closest("[data-rag-node][role='button']");
    if (!target || !["Enter", " "].includes(event.key)) return;
    event.preventDefault();
    selectNode(target);
  });

  root.addEventListener("pointerover", (event) => {
    const target = event.target.closest("[data-rag-node], [data-rag-ref]");
    if (!target || target.contains(event.relatedTarget)) return;
    showTooltip(target, event);
  });

  root.addEventListener("pointerout", (event) => {
    const target = event.target.closest("[data-rag-node], [data-rag-ref]");
    if (!target || target.contains(event.relatedTarget)) return;
    hideTooltip();
  });

  root.addEventListener("focusin", (event) => {
    const target = event.target.closest("[data-rag-node], [data-rag-ref]");
    if (target) showTooltip(target);
  });

  root.addEventListener("focusout", (event) => {
    const target = event.target.closest("[data-rag-node], [data-rag-ref]");
    if (!target || target.contains(event.relatedTarget)) return;
    hideTooltip();
  });
})();
