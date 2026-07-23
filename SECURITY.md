# Security Policy

VoiceCode is an offline desktop transcription app. If you discover a security issue, please report it privately to the maintainers before opening a public issue.

## Local-only design

- The HTTP API is intended to bind only to `127.0.0.1`.
- Audio is sent only to the local VoiceCode service and processed by the local Whisper runtime.
- VoiceCode does not intentionally upload audio, transcript history, logs, settings, or model caches.
- Packaged builds keep future model/cache downloads under the selected install directory's `runtime` folder unless users override cache-related environment variables.

## What to include in a report

Please include:

- A clear description of the issue
- Steps to reproduce
- Your platform and Python version, or the installer version
- Whether you used the source tree, wheel, one-folder app, or installer
- Any relevant logs, screenshots, or crash traces with private transcripts and local secrets removed

We will respond as quickly as possible.

## Local API hardening

VoiceCode's HTTP server must bind only to `127.0.0.1`. During normal desktop runtime, mutating HTTP requests require the per-process `X-VoiceCode-Token` header. The token is generated at startup unless `VOICECODE_API_TOKEN` is explicitly provided for a trusted local integration. Do not run with `VOICECODE_DISABLE_API_TOKEN=1` outside isolated testing or development environments.

Please report any path traversal, cross-origin local API, dependency installation, or token exposure issue as a security vulnerability.

## In-app dependency installation

Dependency installs execute local `pip` subprocesses against cataloged package-index specs and write only to the isolated dependency directory. Treat catalog changes as supply-chain-sensitive. Uninstall uses manifests and path containment checks; report any path escape, arbitrary package spec injection, token bypass, or unsafe subprocess behavior privately.

## Browser boundary hardening

VoiceCode validates loopback Host names, rejects foreign Origins on mutations, requires a per-process mutation token, and sends CSP, anti-framing, `nosniff`, no-referrer, and restrictive permissions headers. Reports involving DNS rebinding, Host bypass, Origin bypass, token disclosure, or DOM injection are security-sensitive.

## Dependency task hardening

Catalog specs default to the configured Python package index. Installs check free disk space, serialize across threads/processes, persist task state, enforce timeouts, support cancellation, and terminate process trees. Manifests are containment-checked during uninstall. Mutable or user-supplied package specs are not accepted by API routes.

The optional dependency directory is never placed ahead of application or standard-library paths, and its `.pth` files are not executed during path activation.
