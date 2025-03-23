#!/bin/bash
set -euo pipefail

# -------------------------------------------------
# 1. Determine the user and home directory
# -------------------------------------------------
if [ "$EUID" -eq 0 ]; then
  USER=$(logname)
  HOME_DIR="/home/$USER"
else
  USER=$(whoami)
  HOME_DIR="$HOME"
fi

echo "Using user: $USER"
echo "Home directory: $HOME_DIR"

# -------------------------------------------------
# 2. Set default target to graphical and update/install packages
# -------------------------------------------------
systemctl set-default graphical.target

apt update && apt full-upgrade -y

# Install minimal GUI components plus Python3 and required modules.
apt install -y lxde-core lxsession lightdm geany lxterminal xinit \
  python3 python3-numpy python3-serial python3-pyqt5

# -------------------------------------------------
# 3. Configure LightDM for autologin
# -------------------------------------------------
# Remove any conflicting LightDM config file.
if [ -f /etc/lightdm/lightdm.conf ]; then
  mv /etc/lightdm/lightdm.conf /etc/lightdm/lightdm.conf.bak
fi

AUTLOGIN_CONF="/etc/lightdm/lightdm.conf.d/50-autologin.conf"
mkdir -p "$(dirname "$AUTLOGIN_CONF")"
cat <<EOF > "$AUTLOGIN_CONF"
[Seat:*]
autologin-user=$USER
autologin-user-timeout=0
user-session=LXDE-pi
greeter-session=pi-greeter
EOF
echo "LightDM autologin configured in $AUTLOGIN_CONF."
systemctl enable lightdm

# -------------------------------------------------
# 4. Configure DTOverlays for DSI screen and power settings
# -------------------------------------------------
if [ -f /boot/firmware/config.txt ]; then
  CONFIG_TXT="/boot/firmware/config.txt"
else
  CONFIG_TXT="/boot/config.txt"
fi

echo "Configuring DTOverlay settings in $CONFIG_TXT..."
for line in \
  "dtoverlay=vc4-kms-dsi-waveshare-panel,10_1_inch" \
  "dtoverlay=gpio-shutdown" \
  "dtoverlay=gpio-poweroff,active_low,gpiopin=2" \
  "boot_delay=1" \
  "enable_uart=1"; do
  if ! grep -qxF "$line" "$CONFIG_TXT"; then
    echo "$line" >> "$CONFIG_TXT"
    echo "Added: $line"
  fi
done

# -------------------------------------------------
# 5. Remove any default Geany autostart entries from global and user autostart folders
# -------------------------------------------------
# Remove from global LXDE autostart if present.
if [ -f /etc/xdg/lxsession/LXDE-pi/autostart ]; then
  sed -i '/geany/d' /etc/xdg/lxsession/LXDE-pi/autostart
  echo "Removed any default Geany autostart entry from /etc/xdg/lxsession/LXDE-pi/autostart."
fi
# Remove from user-level autostart folder.
if [ -f "$HOME_DIR/.config/autostart/geany.desktop" ]; then
  rm "$HOME_DIR/.config/autostart/geany.desktop"
  echo "Removed geany.desktop from user autostart folder."
fi

# -------------------------------------------------
# 6. Ensure user configuration directory exists and is writable
# -------------------------------------------------
mkdir -p "$HOME_DIR/.config"
chown -R "$USER:$USER" "$HOME_DIR/.config"
chmod -R u+rwx "$HOME_DIR/.config"

# -------------------------------------------------
# 7. Create OpsConsole folder and the test siminterface_core.py app
# -------------------------------------------------
OPS_DIR="$HOME_DIR/OpsConsole"
mkdir -p "$OPS_DIR"

SIMAPP="$OPS_DIR/siminterface_core.py"
cat <<'EOF' > "$SIMAPP"
#!/usr/bin/env python3
"""
A simple PyQt5 Hello World application for OpsConsole.
"""
import sys
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout

def main():
    app = QApplication(sys.argv)
    window = QWidget()
    window.setWindowTitle("OpsConsole Test")
    layout = QVBoxLayout()
    label = QLabel("Hello, World from OpsConsole!")
    layout.addWidget(label)
    window.setLayout(layout)
    window.resize(400, 200)
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
EOF
chown "$USER:$USER" "$SIMAPP"
chmod +x "$SIMAPP"
echo "Test siminterface_core.py created in $OPS_DIR."

# -------------------------------------------------
# 8. Set up autostart for siminterface_core.py (user-level)
# -------------------------------------------------
AUTOSTART_DIR="$HOME_DIR/.config/autostart"
mkdir -p "$AUTOSTART_DIR"

SIMAPP_AUTOSTART="$AUTOSTART_DIR/siminterface_core.desktop"
cat <<EOF > "$SIMAPP_AUTOSTART"
[Desktop Entry]
Type=Application
Name=OpsConsole
Exec=/usr/bin/python3 $SIMAPP
Terminal=false
X-GNOME-Autostart-enabled=true
MimeType=application/x-desktop;
EOF
chown "$USER:$USER" "$SIMAPP_AUTOSTART"
chmod +x "$SIMAPP_AUTOSTART"
echo "Autostart entry for siminterface_core.py created at $SIMAPP_AUTOSTART."

# -------------------------------------------------
# 9. Create Desktop Icons for OpsConsole and (conditionally) LXTerminal
# -------------------------------------------------
DESKTOP_DIR="$HOME_DIR/Desktop"
mkdir -p "$DESKTOP_DIR"

# OpsConsole Desktop Icon
OPS_ICON="$DESKTOP_DIR/OpsConsole.desktop"
cat <<EOF > "$OPS_ICON"
[Desktop Entry]
Version=1.0
Type=Application
Name=OpsConsole
Exec=/usr/bin/python3 $SIMAPP
Icon=utilities-terminal
Terminal=false
StartupNotify=true
NoDisplay=false
MimeType=application/x-desktop;
EOF
chown "$USER:$USER" "$OPS_ICON"
chmod +x "$OPS_ICON"

# LXTerminal Desktop Icon: only create if it doesn't already exist.
TERMINAL_ICON="$DESKTOP_DIR/Terminal.desktop"
if [ ! -f "$TERMINAL_ICON" ]; then
  cat <<EOF > "$TERMINAL_ICON"
[Desktop Entry]
Version=1.0
Type=Application
Name=LXTerminal
Exec=/usr/bin/lxterminal
TryExec=/usr/bin/lxterminal
Icon=utilities-terminal
Terminal=false
StartupNotify=true
NoDisplay=false
MimeType=application/x-desktop;
EOF
  chown "$USER:$USER" "$TERMINAL_ICON"
  chmod +x "$TERMINAL_ICON"
  echo "LXTerminal desktop icon created in $DESKTOP_DIR."
else
  echo "LXTerminal desktop icon already exists in $DESKTOP_DIR; not overwriting."
fi

echo "Test environment installation complete."
echo " - System is set to boot to the graphical target with autologin (configured in $AUTLOGIN_CONF)."
echo " - DTOverlay settings for the Waveshare DSI screen and power control have been appended to $CONFIG_TXT."
echo " - OpsConsole (siminterface_core.py) is set to autostart via $AUTOSTART_DIR."
echo " - Desktop icons for OpsConsole and LXTerminal have been created in $DESKTOP_DIR."
echo "Please reboot for all changes to take effect."
