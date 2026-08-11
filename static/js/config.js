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
    decodePresetSel.value = cfg.decode_preset || "balanced";
    vadFilterSel.value = String(cfg.vad_filter !== false);
    conditionOnPreviousTextSel.value = String(cfg.condition_on_previous_text === true);
    langSel.value = cfg.language || "zh";
    uiLanguage = ["en", "zh", "ja"].includes(cfg.ui_language) ? cfg.ui_language : "en";
    await ensureI18nCatalog(uiLanguage);
    audioDeviceSel.value = String(cfg.audio_device || "");
    textModeSel.value = cfg.text_mode || "plain";
    historyEnabledSel.value = String(cfg.history_enabled !== false);
    fsizeSel.value = cfg.font_size || "1rem";
    if (themeSel) themeSel.value = cfg.theme || "system";
    applyTheme(cfg.theme || "system");
    appendSel.value = cfg.append_mode || "append";
    typingModeSel.value = cfg.typing_mode || "clipboard";
    typingDelaySel.value = String(cfg.typing_delay_ms == null ? 150 : cfg.typing_delay_ms);
    partialResultsSel.value = String(cfg.partial_results !== false);
    partialIntervalSel.value = String(cfg.partial_interval_ms == null ? 600 : cfg.partial_interval_ms);
    onTop = Boolean(cfg.on_top);
    transcriptEl.style.fontSize = fsizeSel.value;
    if (cfg.hotkey) currentHotkey = cfg.hotkey;
    renderHotkey();
    updatePresetHighlight();
    zhScriptSel.value = ((cfg.extensions || {}).zh_normalizer || {}).script || "none";
    renderHomeHotkeyHint();
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
