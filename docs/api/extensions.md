# Extensions API

## `GET /extensions`

Returns extension status, availability, dependencies, missing dependencies, and effective config.

Extensions are configured through `POST /config` under the `extensions` object.

Current extension IDs:

- `audio_io`
- `exporters`
- `hotwords`
- `vad`
- `zh_normalizer`
- `quality`
- `diarization`
- `punctuation`
