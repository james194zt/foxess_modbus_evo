# Contributing EVO changes upstream

Goal: PRs to [`nathanmarlor/foxess_modbus`](https://github.com/nathanmarlor/foxess_modbus) contain **Modbus / integration data only** — not fork-specific HACS or dashboard work.

## Branch workflow

1. Fetch upstream: `git fetch upstream`
2. Create PR branch from **`upstream/main`** (not this fork’s old history):
   ```bash
   git checkout -b pr/evo-<topic> upstream/main
   ```
3. Apply EVO commits or patches (entity map, sensors, snapshots, tests).
4. Run tests: `pytest tests/test_entity_descriptions.py`
5. Open PR against `nathanmarlor/foxess_modbus` `main`.

## `hacs.json` — do not change in upstream PRs

Upstream expects **zip releases** (`zip_release` + `foxess_modbus.zip` from tagged releases). That is the author’s intended HACS path.

| Branch | `hacs.json` |
|--------|-------------|
| **This fork `main`** | No `zip_release` — source install for dev/testing |
| **Upstream PR branch** | **Unchanged** — keep upstream’s `zip_release` block |

When preparing a PR, confirm `hacs.json` matches upstream:

```bash
git diff upstream/main -- hacs.json
# Should show no diff (or only if upstream itself changed)
```

If your working tree removed `zip_release` for local HACS, restore before pushing the PR branch:

```bash
git checkout upstream/main -- hacs.json
```

**Never** submit a PR that only removes `zip_release` unless maintainers explicitly agree to change release policy.

## Files typically in an EVO PR

- `custom_components/foxess_modbus/**` (entities, profiles, types, charge periods, …)
- `tests/__snapshots__/.../test_entities[EVO-AUX-latest].json`
- Tests if behaviour changed

## Files to exclude from upstream PRs

- Fork-only `README` / HACS custom-repo instructions
- `docs/FORK_HACS.md` (this fork only)
- `HADashboard/`, `foxess_local`, Lovelace cards
- StormSafe / weather orchestration

## Suggested PR split

1. **EVO register map + fixes** (charge periods `480xx`, scales, BMS, EPS, …)
2. **Derived sensors** (optional): `battery_kwh_remaining`, `battery_status`, `battery_cycles` — separate PR with clear “calculated from registers” notes
