# Troubleshooting

## The installed window shows "The requested URL was not found"

Install or upgrade to VoiceCode v0.2.0 or later. Earlier desktop bundles could omit `voicecode/static`, causing `/` to return HTTP 404. A valid installation contains `<install-dir>\_internal\voicecode\static\index.html`. The v0.2.0 build now fails if this asset is missing.

## Chinese or Japanese text displays as question marks

Install or upgrade to VoiceCode v0.2.0 or later, then restart the application. The UTF-8 catalogs must contain real translated text and `/static/i18n/zh.json` plus `/static/i18n/ja.json` must return HTTP 200. v0.2.0 also fixes switching from Chinese/Japanese back to English in the first-start guide.

## Port 7788 is already in use

VoiceCode v0.2.0 uses a Windows single-instance lock. Starting the app again restores the existing window and exits cleanly. If an unrelated service owns port 7788, close that service or set `PORT` before launching a source build; do not connect VoiceCode to an unidentified local service.

## The app says the model is unavailable

Open Diagnostics and copy the request ID and model state. Common causes:

- model download failed
- offline mode is enabled and the model is not cached
- selected CUDA model needs more VRAM
- CUDA/CuDNN/driver mismatch

Try:

1. Switch hardware to Auto.
2. Choose a smaller model such as `base` or `small`.
3. Use Restore defaults.
4. Check logs using the request ID.

## CUDA is detected but GPU stats are incomplete

GPU telemetry uses optional NVML bindings. Transcription can still work without full telemetry. Install the optional GPU extra if needed:

```powershell
python -m pip install -e ".[gpu]"
```

## A model button is disabled

The current manual CUDA configuration does not meet the model's minimum VRAM requirement. Choose a smaller model, switch to CPU, or enable Auto hardware.

## The UI is blocked by a progress overlay

A long operation is running, usually model reload or transcription. Wait for it to finish. The close button hides the overlay, but the backend operation may still complete in the background.

## The API returns a request ID

Include the `request_id` from the popup/API response when reporting an issue. It maps to backend logs.

## Model downloads or cache deletion fail

Open **Models** and check the cache directory shown at the top. Common causes:

- another model load is already in progress
- offline mode is enabled and the model is not cached
- the selected model is currently active, so its cache cannot be deleted
- the cache directory is not writable
- network access to the model host is blocked (v0.2.0 probes the official endpoint and falls back to `hf-mirror.com` when reachable)

Try choosing a smaller model, switching hardware to Auto, confirming that `VOICECODE_MODEL_DIR` points to a writable folder, or deleting only non-active model caches.

## History search or export does not show expected entries

The History page applies search text and language filters before exporting. Clear the search box and set language to **All languages** to export everything within the configured history limit. If history is empty, confirm that `history_enabled` is on and that `VOICECODE_HISTORY_FILE` points to a writable file if overridden.

## The first-start guide keeps returning

Call `GET /onboarding` or inspect the config `onboarding` object. Completion is written only after `POST /onboarding/complete` succeeds. Confirm the config directory is writable and no environment override points to a read-only file.

## An extension is enabled but not ready

Open **Extensions** and inspect its dependency summary. Some settings make a dependency conditionally required, such as Silero VAD or Chinese script conversion. Use **Install dependencies**, wait for every task to complete, then refresh. Heavy adapters may also require external models/credentials not provided by package installation.

## A dependency install fails

Open **Dependencies**, retry, and inspect the task message/log through `/dependencies/tasks/<id>`. Verify package-index/proxy access, available disk space, and write access to `VOICECODE_DEP_DIR` or the packaged runtime dependency directory.

## Translations fail to load

Confirm `static/i18n/en.json`, `zh.json`, and `ja.json` exist in both source and packaged trees. For wheels/bundles, inspect package contents and verify `/static/i18n/en.json` returns a JSON object.

## A dependency task is stuck or was interrupted

Use the cancel button or `POST /dependencies/tasks/<id>/cancel`. Tasks exceeding `VOICECODE_DEP_INSTALL_TIMEOUT_SECONDS` fail automatically. After an application restart, previously queued/running tasks are restored as failed with an interruption message. If another process owns the dependency lock, close the other VoiceCode instance rather than deleting a fresh lock file.

## An extension is installed but asks for a restart

Binary-heavy packages can already be imported or partially loaded in the current process. Restart the full VoiceCode application, not only the web page.

## Pyannote diarization reports a token error

Set the environment variable named by `extensions.diarization.token_env` (default `HF_TOKEN`) before starting VoiceCode, and ensure access to the configured gated model. Tokens are intentionally not stored in `config.json`.

## The API rejects Host or Origin

VoiceCode accepts loopback Host names and same-port loopback Origins. Use `127.0.0.1`, `localhost`, or `::1`; proxies and embedded clients must preserve a valid local Host and must not send a foreign Origin on mutation requests.

## The Windows installer build times out downloading embedded Python

Current builds download prerequisites before PyInstaller, retry failures, write through an atomic `.part` file, validate the embedded ZIP, and keep successful downloads under `build/windows/downloads/`. Rerun the build after network access recovers. If a cached file is corrupt, delete only the affected file in `build/windows/downloads/`; do not delete the full `build/windows` directory unless you intentionally want to discard the cache.

## Files remain after uninstalling the Windows app

This is expected for user-created runtime data. Setup removes the installed application payload, while downloaded models, optional packages, and caches may remain under `<install-dir>\runtime` for reuse. Reinstall to the same location to reuse them, or manually delete the remaining installation directory for a complete removal.

## A selected model stays on loading

Check `/status` or the progress dialog. Current states distinguish `downloading` from local `loading`/initialization and include `target_model`, downloaded/estimated bytes, transfer speed, elapsed time, stalled time, endpoint, and cache directory. A directory containing only part of a model is reported as a **partial download**, not a usable cache.

The July 24, 2026 installed log showed the original failure pattern: startup ignored the saved `small` selection and began `base`; the official endpoint timed out, fallback selected `hf-mirror.com`, the Xet/CAS file transfer timed out, and a device fallback retried the same network download. VoiceCode now loads the configured model, waits for onboarding selection on first launch, avoids CPU retry for network errors, disables Xet by default, and surfaces a structured failure popup.

For a network timeout:

1. Retry; incomplete Hugging Face files are resumable.
2. Confirm `https://huggingface.co` or the selected mirror is reachable.
3. Check VPN, proxy, firewall, DNS, and security software.
4. Try `tiny` or `base` before a larger model.
5. Verify `<install-dir>\runtime\models` is writable and the drive has enough free space.

Advanced overrides: `HF_ENDPOINT`, `HF_HUB_ETAG_TIMEOUT`, `HF_HUB_DOWNLOAD_TIMEOUT`, and `HF_HUB_DISABLE_XET`. Packaged defaults are 10 seconds for metadata, 30 seconds for each download response, and Xet disabled.

## Model appears downloaded but cannot load

Open Models and check whether the cache is marked partial. VoiceCode now verifies the size of `model.bin`; missing or truncated weights are not considered complete. Delete the partial cache if resume repeatedly fails, then download again.

## Port occupied after closing

VoiceCode performs graceful shutdown and a frozen-process final exit. On the next launch it can also identify and terminate a windowless stale VoiceCode process when that process uses the same executable and still owns the configured local port. Unrelated services are never terminated.
