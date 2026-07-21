fsizeSel.onchange = () => { transcriptEl.style.fontSize = fsizeSel.value; saveConfig({font_size: fsizeSel.value}); };
appendSel.onchange = () => saveConfig({append_mode: appendSel.value});
langSel.onchange = () => saveConfig({language: langSel.value});
audioDeviceSel.onchange = () => saveConfig({audio_device: audioDeviceSel.value});
textModeSel.onchange = () => saveConfig({text_mode: textModeSel.value});
historyEnabledSel.onchange = () => saveConfig({history_enabled: historyEnabledSel.value === "true"});
uiLangSel.onchange = () => { uiLanguage = uiLangSel.value; applyTranslations(); saveConfig({ui_language: uiLanguage}); };

modelSel.onchange = async () => {
  setStatus("processing", "loading_model");
  const r = await requestJSON("POST", "/reload_model", {model: modelSel.value}, {errorTitle: t("failed_reload_model")});
  if (!r.ok) {
    setStatus("error", "model_unavailable");
    return;
  }
  await saveConfig({model: modelSel.value});
  pollModelStatus(true);
};

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
