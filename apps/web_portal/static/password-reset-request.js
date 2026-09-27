(() => {
  "use strict";

  const form = document.querySelector("[data-reset-form]");
  if (!form) return;

  const username = form.querySelector('input[name="username"]');
  const submitButton = form.querySelector("[data-reset-submit]");
  const field = username?.closest("[data-reset-field]");
  const requiredError = field?.querySelector("[data-reset-required-error]");
  if (!username || !submitButton || !field || !requiredError) return;

  username.placeholder = "Usuário";

  const isEmpty = () => !username.value.trim();

  const updateSubmitState = () => {
    const ready = !isEmpty();
    submitButton.disabled = !ready;
    submitButton.setAttribute("aria-disabled", String(!ready));
  };

  const setRequiredError = (show) => {
    const serverErrors = field.querySelector(".login-field__server-errors");
    const hasServerError = Boolean(serverErrors);
    const serverText = serverErrors?.textContent?.trim().toLocaleLowerCase() || "";
    const duplicateRequiredMessage = /este campo.*obrigat|this field is required/.test(serverText);
    const showMessage = show && !duplicateRequiredMessage;

    field.classList.toggle("is-invalid", show || hasServerError);
    requiredError.hidden = !showMessage;
    username.setAttribute("aria-invalid", String(show || hasServerError));

    const describedBy = [];
    if (showMessage) describedBy.push(requiredError.id);
    if (serverErrors?.id) describedBy.push(serverErrors.id);
    if (describedBy.length) username.setAttribute("aria-describedby", describedBy.join(" "));
    else username.removeAttribute("aria-describedby");
  };

  username.addEventListener("focus", () => {
    username.dataset.interacted = "true";
  });
  username.addEventListener("blur", () => {
    if (username.dataset.interacted === "true") setRequiredError(isEmpty());
  });
  username.addEventListener("input", () => {
    if (!isEmpty()) setRequiredError(false);
    else if (username.dataset.interacted === "true") setRequiredError(true);
    updateSubmitState();
  });
  username.addEventListener("change", updateSubmitState);

  form.addEventListener("submit", (event) => {
    if (!isEmpty()) return;
    event.preventDefault();
    setRequiredError(true);
    username.focus();
    updateSubmitState();
  });

  setRequiredError(false);
  updateSubmitState();
  window.addEventListener("pageshow", updateSubmitState);
})();
