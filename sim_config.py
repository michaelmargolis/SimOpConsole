# config file for sim interface

from typing import List, Tuple

# Core config values
AVAILABLE_SIMS: List[Tuple[str, str, str, str]] = [
    ("X-Plane 11", "xplane", "xplane11.jpg", "192.168.1.144"),
    ("X-Plane 12", "xplane", "xplane12.jpg", "127.0.0.1"),
    ("MS FS2020", "fs2020", "fs2020.jpg", "127.0.0.1"),
    ("NoLimits2 Coaster", "nolimits2", "nolimits2.jpg", "127.0.0.1")
]

DEFAULT_SIM_INDEX = 0

AVAILABLE_PLATFORMS: List[Tuple[str, str]] = [
    ("kinematics.cfg_SuspendedPlatform", "Wheelchair platform"),
    ("kinematics.cfg_SuspendedChair", "V3 Chair")
]

DEFAULT_PLATFORM_INDEX = 0
 

def get_switch_comport(os_name: str) -> str:
    """Returns the correct COM port based on the operating system."""
    if os_name == 'nt':
        return "COM11"
    else:
        return "/dev/ttyUSB1"

"""
     # sim name,   sim class module, image,          ip address 
selected_sim =  \
    ["X-Plane 11", "xplane", "xplane11.jpg", "127.0.0.1" ]
    # ["X-Plane 12", "xplane", "xplane12.jpg", "127.0.0.1" ]   
    # ["MS FS2020", "fs2020", "fs2020.jpg", "127.0.0.1" ]    
    # ["NoLimits2 Coaster", "nolimits2", "nolimits2.jpg", "127.0.0.1" ]

#naming#platform_config = "kinematics.cfg_SuspendedChair"
platform_config = "kinematics.cfg_SuspendedPlatform"
if os.name == 'nt':
    switches_comport = "COM11" # the port used by the USB switch interface
else:    
    switches_comport = "/dev/ttyUSB1"  # "/dev/serial0" # Pi GPIO serial
"""