async function pollModelStatus(force = false) {
  try {
    const resp = await fetch("/status");
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || resp.statusText || "Failed to read status");
    const state = data.model_state || {};
    if (state.error && (force || !shownModelErrors.has(state.error))) {
      shownModelErrors.add(state.error);
      showError(state.status === "ready" ? t("model_warning") : t("model_unavailable"), state.error);
    }
    if (state.status === "ready") { setStatus("connected", "connected"); return true; }
    if (state.status === "loading") { setStatus("processing", "loading_model"); return false; }
    if (state.error) { setStatus("error", "model_unavailable"); return true; }
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
    const s = await fetch("/stats").then(r => r.json());
    const cpuName = (s.cpu && s.cpu.name) || "CPU";
    const gpu = s.gpu || null;
    const gpuName = gpu && gpu.name ? gpu.name : "No NVIDIA GPU telemetry";
    const gpuDriver = gpu && gpu.driver ? `Driver ${gpu.driver}` : "Driver n/a";
    const memoryDetail = `${fmtMb(s.system_memory_available_mb)} free / ${fmtMb(s.system_memory_total_mb)} total`;

    if (systemStatusEl) {
      systemStatusEl.innerHTML = [
        `<span class="status-chip">CPU <b>${fmtPercent(s.cpu_percent)}</b></span>`,
        `<span class="status-chip">GPU <b>${gpu ? fmtPercent(gpu.util) : "n/a"}</b></span>`,
        `<span class="status-chip">Memory <b>${fmtPercent(s.system_memory_percent)}</b></span>`,
        `<span class="status-chip">App <b>${fmtMb(s.process_memory_mb)}</b></span>`
      ].join("");
    }

    if (perfEl) {
      perfEl.innerHTML = [
        renderMetricCard(t("stats_inference"), `${s.device} / ${s.compute_type}`, `Model: ${s.model}`),
        renderMetricCard(t("stats_cpu"), fmtPercent(s.cpu_percent), `${cpuName} | cores: ${(s.cpu && s.cpu.physical_cores) || "?"}/${(s.cpu && s.cpu.logical_cores) || "?"}`),
        renderMetricCard(t("stats_ram"), fmtPercent(s.system_memory_percent), memoryDetail),
        renderMetricCard(t("stats_gpu"), gpu ? fmtPercent(gpu.util) : "n/a", `${gpuName} | ${gpuDriver}`)
      ].join("");
    }

    if (homeMetricsEl) {
      const gpuMemory = gpu && gpu.mem_total ? `${gpu.mem_used}/${gpu.mem_total}MB VRAM (${fmtPercent(gpu.mem_percent)})` : "VRAM n/a";
      homeMetricsEl.innerHTML = [
        renderMetricCard(t("stats_app_memory"), fmtMb(s.process_memory_mb), `Process CPU: ${fmtPercent(s.process_cpu_percent)}`),
        renderMetricCard(t("stats_gpu_memory"), gpuMemory, gpuName)
      ].join("");
    }
  } catch (e) {}
}
