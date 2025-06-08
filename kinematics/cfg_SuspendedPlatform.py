import math
import copy
import numpy as np
from kinematics.kinematics_V2SP import Kinematics

class PlatformConfig(object):
    PLATFORM_NAME = "Falcon chair"
    PLATFORM_TYPE = "Inverted Stewart Platform"
    PLATFORM_INVERTED = True
    # MUSCLE_PRESSURE_MAPPING_FILE = 'output/chair_DtoP.csv'
    MUSCLE_PRESSURE_MAPPING_FILE = "output/wheelchair_DtoP.csv"

    PLATFORM_CLEARANCE_OFFSET = 50  # Minimum clearance in mm between platform and base when active
    PLATFORM_LOWEST_Z = -1085       # Z offset of platform when muscles are at full extension (max length)


    def __init__(self):
       
        DEFAULT_PAYLOAD_WEIGHT = 65
        PAYLOAD_WEIGHT_RANGE = (20, 90)

        self.MUSCLE_MAX_LENGTH = 1000
        self.MUSCLE_MIN_LENGTH = self.MUSCLE_MAX_LENGTH * 0.75
        self.MUSCLE_MAX_ACTIVE_LENGTH = self.MUSCLE_MAX_LENGTH - self.PLATFORM_CLEARANCE_OFFSET
        self.MUSCLE_MIN_ACTIVE_LENGTH = self.MUSCLE_MIN_LENGTH

        self.FIXED_HARDWARE_LENGTH = 200

        self.MIN_ACTUATOR_LENGTH = self.MUSCLE_MIN_LENGTH + self.FIXED_HARDWARE_LENGTH
        self.MAX_ACTUATOR_LENGTH = self.MUSCLE_MAX_LENGTH + self.FIXED_HARDWARE_LENGTH
        self.MUSCLE_LENGTH_RANGE = self.MUSCLE_MAX_LENGTH - self.MUSCLE_MIN_LENGTH

        self.UNLOADED_PLATFORM_WEIGHT = 25
        self.PAYLOAD_WEIGHTS = (50, 60, 150) # light, medium, heavy
        self.MOTION_INTENSITY_RANGE = (10, 50, 150)


        self.INVERT_AXIS = (1, 1, -1, -1, 1, 1)
        self.SWAP_ROLL_PITCH = False

        self.LIMITS_1DOF_TRANFORM = (
            90, 90, 100, math.radians(12), math.radians(10), math.radians(12)
        )
        self.LIMIT_Z_TRANSLATION = self.LIMITS_1DOF_TRANFORM[2]
        print("Note: Platform limits need verification, the file contains theoretical max values")

        self.LIMITS_6DOF_TRANSLATION_ROTATION = (
            80, 80, 80, math.radians(10), math.radians(10), math.radians(10)
        )

        self.DEACTIVATED_MUSCLE_LENGTHS = [self.MUSCLE_MAX_LENGTH] * 6
        self.PROPPING_MUSCLE_LENGTHS = [self.MUSCLE_MAX_LENGTH * 0.08] * 6
        self.DEACTIVATED_TRANSFORM = [0, 0, -self.LIMIT_Z_TRANSLATION -50, 0, 0, 0]
        self.PROPPING_TRANSFORM = [0, 0, -self.LIMIT_Z_TRANSLATION, 0, 0, 0]

        self.HAS_PISTON = False
        self.HAS_BRAKE = False

    def calculate_coords(self):
        base_pos = [[379.8, -515.1, 0], [258.7, -585.4, 0], [-636.0, -71.4, 0]]
        platform_half = [
            [617.0, -170.0, 0],
            [-256.2, -586.5, 0],
            [-377.6, -516.7, 0],
        ]

        # Mirror base to get full 6-point base
        other_side_base = copy.deepcopy(base_pos[::-1])
        for inner in other_side_base:
            inner[1] = -inner[1]
        base_pos.extend(other_side_base)
        self.BASE_POS = np.array(base_pos)

        # Build temporary platform_pos for geometry setup
        mirrored_half = copy.deepcopy(platform_half[::-1])
        for p in mirrored_half:
            p[1] = -p[1]
        platform_full = platform_half + mirrored_half

        k = Kinematics()
        k.set_geometry(self.BASE_POS, np.array(platform_full))
        k.set_platform_params(self.MIN_ACTUATOR_LENGTH, self.MAX_ACTUATOR_LENGTH, self.FIXED_HARDWARE_LENGTH)

        def average_muscle_length_at_height(z_offset):
            adjusted_half = [[x, y, z_offset] for x, y, _ in platform_half]
            mirrored = copy.deepcopy(adjusted_half[::-1])
            for p in mirrored:
                p[1] = -p[1]
            full = adjusted_half + mirrored
            k.set_geometry(self.BASE_POS, np.array(full))
            return np.mean(k.muscle_lengths([0, 0, z_offset, 0, 0, 0]))

        low_z = -self.MAX_ACTUATOR_LENGTH
        high_z = -self.MIN_ACTUATOR_LENGTH
        target_avg = (self.MUSCLE_MAX_ACTIVE_LENGTH + self.MUSCLE_MIN_ACTIVE_LENGTH) / 2

        best_z = low_z
        best_error = float('inf')
        for z in np.linspace(low_z, high_z, 200):
            avg_len = average_muscle_length_at_height(z)
            error = abs(avg_len - target_avg)
            if error < best_error:
                best_error = error
                best_z = z

        self.PLATFORM_MID_HEIGHT = best_z

        # Now finalize platform coordinates at computed Z
        adjusted_half = [[x, y, best_z] for x, y, _ in platform_half]
        mirrored = copy.deepcopy(adjusted_half[::-1])
        for p in mirrored:
            p[1] = -p[1]
        full = adjusted_half + mirrored
        self.PLATFORM_POS = np.array(full)

        k.set_geometry(self.BASE_POS, self.PLATFORM_POS)
        self.PLATFORM_NEUTRAL_MUSCLE_LENGTHS = k.muscle_lengths([0, 0, 0, 0, 0, 0])
