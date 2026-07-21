async function startRec() {
  if (recording) return;
  cancelled = false;
  dbg("start recording: POST /record/start");
  const lang = langSel.value === "auto" ? "" : langSel.value;
  const r = await requestJSON("POST", "/record/start", {language: lang, audio_device: audioDeviceSel.value}, {errorTitle: t("failed_start_recording")});
  dbg("start response: " + JSON.stringify(r));
  if (r.status === "recording") {
    recording = true;
    recBtn.classList.add("recording");
    recLabel.textContent = t("recording_release");
    setStatus("recording", "recording");
  } else if (!r.ok) {
    setStatus("error", "model_unavailable");
  }
}

async function stopRec() {
  if (!recording) return;
  recording = false;
  recBtn.classList.remove("recording");
  recLabel.textContent = t("record_idle");
  if (cancelled) {
    cancelled = false;
    dbg("cancel requested: POST /record/cancel");
    await requestJSON("POST", "/record/cancel", {}, {silentAbort: true, suppressPopup: true});
    cancelBtn.style.display = "none";
    setStatus("connected", "connected");
    return;
  }
  setStatus("processing", "processing");
  cancelBtn.style.display = "";
  const lang = langSel.value === "auto" ? "" : langSel.value;
  dbg("stop recording: POST /record/stop lang=" + lang);
  try {
    const d = await requestJSON("POST", "/record/stop", {language: lang}, {abortable: true, timeout: 120000, silentAbort: true, errorTitle: t("request_failed"), timeoutTitle: t("request_timeout"), networkTitle: t("network_error")});
    dbg("transcription response: " + JSON.stringify(d));
    if (d.text && !window.pywebview) window._appendText(d.text);
    if (!d.ok && !d.aborted) setStatus("error", "model_unavailable");
  } finally {
    currentRequest = null;
    cancelBtn.style.display = "none";
    pollModelStatus(false);
  }
}

window._recToggle = () => recording ? stopRec() : startRec();
window._recStart = () => { if (!recording) startRec(); };
window._recStop = () => { if (recording) stopRec(); };
window._appendText = value => { text = appendSel.value === "append" ? (text ? text + "\n" + value : value) : value; renderText(); };

document.addEventListener("keydown", e => { if (recordingKey) return; if (e.code === "Space" && !e.repeat) { e.preventDefault(); startRec(); } });
document.addEventListener("keyup", e => { if (e.code === "Space") { e.preventDefault(); stopRec(); } });
recBtn.addEventListener("mousedown", startRec);
recBtn.addEventListener("mouseup", stopRec);
recBtn.addEventListener("mouseleave", () => { if (recording) stopRec(); });
copyBtn.onclick = () => {
  if (!text.trim()) return;
  navigator.clipboard.writeText(text).then(() => {
    copyBtn.textContent = t("copied");
    copyBtn.classList.add("copied");
    setTimeout(() => { copyBtn.textContent = t("copy"); copyBtn.classList.remove("copied"); }, 1500);
  }).catch(err => showError(t("clipboard_failed"), err.message || t("clipboard_failed_detail")));
};
clearBtn.onclick = () => { text = ""; renderText(); };
cancelBtn.onclick = () => { cancelled = true; cancelBtn.style.display = "none"; if (currentRequest) currentRequest.abort(); requestJSON("POST", "/record/cancel", {}, {silentAbort: true, suppressPopup: true}); };
