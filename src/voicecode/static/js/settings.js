fsizeSel.onchange = () => { transcriptEl.style.fontSize = fsizeSel.value; saveConfig({font_size: fsizeSel.value}); };
if (themeSel) themeSel.onchange = () => { applyTheme(themeSel.value); saveConfig({theme: themeSel.value}); };
appendSel.onchange = () => saveConfig({append_mode: appendSel.value});
typingModeSel.onchange = () => saveConfig({typing_mode: typingModeSel.value});
typingDelaySel.onchange = () => saveConfig({typing_delay_ms: Number(typingDelaySel.value)});
partialResultsSel.onchange = () => saveConfig({partial_results: partialResultsSel.value === "true"});
partialIntervalSel.onchange = () => saveConfig({partial_interval_ms: Number(partialIntervalSel.value)});
langSel.onchange = () => saveConfig({language: langSel.value});
audioDeviceSel.onchange = () => saveConfig({audio_device: audioDeviceSel.value});
textModeSel.onchange = () => saveConfig({text_mode: textModeSel.value});
beamSizeSel.onchange = () => { decodePresetSel.value = "custom"; saveConfig({beam_size: Number(beamSizeSel.value), decode_preset: "custom"}); };
decodePresetSel.onchange = () => saveConfig({decode_preset: decodePresetSel.value});
vadFilterSel.onchange = () => saveConfig({vad_filter: vadFilterSel.value === "true"});
conditionOnPreviousTextSel.onchange = () => { decodePresetSel.value = "custom"; saveConfig({condition_on_previous_text: conditionOnPreviousTextSel.value === "true", decode_preset: "custom"}); };
historyEnabledSel.onchange = () => saveConfig({history_enabled: historyEnabledSel.value === "true"});
async function refreshLanguageSensitiveContent() {
  modelInfoCache = null;
  await updateModelDescription(true);
  await updateAutoDeviceLabel();
  const activeView = document.querySelector(".view.active");
  if (activeView && activeView.id === "view-models" && typeof loadModelsPanel === "function") await loadModelsPanel();
  if (activeView && activeView.id === "view-extensions" && typeof loadExtensionsPanel === "function") await loadExtensionsPanel();
  if (activeView && activeView.id === "view-dependencies" && typeof loadDependenciesPanel === "function") await loadDependenciesPanel();
  if (activeView && activeView.id === "view-history" && typeof loadHistoryPanel === "function") await loadHistoryPanel();
}

if (micTestBtn) micTestBtn.onclick = testMicrophone;

uiLangSel.onchange = async () => {
  uiLanguage = ["en", "zh", "ja"].includes(uiLangSel.value) ? uiLangSel.value : "en";
  await ensureI18nCatalog(uiLanguage);
  applyTranslations();
  await saveConfig({ui_language: uiLanguage});
  await refreshLanguageSensitiveContent();
};

function setMicLevel(percent, statusKey, detail = "") {
  const clamped = Math.max(0, Math.min(100, Number(percent || 0)));
  if (micLevelBarEl) micLevelBarEl.style.width = `${clamped}%`;
  if (micTestStatusEl) micTestStatusEl.textContent = detail || t(statusKey);
}

async function testMicrophone() {
  if (!micTestBtn) return;
  micTestBtn.disabled = true;
  setMicLevel(0, "mic_test_running");
  const r = await requestJSON("POST", "/audio/test", {
    audio_device: audioDeviceSel ? audioDeviceSel.value : "",
    duration_ms: 1000
  }, {errorTitle: t("mic_test_failed"), timeout: 8000});
  micTestBtn.disabled = false;
  if (!r.ok) {
    setMicLevel(0, "mic_test_failed");
    return;
  }
  const percent = Number(r.level_percent || 0);
  const detail = `${r.has_signal ? t("mic_test_signal") : t("mic_test_no_signal")} · ${percent}% · peak ${Number(r.peak || 0).toFixed(3)}`;
  setMicLevel(percent, r.has_signal ? "mic_test_signal" : "mic_test_no_signal", detail);
}

async function loadModelInfo(force = false) {
  if (!force && modelInfoCache) return modelInfoCache;
  const data = await fetch("/models").then(r => r.json());
  modelInfoCache = {models: data.models || {}, compatibility: data.compatibility || {}, cache: data.cache || {}};
  return modelInfoCache;
}

function renderModelButtons() {
  if (!modelButtonListEl || !modelInfoCache) return;
  const models = modelInfoCache.models || {};
  const compatibility = modelInfoCache.compatibility || {};
  const cache = modelInfoCache.cache || {};
  modelButtonListEl.innerHTML = Object.entries(models).map(([name, info]) => {
    const compat = compatibility[name] || {selectable: true};
    const disabled = compat.selectable === false;
    const active = name === modelSel.value;
    const itemCache = cache[name] || {};
    const actionLabel = itemCache.cached ? t("model_load") : t("model_download");
    const latest = name === "large-v3-turbo" ? ` · ${t("latest_model")}` : "";
    const vram = `${t("vram_min")}: ${compat.vram_min_gb || info.vram_min_gb || "?"}GB / ${t("vram_rec")}: ${compat.vram_recommended_gb || info.vram_recommended_gb || "?"}GB`;
    return `<button type="button" class="model-option-btn ${active ? "active" : ""} ${disabled ? "disabled" : ""}" data-model="${name}" data-disabled="${disabled}" data-reason="${(compat.reason || "").replace(/"/g, "&quot;")}"><strong>${name}${latest}</strong><small>${info.description || ""}</small><small>${vram}</small><em>${actionLabel}${itemCache.partial ? ` · ${t("model_cache_partial")}` : ""}</em></button>`;
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
    const vram = `${t("vram_min")}: ${compat.vram_min_gb || info.vram_min_gb || "?"}GB · ${t("vram_rec")}: ${compat.vram_recommended_gb || info.vram_recommended_gb || "?"}GB`;
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
    const [models, hardware] = await Promise.all([
      fetch("/models").then(r => r.json()),
      fetch("/hardware").then(r => r.json()),
    ]);
    const configured = autoDeviceToggle && autoDeviceToggle.checked ? t("auto_device_on") : t("auto_device_off");
    const gpuName = hardware.gpu && hardware.gpu.name ? hardware.gpu.name : "";
    const gpuState = gpuName
      ? `${gpuName} · ${hardware.cuda_available ? t("gpu_cuda_ready") : t("gpu_cuda_unavailable")}`
      : t("gpu_not_detected");
    autoDeviceCurrent.textContent = `${configured}: ${models.device || "?"} / ${models.compute_type || "?"} · ${gpuState}`;
  } catch (e) {
    autoDeviceCurrent.textContent = autoDeviceToggle && autoDeviceToggle.checked ? t("auto_device_on") : t("auto_device_off");
  }
}

async function waitForModelReady(expectedModel, timeoutMs = 900000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const data = await requestJSON("GET", "/status", {}, {suppressPopup: true, timeout: 10000});
    if (!data.ok) throw Object.assign(new Error(data.error || t("request_failed")), {modelState: data});
    const state = data.model_state || {};
    const target = state.target_model || data.configured_model || data.model;
    if (state.status === "ready" && (!expectedModel || target === expectedModel || data.model === expectedModel)) return data;
    if (state.status === "error") {
      throw Object.assign(new Error(state.user_message || state.error || t("model_unavailable")), {modelState: state});
    }
    const progressInfo = modelOperationProgress(state, expectedModel);
    updateProgress(progressInfo.detail, progressInfo.progress, progressInfo.title);
    await new Promise(resolve => setTimeout(resolve, 900));
  }
  const timeoutState = {
    error_code: "model_client_wait_timeout",
    target_model: expectedModel,
    technical_details: t("request_timeout_detail"),
    suggestions: ["check_network", "retry", "use_smaller_model"],
  };
  throw Object.assign(new Error(t("request_timeout_detail")), {modelState: timeoutState});
}

async function reloadWhisperModel() {
  renderDeviceMode();
  const requestedModel = modelSel.value;
  setStatus("processing", "loading_model");
  updateDownloadCenter(t("loading_model"), `${t("model")}: ${requestedModel}
${t("switching_model_detail")}`, null);
  const r = await requestJSON("POST", "/reload_model", {
    model: requestedModel,
    device: deviceSel.value,
    compute_type: computeTypeSel.value,
    beam_size: Number(beamSizeSel.value),
    decode_preset: decodePresetSel.value,
    vad_filter: vadFilterSel.value === "true",
    condition_on_previous_text: conditionOnPreviousTextSel.value === "true"
  }, {errorTitle: t("failed_reload_model"), suppressPopup: true});
  if (!r.ok) {
    showError(t("failed_reload_model"), modelOperationErrorMessage(r));
    setStatus("error", "model_unavailable");
    failDownloadCenter(t("failed_reload_model"), modelOperationErrorMessage(r));
    await loadConfig();
    await updateModelDescription(true);
    return false;
  }
  try {
    await waitForModelReady(requestedModel);
    modelInfoCache = null;
    await pollModelStatus(true);
    await updateAutoDeviceLabel();
    await updateModelDescription(true);
    finishDownloadCenter(t("model_download_complete"));
    return true;
  } catch (e) {
    const detail = modelOperationErrorMessage(e.modelState || {technical_details: e.message});
    showError(t("failed_reload_model"), detail);
    failDownloadCenter(t("failed_reload_model"), detail);
    setStatus("error", "model_unavailable");
    return false;
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
