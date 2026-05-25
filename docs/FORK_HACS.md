# HACS install (this fork)

Upstream [`nathanmarlor/foxess_modbus`](https://github.com/nathanmarlor/foxess_modbus) uses **zip releases**:

```json
"zip_release": true,
"filename": "foxess_modbus.zip"
```

GitHub Actions builds `foxess_modbus.zip` when a **version tag** is pushed. Installing a random commit hash (e.g. during development) will fail if `zip_release` is enabled and no matching release exists.

**This fork’s `main` branch omits `zip_release`** so HACS can install directly from the repository source while you test EVO changes.

## Install via HACS (fork)

1. Custom repository: `https://github.com/james194zt/foxess_modbus_evo`
2. Category: Integration
3. Install / Redownload **FoxESS - Modbus** from `main`
4. Restart Home Assistant

If download fails after a config change: HACS → ⋮ → **Clear cache**, then redownload.

## Before opening a PR to upstream

Do **not** carry the fork’s `hacs.json` into Nathan’s repo. See [UPSTREAM_PR.md](./UPSTREAM_PR.md).
