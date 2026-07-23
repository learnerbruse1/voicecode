fsizeSel.onchange = () => { transcriptEl.style.fontSize = fsizeSel.value; saveConfig({font_size: fsizeSel.value}); };
appendSel.onchange = () => saveConfig({append_mode: appendSel.value});
langSel.onchange = () => saveConfig({language: langSel.value});
audioDeviceSel.onchange = () => saveConfig({audio_device: audioDeviceSel.value});
textModeSel.onchange = () => saveConfig({text_mode: textModeSel.value});
beamSizeSel.onchange = () => saveConfig({beam_size: Number(beamSizeSel.value)});
vadFilterSel.onchange = () => saveConfig({vad_filter: vadFilterSel.value === "true"});
historyEnabledSel.onchange = () => saveConfig({history_enabled: historyEnabledSel.value === "true"});
async function refreshLanguageSensitiveContent() {
  modelInfoCache = null;
  await updateModelDescription(true);
  await updateAutoDeviceLabel();
  const activeView = document.querySelector(".view.active");
  if (activeView && activeView.id === "view-extensions" && typeof loadExtensionsPanel === "function") await loadExtensionsPanel();
  if (activeView && activeView.id === "view-dependencies" && typeof loadDependenciesPanel === "function") await loadDependenciesPanel();
  if (activeView && activeView.id === "view-history" && typeof loadHistoryPanel === "function") await loadHistoryPanel();
}

uiLangSel.onchange = async () => {
  uiLanguage = ["en", "zh", "ja"].includes(uiLangSel.value) ? uiLangSel.value : "en";
  applyTranslations();
  await saveConfig({ui_language: uiLanguage});
  await refreshLanguageSensitiveContent();
};

async function loadModelInfo(force = false) {
  if (!force && modelInfoCache) return modelInfoCache;
  const data = await fetch("/models").then(r => r.json());
  modelInfoCache = {models: data.models || {}, compatibility: data.compatibility || {}};
  return modelInfoCache;
}

function renderModelButtons() {
  if (!modelButtonListEl || !modelInfoCache) return;
  const models = modelInfoCache.models || {};
  const compatibility = modelInfoCache.compatibility || {};
  modelButtonListEl.innerHTML = Object.entries(models).map(([name, info]) => {
    const compat = compatibility[name] || {selectable: true};
    const disabled = compat.selectable === false;
    const active = name === modelSel.value;
    const latest = name === "large-v3-turbo" ? ` ? ${t("latest_model")}` : "";
    const vram = `${t("vram_min")}: ${compat.vram_min_gb || info.vram_min_gb || "?"}GB / ${t("vram_rec")}: ${compat.vram_recommended_gb || info.vram_recommended_gb || "?"}GB`;
    return `<button type="button" class="model-option-btn ${active ? "active" : ""} ${disabled ? "disabled" : ""}" data-model="${name}" data-disabled="${disabled}" data-reason="${(compat.reason || "").replace(/"/g, "&quot;")}"><strong>${name}${latest}</strong><small>${info.description || ""}</small><small>${vram}</small></button>`;
  }).join("");
  modelButtonListEl.querySelectorAll(".model-option-btn").forEach(btn => {
    btn.onclick = () => {
      if (btn.dataset.disabled === "true") {
        showError(t("model_config_too_low"), btn.dataset.reason || t("model_config_too_low_detail"));
        return;
      }
      if (modelSel.value === btn.dataset.model) return;
      modelSel.value = btn.dataset.model;
      updateModelDescription(false);
      reloadWhisperModel();
    };
  });
}

async function updateModelDescription(force = false) {
  if (!modelDescriptionEl) return;
  try {
    const infoBundle = await loadModelInfo(force);
    const info = (infoBundle.models || {})[modelSel.value] || {};
    const compat = (infoBundle.compatibility || {})[modelSel.value] || {};
    const latest = modelSel.value === "large-v3-turbo" ? ` <span class="model-latest">${t("latest_model")}</span>` : "";
    const vram = `${t("vram_min")}: ${compat.vram_min_gb || info.vram_min_gb || "?"}GB ? ${t("vram_rec")}: ${compat.vram_recommended_gb || info.vram_recommended_gb || "?"}GB`;
    modelDescriptionEl.innerHTML = `${info.size || ""} ${info.description || t("model_description_default")} ${vram}${latest}`;
    renderModelButtons();
  } catch (e) {
    modelDescriptionEl.textContent = t("model_description_default");
  }
}

function selectedManualDevice() {
  const selected = document.querySelector("input[name='device-choice']:checked");
  return selected ? selected.value : "cpu";
}

function renderDeviceMode() {
  const autoMode = !autoDeviceToggle || autoDeviceToggle.checked;
  if (manualDeviceOptions) manualDeviceOptions.classList.toggle("show", !autoMode);
  if (deviceSel) deviceSel.value = autoMode ? "auto" : selectedManualDevice();
  updateAutoDeviceLabel();
}

async function updateAutoDeviceLabel() {
  if (!autoDeviceCurrent) return;
  try {
    const data = await fetch("/models").then(r => r.json());
    const configured = autoDeviceToggle && autoDeviceToggle.checked ? t("auto_device_on") : t("auto_device_off");
    autoDeviceCurrent.textContent = `${configured}: ${data.device || "?"} / ${data.compute_type || "?"}`;
  } catch (e) {
    autoDeviceCurrent.textContent = autoDeviceToggle && autoDeviceToggle.checked ? t("auto_device_on") : t("auto_device_off");
  }
}

async function waitForModelReady(timeoutMs = 180000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const resp = await fetch("/status");
    const data = await resp.json();
    const state = data.model_state || {};
    if (state.status === "ready") return data;
    if (state.status === "error") throw new Error(state.error || t("model_unavailable"));
    updateProgress(`${t("loading_model")} ${Math.round((Date.now() - started) / 1000)}s`);
    await new Promise(resolve => setTimeout(resolve, 900));
  }
  throw new Error(t("request_timeout_detail"));
}

async function reloadWhisperModel() {
  renderDeviceMode();
  setStatus("processing", "loading_model");
  showProgress(t("loading_model"), t("switching_model_detail"));
  const r = await requestJSON("POST", "/reload_model", {
    model: modelSel.value,
    device: deviceSel.value,
    compute_type: computeTypeSel.value,
    beam_size: Number(beamSizeSel.value),
    vad_filter: vadFilterSel.value === "true"
  }, {errorTitle: t("failed_reload_model")});
  if (!r.ok) {
    setStatus("error", "model_unavailable");
    hideProgress();
    return;
  }
  try {
    await waitForModelReady();
    modelInfoCache = null;
    await pollModelStatus(true);
    await updateAutoDeviceLabel();
    await updateModelDescription(true);
  } catch (e) {
    showError(t("failed_reload_model"), e.message || String(e));
    setStatus("error", "model_unavailable");
  } finally {
    hideProgress();
  }
}

modelSel.onchange = () => { updateModelDescription(); reloadWhisperModel(); };
computeTypeSel.onchange = reloadWhisperModel;
if (autoDeviceToggle) autoDeviceToggle.onchange = reloadWhisperModel;
document.querySelectorAll("input[name='device-choice']").forEach(input => {
  input.onchange = () => { if (!autoDeviceToggle || !autoDeviceToggle.checked) reloadWhisperModel(); };
});

topBtn.onclick = async () => {
  onTop = !onTop;
  topBtn.textContent = onTop ? t("top_on") : t("top_off");
  topBtn.classList.toggle("on", onTop);
  if (window.pywebview && pywebview.api) {
    try {
      const ok = await pywebview.api.set_on_top(onTop);
      if (!ok) showError(t("failed_update_top"), t("failed_update_top_detail"));
    } catch (e) {
      showError(t("failed_update_top"), e.message || String(e));
    }
  }
  await saveConfig({on_top: onTop});
};


if (resetDefaultsBtn) resetDefaultsBtn.onclick = async () => {
  if (!confirm(t("restore_defaults_confirm"))) return;
  showProgress(t("restore_defaults"), t("restore_defaults_detail"));
  const r = await requestJSON("POST", "/config/reset", {}, {errorTitle: t("failed_save_settings")});
  if (!r.ok) { hideProgress(); return; }
  modelInfoCache = null;
  await loadConfig();
  await reloadWhisperModel();
  hideProgress();
};
