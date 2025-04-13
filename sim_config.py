# config file for sim interface
import os

     # sim name,   sim class module, image,          ip address 
selected_sim =  \
    ["X-Plane 11", "xplaneV2", "xplane11.jpg", "127.0.0.1" ]
    # ["X-Plane 12", "xplane", "xplane12.jpg", "127.0.0.1" ]   
    # ["MS FS2020", "fs2020", "fs2020.jpg", "127.0.0.1" ]    
    # ["NoLimits2 Coaster", "nolimits2", "nolimits2.jpg", "127.0.0.1" ]

#naming#platform_config = "kinematics.cfg_SuspendedChair"
platform_config = "kinematics.cfg_SuspendedPlatform"
if os.name == 'nt':
    switches_comport = "COM11" # the port used by the USB switch interface
else:    
    switches_comport = "/dev/ttyUSB1"  # "/dev/serial0" # Pi GPIO serial