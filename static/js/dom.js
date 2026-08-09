var $ = id => document.getElementById(id);

function htmlEscape(value) {
  return String(value || "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch]));
}

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
var decodePresetSel = $("decode-preset");
var vadFilterSel = $("vad-filter");
var conditionOnPreviousTextSel = $("condition-on-previous-text");
var historyEnabledSel = $("history-enabled");
var fsizeSel = $("fsize");
var themeSel = $("theme");
var appendSel = $("appendmode");
var typingModeSel = $("typing-mode");
var typingDelaySel = $("typing-delay");
var partialResultsSel = $("partial-results");
var partialIntervalSel = $("partial-interval");
var topBtn = $("topbtn");
var resetDefaultsBtn = $("reset-defaults-btn");
var historyBtn = $("history-btn");
var clearHistoryBtn = $("clear-history-btn");
var diagnosticsBtn = $("diagnostics-btn");
var diagnosticsExportBtn = $("diagnostics-export");
var hkDisplay = $("hk-display");
var hkRecordBtn = $("hk-record-btn");
var errorModal = $("error-modal");
var errorTitle = $("error-title");
var errorMessage = $("error-message");
var errorClose = $("error-close");
var errorCopy = $("error-copy");
var errorOpenLogs = $("error-open-logs");

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
var sidebarVersionEl = $("sidebar-version");
var winMinBtn = $("win-min");
var winMaxBtn = $("win-max");
var winCloseBtn = $("win-close");
var autoDeviceToggle = $("auto-device-toggle");
var autoDeviceCurrent = $("auto-device-current");
var manualDeviceOptions = $("device-manual-options");
var progressOverlay = $("progress-overlay");
var progressTitle = $("progress-title");
var progressDetail = $("progress-detail");
var progressBar = $("progress-bar");
var progressClose = $("progress-close");
var downloadCenter = $("download-center");
var downloadCenterTitle = $("download-center-title");
var downloadCenterDetail = $("download-center-detail");
var downloadCenterBar = $("download-center-bar");
var downloadCenterClose = $("download-center-close");

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
var downloadCenterHideTimer = null;

function t(key) {
  const catalogs = window.I18N || {};
  const current = catalogs[uiLanguage] || {};
  const fallback = catalogs.en || {};
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
  if (typeof window.refreshGamesTranslations === "function") window.refreshGamesTranslations();
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
  const headers = {"Content-Type": "application/json"};
  const token = document.querySelector('meta[name="voicecode-api-token"]')?.content || "";
  if (token) headers["X-VoiceCode-Token"] = token;
  fetch("/log", {method: "POST", headers, body: JSON.stringify({msg})}).catch(() => {});
}


function resolveTheme(theme) {
  if (theme === "system") return matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  return theme === "light" ? "light" : "dark";
}

function applyTheme(theme = "system") {
  const preference = ["dark", "light", "system"].includes(theme) ? theme : "system";
  document.documentElement.dataset.themePreference = preference;
  document.documentElement.dataset.theme = resolveTheme(preference);
  try { localStorage.setItem("voicecode.theme", preference); } catch (_) {}
}

function updateDownloadCenter(title, detail, percent = null) {
  if (!downloadCenter) return;
  if (downloadCenterHideTimer) { clearTimeout(downloadCenterHideTimer); downloadCenterHideTimer = null; }
  downloadCenter.classList.remove("failed", "complete");
  downloadCenter.classList.add("show");
  if (title) downloadCenterTitle.textContent = title;
  if (detail) downloadCenterDetail.textContent = detail;
  if (downloadCenterBar) {
    const value = Number(percent);
    downloadCenterBar.classList.toggle("indeterminate", !Number.isFinite(value));
    downloadCenterBar.style.width = Number.isFinite(value) ? `${Math.max(0, Math.min(100, value))}%` : "35%";
  }
}

function finishDownloadCenter(detail = "") {
  if (!downloadCenter) return;
  downloadCenter.classList.remove("failed");
  downloadCenter.classList.add("complete", "show");
  if (detail) downloadCenterDetail.textContent = detail;
  if (downloadCenterBar) { downloadCenterBar.classList.remove("indeterminate"); downloadCenterBar.style.width = "100%"; }
  downloadCenterHideTimer = setTimeout(() => downloadCenter?.classList.remove("show"), 2600);
}

function failDownloadCenter(title, detail = "") {
  if (!downloadCenter) return;
  downloadCenter.classList.remove("complete");
  downloadCenter.classList.add("failed", "show");
  if (title) downloadCenterTitle.textContent = title;
  if (detail) downloadCenterDetail.textContent = detail;
  if (downloadCenterBar) { downloadCenterBar.classList.remove("indeterminate"); downloadCenterBar.style.width = "100%"; }
}

matchMedia("(prefers-color-scheme: light)").addEventListener?.("change", () => {
  if (document.documentElement.dataset.themePreference === "system") applyTheme("system");
});
if (downloadCenterClose) downloadCenterClose.onclick = () => downloadCenter.classList.remove("show");

function showProgress(title, detail) {
  if (!progressOverlay) return;
  progressTitle.textContent = title || t("operation_in_progress");
  progressDetail.textContent = detail || t("please_wait");
  if (progressBar) {
    progressBar.classList.remove("determinate");
    progressBar.style.width = "35%";
  }
  progressOverlay.classList.add("show");
  progressOverlay.setAttribute("aria-hidden", "false");
  document.body.classList.add("progress-active");
  activateDialog(progressOverlay, progressClose);
}

function updateProgress(detail, percent = null, title = null) {
  if (progressDetail && detail) progressDetail.textContent = detail;
  if (progressTitle && title) progressTitle.textContent = title;
  updateDownloadCenter(title || progressTitle?.textContent, detail, percent);
  if (!progressBar) return;
  const numeric = Number(percent);
  if (Number.isFinite(numeric)) {
    progressBar.classList.add("determinate");
    progressBar.style.width = `${Math.max(0, Math.min(100, numeric))}%`;
  } else {
    progressBar.classList.remove("determinate");
    progressBar.style.width = "35%";
  }
}

function formatModelBytes(bytes) {
  const value = Number(bytes || 0);
  if (value >= 1024 ** 3) return `${(value / 1024 ** 3).toFixed(2)} GB`;
  if (value >= 1024 ** 2) return `${(value / 1024 ** 2).toFixed(1)} MB`;
  if (value >= 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${Math.max(0, value).toFixed(0)} B`;
}

function formatModelDuration(seconds) {
  const value = Math.max(0, Number(seconds || 0));
  if (value < 60) return `${Math.round(value)}s`;
  return `${Math.floor(value / 60)}m ${Math.round(value % 60)}s`;
}

function modelOperationProgress(state = {}, fallbackModel = "") {
  const modelName = state.target_model || fallbackModel || "?";
  const downloaded = Number(state.downloaded_bytes || 0);
  const estimated = Number(state.estimated_bytes || 0);
  const speed = Number(state.download_speed_bps || 0);
  const progress = Number(state.progress || 0);
  const elapsed = Number(state.elapsed_seconds || 0);
  const stalled = Number(state.stalled_seconds || 0);
  const downloading = state.status === "downloading" || state.phase === "download";
  const lines = [
    `${t("model")}: ${modelName}`,
    downloading
      ? `${t("model_download_progress")}: ${formatModelBytes(downloaded)} / ~${formatModelBytes(estimated)} (${progress}%)`
      : `${t("model_initializing_detail")} (${progress}%)`,
  ];
  if (speed > 0) lines.push(`${t("model_download_speed")}: ${formatModelBytes(speed)}/s`);
  if (elapsed > 0) lines.push(`${t("model_elapsed")}: ${formatModelDuration(elapsed)}`);
  if (stalled >= 30) lines.push(`${t("model_download_stalled")} (${formatModelDuration(stalled)})`);
  if (state.endpoint) lines.push(`${t("model_download_source")}: ${state.endpoint}`);
  if (state.cache_dir) lines.push(`${t("model_cache_dir")}: ${state.cache_dir}`);
  return {
    title: downloading ? t("model_downloading") : t("loading_model"),
    detail: lines.join("\n"),
    progress,
  };
}

function modelOperationErrorMessage(payload = {}) {
  const state = payload.model_state || payload.state || payload;
  const code = payload.error_code || state.error_code || "model_load_failed";
  const translated = t(code);
  const lines = [translated === code ? (state.user_message || payload.error || t("model_unavailable")) : translated];
  const target = state.target_model || payload.requested_model;
  if (target) lines.push(`${t("model")}: ${target}`);
  if (state.active_model_available && state.active_model) lines.push(`${t("model_previous_active")}: ${state.active_model}`);
  if (state.technical_details) lines.push(`${t("technical_details")}: ${state.technical_details}`);
  const suggestions = Array.isArray(state.suggestions) ? state.suggestions : [];
  if (suggestions.length) {
    lines.push(
      `${t("model_suggestions")}:\n${suggestions.map(item => `- ${t(`model_suggestion_${item}`)}`).join("\n")}`
    );
  }
  if (state.endpoint) lines.push(`${t("model_download_source")}: ${state.endpoint}`);
  if (state.cache_dir) lines.push(`${t("model_cache_dir")}: ${state.cache_dir}`);
  if (payload.request_id) lines.push(`Request ID: ${payload.request_id}`);
  return lines.join("\n");
}

function hideProgress() {
  if (!progressOverlay) return;
  progressOverlay.classList.remove("show");
  progressOverlay.setAttribute("aria-hidden", "true");
  document.body.classList.remove("progress-active");
  if (progressBar) {
    progressBar.classList.remove("determinate");
    progressBar.style.width = "35%";
  }
  deactivateDialog(progressOverlay);
}

if (progressClose) progressClose.onclick = hideProgress;

function renderText() {
  if (text) {
    transcriptEl.textContent = text;
  } else {
    transcriptEl.innerHTML = `<span class="placeholder" data-i18n="transcript_placeholder">${t("transcript_placeholder")}</span>`;
  }
}

var partialDraft = "";
function renderDraft() {
  if (partialDraft) {
    transcriptEl.innerHTML = `<span class="partial-draft">${htmlEscape(partialDraft)}…</span>`;
  } else {
    renderText();
  }
}
