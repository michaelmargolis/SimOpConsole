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
    PLATFORM_NAME = "Chair v3"
    PLATFORM_TYPE = "Inverted Stewart Platform"
    PLATFORM_INVERTED = True
    DISTANCE_TO_PRESSURE_TABLE = 'output/chair_DtoP.csv'

    def __init__(self):
        self.PLATFORM_UNLOADED_WEIGHT = 25  # weight of moving platform without 'passenger' in killograms
        DEFAULT_PAYLOAD_WEIGHT = 65    # weight of 'passenger'
        LOAD_RANGE = (20,90) # in Kg

        MAX_MUSCLE_LEN = 800  # length of muscle at minimum pressure
        MIN_MUSCLE_LEN = MAX_MUSCLE_LEN * .75 # length of muscle at maximum pressure
        self.FIXED_LEN = 200  #  length of fixing hardware
        
        self.MIN_ACTUATOR_LEN = MIN_MUSCLE_LEN + self.FIXED_LEN  # total min actuator distance including fixing hardware
        self.MAX_ACTUATOR_LEN = MAX_MUSCLE_LEN + self.FIXED_LEN # total max actuator distance including fixing hardware
        self.MAX_ACTUATOR_RANGE = self.MAX_ACTUATOR_LEN - self.MIN_ACTUATOR_LEN
        MID_ACTUATOR_LEN = self.MIN_ACTUATOR_LEN + (self.MAX_ACTUATOR_RANGE/2)

        self.INTENSITY_RANGE = (10, 50,150) # steps, min, max in percent
        self.LOAD_RANGE = (5, 0,100) # steps, min, max in Kg
        
    
        self.INVERT_AXIS = (1,1,-1,-1,1,1) # set -1 to invert: x, y, z, roll, pitch, yaw
        self.SWAP_ROLL_PITCH = False   # set true to swap roll and pitch (also swaps x and y)

        #  the max movement in a single DOF
        self.limits_1dof = (100, 122, 140, math.radians(15), math.radians(20), math.radians(12))
        self.limit_Z = self.limits_1dof[2] 
        print("Note:  platform limits need verification, the file contans theoretical max values") 
        # limits at extremes of movement
        self.limits_6dof = (80, 80, 80, math.radians(12), math.radians(12), math.radians(10))

        self.DISABLED_DISTANCES = [self.MAX_ACTUATOR_LEN *.05] * 6
        self.PROPPING_DISTANCES = [self.MAX_ACTUATOR_LEN *.08] * 6 # length for attaching stairs or moving prop
        self.DISABLED_XFORM = [0, 0, -self.limit_Z, 0, 0, 0] # only used to echo slow moves
        self.PROPPING_XFORM = [0, 0, -self.limit_Z, 0, 0, 0] # only used to echo slow moves 
        self.HAS_PISTON = True  # True if platform has piston actuated prop
        self.HAS_BRAKE = False # True if platform has electronic braking when parked

    def calculate_coords(self):

        #  uncomment this to enter hard coded coordinates

        #  input x and y coordinates with origin as center of the base plate
        #  the z value should be zero for both base and platform
        #  only -Y side is needed as other side is symmetrical (see figure)

        GEOMETRY_PERFECT = False  # set to false for wide front spacing
        GEOMETRY_WIDE = not GEOMETRY_PERFECT

            
        base_pos = [[379.8, -515.1, 0],[258.7, -585.4, 0],[-636.0, -71.4, 0]]
        self.PLATFORM_MID_HEIGHT = -715
        
        if GEOMETRY_PERFECT:
            GEOMETRY_TYPE = "Using geometry values with ideally spaced front attachment points"
            platform_pos = [[636.3, -68.6, self.PLATFORM_MID_HEIGHT], # left front (facing platform)
                            [-256.2, -586.5, self.PLATFORM_MID_HEIGHT],
                            [-377.6, -516.7, self.PLATFORM_MID_HEIGHT]]
        elif GEOMETRY_WIDE:
            GEOMETRY_TYPE = "Using geometry values based on 34cm spaced front attachment points"
            platform_pos = [[617.0, -170.0, self.PLATFORM_MID_HEIGHT],
                            [-256.2, -586.5, self.PLATFORM_MID_HEIGHT],
                            [-377.6, -516.7, self.PLATFORM_MID_HEIGHT]]
        else:
            GEOMETRY_TYPE = "Geometry type not defined"
            
        # reflect around X axis to generate right side coordinates
        otherSide = copy.deepcopy(base_pos[::-1])  # order reversed
        for inner in otherSide:
            inner[1] = -inner[1]   # negate Y values
        base_pos.extend(otherSide)
        self.BASE_POS = np.array(base_pos)

        otherSide = copy.deepcopy(platform_pos[::-1])  # order reversed
        for inner in otherSide:
            inner[1] = -inner[1]   # negate Y values
        platform_pos.extend(otherSide)
        self.PLATFORM_POS = np.array(platform_pos)

if __name__ == "__main__":
    import plot_config 
    cfg = PlatformConfig()
    cfg.calculate_coords()
    plot_config.plot(cfg.BASE_POS, cfg.PLATFORM_POS, cfg.PLATFORM_MID_HEIGHT, cfg.PLATFORM_NAME )
    plot_config.plot3d(cfg, cfg.PLATFORM_POS)

