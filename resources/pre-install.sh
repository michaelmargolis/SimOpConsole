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
# 2. Check for Git and install if necessary.
# -------------------------------------------------
if ! command -v git >/dev/null 2>&1; then
  echo "Git not found. Installing Git..."
  apt update && apt install -y git
fi

# -------------------------------------------------
# 3. Create OpsConsole directory and clone/update repository
# -------------------------------------------------
OPS_DIR="$HOME_DIR/OpsConsole"
echo "Ensuring OpsConsole directory exists at $OPS_DIR..."
mkdir -p "$OPS_DIR"

# Check if the OpsConsole directory is empty.
if [ -z "$(ls -A "$OPS_DIR")" ]; then
  echo "$OPS_DIR is empty. Cloning repository from https://github.com/michaelmargolis/SimOpConsole.git into $OPS_DIR..."
  git clone https://github.com/michaelmargolis/SimOpConsole.git "$OPS_DIR"
else
  # Directory is not empty. Check if it is a Git repository.
  if [ -d "$OPS_DIR/.git" ]; then
    echo "OpsConsole directory already contains a Git repository; updating repository..."
    cd "$OPS_DIR"
    git pull
  else
    echo "Error: $OPS_DIR already exists and is not empty, and does not appear to be a Git repository."
    echo "Please remove or backup this directory and run the script again."
    exit 1
  fi
fi

# -------------------------------------------------
# 4. Run the full setup script from the repository's resources.
# -------------------------------------------------
SETUP_SCRIPT="$OPS_DIR/resources/setup-console.sh"
if [ -f "$SETUP_SCRIPT" ]; then
    echo "Found setup script at $SETUP_SCRIPT. Making it executable and running it..."
    chmod +x "$SETUP_SCRIPT"
    bash "$SETUP_SCRIPT"
else
    echo "Error: Setup script not found at $SETUP_SCRIPT."
    exit 1
fi

echo "Pre-install script complete."
