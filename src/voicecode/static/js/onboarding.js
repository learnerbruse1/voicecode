var onboardingState = null;
var onboardingStep = Number(sessionStorage.getItem("voicecode.onboardingStep") || 0);
const onboardingSteps = ["language", "runtime", "audio", "model", "finish"];

function onboardingElement(id) { return document.getElementById(id); }

function onboardingSelect(id, options, value) {
  return `<select id="${id}">${options.map(option => `<option value="${htmlEscape(option.value)}" ${option.value === value ? "selected" : ""}>${htmlEscape(t(option.label))}</option>`).join("")}</select>`;
}

function renderOnboarding() {
  const overlay = onboardingElement("onboarding-overlay");
  const body = onboardingElement("onboarding-body");
  if (!overlay || !body || !onboardingState) return;
  onboardingStep = Math.max(0, Math.min(onboardingSteps.length - 1, onboardingStep));
  sessionStorage.setItem("voicecode.onboardingStep", String(onboardingStep));
  const step = onboardingSteps[onboardingStep];
  const config = onboardingState.config || {};
  const steps = onboardingState.steps || {};
  const titles = {language: "onboarding_language", runtime: "onboarding_runtime", audio: "onboarding_audio", model: "onboarding_model", finish: "onboarding_finish"};
  onboardingElement("onboarding-step-title").textContent = t(titles[step]);
  onboardingElement("onboarding-step-count").textContent = `${onboardingStep + 1} / ${onboardingSteps.length}`;
  document.querySelectorAll(".onboarding-dot").forEach((dot, index) => dot.classList.toggle("active", index <= onboardingStep));
  if (step === "language") {
    body.innerHTML = `<p>${t("onboarding_intro")}</p><div class="onboarding-form-grid"><label><span>${t("ui_language")}</span>${onboardingSelect("onboarding-ui-language", [{value:"en",label:"ui_en"},{value:"zh",label:"ui_zh"},{value:"ja",label:"ui_ja"}], config.ui_language || "en")}</label><label><span>${t("language")}</span>${onboardingSelect("onboarding-language", [{value:"auto",label:"lang_auto"},{value:"zh",label:"lang_zh"},{value:"en",label:"lang_en"},{value:"ja",label:"lang_ja"}], config.language || "zh")}</label></div>`;
    const languageSelect = onboardingElement("onboarding-ui-language");
    languageSelect.onchange = async () => { await ensureI18nCatalog(languageSelect.value); uiLanguage = languageSelect.value; applyTranslations(); renderOnboarding(); };
  } else if (step === "runtime") {
    const runtime = steps.runtime || {};
    const missing = runtime.missing || [];
    body.innerHTML = `<p>${t("onboarding_runtime_detail")}</p><div class="setup-status ${runtime.ready ? "ready" : "warning"}"><strong>${runtime.ready ? t("onboarding_ready") : t("onboarding_not_ready")}</strong><span>${missing.map(item => htmlEscape(item.name)).join(", ") || t("extension_no_dependencies")}</span></div><button id="onboarding-install" class="primary" type="button" ${runtime.ready ? "disabled" : ""}>${t("onboarding_install_required")}</button><p id="onboarding-task-status" class="muted-text"></p>`;
    const install = onboardingElement("onboarding-install");
    if (install) install.onclick = installOnboardingDependencies;
  } else if (step === "audio") {
    const audio = steps.audio || {};
    const options = [{value:"",label:"audio_default"}, ...(audio.devices || []).map(device => ({value:String(device.index), label:null, text:device.name}))];
    body.innerHTML = `<div class="setup-status ${audio.ready ? "ready" : "warning"}"><strong>${audio.ready ? t("onboarding_ready") : t("onboarding_not_ready")}</strong><span>${htmlEscape(audio.error || `${(audio.devices || []).length} device(s)`)}</span></div><label><span>${t("audio_device")}</span><select id="onboarding-audio-device">${options.map(option => `<option value="${htmlEscape(option.value)}" ${String(config.audio_device || "") === option.value ? "selected" : ""}>${htmlEscape(option.text || t(option.label))}</option>`).join("")}</select></label><button id="onboarding-mic-test" type="button">${t("mic_test_start")}</button><div class="mic-level"><div id="onboarding-mic-level"></div></div><p id="onboarding-mic-status" class="muted-text">${t("mic_test_idle")}</p>`;
    onboardingElement("onboarding-mic-test").onclick = testOnboardingMicrophone;
  } else if (step === "model") {
    body.innerHTML = `<div class="onboarding-form-grid"><label><span>${t("model")}</span><select id="onboarding-model">${["tiny","base","small","medium","large-v3-turbo","large-v3","distil-large-v3"].map(model => `<option value="${model}" ${model === config.model ? "selected" : ""}>${model}</option>`).join("")}</select></label><label><span>${t("device")}</span><select id="onboarding-device"><option value="auto" ${config.device === "auto" ? "selected" : ""}>${t("device_auto")}</option><option value="cpu" ${config.device === "cpu" ? "selected" : ""}>CPU</option><option value="cuda" ${config.device === "cuda" ? "selected" : ""}>CUDA</option></select></label></div><p class="muted-text">${t("models_subtitle")}</p><p class="setup-recommendation">${t("onboarding_recommended_model")}: <strong>${htmlEscape((steps.model || {}).recommended_model || "base")}</strong></p>`;
  } else {
    const runtimeReady = Boolean(steps.runtime && steps.runtime.ready);
    const audioReady = Boolean(steps.audio && steps.audio.ready);
    body.innerHTML = `<p>${t("onboarding_finish")}</p><div class="setup-summary"><div><span>${t("onboarding_runtime")}</span><strong>${runtimeReady ? t("onboarding_ready") : t("onboarding_not_ready")}</strong></div><div><span>${t("onboarding_audio")}</span><strong>${audioReady ? t("onboarding_ready") : t("onboarding_not_ready")}</strong></div><div><span>${t("model")}</span><strong>${htmlEscape(config.model || "base")}</strong></div></div>`;
  }
  onboardingElement("onboarding-back").disabled = onboardingStep === 0;
  onboardingElement("onboarding-next").textContent = onboardingStep === onboardingSteps.length - 1 ? t("onboarding_complete") : t("onboarding_next");
  const wasVisible = overlay.classList.contains("show");
  overlay.classList.add("show"); overlay.setAttribute("aria-hidden", "false");
  if (!wasVisible) activateDialog(overlay, onboardingElement("onboarding-step-title"));
}

function captureOnboardingStep() {
  const config = onboardingState.config || (onboardingState.config = {});
  const ui = onboardingElement("onboarding-ui-language"); if (ui) config.ui_language = ui.value;
  const lang = onboardingElement("onboarding-language"); if (lang) config.language = lang.value;
  const audio = onboardingElement("onboarding-audio-device"); if (audio) config.audio_device = audio.value;
  const model = onboardingElement("onboarding-model"); if (model) config.model = model.value;
  const device = onboardingElement("onboarding-device"); if (device) config.device = device.value;
}

export async function loadOnboarding(force = false) {
  const result = await requestJSON("GET", "/onboarding", {}, {suppressPopup: true});
  if (!result.ok) return false;
  onboardingState = result;
  const shouldShow = Boolean(force || result.required);
  if (shouldShow) { onboardingStep = 0; renderOnboarding(); }
  return shouldShow;
}

async function refreshOnboardingState() {
  const result = await requestJSON("GET", "/onboarding", {}, {suppressPopup: true});
  if (result.ok) { const previous = onboardingState && onboardingState.config; onboardingState = result; onboardingState.config = {...result.config, ...previous}; renderOnboarding(); }
}

async function installOnboardingDependencies() {
  const button = onboardingElement("onboarding-install"); if (button) button.disabled = true;
  const status = onboardingElement("onboarding-task-status"); if (status) status.textContent = t("onboarding_installing");
  const result = await requestJSON("POST", "/dependencies/install-required", {}, {errorTitle:t("dependency_install_failed"), timeout:20000});
  if (!result.ok) { if (button) button.disabled = false; return; }
  try { for (const task of result.tasks || []) await waitForDependencyTask(task.id); await refreshOnboardingState(); }
  catch (error) { showError(t("dependency_install_failed"), error.message || String(error)); if (button) button.disabled = false; }
}

async function testOnboardingMicrophone() {
  const status = onboardingElement("onboarding-mic-status"); if (status) status.textContent = t("mic_test_running");
  const result = await requestJSON("POST", "/audio/test", {audio_device:onboardingElement("onboarding-audio-device").value,duration_ms:1000}, {errorTitle:t("mic_test_failed"),timeout:8000});
  if (!result.ok) return;
  const level = Number(result.level_percent || 0); const bar = onboardingElement("onboarding-mic-level"); if (bar) bar.style.width = `${level}%`;
  if (status) status.textContent = `${result.has_signal ? t("mic_test_signal") : t("mic_test_no_signal")} · ${level}%`;
  captureOnboardingStep();
}

async function completeOnboarding(skipped = false) {
  captureOnboardingStep();
  const runtimeReady = Boolean(onboardingState.steps?.runtime?.ready);
  const audioReady = Boolean(onboardingState.steps?.audio?.ready);
  if (!skipped && (!runtimeReady || !audioReady) && !confirm(t("onboarding_finish_warning"))) return;
  const result = await requestJSON("POST", "/onboarding/complete", {config:onboardingState.config || {}, skipped}, {errorTitle:t("failed_save_settings")});
  if (!result.ok) return;
  const overlay = onboardingElement("onboarding-overlay"); overlay.classList.remove("show"); overlay.setAttribute("aria-hidden", "true"); deactivateDialog(overlay); sessionStorage.removeItem("voicecode.onboardingStep");
  await loadAudioDevices(); await loadConfig(); await pollModelStatus(true);
}

export function setupOnboarding() {
  document.addEventListener("keydown", event => trapDialogFocus(event, onboardingElement("onboarding-overlay")));
  const back = onboardingElement("onboarding-back"); const next = onboardingElement("onboarding-next"); const skip = onboardingElement("onboarding-skip");
  if (back) back.onclick = () => { captureOnboardingStep(); onboardingStep = Math.max(0, onboardingStep - 1); renderOnboarding(); };
  if (next) next.onclick = () => { captureOnboardingStep(); if (onboardingStep === onboardingSteps.length - 1) completeOnboarding(false); else { onboardingStep += 1; renderOnboarding(); } };
  if (skip) skip.onclick = () => completeOnboarding(true);
  const rerun = onboardingElement("rerun-onboarding"); if (rerun) rerun.onclick = async () => { await requestJSON("POST", "/onboarding/reset", {}); await loadOnboarding(true); };
}

Object.assign(window, {loadOnboarding, setupOnboarding});
