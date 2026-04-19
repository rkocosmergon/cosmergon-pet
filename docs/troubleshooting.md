# Troubleshooting

Symptom-first. Find your symptom, read the fix.

## Quick fixes

The four cases the build guide already lists. If you're holding the
printed PDF, these are the same four bullets — just with more room.

### Display dark

The OLED is wired up but nothing appears.

**Why:** Either the wiring is off or the I²C bus can't see the display.

**Fix:** Power the Pi off, double-check the four OLED jumpers against
the table in the build guide (especially VCC / GND — easy to swap).
Power on, then:

```bash
sudo i2cdetect -y 1
```

You should see `3c` (or `3d`) in the grid. If you see neither, the
display isn't reachable — re-seat the Dupont connectors firmly, they
sometimes sit half-loose.

If `i2cdetect` itself complains "Error: Could not open file
`/dev/i2c-1`": I²C isn't enabled. Run
`sudo raspi-config nonint do_i2c 0 && sudo reboot`.

### Encoder dead

The display works (face appears), but turning the knob does nothing.

**Why:** Your user isn't in the `gpio` group, so the GPIO library can't
register edge interrupts.

**Fix:** Re-run the installer once. It adds your user to `gpio`, `i2c`
and `spi`. Group membership only takes effect after a new login session,
so log out and back in (or reboot), then re-run the installer:

```bash
curl -sL https://raw.githubusercontent.com/rkocosmergon/cosmergon-pet/main/install/install.sh | bash
```

Verify with `groups` — `gpio`, `i2c` and `spi` should appear.

### Service not running

The Pet doesn't come up after a reboot, or stops responding.

**Fix:** Check status, then logs.

```bash
sudo systemctl status cosmergon-pet
sudo journalctl -u cosmergon-pet -n 50
```

The status output tells you if it's failed (red) or just inactive. The
journal shows the last 50 log lines — usually the cause is at or near
the bottom.

To restart:

```bash
sudo systemctl restart cosmergon-pet
```

### Wrong agent on display, or "agent error"

The Pet shows a different agent name than the one you use on the
Dashboard, or the bottom line shows `! Could not resolve a…` /
`! Agent not co…`.

**Fix:** See `onboarding.md` — Path B explains how to attach an
existing agent to the Pet via `scp`.

## Specific failures

### `xCreatePipe: Can't set permissions for //.lgd-nfy0`

Cause: the systemd service is running with `cwd=/`, where the lgpio
library can't create its notification pipe. Fixed in v0.1.3 by setting
`WorkingDirectory=$HOME` in the service template. If you see this on a
v0.1.3+ install, your service unit is stale — re-run the installer.

### `command 'swig' failed` during install

Cause: the Pi OS Lite image doesn't ship `swig` or `liblgpio-dev`, but
the lgpio Python wheel needs both to build from source on aarch64.
Fixed in v0.1.2 by adding both to the installer's apt list.

### `Failed to add edge detection` in the log

Same as "Encoder dead" above. Group membership.

### `! state: Agent not co…` on the display

Cause: the Pet's run loop isn't opening the SDK's HTTP client. Fixed in
v0.1.4. If you see this on a v0.1.4+ install, your installed Pet
package is stale — re-run the installer.

## Asking for help

If your symptom isn't here, open an issue:
[github.com/rkocosmergon/cosmergon-pet/issues](https://github.com/rkocosmergon/cosmergon-pet/issues).
Include:

- The output of `sudo journalctl -u cosmergon-pet -n 50`.
- The output of `cosmergon-pet --version` (or the Git commit you
  installed from).
- Your Pi model and the Raspberry Pi OS version
  (`cat /etc/os-release`).

Don't paste the full content of `~/.cosmergon/config.toml` — the
`api_key` value is sensitive. The SDK version and the agent name are
fine.
