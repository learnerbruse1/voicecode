import {initializeI18n} from "./i18n.js";
import "./api.js";
import "./accessibility.js";
import "./dependencies.js";
import "./extensions.js";
import "./onboarding.js";

function rememberActiveView(viewName) {
  try { window.sessionStorage.setItem("voicecode.activeView", viewName); }
  catch (_) { /* sessionStorage can be disabled; navigation still works. */ }
}

function initialViewName() {
  try {
    const saved = window.sessionStorage.getItem("voicecode.activeView");
    if (saved && document.getElementById(`view-${saved}`)) return saved;
  } catch (_) { /* ignore unavailable sessionStorage */ }
  return "home";
}

function setActiveView(viewName) {
  if (!document.getElementById(`view-${viewName}`)) viewName = "home";
  rememberActiveView(viewName);
  document.querySelectorAll(".nav-item").forEach(btn => btn.classList.toggle("active", btn.dataset.view === viewName));
  document.querySelectorAll(".view").forEach(view => view.classList.toggle("active", view.id === `view-${viewName}`));
  const view = $(`view-${viewName}`);
  if (view) {
    const titleKey = view.dataset.titleKey || "nav_home";
    const subtitleKey = view.dataset.subtitleKey || "home_subtitle";
    viewTitle.dataset.i18n = titleKey;
    viewSubtitle.dataset.i18n = subtitleKey;
    viewTitle.textContent = t(titleKey);
    viewSubtitle.textContent = t(subtitleKey);
  }
  if (contentScroll) contentScroll.scrollTop = 0;
  if (viewName === "history") loadHistoryPanel();
  if (viewName === "diagnostics") loadDiagnosticsPanel();
  if (viewName === "models") loadModelsPanel();
  if (viewName === "extensions") loadExtensionsPanel();
  if (viewName === "dependencies") loadDependenciesPanel();
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

async function bootstrapVoiceCode() {
  await initializeI18n("en");
  const version = document.querySelector('meta[name="voicecode-version"]')?.content;
  if (sidebarVersionEl) sidebarVersionEl.textContent = version ? `VoiceCode ${version}` : "VoiceCode";
  applyTranslations();
  setupNavigation();
  setupWindowControls();
  setupOnboarding();
  setActiveView(initialViewName());
  await loadConfig();
  // Determine first-start state before optional runtime probes. The onboarding
  // payload already contains audio/runtime readiness, so the main UI does not
  // need to enumerate audio devices behind the guide.
  const onboardingVisible = await loadOnboarding(false);
  if (!onboardingVisible) await loadAudioDevices();
  await pollModelStatus(true);
  await updateAutoDeviceLabel();
  if (!onboardingVisible) await warnMissingDependenciesOnce();
  await resumeDependencyTasks();
  updateStats();
  scheduleStatusPolling();
}

var statusPollTimer = null;
async function runStatusPoll() {
  if (recording) {
    scheduleStatusPolling();
    return;
  }
  await Promise.allSettled([pollModelStatus(false), updateStats()]);
  scheduleStatusPolling();
}

function scheduleStatusPolling() {
  if (statusPollTimer) clearTimeout(statusPollTimer);
  const delay = document.hidden ? 15000 : (statusActive ? 3000 : 10000);
  statusPollTimer = setTimeout(runStatusPoll, delay);
}

document.addEventListener("visibilitychange", () => {
  if (!document.hidden) runStatusPoll();
  else scheduleStatusPolling();
});

bootstrapVoiceCode().catch(error => showError(t("operation_failed"), error.message || String(error)));
