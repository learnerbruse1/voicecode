function hotkeyLabel(hk) {
  const mods = (hk.modifiers || []).map(m => m[0].toUpperCase() + m.slice(1));
  return [...mods, hk.key === "space" ? "Space" : hk.key.toUpperCase()].join("+");
}

function renderHotkey() {
  hkDisplay.textContent = hotkeyLabel(currentHotkey);
}

function updatePresetHighlight() {
  document.querySelectorAll(".hk-preset").forEach(btn => {
    const mods = btn.dataset.mods.split(",").filter(Boolean).sort();
    const cur = [...(currentHotkey.modifiers || [])].sort();
    btn.classList.toggle("active", cur.join(",") === mods.join(",") && btn.dataset.key === currentHotkey.key);
  });
}

async function applyHotkey(hk) {
  currentHotkey = hk;
  renderHotkey();
  updatePresetHighlight();
  const saved = await saveConfig({hotkey: hk});
  if (!saved) return;
  if (window.pywebview && pywebview.api) {
    try {
      const ok = await pywebview.api.update_hotkey(hk);
      if (!ok) showError(t("failed_update_hotkey"), t("failed_update_hotkey_detail"));
    } catch (e) {
      showError(t("failed_update_hotkey"), e.message || String(e));
    }
  }
}

document.querySelectorAll(".hk-preset").forEach(btn => {
  btn.onclick = () => applyHotkey({modifiers: btn.dataset.mods.split(",").filter(Boolean), key: btn.dataset.key});
});

hkRecordBtn.onclick = () => {
  if (recordingKey) return;
  recordingKey = true;
  pendingMods = [];
  hkDisplay.classList.add("recording-key");
  hkDisplay.textContent = t("press_shortcut");
  hkRecordBtn.textContent = t("press_any_key");
};

const MOD_KEYS = new Set(["Alt", "AltGraph", "Control", "Shift", "Meta"]);
document.addEventListener("keydown", e => {
  if (!recordingKey) return;
  e.preventDefault();
  if (MOD_KEYS.has(e.key)) {
    const m = e.key.toLowerCase().replace("control", "ctrl").replace("meta", "ctrl").replace("altgraph", "alt");
    if (!pendingMods.includes(m)) pendingMods.push(m);
    return;
  }
  const key = e.key.toLowerCase() === " " ? "space" : e.key.toLowerCase();
  recordingKey = false;
  hkDisplay.classList.remove("recording-key");
  hkRecordBtn.textContent = t("set_hotkey");
  applyHotkey({modifiers: [...new Set(pendingMods)], key});
});
