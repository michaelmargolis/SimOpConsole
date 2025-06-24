import math
import numpy as np

class PlatformConfig(object):
    PLATFORM_NAME = "Falcon chair"
    PLATFORM_TYPE = "Inverted Stewart Platform"
    PLATFORM_INVERTED = True
    MUSCLE_PRESSURE_MAPPING_FILE = "output/wheelchair_DtoP.csv"

    PLATFORM_CLEARANCE_OFFSET = 50  # mm
    PLATFORM_LOWEST_Z = -1085       # Legacy (unused now if mid-height is auto-computed)
    UPPER_ACTUATOR_Z_HEIGHT = 1070  # Z height of base attachment ring

    def __init__(self):
        self.MUSCLE_MAX_LENGTH = 1000
        self.MUSCLE_MIN_LENGTH = self.MUSCLE_MAX_LENGTH * 0.75
        self.FIXED_HARDWARE_LENGTH = 200

        self.MIN_ACTUATOR_LENGTH = self.MUSCLE_MIN_LENGTH + self.FIXED_HARDWARE_LENGTH
        self.MAX_ACTUATOR_LENGTH = self.MUSCLE_MAX_LENGTH + self.FIXED_HARDWARE_LENGTH
        self.MUSCLE_LENGTH_RANGE = self.MUSCLE_MAX_LENGTH - self.MUSCLE_MIN_LENGTH
        self.MUSCLE_MAX_ACTIVE_LENGTH = self.MUSCLE_MAX_LENGTH - self.PLATFORM_CLEARANCE_OFFSET
        self.MUSCLE_MIN_ACTIVE_LENGTH = self.MUSCLE_MIN_LENGTH

        self.DEFAULT_PAYLOAD_WEIGHT = 65
        self.PAYLOAD_WEIGHT_RANGE = (20, 90)
        self.UNLOADED_PLATFORM_WEIGHT = 25
        self.PAYLOAD_WEIGHTS = (50, 60, 150)
        self.MOTION_INTENSITY_RANGE = (10, 50, 150)

        self.LIMITS_1DOF_TRANFORM = (
            90, 90, 100,
            math.radians(12), math.radians(10), math.radians(12)
        )

        self.LIMITS_6DOF_TRANSLATION_ROTATION = (
            80, 80, 80,
            math.radians(10), math.radians(10), math.radians(10)
        )

        self.DEACTIVATED_MUSCLE_LENGTHS = [self.MUSCLE_MAX_LENGTH] * 6
        self.PROPPING_MUSCLE_LENGTHS = [self.MUSCLE_MAX_LENGTH * 0.08] * 6
        self.DEACTIVATED_TRANSFORM = [0, 0, -self.LIMITS_1DOF_TRANFORM[2] - 50, 0, 0, 0]
        self.PROPPING_TRANSFORM = [0, 0, -self.LIMITS_1DOF_TRANFORM[2], 0, 0, 0]

        self.HAS_PISTON = False
        self.HAS_BRAKE = False
        

        # Geometry (left side only)
        self.base_coords = [
            [379.8, -515.1, self.UPPER_ACTUATOR_Z_HEIGHT],
            [258.7, -585.4, self.UPPER_ACTUATOR_Z_HEIGHT],
            [-636.0, -71.4, self.UPPER_ACTUATOR_Z_HEIGHT],
        ]

        self.platform_coords_xy = [
            [617.0, -170.0],
            [-256.2, -586.5],
            [-377.6, -516.7],
        ]


