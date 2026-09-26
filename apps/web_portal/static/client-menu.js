(() => {
  const initializeMenu = () => {
    const trigger = document.querySelector("[data-client-menu-trigger]");
    const menu = document.querySelector("[data-client-menu]");
    const themeToggle = document.querySelector("[data-theme-toggle]");
    if (!trigger || !menu) return;

    const closeMenu = () => {
      menu.hidden = true;
      trigger.setAttribute("aria-expanded", "false");
    };
    const updateThemeLabel = () => {
      if (!themeToggle) return;
      const dark = document.documentElement.dataset.theme === "dark";
      themeToggle.querySelector("[data-theme-label]").textContent = dark ? "Tema claro" : "Tema escuro";
      themeToggle.querySelector(".theme-icon").textContent = dark ? "☀" : "☾";
    };

    updateThemeLabel();
    trigger.addEventListener("click", (event) => {
      event.preventDefault();
      menu.hidden = !menu.hidden;
      trigger.setAttribute("aria-expanded", String(!menu.hidden));
    });
    document.addEventListener("click", (event) => {
      if (!menu.hidden && !menu.contains(event.target) && !trigger.contains(event.target)) closeMenu();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !menu.hidden) {
        closeMenu();
        trigger.focus();
      }
    });
    themeToggle?.addEventListener("click", () => {
      window.setGetnetPortalTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
      updateThemeLabel();
      closeMenu();
      trigger.focus();
    });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeMenu, { once: true });
  } else {
    initializeMenu();
  }
})();
