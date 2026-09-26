(() => {
  let theme = "light";
  try {
    theme = localStorage.getItem("getnet-portal-theme") === "dark" ? "dark" : "light";
  } catch (_) {
    // Private browsing may disable storage; the default remains light.
  }
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;

  window.setGetnetPortalTheme = (nextTheme) => {
    const value = nextTheme === "dark" ? "dark" : "light";
    document.documentElement.dataset.theme = value;
    document.documentElement.style.colorScheme = value;
    try { localStorage.setItem("getnet-portal-theme", value); } catch (_) {}
    document.dispatchEvent(new CustomEvent("portalthemechange", { detail: value }));
  };
})();
