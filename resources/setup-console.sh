#!/bin/bash
set -euo pipefail

# -------------------------------------------------
# 1. Determine the actual user and home directory.
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
# 2. Set default target to graphical and update/install packages.
# -------------------------------------------------
systemctl set-default graphical.target

apt update && apt full-upgrade -y

# Install minimal GUI components plus Python3 and required modules.
apt install -y lxde-core lxsession lightdm geany lxterminal xinit \
  python3 python3-numpy python3-serial python3-pyqt5

# -------------------------------------------------
# X. Disable the serial-getty service on /dev/ttyS0 to free the serial port.
# -------------------------------------------------
echo "Disabling serial-getty on /dev/ttyS0..."
sudo systemctl disable serial-getty@ttyS0.service
sudo systemctl stop serial-getty@ttyS0.service

# -------------------------------------------------
# 3. Configure LightDM for autologin.
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
user-session=LXDE
greeter-session=lightdm-gtk-greeter
EOF
echo "LightDM autologin configured in $AUTLOGIN_CONF."
systemctl enable lightdm

# -------------------------------------------------
# 4. Remove serial console parameter from cmdline and configure DTOverlays for DSI screen and power settings.
# -------------------------------------------------
# Remove console=serial0,115200 from cmdline.txt to free the serial port.
if [ -f /boot/firmware/cmdline.txt ]; then
  CMDLINE="/boot/firmware/cmdline.txt"
else
  CMDLINE="/boot/cmdline.txt"
fi
if grep -q "console=serial0,115200" "$CMDLINE"; then
  sed -i 's/console=serial0,115200//g' "$CMDLINE"
  echo "Removed console=serial0,115200 from $CMDLINE."
else
  echo "No console=serial0,115200 parameter found in $CMDLINE."
fi

# Configure DTOverlay settings.
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
# 5. Ensure the global LXDE autostart file starts the desktop manager.
# -------------------------------------------------
GLOBAL_AUTOSTART="/etc/xdg/lxsession/LXDE/autostart"
if [ ! -f "$GLOBAL_AUTOSTART" ]; then
  echo "Global autostart file $GLOBAL_AUTOSTART not found. Creating it..."
  mkdir -p "$(dirname "$GLOBAL_AUTOSTART")"
  cat <<EOF > "$GLOBAL_AUTOSTART"
@lxpanel --profile LXDE
@pcmanfm --desktop --profile LXDE
@xscreensaver -no-splash
EOF
  echo "Created global autostart file with PCManFM start command."
else
  if ! grep -q "pcmanfm --desktop" "$GLOBAL_AUTOSTART"; then
    echo "@pcmanfm --desktop --profile LXDE" >> "$GLOBAL_AUTOSTART"
    echo "Added PCManFM desktop command to global autostart."
  else
    echo "Global autostart file already includes PCManFM."
  fi
fi

# -------------------------------------------------
# 6. Remove any default Geany autostart entries.
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
# 6.5. Create Desktop Icon for Geany (manual launch)
# -------------------------------------------------
GEANY_DESKTOP_ICON="$HOME_DIR/Desktop/Geany.desktop"
cat <<EOF > "$GEANY_DESKTOP_ICON"
[Desktop Entry]
Version=1.0
Type=Application
Name=Geany
Exec=geany
Icon=accessories-text-editor
Terminal=false
StartupNotify=true
NoDisplay=false
MimeType=application/x-desktop;
EOF
chown "$USER:$USER" "$GEANY_DESKTOP_ICON"
chmod 644 "$GEANY_DESKTOP_ICON"
echo "Desktop icon for Geany created at $GEANY_DESKTOP_ICON."

# -------------------------------------------------
# 7. Ensure user configuration directory exists and is writable.
# -------------------------------------------------
mkdir -p "$HOME_DIR/.config"
chown -R "$USER:$USER" "$HOME_DIR/.config"
chmod -R u+rwx "$HOME_DIR/.config"

# -------------------------------------------------
# 8. Use siminterface_core.py from the repository.
# -------------------------------------------------
OPS_DIR="$HOME_DIR/OpsConsole"
SIMAPP="$OPS_DIR/siminterface_core.py"
if [ ! -f "$SIMAPP" ]; then
    echo "Error: siminterface_core.py not found at $SIMAPP. Please ensure the repository is up to date."
    exit 1
fi
chown "$USER:$USER" "$SIMAPP"
chmod +x "$SIMAPP"
echo "siminterface_core.py is located at $SIMAPP."

# Ensure the entire OpsConsole directory and its contents are owned by the user.
chown -R "$USER:$USER" "$OPS_DIR"

# -------------------------------------------------
# 9. Set up autostart for siminterface_core.py (user-level).
# -------------------------------------------------

# Create the start-console.sh script that changes directory and runs the app.
START_CONSOLE_SCRIPT="$HOME_DIR/start-console.sh"
cat <<EOF > "$START_CONSOLE_SCRIPT"
#!/bin/bash
cd /home/$USER/OpsConsole
/usr/bin/python3 siminterface_core.py
EOF
chown "$USER:$USER" "$START_CONSOLE_SCRIPT"
chmod 755 "$START_CONSOLE_SCRIPT"
echo "Created start-console.sh in $HOME_DIR."

# Set up the autostart entry to run the start-console.sh script.
AUTOSTART_DIR="$HOME_DIR/.config/autostart"
mkdir -p "$AUTOSTART_DIR"
SIMAPP_AUTOSTART="$AUTOSTART_DIR/siminterface_core.desktop"
cat <<EOF > "$SIMAPP_AUTOSTART"
[Desktop Entry]
Type=Application
Name=OpsConsole
Exec=$HOME_DIR/start-console.sh
Terminal=false
X-GNOME-Autostart-enabled=true
MimeType=application/x-desktop;
EOF
chown "$USER:$USER" "$SIMAPP_AUTOSTART"
chmod 644 "$SIMAPP_AUTOSTART"
echo "Autostart entry for OpsConsole created at $SIMAPP_AUTOSTART."

# -------------------------------------------------
# 10. Create Desktop Icons for OpsConsole and (conditionally) LXTerminal.
# -------------------------------------------------
DESKTOP_DIR="$HOME_DIR/Desktop"
mkdir -p "$DESKTOP_DIR"

# OpsConsole Desktop Icon using the actual icon from the resources folder.
OPS_ICON="$DESKTOP_DIR/OpsConsole.desktop"
cat <<EOF > "$OPS_ICON"
[Desktop Entry]
Version=1.0
Type=Application
Name=OpsConsole
Exec=/usr/bin/python3 siminterface_core.py
Path=/home/raes/OpsConsole
Icon=$HOME_DIR/OpsConsole/resources/falcon2_icon.png
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

# -------------------------------------------------
# 11. Set the desktop background to Falcon2_splash.png using a wrapper script.
# -------------------------------------------------
WALLPAPER_WRAPPER="$OPS_DIR/resources/set_wallpaper.sh"
cat <<'EOF' > "$WALLPAPER_WRAPPER"
#!/bin/bash
# Wait until PCManFM is active in desktop mode.
while ! pgrep -f "pcmanfm --desktop" > /dev/null; do
  sleep 0.5
done
# Set the wallpaper; redirect stderr to suppress error dialogs.
pcmanfm --set-wallpaper="/home/$USER/OpsConsole/resources/falcon2_splash.png" --wallpaper-mode=stretch 2>/dev/null
EOF
chown "$USER:$USER" "$WALLPAPER_WRAPPER"
chmod 644 "$WALLPAPER_WRAPPER"
echo "Wallpaper wrapper script created at $WALLPAPER_WRAPPER."

WALLPAPER_AUTOSTART="$AUTOSTART_DIR/set-wallpaper.desktop"
cat <<EOF > "$WALLPAPER_AUTOSTART"
[Desktop Entry]
Type=Application
Name=Set Wallpaper
Exec=$WALLPAPER_WRAPPER
Terminal=false
X-GNOME-Autostart-enabled=true
MimeType=application/x-desktop;
EOF
chown "$USER:$USER" "$WALLPAPER_AUTOSTART"
chmod 644 "$WALLPAPER_AUTOSTART"
echo "Autostart entry for setting desktop wallpaper created at $WALLPAPER_AUTOSTART."

# -------------------------------------------------
# 12. Install the MS33558.ttf font from the repository.
# -------------------------------------------------
FONT_SRC="$OPS_DIR/resources/MS33558.ttf"
FONT_DEST="$HOME_DIR/.local/share/fonts/MS33558.ttf"
mkdir -p "$HOME_DIR/.local/share/fonts"
if [ -f "$FONT_SRC" ]; then
  cp "$FONT_SRC" "$FONT_DEST"
  echo "Copied MS33558.ttf to $FONT_DEST."
  fc-cache -f "$HOME_DIR/.local/share/fonts"
  echo "Font cache updated."
else
  echo "Error: MS33558.ttf not found in $OPS_DIR/resources."
fi

# -------------------------------------------------
# 13. Create ~/.Xresources with a larger cursor size if it doesn't exist.
# -------------------------------------------------
XRESOURCES="$HOME_DIR/.Xresources"
if [ ! -f "$XRESOURCES" ]; then
  echo "Xcursor.size: 48" > "$XRESOURCES"
  echo "Created $XRESOURCES with Xcursor.size: 48"
else
  echo "$XRESOURCES already exists; not modifying."
fi

# -------------------------------------------------
# Final Message
# -------------------------------------------------
echo "Test environment installation complete."
echo " - System is set to boot to the graphical target with autologin (configured in $AUTLOGIN_CONF)."
echo " - DTOverlay settings for the Waveshare DSI screen and power control have been appended to $CONFIG_TXT."
echo " - OpsConsole (siminterface_core.py) is set to autostart via $HOME_DIR/.config/autostart."
echo " - Desktop icons for OpsConsole and LXTerminal have been created in $DESKTOP_DIR."
echo " - An autostart entry to set the desktop background to Falcon2_splash.png has been created."
echo "Please reboot for all changes to take effect."
