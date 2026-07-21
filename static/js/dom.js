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
var langSel = $("lang");
var uiLangSel = $("uilang");
var audioDeviceSel = $("audio-device");
var textModeSel = $("text-mode");
var historyEnabledSel = $("history-enabled");
var fsizeSel = $("fsize");
var appendSel = $("appendmode");
var topBtn = $("topbtn");
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
var dbgLines = [];

function t(key) {
  return (window.I18N[uiLanguage] && window.I18N[uiLanguage][key]) || window.I18N.en[key] || key;
}

function applyTranslations() {
  document.documentElement.lang = uiLanguage;
  document.querySelectorAll("[data-i18n]").forEach(el => { el.textContent = t(el.dataset.i18n); });
  document.querySelectorAll("[data-i18n-title]").forEach(el => { el.title = t(el.dataset.i18nTitle); });
  uiLangSel.value = uiLanguage;
  topBtn.textContent = onTop ? t("top_on") : t("top_off");
  hkRecordBtn.textContent = recordingKey ? t("press_any_key") : t("set_hotkey");
  recLabel.textContent = recording ? t("recording_release") : t("record_idle");
  slabel.textContent = t(currentStatusKey);
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

function renderText() {
  if (text) {
    transcriptEl.textContent = text;
  } else {
    transcriptEl.innerHTML = `<span class="placeholder" data-i18n="transcript_placeholder">${t("transcript_placeholder")}</span>`;
  }
}
