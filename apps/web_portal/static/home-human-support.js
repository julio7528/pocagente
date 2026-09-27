(() => {
  const root = document.querySelector("[data-home-human]");
  if (!root) return;

  const svgNodes = [...root.querySelectorAll(".home-human-node[data-human-node]")];
  const controls = [...root.querySelectorAll("[data-human-node]")];
  const mobileSteps = [...root.querySelectorAll("[data-human-ref]")];
  const edges = [...root.querySelectorAll("[data-human-edge]")];
  const title = root.querySelector("[data-human-details-title]");
  const description = root.querySelector("[data-human-details-description]");
  const meta = root.querySelector("[data-human-details-meta]");
  const metaLabel = root.querySelector("[data-human-details-meta-label]");
  const metaValue = root.querySelector("[data-human-details-meta-value]");
  const relatedEdges = {
    direct: ["direct-waiting"],
    offer: ["offer-confirm"],
    confirm: ["offer-confirm", "confirm-waiting"],
    waiting: ["direct-waiting", "confirm-waiting", "waiting-queue"],
    queue: ["waiting-queue", "queue-claim"],
    claim: ["queue-claim", "claim-human"],
    human: ["claim-human", "human-thread"],
    thread: ["human-thread", "thread-resolve"],
    resolve: ["thread-resolve"],
  };

  function select(control) {
    const key = control.dataset.humanNode;
    controls.forEach((item) => {
      const selected = item.dataset.humanNode === key;
      item.setAttribute("aria-pressed", String(selected));
      item.classList.toggle("is-selected", selected);
    });

    const activeEdges = relatedEdges[key] || [];
    edges.forEach((edge) => edge.classList.toggle("is-related", activeEdges.includes(edge.dataset.humanEdge)));

    if (title) title.textContent = control.dataset.title || "Atendimento Humano";
    if (description) description.textContent = control.dataset.detail || control.dataset.description || "";
    if (meta && metaLabel && metaValue) {
      const hasMeta = Boolean(control.dataset.meta);
      meta.hidden = !hasMeta;
      metaLabel.textContent = hasMeta ? `${control.dataset.metaLabel || "Detalhe"}: ` : "";
      metaValue.textContent = hasMeta ? control.dataset.meta : "";
    }
  }

  controls.forEach((control) => {
    control.addEventListener("click", () => select(control));
    control.addEventListener("mouseenter", () => select(control));
    control.addEventListener("focus", () => select(control));
    control.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        select(control);
        return;
      }
      if (!["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp", "Home", "End"].includes(event.key)) return;
      const group = control.classList.contains("home-human-node") ? svgNodes : controls.filter((item) => item.classList.contains("home-human-capability"));
      const index = group.indexOf(control);
      if (index < 0) return;
      event.preventDefault();
      const nextIndex = event.key === "Home" ? 0 : event.key === "End" ? group.length - 1 : (index + (event.key === "ArrowRight" || event.key === "ArrowDown" ? 1 : -1) + group.length) % group.length;
      group[nextIndex].focus();
    });
  });

  mobileSteps.forEach((step) => {
    step.addEventListener("click", () => {
      const key = step.dataset.humanRef;
      const target = svgNodes.find((node) => node.dataset.humanNode === key);
      if (target) select(target);
    });
  });
})();
