(() => {
  const roadmap = document.querySelector("[data-home-roadmap]");
  const decisions = document.querySelector("[data-home-decisions]");

  if (roadmap) {
    const steps = [...roadmap.querySelectorAll("[data-roadmap-step]")];
    const title = roadmap.querySelector("[data-roadmap-details-title]");
    const description = roadmap.querySelector("[data-roadmap-details-description]");
    const status = roadmap.querySelector("[data-roadmap-details-status]");

    function selectStep(step) {
      steps.forEach((item) => {
        const selected = item === step;
        item.setAttribute("aria-pressed", String(selected));
        item.classList.toggle("is-selected", selected);
      });
      if (title) title.textContent = step.dataset.title;
      if (description) description.textContent = step.dataset.detail;
      if (status) {
        status.textContent = step.dataset.status;
        status.dataset.state = step.dataset.status.split(" · ")[0].toLowerCase();
      }
    }

    steps.forEach((step, index) => {
      step.addEventListener("click", () => selectStep(step));
      step.addEventListener("focus", () => selectStep(step));
      step.addEventListener("keydown", (event) => {
        let nextIndex = index;
        if (event.key === "Home") nextIndex = 0;
        else if (event.key === "End") nextIndex = steps.length - 1;
        else if (event.key === "ArrowRight") nextIndex = Math.min(index + 1, steps.length - 1);
        else if (event.key === "ArrowLeft") nextIndex = Math.max(index - 1, 0);
        else if (event.key === "ArrowDown") nextIndex = Math.min(index + 6, steps.length - 1);
        else if (event.key === "ArrowUp") nextIndex = Math.max(index - 6, 0);
        else return;
        event.preventDefault();
        steps[nextIndex].focus();
      });
    });

    const currentStep = steps.find((step) => step.getAttribute("aria-pressed") === "true") || steps[0];
    if (currentStep) selectStep(currentStep);
  }

  if (decisions) {
    const items = [...decisions.querySelectorAll("[data-decision-item]")];
    const number = decisions.querySelector("[data-decision-number]");
    const title = decisions.querySelector("[data-decision-title]");
    const decision = decisions.querySelector("[data-decision-value]");
    const reason = decisions.querySelector("[data-decision-reason]");
    const result = decisions.querySelector("[data-decision-result]");

    function selectDecision(item, index) {
      items.forEach((option) => {
        const selected = option === item;
        option.setAttribute("aria-pressed", String(selected));
        option.classList.toggle("is-selected", selected);
      });
      if (number) number.textContent = String(index + 1).padStart(2, "0");
      if (title) title.textContent = item.dataset.title;
      if (decision) decision.textContent = item.dataset.decision;
      if (reason) reason.textContent = item.dataset.reason;
      if (result) result.textContent = item.dataset.result;
    }

    items.forEach((item, index) => {
      item.addEventListener("click", () => selectDecision(item, index));
      item.addEventListener("focus", () => selectDecision(item, index));
      item.addEventListener("keydown", (event) => {
        let nextIndex = index;
        if (event.key === "Home") nextIndex = 0;
        else if (event.key === "End") nextIndex = items.length - 1;
        else if (event.key === "ArrowDown" || event.key === "ArrowRight") nextIndex = (index + 1) % items.length;
        else if (event.key === "ArrowUp" || event.key === "ArrowLeft") nextIndex = (index - 1 + items.length) % items.length;
        else return;
        event.preventDefault();
        items[nextIndex].focus();
      });
    });

    const initial = items.find((item) => item.getAttribute("aria-pressed") === "true") || items[0];
    if (initial) selectDecision(initial, items.indexOf(initial));
  }
})();
