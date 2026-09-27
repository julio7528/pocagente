(() => {
  const root = document.querySelector("[data-home-security]");
  if (!root) return;

  const title = root.querySelector("[data-security-details-title]");
  const description = root.querySelector("[data-security-details-description]");
  const meta = root.querySelector("[data-security-details-meta]");
  const metaLabel = root.querySelector("[data-security-details-meta-label]");
  const metaValue = root.querySelector("[data-security-details-meta-value]");
  const tooltip = root.querySelector("[data-security-tooltip]");
  let describedElement = null;

  const resolveItem = (element) => {
    if (!element) return null;
    if (element.matches("[data-security-ref]")) {
      const referenced = document.getElementById(element.dataset.securityRef);
      return referenced && root.contains(referenced) ? referenced : null;
    }
    return element.matches("[data-security-node]") ? element : null;
  };

  const clearDescriptionLink = () => {
    if (describedElement) {
      describedElement.removeAttribute("aria-describedby");
      describedElement = null;
    }
  };

  const hideTooltip = () => {
    tooltip.hidden = true;
    tooltip.textContent = "";
    clearDescriptionLink();
  };

  const showTooltip = (element, pointerEvent) => {
    const item = resolveItem(element);
    if (!item) return;
    const itemTitle = item.dataset.title || "";
    const itemDescription = item.dataset.description || "";
    tooltip.textContent = itemDescription ? itemTitle + ": " + itemDescription : itemTitle;
    tooltip.hidden = false;

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

    clearDescriptionLink();
    element.setAttribute("aria-describedby", tooltip.id);
    describedElement = element;
  };

  const resetDetails = () => {
    title.textContent = "Explore os controles de segurança";
    description.textContent = "Selecione uma etapa para entender como o Getnet Support protege solicitações, respostas e registros de auditoria.";
    meta.hidden = true;
    metaLabel.textContent = "";
    metaValue.textContent = "";
  };

  const clearSelection = () => {
    root.querySelectorAll("[data-security-node][aria-pressed='true'], [data-security-ref][aria-pressed='true']")
      .forEach((element) => element.setAttribute("aria-pressed", "false"));
    root.querySelectorAll(".home-security-node.is-selected, .home-security-capability.is-selected, .home-security__mobile-flow button.is-selected")
      .forEach((element) => element.classList.remove("is-selected"));
    root.querySelectorAll(".home-security-edge.is-related")
      .forEach((edge) => edge.classList.remove("is-related"));
  };

  const selectItem = (element) => {
    const item = resolveItem(element);
    if (!item) return;

    clearSelection();
    item.setAttribute("aria-pressed", "true");
    item.classList.add("is-selected");
    root.querySelectorAll("[data-security-ref]").forEach((reference) => {
      if (reference.dataset.securityRef === item.id) {
        reference.setAttribute("aria-pressed", "true");
        reference.classList.add("is-selected");
      }
    });

    const key = item.dataset.securityNode;
    root.querySelectorAll("[data-security-edge]").forEach((edge) => {
      edge.classList.toggle("is-related", edge.dataset.securityEdge.split(/\s+/).includes(key));
    });

    title.textContent = item.dataset.title || "";
    description.textContent = item.dataset.detail || item.dataset.description || "";
    metaLabel.textContent = item.dataset.metaLabel || "";
    metaValue.textContent = item.dataset.meta || "";
    meta.hidden = !item.dataset.meta;
    hideTooltip();
  };

  root.addEventListener("click", (event) => {
    const target = event.target.closest("[data-security-node], [data-security-ref]");
    if (target) selectItem(target);
  });

  root.addEventListener("keydown", (event) => {
    const target = event.target.closest("[data-security-node][role='button']");
    if (target && ["Enter", " "].includes(event.key)) {
      event.preventDefault();
      selectItem(target);
      return;
    }
    if (event.key === "Escape") {
      clearSelection();
      hideTooltip();
      resetDetails();
    }
  });

  root.addEventListener("pointerover", (event) => {
    const target = event.target.closest("[data-security-node], [data-security-ref]");
    if (!target || target.contains(event.relatedTarget)) return;
    showTooltip(target, event);
  });

  root.addEventListener("pointerout", (event) => {
    const target = event.target.closest("[data-security-node], [data-security-ref]");
    if (!target || target.contains(event.relatedTarget)) return;
    hideTooltip();
  });

  root.addEventListener("focusin", (event) => {
    const target = event.target.closest("[data-security-node], [data-security-ref]");
    if (target) showTooltip(target);
  });

  root.addEventListener("focusout", (event) => {
    const target = event.target.closest("[data-security-node], [data-security-ref]");
    if (!target || target.contains(event.relatedTarget)) return;
    hideTooltip();
  });
})();
