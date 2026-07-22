async function loadConfig() {
  try {
    const resp = await fetch("/config");
    const cfg = await resp.json();
    if (!resp.ok) throw new Error(cfg.error || resp.statusText || "Failed to load config");
    modelSel.value = cfg.model || "base";
    deviceSel.value = cfg.device || "auto";
    if (autoDeviceToggle) autoDeviceToggle.checked = deviceSel.value === "auto";
    document.querySelectorAll("input[name='device-choice']").forEach(input => { input.checked = input.value === (deviceSel.value === "auto" ? "cpu" : deviceSel.value); });
    computeTypeSel.value = cfg.compute_type || "auto";
    renderDeviceMode();
    updateModelDescription();
    beamSizeSel.value = String(cfg.beam_size || 5);
    vadFilterSel.value = String(cfg.vad_filter !== false);
    langSel.value = cfg.language || "zh";
    uiLanguage = ["en", "zh", "ja"].includes(cfg.ui_language) ? cfg.ui_language : "en";
    audioDeviceSel.value = String(cfg.audio_device || "");
    textModeSel.value = cfg.text_mode || "plain";
    historyEnabledSel.value = String(cfg.history_enabled !== false);
    fsizeSel.value = cfg.font_size || "1rem";
    appendSel.value = cfg.append_mode || "append";
    onTop = Boolean(cfg.on_top);
    transcriptEl.style.fontSize = fsizeSel.value;
    if (cfg.hotkey) currentHotkey = cfg.hotkey;
    renderHotkey();
    updatePresetHighlight();
    applyTranslations();
  } catch (e) {
    showError(t("failed_load_settings"), e.message || String(e));
  }
}

async function loadAudioDevices() {
  const r = await requestJSON("GET", "/audio/devices", {}, {errorTitle: t("audio_unavailable")});
  if (!r.ok) return;
  const current = audioDeviceSel.value;
  audioDeviceSel.innerHTML = `<option value="" data-i18n="audio_default">${t("audio_default")}</option>`;
  for (const dev of r.devices || []) {
    const opt = document.createElement("option");
    opt.value = String(dev.index);
    opt.textContent = `${dev.name}${dev.is_default ? " (default)" : ""}`;
    audioDeviceSel.appendChild(opt);
  }
  audioDeviceSel.value = current;
}

async function saveConfig(patch) {
  const r = await requestJSON("POST", "/config", patch, {errorTitle: t("failed_save_settings")});
  return r.ok ? r : null;
}
