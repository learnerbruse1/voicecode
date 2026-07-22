# Troubleshooting

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
