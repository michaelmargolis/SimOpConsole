"""
 config file for sim interface
 
 For Falcon2 the X-Plane 11 IP address must be set the computer running X-Plane
 
 Other values are pre configured and should be left as is  

"""
from typing import List, Tuple

XPLANE_11_IP_ADDRESS =  '127.0.0.1' # '192.168.1.241' # <== set this ip address

# Core config values
AVAILABLE_SIMS: List[Tuple[str, str, str, str]] = [
    ("X-Plane 11", "xplane", "xplane11.jpg", XPLANE_11_IP_ADDRESS),  
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
 
FESTO_IP = "192.168.0.10"

def get_switch_comport(os_name: str) -> str:
    """Returns the correct COM port based on the operating system."""
    if os_name == 'nt':
        return "COM11"
    else:
        return "/dev/ttyUSB1"
