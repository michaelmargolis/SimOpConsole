"""
Created 5 Sep 2018
@author: mem
configuration for V3 chair
updated April 12 2020 to include z axis  and calculations for both sides 
"""

"""
This file defines the coordinates of the upper (base) and lower (platform) attachment points
Note: because the chair is an inverted stewart platform, the base is the plane defined by the upper attachment points

The coordinate frame used follows ROS conventions, positive values: X is forward, Y is left, Z is up,
roll is right side down, pitch is nose down, yaw is CCW; all from perspective of person on the chair.

The origin is the center of the circle intersecting the attachment points. The X axis is the line through the origin running
 from back to front (X values increase moving forward). The Y axis passes through the origin with values increasing
 to the left.
                   +y 
                 -------- 
                []::::::
                []:::::::                
      -x        []::::::::   +X  (front)
                []::::::: 
                {}::::::
                 --------
                   -y
                 
The attachment coordinates can be specified explicitly or with vectors from the origin to
 each attachment point. Uncomment the desired method of entry.
 
Actuator length parameters are muscle lengths in mm, distance parms are muscle contraction in mm

You only need enter values for the left side, the other side is a mirror image and is calculated ny this software
"""

import math
import copy
import numpy as np

class PlatformConfig(object):
    PLATFORM_NAME = "Falcon chair"
    PLATFORM_TYPE = "Inverted Stewart Platform"
    PLATFORM_INVERTED = True
    MUSCLE_PRESSURE_MAPPING_FILE = 'output/chair_DtoP.csv'  # Updated name

    ACTIVE_CLEARANCE_OFFSET = 50  #  min clearance in mm between platform and base when active

    def __init__(self):
        self.UNLOADED_PLATFORM_WEIGHT = 25  # weight of moving platform without 'payload' in kilograms
        DEFAULT_PAYLOAD_WEIGHT = 65  # weight of 'payload'
        PAYLOAD_WEIGHT_RANGE = (20, 90)  # in Kg

        self.MAX_MUSCLE_LENGTH = 1000  # length of muscle at minimum pressure
        self.MIN_MUSCLE_LENGTH = self.MAX_MUSCLE_LENGTH * 0.75  # length of muscle at maximum pressure
        self.FIXED_HARDWARE_LENGTH = 200  # length of fixing hardware

        self.MIN_ACTUATOR_LENGTH = self.MIN_MUSCLE_LENGTH + self.FIXED_HARDWARE_LENGTH  # total min actuator distance including fixing hardware
        self.MAX_ACTUATOR_LENGTH = self.MAX_MUSCLE_LENGTH + self.FIXED_HARDWARE_LENGTH  # total max actuator distance including fixing hardware
        self.MUSCLE_LENGTH_RANGE = self.MAX_MUSCLE_LENGTH - self.MIN_MUSCLE_LENGTH
        MID_ACTUATOR_LENGTH = self.MIN_ACTUATOR_LENGTH + (self.MUSCLE_LENGTH_RANGE / 2)

        self.MOTION_INTENSITY_RANGE = (10, 50, 150)  # steps, min, max in percent
        self.PAYLOAD_WEIGHT_RANGE = (5, 0, 100)  # steps, min, max in Kg

        self.INVERT_AXIS = (1, 1, -1, -1, 1, 1)  # set -1 to invert: x, y, z, roll, pitch, yaw
        self.SWAP_ROLL_PITCH = False  # set true to swap roll and pitch (also swaps x and y)

        # The max movement in a single DOF
        self.LIMITS_1DOF_TRANFORM = (
            100, 122, 140, math.radians(15), math.radians(20), math.radians(12)
        )
        self.LIMIT_Z_TRANSLATION = self.LIMITS_1DOF_TRANFORM[2]
        print("Note: Platform limits need verification, the file contains theoretical max values")

        # Limits at extremes of movement
        self.LIMITS_6DOF_TRANSLATION_ROTATION = (
            80, 80, 80, math.radians(12), math.radians(12), math.radians(10)
        )

        self.DISABLED_MUSCLE_LENGTHS = [self.MAX_MUSCLE_LENGTH] * 6
        self.PROPPING_MUSCLE_LENGTHS = [self.MAX_MUSCLE_LENGTH * 0.08] * 6  # Length for attaching stairs or moving prop
        self.DISABLED_TRANSFORM = [0, 0, -self.LIMIT_Z_TRANSLATION, 0, 0, 0]  # Only used to echo slow moves
        self.PROPPING_TRANSFORM = [0, 0, -self.LIMIT_Z_TRANSLATION, 0, 0, 0]  # Only used to echo slow moves

        self.HAS_PISTON = False  # True if platform has piston-actuated prop
        self.HAS_BRAKE = False  # True if platform has electronic braking when parked

    def calculate_coords(self):
        """ Compute platform and base attachment coordinates. """

        # Uncomment this to enter hardcoded coordinates

        # Input x and y coordinates with origin as center of the base plate
        # The z value should be zero for both base and platform
        # Only -Y side is needed as other side is symmetrical (see figure)

        GEOMETRY_PERFECT = False  # Set to False for wide front spacing
        GEOMETRY_WIDE = not GEOMETRY_PERFECT

        base_pos = [[379.8, -515.1, 0], [258.7, -585.4, 0], [-636.0, -71.4, 0]]
        self.PLATFORM_MID_HEIGHT = -((self.MIN_ACTUATOR_LENGTH + self.MAX_ACTUATOR_LENGTH) / 2 - self.ACTIVE_CLEARANCE_OFFSET)
        self.PLATFORM_MID_MUSCLE_LENGTHS = [((self.MAX_MUSCLE_LENGTH + self.MIN_MUSCLE_LENGTH) / 2) - self.ACTIVE_CLEARANCE_OFFSET] * 6
 
        if GEOMETRY_PERFECT:
            GEOMETRY_TYPE = "Using geometry values with ideally spaced front attachment points"
            platform_pos = [
                [636.3, -68.6, self.PLATFORM_MID_HEIGHT],  # Left front (facing platform)
                [-256.2, -586.5, self.PLATFORM_MID_HEIGHT],
                [-377.6, -516.7, self.PLATFORM_MID_HEIGHT],
            ]
        elif GEOMETRY_WIDE:
            GEOMETRY_TYPE = "Using geometry values based on 34cm spaced front attachment points"
            platform_pos = [
                [617.0, -170.0, self.PLATFORM_MID_HEIGHT],
                [-256.2, -586.5, self.PLATFORM_MID_HEIGHT],
                [-377.6, -516.7, self.PLATFORM_MID_HEIGHT],
            ]
        else:
            GEOMETRY_TYPE = "Geometry type not defined"

        # Reflect around X-axis to generate right-side coordinates
        otherSide = copy.deepcopy(base_pos[::-1])  # Order reversed
        for inner in otherSide:
            inner[1] = -inner[1]  # Negate Y values
        base_pos.extend(otherSide)
        self.BASE_POS = np.array(base_pos)

        otherSide = copy.deepcopy(platform_pos[::-1])  # Order reversed
        for inner in otherSide:
            inner[1] = -inner[1]  # Negate Y values
        platform_pos.extend(otherSide)
        self.PLATFORM_POS = np.array(platform_pos)
