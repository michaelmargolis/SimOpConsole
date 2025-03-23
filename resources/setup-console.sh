#!/bin/bash
set -euo pipefail

USER="raes"
HOME_DIR="/home/$USER"

# ------------------------------
# 1. Install Core Desktop & Display Manager
# ------------------------------

echo ">>> Updating system..."
apt update && apt full-upgrade -y

echo ">>> Installing desktop & display manager packages..."
if ! dpkg -l | grep -qw lxde-core; then
  apt install -y --no-install-recommends lxde-core lxappearance lxsession lightdm
fi

echo ">>> Enabling graphical login..."
systemctl set-default graphical.target
mkdir -p "$(dirname /etc/lightdm/lightdm.conf.d/50-autologin.conf)"
if ! grep -q "^autologin-user=$USER" /etc/lightdm/lightdm.conf.d/50-autologin.conf 2>/dev/null; then
  cat <<EOF >/etc/lightdm/lightdm.conf.d/50-autologin.conf
[Seat:*]
autologin-user=$USER
autologin-session=LXDE
EOF
fi
systemctl enable lightdm

# ------------------------------
# 2. Install Additional Components (Python, lxterminal, etc.)
# ------------------------------

echo ">>> Installing Python3, pyserial, and additional packages..."
apt install -y python3 python3-serial

echo ">>> Installing Python modules, editor, and lxterminal..."
for pkg in python3-pyqt5 python3-numpy python3-serial geany; do
  dpkg -l | grep -qw "$pkg" || apt install -y "$pkg"
done

if ! dpkg -l | grep -qw lxterminal; then
  apt install -y lxterminal
fi

echo ">>> Adding user '$USER' to dialout group for serial access..."
usermod -a -G dialout "$USER"

# ------------------------------
# 3. Update Boot & Configuration Files for Serial/Overlay Settings
# ------------------------------

# Determine cmdline and config file paths
if [ -f /boot/firmware/cmdline.txt ]; then
  CMDLINE="/boot/firmware/cmdline.txt"
else
  CMDLINE="/boot/cmdline.txt"
fi

if [ -f /boot/firmware/config.txt ]; then
  CONFIG_TXT="/boot/firmware/config.txt"
else
  CONFIG_TXT="/boot/config.txt"
fi

echo ">>> Disabling serial console if present..."
if [ -f "$CMDLINE" ] && grep -q "console=serial0,115200" "$CMDLINE"; then
    sed -i 's/console=serial0,115200//g' "$CMDLINE"
fi

echo ">>> Configuring DTOverlays and boot_delay... "
for line in \
  "dtoverlay=vc4-kms-dsi-waveshare-panel,10_1_inch" \
  "dtoverlay=gpio-shutdown" \
  "dtoverlay=gpio-poweroff,active_low,gpiopin=2" \
  "boot_delay=1" \
  "enable_uart=1"; do
  grep -qxF "$line" "$CONFIG_TXT" || echo "$line" | tee -a "$CONFIG_TXT"
done


# Only disable Bluetooth if it is using the UART.
echo ">>> Checking if Bluetooth is using the UART..."
if systemctl is-active --quiet hciuart; then
    echo "Bluetooth UART is active, adding overlay to disable Bluetooth..."
    OVERLAY_LINE="dtoverlay=disable-bt"
    if [ -f "$CONFIG_TXT" ] && ! grep -qxF "$OVERLAY_LINE" "$CONFIG_TXT"; then
        echo "$OVERLAY_LINE" | tee -a "$CONFIG_TXT"
    fi
else
    echo "Bluetooth is not using the UART; leaving configuration unchanged."
fi

echo ">>> Ensuring boot parameters include 'quiet splash plymouth.ignore-serial-consoles'..."
if ! grep -q "quiet splash" "$CMDLINE"; then
  sed -i '1 s/$/ quiet splash plymouth.ignore-serial-consoles/' "$CMDLINE"
fi

echo ">>> Disabling unnecessary services..."
for svc in bluetooth triggerhappy; do
  systemctl disable "${svc}.service" &>/dev/null || :
done

# ------------------------------
# 4. Setup OpsConsole Application & Auto-Start Script
# ------------------------------

AUTOSTART_LXDE="$HOME_DIR/.config/lxsession/LXDE-pi/autostart"
AUTOSTART_SCRIPT="$HOME_DIR/OpsConsole/start_console.sh"

echo ">>> Creating OpsConsole directory & launcher script..."
mkdir -p "$HOME_DIR/OpsConsole"
chown -R "$USER:$USER" "$HOME_DIR/OpsConsole"

if [ ! -f "$AUTOSTART_SCRIPT" ]; then
  cat <<EOF >"$AUTOSTART_SCRIPT"
#!/bin/bash
cd "$HOME_DIR/OpsConsole" || exit
exec python3 siminterface_core.py
EOF
  chmod +x "$AUTOSTART_SCRIPT"
  chown "$USER:$USER" "$AUTOSTART_SCRIPT"
fi

mkdir -p "$(dirname "$AUTOSTART_LXDE")"
grep -qxF "@bash $AUTOSTART_SCRIPT" "$AUTOSTART_LXDE" 2>/dev/null || echo "@bash $AUTOSTART_SCRIPT" >>"$AUTOSTART_LXDE"
chown -R "$USER:$USER" "$HOME_DIR/.config"

# ------------------------------
# 5. Setup Plymouth Splash
# ------------------------------

PLY_THEME_DIR="/usr/share/plymouth/themes/falcon_splash"
echo ">>> Setting up Plymouth splash..."
apt install -y plymouth plymouth-themes
if [ ! -d "$PLY_THEME_DIR" ]; then
  mkdir -p "$PLY_THEME_DIR"
  cp "$HOME_DIR/falcon2_splash.png" "$PLY_THEME_DIR"/falcon2_splash.png
  cat <<EOF >"$PLY_THEME_DIR/falcon2_splash.plymouth"
[Plymouth Theme]
Name=Falcon2 Splash
Description=Custom splash
ModuleName=script

[script]
ImageDir=$PLY_THEME_DIR
ScriptFile=$PLY_THEME_DIR/falcon2_splash.script
EOF
  cat <<EOF >"$PLY_THEME_DIR/falcon2_splash.script"
wallpaper_image("\${ImageDir}/falcon2_splash.png");
EOF
  update-alternatives --install /usr/share/plymouth/themes/default.plymouth default.plymouth "$PLY_THEME_DIR/falcon2_splash.plymouth" 200
fi
update-alternatives --set default.plymouth "$PLY_THEME_DIR/falcon2_splash.plymouth"
update-initramfs -u

# ------------------------------
# 6. Create Desktop Launcher for Falcon2 Console
# ------------------------------
 
LAUNCHER="$HOME_DIR/.local/share/applications/falcon2_console.desktop"
echo ">>> Creating Falcon2 Console desktop launcher..."
mkdir -p "$HOME_DIR/.local/share/applications"
if [ ! -f "$LAUNCHER" ]; then
  cat <<EOF > "$LAUNCHER"
[Desktop Entry]
Version=1.0
Type=Application
Name=Falcon2 Console
Exec=/home/raes/start_console.sh
Icon=/home/raes/OpsConsole/images/falcon2_icon.png
Terminal=true
EOF
  chown "$USER:$USER" "$LAUNCHER"
fi

# ------------------------------
# 7. Create Desktop Icons for Editor and Terminal
# ------------------------------

DESKTOP_DIR="$HOME_DIR/Desktop"
mkdir -p "$DESKTOP_DIR"

EDITOR_LAUNCHER="$HOME_DIR/.local/share/applications/falcon2_editor.desktop"
if [ ! -f "$EDITOR_LAUNCHER" ]; then
  cat <<EOF > "$EDITOR_LAUNCHER"
[Desktop Entry]
Version=1.0
Type=Application
Name=Falcon2 Editor
Exec=geany
Icon=geany
Terminal=false
X-GNOME-Autostart-enabled=true
EOF
  chown "$USER:$USER" "$EDITOR_LAUNCHER"
  chmod +x "$EDITOR_LAUNCHER"
fi

TERMINAL_LAUNCHER="$HOME_DIR/.local/share/applications/falcon2_terminal.desktop"
if [ ! -f "$TERMINAL_LAUNCHER" ]; then
  cat <<EOF > "$TERMINAL_LAUNCHER"
[Desktop Entry]
Version=1.0
Type=Application
Name=Falcon2 Terminal
Exec=lxterminal
Icon=utilities-terminal
Terminal=false
X-GNOME-Autostart-enabled=true
EOF
  chown "$USER:$USER" "$TERMINAL_LAUNCHER"
  chmod +x "$TERMINAL_LAUNCHER"
fi

# Copy launchers to the Desktop folder so that they appear as icons.
cp "$EDITOR_LAUNCHER" "$DESKTOP_DIR/"
cp "$TERMINAL_LAUNCHER" "$DESKTOP_DIR/"
chmod +x "$DESKTOP_DIR/falcon2_editor.desktop" "$DESKTOP_DIR/falcon2_terminal.desktop"
chown "$USER:$USER" "$DESKTOP_DIR/falcon2_editor.desktop" "$DESKTOP_DIR/falcon2_terminal.desktop"


echo ">>> Setup complete — please reboot for all changes to take effect!"
