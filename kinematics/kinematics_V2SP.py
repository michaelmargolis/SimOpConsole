""" kinematics_V2SP
This module provides inverse kinematics for the Mdx motion platforms.
The core method, named inverse_kinematics, is passed the desired orientation as: [surge, sway, heave, roll, pitch, yaw]
and returns the platform pose as an array of coordinates for the attachment points.
Pose is converted to actuator lengths using the method: muscle_lengths_from_pose.

This version is for the suspended platform only
NOTE: All length values returned now represent actual **muscle lengths** instead of contraction amounts.
"""

import math
import numpy as np
import logging

log = logging.getLogger(__name__)

class Kinematics(object):
    def __init__(self):
        np.set_printoptions(precision=3, suppress=True)
        self.intensity = 1.0

    def clamp(self, n, minn, maxn):
        return max(min(maxn, n), minn)

    def set_geometry(self, base_coords, platform_coords):
        self.base_coords = base_coords
        self.platform_coords = platform_coords
        assert self.base_coords.shape == (6, 3), "Base coordinates must be 6x3"
        assert self.platform_coords.shape == (6, 3), "Platform coordinates must be 6x3"

    def set_platform_params(self, min_muscle_len, max_muscle_len, fixed_len):
        self.MIN_MUSCLE_LENGTH = min_muscle_len
        self.MAX_MUSCLE_LENGTH = max_muscle_len
        self.FIXED_HARDWARE_LENGTH = fixed_len
        self.MUSCLE_LENGTH_RANGE = max_muscle_len - min_muscle_len
        log.info("Kinematics set for Stewart platform")

    def calc_rotation(self, rpy):
        roll, pitch, yaw = rpy
        cos_roll, sin_roll = math.cos(roll), math.sin(roll)
        cos_pitch, sin_pitch = math.cos(pitch), math.sin(pitch)
        cos_yaw, sin_yaw = math.cos(yaw), math.sin(yaw)

        return np.array([
            [cos_yaw * cos_pitch,
             cos_yaw * sin_pitch * sin_roll - sin_yaw * cos_roll,
             cos_yaw * sin_pitch * cos_roll + sin_yaw * sin_roll],
            [sin_yaw * cos_pitch,
             sin_yaw * sin_pitch * sin_roll + cos_yaw * cos_roll,
             sin_yaw * sin_pitch * cos_roll - cos_yaw * sin_roll],
            [-sin_pitch,
             cos_pitch * sin_roll,
             cos_pitch * cos_roll]
        ])

    def inverse_kinematics(self, request, return_lengths=False):
        assert len(request) == 6, "Transform must be 6-element sequence"
        a = np.asarray(request, dtype=float) * self.intensity
        translation = a[:3]
        rpy = a[3:6]

        Rxyz = self.calc_rotation(rpy)
        pose = (Rxyz @ self.platform_coords.T).T + translation  # shape (6, 3)
        self.pose = pose

        if return_lengths:
            actuator_lengths = np.linalg.norm(pose - self.base_coords, axis=1)
            return pose, actuator_lengths
        return pose

    def muscle_lengths(self, xyzrpy):
        _, actuator_lengths = self.inverse_kinematics(xyzrpy, return_lengths=True)
        return self.muscle_lengths_from_lengths(actuator_lengths)

    def muscle_lengths_from_lengths(self, actuator_lengths):
        # return np.clip(actuator_lengths - self.FIXED_HARDWARE_LENGTH, 0, self.MAX_MUSCLE_LENGTH)
        """
        return [
            min(int(round(length - self.FIXED_HARDWARE_LENGTH)), self.MAX_MUSCLE_LENGTH)
            for length in actuator_lengths
        ]
        """     
        return [
            int(round(length - self.FIXED_HARDWARE_LENGTH))
            for length in actuator_lengths
        ]
 

    def muscle_lengths_from_pose(self, pose):
        actuator_lengths = np.linalg.norm(pose - self.base_coords, axis=1)
        return self.muscle_lengths_from_lengths(actuator_lengths)

    def muscle_percents(self, xyzrpy, offset=0):
        pose, actuator_lengths = self.inverse_kinematics(xyzrpy, return_lengths=True)
        lengths = self.muscle_lengths_from_lengths(actuator_lengths)
        return self.percent_from_muscle_length(lengths, offset)

    def percent_from_muscle_length(self, lengths, offset=0):
        return [round(((l - offset) * 100.0) / self.MUSCLE_LENGTH_RANGE, 1) for l in lengths]

    def get_pose(self):
        return self.pose

    def set_intensity(self, intensity):
        self.intensity = intensity
        log.info("Kinematics intensity set to %.1f", intensity)


if __name__ == "__main__":
    from cfg_SuspendedPlatform import PlatformConfig

    k = Kinematics()
    cfg = PlatformConfig()
    cfg.calculate_coords()

    # Debug print for key constants
    print("=== Platform Muscle Configuration ===")
    print(f"MUSCLE_MAX_LENGTH         = {cfg.MUSCLE_MAX_LENGTH}")
    print(f"MUSCLE_MIN_LENGTH         = {cfg.MUSCLE_MIN_LENGTH}")
    print(f"MUSCLE_MAX_ACTIVE_LENGTH  = {cfg.MUSCLE_MAX_ACTIVE_LENGTH}")
    print(f"MUSCLE_MIN_ACTIVE_LENGTH  = {cfg.MUSCLE_MIN_ACTIVE_LENGTH}")
    print(f"FIXED_HARDWARE_LENGTH     = {cfg.FIXED_HARDWARE_LENGTH}")
    print(f"MIN_ACTUATOR_LENGTH       = {cfg.MIN_ACTUATOR_LENGTH}")
    print(f"MAX_ACTUATOR_LENGTH       = {cfg.MAX_ACTUATOR_LENGTH}")
    print(f"PLATFORM_MID_HEIGHT       = {cfg.PLATFORM_MID_HEIGHT}")
    # print(f"PLATFORM_MID_MUSCLE_LENGTHS = {cfg.PLATFORM_MID_MUSCLE_LENGTHS}")
    print(f"PLATFORM_NEUTRAL_MUSCLE_LENGTHS = {cfg.PLATFORM_NEUTRAL_MUSCLE_LENGTHS}\n")

    k.set_geometry(cfg.BASE_POS, cfg.PLATFORM_POS)
    k.set_platform_params(
        cfg.MIN_ACTUATOR_LENGTH,
        cfg.MAX_ACTUATOR_LENGTH,
        cfg.FIXED_HARDWARE_LENGTH
    )

    invert_axis = cfg.INVERT_AXIS
    swap_roll_pitch = cfg.SWAP_ROLL_PITCH

    limits_range = cfg.LIMITS_1DOF_TRANFORM
    print("limits range: ", limits_range)

    def move_platform(transform):
        transform = [inv * axis for inv, axis in zip(invert_axis, transform)]
        if swap_roll_pitch:
            transform[0], transform[1], transform[3], transform[4] = (
                transform[1], transform[0], transform[4], transform[3]
            )
        real_transform = np.multiply(transform, limits_range)
        print("real_transform:", real_transform)
        muscle_lengths = k.muscle_lengths(real_transform)
        return muscle_lengths

    def test_all_dofs():
        dof_labels = ["surge", "sway", "heave", "roll", "pitch", "yaw"]
        test_values = [-1.0, 0.0, 1.0]

        for i in range(6):
            print(f"--- {dof_labels[i]} ---")
            for val in test_values:
                transform = [0.0] * 6
                transform[i] = val
                muscle_lengths = move_platform(transform)
                print(f"{dof_labels[i]} = {val}: → lengths: {muscle_lengths}")
            print()

    test_all_dofs()
