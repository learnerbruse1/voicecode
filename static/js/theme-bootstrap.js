try {
  const preference = localStorage.getItem("voicecode.theme") || "system";
  const systemLight = matchMedia("(prefers-color-scheme: light)").matches;
  document.documentElement.dataset.themePreference = preference;
  document.documentElement.dataset.theme =
    preference === "system" ? (systemLight ? "light" : "dark") : preference;
} catch (_) {
  // Theme initialization is best effort; the main UI applies a safe fallback.
}
