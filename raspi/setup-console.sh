#!/bin/bash

echo "?? Starting Raspberry Pi PyQt Console Setup..."
echo "?? Updating package list..."
sudo apt update && sudo apt upgrade -y

# ? Add user "raes" to necessary groups
echo "?? Adding 'raes' to required groups..."
sudo usermod -aG sudo,video,input,render,tty raes

# ? Install minimal GUI environment
echo "??? Installing Xorg, Openbox, and LightDM..."
sudo apt install --no-install-recommends xserver-xorg xserver-xorg-legacy xinit openbox lightdm x11-xserver-utils -y

# ? Ensure Xorg Allows Non-Root Users
echo "??? Configuring Xorg permissions..."
sudo bash -c 'echo -e "allowed_users=anybody\nneeds_root_rights=no" > /etc/X11/Xwrapper.config'

# ? Install Python, PyQt, and Required Libraries
echo "?? Installing Python 3, PyQt5, NumPy, and PySerial..."
sudo apt install python3 python3-pyqt5 python3-serial python3-numpy -y

# ? Install Qt Dependencies for "xcb" Support
echo "??? Installing Qt platform plugins..."
sudo apt install --reinstall qt5-default qtwayland5 libxcb-xinerama0 libxkbcommon-x11-0 libxcb-util1 -y

# ? Install Geany Text Editor
echo "?? Installing Geany..."
sudo apt install geany -y

# ? Enable DSI Display Support in /boot/firmware/config.txt
echo "??? Enabling DSI Display Support..."
CONFIG_FILE="/boot/firmware/config.txt"

if ! grep -q "dtoverlay=vc4-kms-dsi-waveshare-panel,10_1_inch" "$CONFIG_FILE"; then
    echo "dtoverlay=vc4-kms-dsi-waveshare-panel,10_1_inch" | sudo tee -a "$CONFIG_FILE"
    echo "? DSI overlay added."
else
    echo "? DSI overlay already present."
fi

# ? Enable GPIO Shutdown in /boot/firmware/config.txt
echo "?? Enabling GPIO Shutdown..."
if ! grep -q "dtoverlay=gpio-shutdown" "$CONFIG_FILE"; then
    echo "dtoverlay=gpio-shutdown" | sudo tee -a "$CONFIG_FILE"
    echo "? GPIO Shutdown enabled."
else
    echo "? GPIO Shutdown already present."
fi

# ? Ensure the PyQt application directory exists
echo "?? Checking application directory..."
mkdir -p /home/raes/OpsConsole

# ? Create an Auto-Start Script for the PyQt App
echo "?? Creating startup script..."
cat <<EOF > /home/raes/start_console.sh
#!/bin/bash
cd /home/raes/OpsConsole || exit
export DISPLAY=:0
export QT_QPA_PLATFORM=xcb
exec startx /usr/bin/python3 /home/raes/OpsConsole/siminterface_core.py -- :0 vt1
EOF
chmod +x /home/raes/start_console.sh
chown raes:raes /home/raes/start_console.sh

# ? Ensure .Xauthority file exists
echo "??? Creating .Xauthority file for Xorg..."
touch /home/raes/.Xauthority
sudo chown raes:raes /home/raes/.Xauthority

# ? Set Auto-Run in .bashrc
echo "?? Configuring auto-run on boot..."
if ! grep -q "/home/raes/start_console.sh" "/home/raes/.bashrc"; then
    echo 'if [[ -z $DISPLAY ]] && [[ $(tty) == /dev/tty1 ]]; then' >> /home/raes/.bashrc
    echo '    exec /home/raes/start_console.sh' >> /home/raes/.bashrc
    echo 'fi' >> /home/raes/.bashrc
fi

# ? Optimize Boot Time
echo "?? Optimizing boot time..."
sudo systemctl mask networking.service
sudo systemctl mask dphys-swapfile.service
sudo systemctl mask systemd-timesyncd.service

# ? Enable Auto-Login
echo "?? Enabling auto-login..."
sudo raspi-config nonint do_boot_behaviour B2

# ? Set Boot Splash Screen
echo "??? Configuring splash screen..."
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
    sudo sed -i 's/^#Disable Plymouth/#Disable Plymouth\nplymouth.enable=1/' /boot/firmware/cmdline.txt
    echo "? Boot splash screen configured!"
else
    echo "?? Warning: Splash image not found! Please add falcon2_splash.png to /home/raes"
fi

# ? Final Fix: Ensure Kernel Uses the Correct `cmdline.txt`
echo "?? Ensuring correct boot parameters..."
sudo sed -i 's/rootwait/& quiet splash plymouth.enable=1/' /boot/firmware/cmdline.txt

# ? Apply Changes and Reboot
echo "? Setup complete! Rebuilding initramfs and rebooting..."
sudo update-initramfs -u
sync
sudo reboot
