var $ = id => document.getElementById(id);

var dot = $("dot");
var slabel = $("slabel");
var transcriptEl = $("transcript");
var dbgEl = $("dbg");
var perfEl = $("perf");
var recBtn = $("rec-btn");
var copyBtn = $("copy-btn");
var clearBtn = $("clear-btn");
var recLabel = $("rec-label");
var cancelBtn = $("cancel-btn");
var modelSel = $("model");
var modelDescriptionEl = $("model-description");
var modelButtonListEl = $("model-button-list");
var deviceSel = $("device");
var computeTypeSel = $("compute-type");
var langSel = $("lang");
var uiLangSel = $("uilang");
var audioDeviceSel = $("audio-device");
var micTestBtn = $("mic-test-btn");
var micTestStatusEl = $("mic-test-status");
var micLevelBarEl = $("mic-level-bar");
var textModeSel = $("text-mode");
var beamSizeSel = $("beam-size");
var vadFilterSel = $("vad-filter");
var historyEnabledSel = $("history-enabled");
var fsizeSel = $("fsize");
var appendSel = $("appendmode");
var topBtn = $("topbtn");
var resetDefaultsBtn = $("reset-defaults-btn");
var historyBtn = $("history-btn");
var clearHistoryBtn = $("clear-history-btn");
var diagnosticsBtn = $("diagnostics-btn");
var hkDisplay = $("hk-display");
var hkRecordBtn = $("hk-record-btn");
var errorModal = $("error-modal");
var errorTitle = $("error-title");
var errorMessage = $("error-message");
var errorClose = $("error-close");
var errorCopy = $("error-copy");

var contentScroll = $("content-scroll");
var viewTitle = $("view-title");
var viewSubtitle = $("view-subtitle");
var systemStatusEl = $("system-status");
var homeMetricsEl = $("home-metrics");
var historyListEl = $("history-list");
var historySearchEl = $("history-search");
var historyLanguageEl = $("history-language");
var historySummaryEl = $("history-summary");
var historyExportJsonBtn = $("history-export-json");
var historyExportMdBtn = $("history-export-md");
var historyExportTxtBtn = $("history-export-txt");
var diagnosticsOutputEl = $("diagnostics-output");
var modelsListEl = $("models-list");
var modelsRefreshBtn = $("models-refresh");
var modelsCacheDirEl = $("models-cache-dir");
var extensionsListEl = $("extensions-list");
var extensionsRefreshBtn = $("extensions-refresh");
var dependenciesListEl = $("dependencies-list");
var dependenciesRefreshBtn = $("dependencies-refresh");
var dependencyDirEl = $("dependency-dir");
var winMinBtn = $("win-min");
var winMaxBtn = $("win-max");
var winCloseBtn = $("win-close");
var autoDeviceToggle = $("auto-device-toggle");
var autoDeviceCurrent = $("auto-device-current");
var manualDeviceOptions = $("device-manual-options");
var progressOverlay = $("progress-overlay");
var progressTitle = $("progress-title");
var progressDetail = $("progress-detail");
var progressClose = $("progress-close");

var uiLanguage = "en";
var recording = false;
var text = "";
var cancelled = false;
var onTop = false;
var recordingKey = false;
var currentRequest = null;
var currentStatusKey = "status_ready";
var currentHotkey = {modifiers: ["alt"], key: "z"};
var pendingMods = [];
var shownModelErrors = new Set();
var shownDependencyWarning = false;
var modelInfoCache = null;
var dbgLines = [];

function t(key) {
  const current = window.I18N[uiLanguage] || {};
  const fallback = window.I18N.en || {};
  return current[key] || fallback[key] || key;
}

function applyTranslations() {
  const supported = window.I18N[uiLanguage] ? uiLanguage : "en";
  uiLanguage = supported;
  document.documentElement.lang = supported;
  document.documentElement.dataset.uiLanguage = supported;
  document.body.dataset.uiLanguage = supported;
  document.querySelectorAll("[data-i18n]").forEach(el => { el.textContent = t(el.dataset.i18n); });
  document.querySelectorAll("[data-i18n-title]").forEach(el => { el.title = t(el.dataset.i18nTitle); });
  document.querySelectorAll("[data-i18n-aria]").forEach(el => { el.setAttribute("aria-label", t(el.dataset.i18nAria)); });
  document.querySelectorAll("[data-i18n-placeholder]").forEach(el => { el.placeholder = t(el.dataset.i18nPlaceholder); });
  if (uiLangSel) uiLangSel.value = supported;
  if (topBtn) topBtn.textContent = onTop ? t("top_on") : t("top_off");
  if (hkRecordBtn) hkRecordBtn.textContent = recordingKey ? t("press_any_key") : t("set_hotkey");
  if (recLabel) recLabel.textContent = recording ? t("recording_release") : t("record_idle");
  if (slabel) slabel.textContent = t(currentStatusKey);
  if (!text) renderText();
  updateStats();
}

function setStatus(state, key) {
  dot.className = state;
  currentStatusKey = key;
  slabel.textContent = t(key);
}

function dbg(msg) {
  const ts = new Date().toLocaleTimeString("en-US", {hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit"});
  dbgLines.push(ts + " " + msg);
  if (dbgLines.length > 12) dbgLines.shift();
  dbgEl.textContent = dbgLines.join("\n");
  fetch("/log", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({msg})}).catch(() => {});
}


function showProgress(title, detail) {
  if (!progressOverlay) return;
  progressTitle.textContent = title || t("operation_in_progress");
  progressDetail.textContent = detail || t("please_wait");
  progressOverlay.classList.add("show");
  progressOverlay.setAttribute("aria-hidden", "false");
  document.body.classList.add("progress-active");
}

function updateProgress(detail) {
  if (progressDetail && detail) progressDetail.textContent = detail;
}

function hideProgress() {
  if (!progressOverlay) return;
  progressOverlay.classList.remove("show");
  progressOverlay.setAttribute("aria-hidden", "true");
  document.body.classList.remove("progress-active");
}

if (progressClose) progressClose.onclick = hideProgress;

function renderText() {
  if (text) {
    transcriptEl.textContent = text;
  } else {
    transcriptEl.innerHTML = `<span class="placeholder" data-i18n="transcript_placeholder">${t("transcript_placeholder")}</span>`;
  }
}
