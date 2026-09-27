(() => {
  "use strict";

  const root = document.querySelector("[data-login-root]");
  if (!root) return;

  const welcomeView = root.querySelector('[data-login-view="welcome"]');
  const loginView = root.querySelector('[data-login-view="login"]');
  const openButton = root.querySelector("[data-login-open]");
  const backButton = root.querySelector("[data-login-back]");
  const form = root.querySelector("[data-login-form]");
  const username = form?.querySelector('input[name="username"]');
  const password = form?.querySelector('input[name="password"]');
  const submitButton = form?.querySelector("[data-login-submit]");
  const passwordToggle = form?.querySelector("[data-password-toggle]");
  const rememberToggle = form?.querySelector("[data-remember-username]");
  const storageKey = "getnet-support-remembered-username";

  if (!welcomeView || !loginView || !openButton || !backButton || !form || !username || !password || !submitButton) return;

  username.placeholder = "Usuário";
  password.placeholder = "Senha";

  const setView = (view, { focus = true } = {}) => {
    const showLogin = view === "login";
    welcomeView.hidden = showLogin;
    loginView.hidden = !showLogin;
    backButton.hidden = !showLogin;
    openButton.setAttribute("aria-expanded", String(showLogin));

    if (focus) {
      window.requestAnimationFrame(() => {
        (showLogin ? username : openButton).focus();
      });
    }
  };

  const fieldContainer = (input) => input.closest("[data-login-field]");
  const requiredError = (input) => fieldContainer(input)?.querySelector("[data-required-error]");

  const setFieldError = (input, show) => {
    const field = fieldContainer(input);
    const error = requiredError(input);
    if (!field || !error) return;

    const serverErrors = field.querySelector(".login-field__server-errors");
    const hasServerError = Boolean(serverErrors);
    const serverText = serverErrors?.textContent?.trim().toLocaleLowerCase() || "";
    const duplicateRequiredMessage = /este campo.*obrigat|this field is required/.test(serverText);
    const showRequiredMessage = show && !duplicateRequiredMessage;
    field.classList.toggle("is-invalid", show || hasServerError);
    error.hidden = !showRequiredMessage;
    input.setAttribute("aria-invalid", String(show || hasServerError));

    const describedBy = [];
    if (showRequiredMessage) describedBy.push(error.id);
    if (serverErrors?.id) describedBy.push(serverErrors.id);
    if (describedBy.length) input.setAttribute("aria-describedby", describedBy.join(" "));
    else input.removeAttribute("aria-describedby");
  };

  const updateSubmitState = () => {
    const ready = Boolean(username.value.trim() && password.value);
    submitButton.disabled = !ready;
    submitButton.setAttribute("aria-disabled", String(!ready));
  };

  const readRememberedUsername = () => {
    if (!rememberToggle) return;
    try {
      const savedUsername = window.localStorage.getItem(storageKey);
      if (savedUsername) {
        rememberToggle.checked = true;
        if (!username.value) username.value = savedUsername;
      }
    } catch (_error) {
      rememberToggle.checked = false;
    }
  };

  const persistRememberedUsername = () => {
    if (!rememberToggle) return;
    try {
      if (rememberToggle.checked && username.value.trim()) {
        window.localStorage.setItem(storageKey, username.value.trim());
      } else {
        window.localStorage.removeItem(storageKey);
      }
    } catch (_error) {
      // The login remains fully functional when browser storage is unavailable.
    }
  };

  openButton.setAttribute("aria-expanded", "false");
  openButton.setAttribute("aria-controls", "login-auth-view");
  loginView.id = "login-auth-view";
  openButton.addEventListener("click", () => setView("login"));
  backButton.addEventListener("click", () => setView("welcome"));

  for (const input of [username, password]) {
    input.addEventListener("focus", () => {
      input.dataset.interacted = "true";
    });
    input.addEventListener("blur", () => {
      const empty = input === username ? !input.value.trim() : !input.value;
      if (input.dataset.interacted === "true") setFieldError(input, empty);
    });
    input.addEventListener("input", () => {
      const empty = input === username ? !input.value.trim() : !input.value;
      if (!empty) setFieldError(input, false);
      else if (input.dataset.interacted === "true") setFieldError(input, true);
      updateSubmitState();
      if (input === username && rememberToggle?.checked) persistRememberedUsername();
    });
    input.addEventListener("change", updateSubmitState);
    setFieldError(input, false);
  }

  passwordToggle?.addEventListener("click", () => {
    const willShow = password.type === "password";
    password.type = willShow ? "text" : "password";
    passwordToggle.setAttribute("aria-pressed", String(willShow));
    passwordToggle.setAttribute("aria-label", willShow ? "Ocultar senha" : "Mostrar senha");
    password.focus();
  });

  rememberToggle?.addEventListener("change", persistRememberedUsername);

  form.addEventListener("submit", (event) => {
    const missingUsername = !username.value.trim();
    const missingPassword = !password.value;
    setFieldError(username, missingUsername);
    setFieldError(password, missingPassword);
    updateSubmitState();

    if (missingUsername || missingPassword) {
      event.preventDefault();
      (missingUsername ? username : password).focus();
      return;
    }

    persistRememberedUsername();
  });

  readRememberedUsername();
  updateSubmitState();
  window.addEventListener("pageshow", updateSubmitState);
  setView(root.dataset.initialState === "login" ? "login" : "welcome", { focus: false });
})();
