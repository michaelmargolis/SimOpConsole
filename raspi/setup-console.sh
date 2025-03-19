#!/bin/bash

echo "Starting Raspberry Pi PyQt Console Setup..."

# Update package list and upgrade existing packages
echo "Updating package list and upgrading packages..."
sudo apt update && sudo apt upgrade -y

# Add user 'raes' to necessary groups
echo "Adding 'raes' to required groups..."
sudo usermod -aG sudo,video,input,render,tty raes

# Install minimal GUI environment
echo "Installing Xorg, Openbox, and LightDM..."
sudo apt install --no-install-recommends xserver-xorg xserver-xorg-legacy xinit openbox lightdm x11-xserver-utils -y

# Ensure Xorg allows non-root users
echo "Configuring Xorg permissions..."
sudo bash -c 'echo -e "allowed_users=anybody\nneeds_root_rights=no" > /etc/X11/Xwrapper.config'

# Install Python, PyQt, and required libraries
echo "Installing Python 3, PyQt5, NumPy, and PySerial..."
sudo apt install python3 python3-pyqt5 python3-serial python3-numpy -y

# Install Qt dependencies for 'xcb' support
echo "Installing Qt platform plugins..."
sudo apt install --reinstall qt5-default qtwayland5 libxcb-xinerama0 libxkbcommon-x11-0 libxcb-util1 -y

# Install Geany text editor
echo "Installing Geany..."
sudo apt install geany -y

# Enable DSI display support in /boot/config.txt
echo "Enabling DSI Display Support..."
CONFIG_FILE="/boot/config.txt"

if ! grep -q "dtoverlay=vc4-kms-dsi-waveshare-panel,10_1_inch" "$CONFIG_FILE"; then
    echo "dtoverlay=vc4-kms-dsi-waveshare-panel,10_1_inch" | sudo tee -a "$CONFIG_FILE"
    echo "DSI overlay added."
else
    echo "DSI overlay already present."
fi

# Enable GPIO shutdown in /boot/config.txt
echo "Enabling GPIO Shutdown..."
if ! grep -q "dtoverlay=gpio-shutdown" "$CONFIG_FILE"; then
    echo "dtoverlay=gpio-shutdown" | sudo tee -a "$CONFIG_FILE"
    echo "GPIO Shutdown enabled."
else
    echo "GPIO Shutdown already present."
fi

# Ensure the PyQt application directory exists
echo "Ensuring application directory exists..."
mkdir -p /home/raes/OpsConsole

# Create an auto-start script for the PyQt app
echo "Creating startup script..."
cat <<EOF > /home/raes/start_console.sh
#!/bin/bash
cd /home/raes/OpsConsole || exit
export DISPLAY=:0
export QT_QPA_PLATFORM=xcb
xinit /usr/bin/python3 /home/raes/OpsConsole/siminterface_core.py -- :0 vt1 || bash
EOF
chmod +x /home/raes/start_console.sh
chown raes:raes /home/raes/start_console.sh

# Ensure .Xauthority file exists
echo "Creating .Xauthority file for Xorg..."
touch /home/raes/.Xauthority
sudo chown raes:raes /home/raes/.Xauthority

# Add auto-run configuration to .bashrc if not already present
echo "Configuring auto-run on boot..."
BASHRC_FILE="/home/raes/.bashrc"
AUTO_RUN_CMD='if [ "$(tty)" = "/dev/tty1" ]; then /home/raes/start_console.sh; fi'

# Check if the auto-run command is already in .bashrc
if ! grep -Fxq "$AUTO_RUN_CMD" "$BASHRC_FILE"; then
    echo "$AUTO_RUN_CMD" >> "$BASHRC_FILE"
    echo "Auto-run command added to .bashrc."
else
    echo "Auto-run command already present in .bashrc."
fi

# Optimize boot time
echo "Optimizing boot time..."
sudo systemctl mask networking.service
sudo systemctl mask dphys-swapfile.service
sudo systemctl mask systemd-timesyncd.service

# Enable auto-login
echo "Enabling auto-login..."
sudo raspi-config nonint do_boot_behaviour B2

# Set boot splash screen
echo "Configuring splash screen..."
SPLASH_IMAGE="/home/raes/falcon2_splash.png"

if [[ -f "$SPLASH_IMAGE" ]]; then
    sudo apt install plymouth plymouth-themes -y
    sudo mkdir -p /usr/share/plymouth/themes/falcon2
    sudo cp "$SPLASH_IMAGE" /usr/share/plymouth/themes/falcon2/falcon2_splash.png

    cat <<EOT | sudo tee /usr/share/plymouth/themes/falcon2/falcon2.plymouth
[Plymouth Theme]
Name=Falcon2 Boot Splash
Description=Falcon2 custom splash screen
ModuleName=script

[script]
ImageDir=/usr/share/plymouth/themes/falcon2
ScriptFile=/usr/share/plymouth/themes/falcon2/falcon2.script
EOT

    cat <<EOT | sudo tee /usr/share/plymouth/themes/falcon2/falcon2.script
wallpaper_image = Image("falcon2_splash.png");
wallpaper_sprite = Sprite(wallpaper_image);
wallpaper_sprite.SetZ(-100);
EOT

    sudo plymouth-set-default-theme -R falcon2
    sudo sed -i 's/^#Disable Plymouth/#Disable Plymouth\nplymouth.enable=1/' /boot/cmdline.txt
    echo "Boot splash screen configured!"
else
    echo "Warning: Splash image not found! Please add falcon2_splash.png to /home/raes"
fi

# Final fix: Ensure kernel uses the correct cmdline.txt
echo "Ensuring correct boot parameters..."
sudo sed -i 's/rootwait/& quiet splash plymouth.enable=1/' /boot/cmdline.txt

# Apply changes and reboot
echo "Setup complete! Rebuilding initramfs and rebooting..."
sudo update-initramfs -u
sync
sudo reboot
