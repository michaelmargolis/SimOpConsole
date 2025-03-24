""" kinematics_V2SP
This module provides inverse kinematics for the Mdx motion platforms.
The core method, named inverse_kinematics, is passed the desired orientation as: [surge, sway, heave, roll, pitch, yaw]
and returns the platform pose as an array of coordinates for the attachment points.
Pose is converted to actuator lengths using the method: muscle_lengths_from_pose.

This version is for the suspended platform only
NOTE: All length values returned now represent actual **muscle lengths** instead of contraction amounts.
"""

import math
import copy
import numpy as np
import logging

log = logging.getLogger(__name__)

class Kinematics(object):
    def __init__(self):
        """ Initialize kinematics class and set NumPy print options. """
        np.set_printoptions(precision=3, suppress=True)

    def clamp(self, n, minn, maxn):
        """ Clamp a value `n` within the given min and max bounds. """
        return max(min(maxn, n), minn)

    def set_geometry(self, base_coords, platform_coords):
        """ Set the platform and base attachment point coordinates. """
        self.base_coords = base_coords
        self.platform_coords = platform_coords       
        self.intensity = 1.0

    def set_platform_params(self, min_muscle_len, max_muscle_len, fixed_len):
        """ Define muscle length limits and fixed frame length for the Stewart platform. """
        self.MIN_MUSCLE_LENGTH = min_muscle_len
        self.MAX_MUSCLE_LENGTH = max_muscle_len
        self.FIXED_HARDWARE_LENGTH = fixed_len
        self.MUSCLE_LENGTH_RANGE = max_muscle_len - min_muscle_len
        log.info("Kinematics set for Stewart platform")

    def calc_rotation(self, rpy):
        """ Compute and return the 3x3 rotation matrix from roll, pitch, yaw angles. """
        roll, pitch, yaw = rpy  # roll: right side down, pitch: nose down, yaw: CCW
        
        cos_roll, sin_roll = math.cos(roll), math.sin(roll)
        cos_pitch, sin_pitch = math.cos(pitch), math.sin(pitch)
        cos_yaw, sin_yaw = math.cos(yaw), math.sin(yaw)

        # Calculate rotation matrix
        Rxyz = np.array([
            [cos_yaw * cos_pitch, cos_yaw * sin_pitch * sin_roll - sin_yaw * cos_roll, cos_yaw * sin_pitch * cos_roll + sin_yaw * sin_roll],
            [sin_yaw * cos_pitch, sin_yaw * sin_pitch * sin_roll + cos_yaw * cos_roll, sin_yaw * sin_pitch * cos_roll - cos_yaw * sin_roll],
            [-sin_pitch, cos_pitch * sin_roll, cos_pitch * cos_roll]
        ])
        return Rxyz

    def inverse_kinematics(self, request):
        """ Compute and return platform attachment points for the given pose. """
        xyzrpy = np.asarray(copy.deepcopy(request)) * self.intensity
        a = np.array(xyzrpy).transpose()
        platform_xlate = a[:3] + self.platform_coords  # surge, sway, heave

        rpy = a[3:6]  # roll, pitch, yaw
        Rxyz = self.calc_rotation(rpy)

        self.pose = np.zeros(self.platform_coords.shape)
        for i in range(6):
            self.pose[i, :] = np.dot(Rxyz, platform_xlate[i, :])
        return self.pose  # 6 rows of 3D platform attachment points

    def muscle_lengths(self, xyzrpy):
        """ Compute and return the muscle lengths for a given pose. """
        pose = self.inverse_kinematics(xyzrpy)
        return self.muscle_lengths_from_pose(pose)

    def muscle_lengths_from_pose(self, pose):
        """ Compute and return the required muscle lengths for a given pose. """
        actuator_lengths = np.linalg.norm(self.pose - self.base_coords, axis=1)
        # Adjust lengths and clamp them within the allowed range
        muscle_lengths = [
            self.clamp(int(round(length - self.FIXED_HARDWARE_LENGTH)), self.MIN_MUSCLE_LENGTH, self.MAX_MUSCLE_LENGTH)
            for length in actuator_lengths
        ]    
        return muscle_lengths
        
    def muscle_percents(self, xyzrpy, offset=0):
        """ Compute muscle lengths as a percentage of their range, with an optional offset. """
        pose = self.inverse_kinematics(xyzrpy)
        lengths = self.muscle_lengths_from_pose(pose)
        return self.percent_from_muscle_length(lengths, offset)
        
    def percent_from_muscle_length(self, lengths, offset=0):
        """ Convert muscle lengths to percentages of their operational range, subtracting `offset`. """
        return [round(((l - offset) * 100.0) / self.MUSCLE_LENGTH_RANGE, 1) for l in lengths]

    def get_pose(self):
        """ Return the last computed platform pose. """
        return self.pose    

    def set_intensity(self, intensity):
        """ Set scaling factor for motion intensity. """
        self.intensity = intensity
        log.info("Kinematics intensity set to %.1f", intensity)
