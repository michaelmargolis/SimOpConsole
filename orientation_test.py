import time

from kinematics.kinematics_V3 import Kinematics, PlatformParams
from kinematics.cfg_SuspendedPlatform import PlatformConfig
from output.muscle_output import MuscleOutput
from output.d_to_p import DistanceToPressure

# Initialize platform configuration
cfg = PlatformConfig()
FESTO_IP = '192.168.0.10'

# Initialize Distance to Pressure converter
DtoP = DistanceToPressure(cfg.MUSCLE_LENGTH_RANGE + 1, cfg.MUSCLE_MAX_LENGTH)
try:
    if DtoP.load_data(cfg.MUSCLE_PRESSURE_MAPPING_FILE):
        print("Muscle pressure mapping table loaded.")
        DtoP.set_load(50)   
except Exception as e:
    print(e)
            

# Initialize MuscleOutput
muscle_output = MuscleOutput(
    DtoP.muscle_length_to_pressure,
    None,
    FESTO_IP,
    cfg.MUSCLE_MAX_LENGTH,
    cfg.MUSCLE_LENGTH_RANGE
)

# Initialize Kinematics
k = Kinematics()
params = PlatformParams(
        cfg.MUSCLE_MIN_LENGTH,
        cfg.MUSCLE_MAX_LENGTH,
        cfg.FIXED_HARDWARE_LENGTH,
        cfg.LIMITS_1DOF_TRANFORM
    )
            
k.set_geometry(cfg.base_coords, cfg.platform_coords_xy, params, cfg.PLATFORM_CLEARANCE_OFFSET)

# Define axis labels
axis_labels = ['X (Surge)', 'Y (Sway)', 'Z (Heave)', 'Roll', 'Pitch', 'Yaw']

# Test each axis
import time

# Define axis labels
axis_labels = ['X (Surge)', 'Y (Sway)', 'Z (Heave)', 'Roll', 'Pitch', 'Yaw']

expected_directions = [
    'forward',    # X
    'left',       # Y
    'up',         # Z
    'right side down (roll)',   # Roll
    'nose down (pitch)',        # Pitch
    'yaw CCW (left turn)'       # Yaw
]

# Test each axis using half of the allowed transform range
for i in range(6):
    print(f"\n🧪 Testing {axis_labels[i]} axis")
    print(f"   Expected movement: {expected_directions[i]}")

    transform = [0.0] * 6
    transform[i] = cfg.LIMITS_1DOF_TRANFORM[i] / 2  # use half the range for that axis

    print(f"→ Transform: {transform}")
    muscle_lengths = k.muscle_lengths(transform)
    pressures = DtoP.muscle_length_to_pressure(muscle_lengths)

    print(f"   Muscle Lengths: {[int(l) for l in muscle_lengths]}")
    print(f"   Pressures:      {[int(p) for p in pressures]}")

    input("Press Enter to activate platform and test this movement...")

    muscle_output.send_pressures(pressures)
    time.sleep(2)
    input("Press Enter to continue to the next axis test...")

