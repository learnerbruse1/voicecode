var modelStatusProgressVisible = false;

function setHtmlIfChanged(el, html) {
  if (el && el.dataset.rendered !== html) {
    el.innerHTML = html;
    el.dataset.rendered = html;
  }
}

async function pollModelStatus(force = false) {
  try {
    const {response: resp, data} = await fetchJSONTimeout("/status", 8000);
    if (!resp || !resp.ok) throw new Error((data && data.error) || "Failed to read status");
    const state = data.model_state || {};
    const onboardingVisible = document.getElementById("onboarding-overlay")?.classList.contains("show");
    const active = ["checking", "downloading", "loading"].includes(state.status);
    const errorKey = `${state.error_code || ""}:${state.technical_details || state.error || ""}`;
    if (state.status === "error" && !onboardingVisible && (force || !shownModelErrors.has(errorKey))) {
      shownModelErrors.add(errorKey);
      showError(t("model_unavailable"), modelOperationErrorMessage(state));
    }
    if (state.status === "ready") {
      setStatus("connected", "connected");
      if (modelStatusProgressVisible) finishDownloadCenter(t("model_download_complete"));
      modelStatusProgressVisible = false;
      return true;
    }
    if (active) {
      setStatus("processing", state.status === "downloading" ? "model_downloading" : "loading_model");
      const progressInfo = modelOperationProgress(state, data.configured_model || data.model);
      if (!onboardingVisible) {
        updateDownloadCenter(progressInfo.title, progressInfo.detail, progressInfo.progress);
        modelStatusProgressVisible = true;
      }
      return false;
    }
    if (state.status === "awaiting_selection") {
      setStatus("processing", "model_waiting_selection");
      return false;
    }
    if (state.error) {
      setStatus("error", "model_unavailable");
      return true;
    }
    return false;
  } catch (e) {
    showError(t("failed_load_settings"), e.message || String(e));
    return true;
  }
}

function fmtPercent(value) { return typeof value === "number" && value >= 0 ? `${value}%` : "n/a"; }
function fmtMb(value) { return typeof value === "number" && value >= 0 ? `${value}MB` : "n/a"; }

function renderMetricCard(label, value, detail) {
  return `<div class="metric-card"><span>${label}</span><strong>${value}</strong><small>${detail || ""}</small></div>`;
}

async function updateStats() {
  try {
    const {data: s} = await fetchJSONTimeout("/stats", 8000);
    if (!s) return;
    const cpuName = (s.cpu && s.cpu.name) || "CPU";
    const gpu = s.gpu || null;
    const gpuName = gpu && gpu.name ? gpu.name : "No NVIDIA GPU telemetry";
    const gpuDriver = gpu && gpu.driver ? `Driver ${gpu.driver}` : "Driver n/a";
    const memoryDetail = `${fmtMb(s.system_memory_available_mb)} free / ${fmtMb(s.system_memory_total_mb)} total`;

    if (systemStatusEl) {
      const chips = [
        `<span class="status-chip"><span>${t("stats_cpu")}</span><b>${fmtPercent(s.cpu_percent)}</b></span>`,
        `<span class="status-chip"><span>${t("stats_gpu")}</span><b>${gpu ? fmtPercent(gpu.util) : t("unavailable_short")}</b></span>`,
        `<span class="status-chip"><span>${t("stats_ram")}</span><b>${fmtPercent(s.system_memory_percent)}</b></span>`
      ].join("");
      setHtmlIfChanged(systemStatusEl, chips);
    }

    if (perfEl) {
      const perfHtml = [
        renderMetricCard(t("stats_inference"), `${s.device} / ${s.compute_type}`, `Model: ${s.model}`),
        renderMetricCard(t("stats_cpu"), fmtPercent(s.cpu_percent), `${cpuName} | cores: ${(s.cpu && s.cpu.physical_cores) || "?"}/${(s.cpu && s.cpu.logical_cores) || "?"}`),
        renderMetricCard(t("stats_ram"), fmtPercent(s.system_memory_percent), memoryDetail),
        renderMetricCard(t("stats_gpu"), gpu ? fmtPercent(gpu.util) : "n/a", `${gpuName} | ${gpuDriver}`)
      ].join("");
      setHtmlIfChanged(perfEl, perfHtml);
    }

    if (homeMetricsEl) {
      const gpuMemory = gpu && gpu.mem_total ? `${gpu.mem_used}/${gpu.mem_total}MB VRAM (${fmtPercent(gpu.mem_percent)})` : "VRAM n/a";
      const homeHtml = [
        renderMetricCard(t("stats_app_memory"), fmtMb(s.process_memory_mb), `Process CPU: ${fmtPercent(s.process_cpu_percent)}`),
        renderMetricCard(t("stats_gpu_memory"), gpuMemory, gpuName)
      ].join("");
      setHtmlIfChanged(homeMetricsEl, homeHtml);
    }
  } catch (e) {}
}
