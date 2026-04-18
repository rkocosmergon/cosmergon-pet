#!/usr/bin/env bash
# Cosmergon Pet — one-line installer for Raspberry Pi OS.
#
#   curl -sL https://raw.githubusercontent.com/rkocosmergon/cosmergon-pet/main/install/install.sh | bash
#
# What this does (idempotent, can be re-run):
#   1. Sanity check: Linux on ARM, Python 3.10+, has sudo
#   2. Enable I2C (via raspi-config)
#   3. apt install python3-pip, python3-venv, python3-dev
#   4. Create ~/cosmergon-env (if missing)
#   5. pip install cosmergon-pet from GitHub (pulls all deps)
#   6. Install + enable systemd unit
#
# Flags:
#   --no-systemd    Install the package only, skip the systemd unit.
#   --no-i2c        Don't touch raspi-config (assume I2C is handled).
#   --dev           Install from current working directory (pip install -e .),
#                   useful when you cloned the repo.
#
# License: MIT. See LICENSES/MIT.txt.

set -euo pipefail

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
VENV="${HOME}/cosmergon-env"
SERVICE_NAME="cosmergon-pet"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
REPO_URL="https://github.com/rkocosmergon/cosmergon-pet"

INSTALL_SYSTEMD=1
ENABLE_I2C=1
DEV_INSTALL=0

for arg in "$@"; do
    case "$arg" in
        --no-systemd) INSTALL_SYSTEMD=0 ;;
        --no-i2c)     ENABLE_I2C=0 ;;
        --dev)        DEV_INSTALL=1 ;;
        --help|-h)
            sed -n '/^# /,/^$/p' "$0" | head -30 | sed 's/^# //'
            exit 0
            ;;
        *)
            echo "Unknown option: $arg" >&2
            echo "Try --help." >&2
            exit 1
            ;;
    esac
done

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
log() { printf '\033[1;34m[cosmergon-pet]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[cosmergon-pet]\033[0m %s\n' "$*" >&2; }
die() { printf '\033[1;31m[cosmergon-pet]\033[0m %s\n' "$*" >&2; exit 1; }

need_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "missing command: $1"
}

# -----------------------------------------------------------------------------
# 1. Sanity checks
# -----------------------------------------------------------------------------
log "Sanity checks"

if [ "$(uname)" != "Linux" ]; then
    die "This installer is for Linux (Raspberry Pi OS). You're on $(uname)."
fi

ARCH="$(uname -m)"
case "$ARCH" in
    aarch64|armv7l|armv6l) ;;
    x86_64)
        warn "You're on x86_64, not ARM. The Pet runs on Raspberry Pi."
        warn "Continuing anyway — maybe you're testing in a VM."
        ;;
    *)
        warn "Unexpected architecture: $ARCH. Continuing at your own risk."
        ;;
esac

need_cmd python3
need_cmd sudo
need_cmd apt

PY_VERSION="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
    die "Python 3.10+ required, got $PY_VERSION."
fi
log "  Linux $ARCH, Python $PY_VERSION — OK"

# -----------------------------------------------------------------------------
# 2. I2C
# -----------------------------------------------------------------------------
if [ "$ENABLE_I2C" = "1" ]; then
    log "Enabling I2C (sudo raspi-config nonint do_i2c 0)"
    if command -v raspi-config >/dev/null 2>&1; then
        sudo raspi-config nonint do_i2c 0 || warn "raspi-config returned non-zero — check manually"
    else
        warn "raspi-config not found — you're probably not on Raspberry Pi OS."
        warn "Skipping I2C setup. Make sure /dev/i2c-1 exists before starting the Pet."
    fi
fi

# -----------------------------------------------------------------------------
# 3. apt packages
# -----------------------------------------------------------------------------
log "Installing apt packages (python3-pip, python3-venv, python3-dev, git)"
sudo apt-get update -qq
# `git` is required because we pip-install from a git+https:// URL and pip
# shells out to the git binary. Raspberry Pi OS Lite does not ship with it.
sudo apt-get install -y -qq python3-pip python3-venv python3-dev git

# -----------------------------------------------------------------------------
# 3b. GPIO / I2C group membership
# -----------------------------------------------------------------------------
# Without these groups, Python can import RPi.GPIO but GPIO.add_event_detect()
# fails with "Failed to add edge detection" — the Pet then falls back to
# keyboard input, which is useless headless-via-SSH. Symptom reported in
# cosmergon-pet#1.
ADDED_GROUPS=()
for group in gpio i2c spi; do
    if ! getent group "$group" >/dev/null 2>&1; then
        continue  # Group doesn't exist on this system (non-RPi)
    fi
    if id -nG "$USER" | tr ' ' '\n' | grep -qx "$group"; then
        continue  # Already a member
    fi
    sudo usermod -aG "$group" "$USER"
    ADDED_GROUPS+=("$group")
done

if [ "${#ADDED_GROUPS[@]}" -gt 0 ]; then
    warn "Added $USER to groups: ${ADDED_GROUPS[*]}"
    warn "Group membership only takes effect after a new login session."
    warn "After the installer finishes, log out + in (or reboot) and re-run this installer."
    warn "The systemd unit will use the new groups on next boot automatically."
fi

# -----------------------------------------------------------------------------
# 4. Virtualenv
# -----------------------------------------------------------------------------
if [ ! -d "$VENV" ]; then
    log "Creating virtualenv at $VENV"
    python3 -m venv "$VENV"
else
    log "Virtualenv already exists at $VENV"
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"
python -m pip install --quiet --upgrade pip

# -----------------------------------------------------------------------------
# 4b. Drop legacy RPi.GPIO if present
# -----------------------------------------------------------------------------
# On Raspberry Pi OS Bookworm (Debian 12, kernel >=6.6) RPi.GPIO can read/write
# pins but GPIO.add_event_detect() fails with "Failed to add edge detection"
# because the old sysfs GPIO interface (/sys/class/gpio/*) has been removed in
# favour of the libgpiod character device /dev/gpiochipN. We ship rpi-lgpio,
# a drop-in namespace-compatible replacement. If a legacy RPi.GPIO is still
# around from an earlier install, uninstall it so rpi-lgpio owns the RPi.GPIO
# namespace cleanly. Reported as cosmergon-pet#1.
if pip show "RPi.GPIO" >/dev/null 2>&1; then
    log "Removing legacy RPi.GPIO (replaced by rpi-lgpio)"
    pip uninstall --quiet -y "RPi.GPIO"
fi

# -----------------------------------------------------------------------------
# 5. Install Cosmergon Pet
# -----------------------------------------------------------------------------
if [ "$DEV_INSTALL" = "1" ]; then
    log "Installing Cosmergon Pet in editable mode from current directory"
    pip install --quiet -e .
else
    log "Installing Cosmergon Pet from $REPO_URL"
    pip install --quiet --upgrade "git+${REPO_URL}"
fi

PET_BIN="$VENV/bin/cosmergon-pet"
if [ ! -x "$PET_BIN" ]; then
    die "Install succeeded but $PET_BIN is not executable — unexpected."
fi
log "  $PET_BIN installed"

# -----------------------------------------------------------------------------
# 6. systemd
# -----------------------------------------------------------------------------
if [ "$INSTALL_SYSTEMD" = "1" ]; then
    log "Installing systemd unit $SERVICE_FILE"
    sudo tee "$SERVICE_FILE" >/dev/null <<EOF
[Unit]
Description=Cosmergon Pet
After=network-online.target
Wants=network-online.target

[Service]
User=${USER}
ExecStart=${PET_BIN}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable "${SERVICE_NAME}"
    sudo systemctl restart "${SERVICE_NAME}"

    sleep 1
    if systemctl is-active --quiet "${SERVICE_NAME}"; then
        log "Service ${SERVICE_NAME} is running."
    else
        warn "Service ${SERVICE_NAME} is not active. Check: sudo journalctl -u ${SERVICE_NAME} -n 30"
    fi
else
    log "Skipping systemd (--no-systemd)."
    log "Start manually with: source $VENV/bin/activate && cosmergon-pet"
fi

# -----------------------------------------------------------------------------
# Done
# -----------------------------------------------------------------------------
cat <<EOF

  Cosmergon Pet installed.

  Next steps:
    * Face should appear on the OLED within ~10 seconds.
    * Status:    sudo systemctl status ${SERVICE_NAME}
    * Logs:      sudo journalctl -u ${SERVICE_NAME} -f
    * Stop:      sudo systemctl stop ${SERVICE_NAME}
    * Simulate:  source ${VENV}/bin/activate && cosmergon-pet --simulate
    * Update:    re-run this installer (idempotent)

  Build guide:  ${REPO_URL}/blob/main/guide/cosmergon-pet-bauanleitung.pdf
  Issues:       ${REPO_URL}/issues
EOF
