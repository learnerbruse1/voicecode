fsizeSel.onchange = () => { transcriptEl.style.fontSize = fsizeSel.value; saveConfig({font_size: fsizeSel.value}); };
appendSel.onchange = () => saveConfig({append_mode: appendSel.value});
langSel.onchange = () => saveConfig({language: langSel.value});
audioDeviceSel.onchange = () => saveConfig({audio_device: audioDeviceSel.value});
textModeSel.onchange = () => saveConfig({text_mode: textModeSel.value});
beamSizeSel.onchange = () => saveConfig({beam_size: Number(beamSizeSel.value)});
vadFilterSel.onchange = () => saveConfig({vad_filter: vadFilterSel.value === "true"});
historyEnabledSel.onchange = () => saveConfig({history_enabled: historyEnabledSel.value === "true"});
uiLangSel.onchange = () => { uiLanguage = uiLangSel.value; applyTranslations(); saveConfig({ui_language: uiLanguage}); };

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
    await pollModelStatus(true);
    await updateAutoDeviceLabel();
  } catch (e) {
    showError(t("failed_reload_model"), e.message || String(e));
    setStatus("error", "model_unavailable");
  } finally {
    hideProgress();
  }
}

modelSel.onchange = reloadWhisperModel;
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
