function setActiveView(viewName) {
  document.querySelectorAll(".nav-item").forEach(btn => btn.classList.toggle("active", btn.dataset.view === viewName));
  document.querySelectorAll(".view").forEach(view => view.classList.toggle("active", view.id === `view-${viewName}`));
  const view = $(`view-${viewName}`);
  if (view) {
    const titleKey = view.dataset.titleKey || "nav_home";
    const subtitleKey = view.dataset.subtitleKey || "home_subtitle";
    viewTitle.textContent = t(titleKey);
    viewSubtitle.textContent = t(subtitleKey);
  }
  if (contentScroll) contentScroll.scrollTop = 0;
  if (viewName === "history") loadHistoryPanel();
  if (viewName === "diagnostics") loadDiagnosticsPanel();
  if (viewName === "extensions") loadExtensionsPanel();
}

function setupNavigation() {
  document.querySelectorAll(".nav-item").forEach(btn => {
    btn.onclick = () => setActiveView(btn.dataset.view || "home");
  });
}

async function callWindowApi(method) {
  if (!(window.pywebview && pywebview.api && pywebview.api[method])) return false;
  try { return await pywebview.api[method](); }
  catch (e) { showError(t("operation_failed"), e.message || String(e)); return false; }
}

function setupWindowControls() {
  if (winMinBtn) winMinBtn.onclick = () => callWindowApi("minimize_window");
  if (winMaxBtn) winMaxBtn.onclick = () => callWindowApi("toggle_maximize_window");
  if (winCloseBtn) winCloseBtn.onclick = () => callWindowApi("close_window");
}

setupNavigation();
setupWindowControls();
loadAudioDevices().then(loadConfig).then(() => pollModelStatus(true)).then(updateAutoDeviceLabel);
setInterval(() => pollModelStatus(false), 3000);
setInterval(updateStats, 3000);
applyTranslations();
updateStats();
