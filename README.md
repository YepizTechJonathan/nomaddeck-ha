# NomadDeck — Home Assistant integration (install via HACS)

This repository hosts the **NomadDeck Home Assistant integration**. NomadDeck is a
local-first operations platform: a control plane watches over a small fleet of
machines (sync health, machine reachability, power state, GPU workloads) and
exposes that fleet over a private HTTP API. This integration makes Home Assistant
the dashboard for it.

## What you get

One hub device (`NomadDeck Control Plane`) plus one device per machine in your
fleet, with:

| Entity | Type | What it tells you |
|---|---|---|
| `sensor.nomaddeck_fleet_health` | enum | `healthy` / `degraded` / `error` — the fleet verdict |
| `sensor.nomaddeck_machines_reachable` | measurement | Machines answering vs. expected |
| `sensor.nomaddeck_power_targets_on` | measurement | How many power-managed machines are up |
| `sensor.nomaddeck_findings` | measurement | Outstanding problems from the fleet sweep |
| `sensor.nomaddeck_sync_state` | enum | `synced` / `syncing` / `offline` |
| `sensor.nomaddeck_sync_devices_connected` | measurement | File-sync peers online vs. expected |
| `sensor.nomaddeck_sync_divergences` | measurement | Sync conflicts needing attention |
| `sensor.nomaddeck_jobs` | enum | `clear` / `active` |
| `sensor.nomaddeck_last_fleet_sweep` | timestamp | When the watchdog last ran |
| `sensor.nomaddeck_version` | diagnostic | Control-plane version |
| `binary_sensor.nomaddeck_fleet_ok` | problem | Off when the fleet is unhealthy (use in automations) |
| `binary_sensor.nomaddeck_sync_ok` | problem | Off when sync is broken |
| `binary_sensor.<machine>_api_reachable` | connectivity | Per-machine API reachability |
| `sensor.<machine>_power` | enum | Per-machine `on` / `off` / `unknown` |

Everything is polled from the control plane every 30 seconds by default
(adjustable in the integration options). Nothing is pushed to Home Assistant, and
no cloud service is involved.

## Requirements

- A running NomadDeck control plane, reachable from your Home Assistant host.
- The control plane's API port (default `8787`).

If your control plane is only reachable over a VPN such as Tailscale, use its
VPN address when adding the integration.

## Install

### With HACS (recommended)

1. In Home Assistant, open **HACS**.
2. Open the three-dot menu (top right) → **Custom repositories**.
3. Paste this repository's URL, choose category **Integration**, and click **Add**.
4. Search HACS for **NomadDeck** and click **Download**.
5. Restart Home Assistant.
6. Go to **Settings → Devices & Services → Add Integration → NomadDeck**, enter your
   control plane's host and port, and submit. The flow tests the connection before
   saving.

### Manually (no HACS)

Copy `custom_components/nomaddeck/` into your Home Assistant `config/custom_components/`
directory, restart Home Assistant, then add the integration as in step 6 above.

## Options

After setup, use **Configure** on the integration entry to change the poll
interval (10–600 seconds).

## Troubleshooting

**"Could not reach a NomadDeck control plane at that address"** — check that the
API is running on the control plane and that the host/port are correct. From the
control plane itself, `curl http://127.0.0.1:8787/api/status` should return JSON.

**Entities show as unavailable** — the control plane stopped answering. The
integration marks itself unavailable rather than reporting stale data; check the
control plane's service.

## Scope

This integration is read-only by design. Wake/sleep and other power actions stay
behind NomadDeck's own approval gate, so they are deliberately *not* exposed as
one-tap Home Assistant buttons.
