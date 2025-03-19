#!/bin/bash
cd /home/raes/OpsConsole || exit
export DISPLAY=:0
export QT_QPA_PLATFORM=xcb
xinit /usr/bin/python3 /home/raes/OpsConsole/siminterface_core.py -- :0 vt1 || bash
