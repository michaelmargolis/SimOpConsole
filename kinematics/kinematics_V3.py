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
from collections import namedtuple
import logging

log = logging.getLogger(__name__)


PlatformParams = namedtuple("PlatformParams", [
    "MUSCLE_MIN_LENGTH",
    "MUSCLE_MAX_LENGTH",
    "FIXED_HARDWARE_LENGTH",
    "LIMITS_1DOF_TRANSFORM"
])

class Kinematics(object):
    def __init__(self):
        np.set_printoptions(precision=3, suppress=True)
        self.intensity = 1.0
        self.set_axis_flip_mask([1,1,-1,-1,1,1]) # defualt, the sim will set the mask it needs


    def clamp(self, n, minn, maxn):
        return max(min(maxn, n), minn)


    def set_geometry(self, base_coords, platform_coords, platform_params, clearance_offset=50):
        """
        Sets base and platform geometry, handles half-side definitions and calculates mid-height.
        
        Arguments:
        - base_coords: list of 3 or 6 [x, y, z] points
        - platform_coords: list of 3 or 6 [x, y] or [x, y, z] points
        - platform_params: namedtuple/class with:
            MUSCLE_MIN_LENGTH, MUSCLE_MAX_LENGTH, FIXED_HARDWARE_LENGTH, LIMITS_1DOF_TRANSFORM
        - clearance_offset: starting Z for platform (default: 50 mm)
        """
        # ───── Unpack platform parameters ─────
        self.MIN_MUSCLE_LENGTH = platform_params.MUSCLE_MIN_LENGTH
        self.MAX_MUSCLE_LENGTH = platform_params.MUSCLE_MAX_LENGTH
        self.FIXED_HARDWARE_LENGTH = platform_params.FIXED_HARDWARE_LENGTH
        self.MUSCLE_LENGTH_RANGE = self.MAX_MUSCLE_LENGTH - self.MIN_MUSCLE_LENGTH
        self.MIN_ACTUATOR_LENGTH = self.MIN_MUSCLE_LENGTH + self.FIXED_HARDWARE_LENGTH
        self.MAX_ACTUATOR_LENGTH = self.MAX_MUSCLE_LENGTH + self.FIXED_HARDWARE_LENGTH
        self.limits_1dof = platform_params.LIMITS_1DOF_TRANSFORM

        def mirror(coords):
            return coords + [[x, -y, z] for x, y, z in reversed(coords)]

        # ───── Prepare base_coords ─────
        if len(base_coords) == 3:
            self.base_coords = np.array(mirror(base_coords))
        else:
            self.base_coords = np.array(base_coords)

        # Infer UPPER_ACTUATOR_Z_HEIGHT from average Z of base coords
        self.UPPER_ACTUATOR_Z_HEIGHT = np.mean(self.base_coords[:, 2])

        # ───── Expand platform XY to XYZ, then mirror if needed ─────
        if len(platform_coords[0]) == 2:
            platform_coords = [[x, y, clearance_offset] for x, y in platform_coords]
        if len(platform_coords) == 3:
            platform_coords = mirror(platform_coords)
        platform_coords = np.array(platform_coords)

        # ───── Search for PLATFORM_MID_HEIGHT ─────
        low_z = clearance_offset
        high_z = self.UPPER_ACTUATOR_Z_HEIGHT - self.FIXED_HARDWARE_LENGTH - self.MIN_MUSCLE_LENGTH
        target_avg = (self.MIN_ACTUATOR_LENGTH + self.MAX_ACTUATOR_LENGTH) / 2

        best_z = None
        best_error = float('inf')

        for z in np.linspace(low_z, high_z, 200):
            candidate_coords = np.array([[x, y, z] for x, y, _ in platform_coords])
            lengths = np.linalg.norm(candidate_coords - self.base_coords, axis=1)
            if any(l < self.MIN_ACTUATOR_LENGTH or l > self.MAX_ACTUATOR_LENGTH for l in lengths):
                continue
            avg = np.mean(lengths)
            error = abs(avg - target_avg)
            if error < best_error:
                best_error = error
                best_z = z

        if best_z is None:
            raise ValueError("Unable to determine valid PLATFORM_MID_HEIGHT.")

        # ───── Finalize geometry ─────
        self.platform_coords = np.array([[x, y, best_z] for x, y, _ in platform_coords])
        self.PLATFORM_MID_HEIGHT = best_z
        log.info(f"Platform mid height:  {round(self.PLATFORM_MID_HEIGHT)}")
        actuator_lengths = np.linalg.norm(self.platform_coords - self.base_coords, axis=1)
        self.PLATFORM_NEUTRAL_MUSCLE_LENGTHS = actuator_lengths - self.FIXED_HARDWARE_LENGTH
        self.cached_muscle_lengths = self.PLATFORM_NEUTRAL_MUSCLE_LENGTHS.copy()


    def set_axis_flip_mask(self, axis_flip_mask):
        assert len(axis_flip_mask) == 6, "Axis flip mask must be 6 elements"
        self.AXIS_FLIP_MASK = np.asarray(axis_flip_mask, dtype=float)
        self.FLIP_TRANSLATION = self.AXIS_FLIP_MASK[:3]
        self.FLIP_ROTATION = self.AXIS_FLIP_MASK[3:]

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

        a = np.asarray(request, dtype=float)

        translation = a[:3] * self.FLIP_TRANSLATION
        rpy = a[3:6] * self.FLIP_ROTATION

        Rxyz = self.calc_rotation(rpy)

        pose = (Rxyz @ self.platform_coords.T).T + translation
        self.cached_pose = pose
        # print("lengths = ", np.linalg.norm(pose - self.base_coords, axis=1)  )      
        
        if return_lengths:
            actuator_lengths = np.linalg.norm(pose - self.base_coords, axis=1)
            return pose, actuator_lengths
        return pose

    def muscle_lengths(self, xyzrpy):
        _, actuator_lengths = self.inverse_kinematics(xyzrpy, return_lengths=True)
        self.cached_muscle_lengths = tuple(self.muscle_lengths_from_lengths(actuator_lengths)) # cache the calculated muscle lengths
        return self.muscle_lengths_from_lengths(actuator_lengths)

    def muscle_lengths_from_lengths(self, actuator_lengths):
        # return np.clip(actuator_lengths - self.FIXED_HARDWARE_LENGTH, 0, self.MAX_MUSCLE_LENGTH)
        return [
            min(int(round(length - self.FIXED_HARDWARE_LENGTH)), self.MAX_MUSCLE_LENGTH)
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

    def get_cached_pose(self):
        return self.cached_pose

    def get_cached_muscle_lengths(self):
        return self.cached_muscle_lengths
        
    def set_intensity(self, intensity):
        self.intensity = intensity
        log.info("Kinematics intensity set to %.1f", intensity)

    def norm_to_real(self, transform):
        xform = np.asarray(transform, dtype=float)
        np.clip(xform, -1, 1, xform)  # clip normalized values
        #  convert from normalized to real world values
        real_transform = np.multiply(xform, self.limits_1dof) 
        return real_transform        
        

if __name__ == "__main__":
    from collections import namedtuple
    from cfg_SuspendedPlatform import PlatformConfig

    # NamedTuple for platform params
    PlatformParams = namedtuple("PlatformParams", [
        "MUSCLE_MIN_LENGTH",
        "MUSCLE_MAX_LENGTH",
        "FIXED_HARDWARE_LENGTH",
        "LIMITS_1DOF_TRANSFORM"
    ])

    cfg = PlatformConfig()
    params = PlatformParams(
        cfg.MUSCLE_MIN_LENGTH,
        cfg.MUSCLE_MAX_LENGTH,
        cfg.FIXED_HARDWARE_LENGTH,
        cfg.LIMITS_1DOF_TRANFORM
    )

    print("=== Platform Muscle Configuration ===")
    print(f"MUSCLE_MAX_LENGTH         = {cfg.MUSCLE_MAX_LENGTH}")
    print(f"MUSCLE_MIN_LENGTH         = {cfg.MUSCLE_MIN_LENGTH}")
    print(f"MUSCLE_MAX_ACTIVE_LENGTH  = {cfg.MUSCLE_MAX_ACTIVE_LENGTH}")
    print(f"MUSCLE_MIN_ACTIVE_LENGTH  = {cfg.MUSCLE_MIN_ACTIVE_LENGTH}")
    print(f"FIXED_HARDWARE_LENGTH     = {cfg.FIXED_HARDWARE_LENGTH}")
    print(f"MIN_ACTUATOR_LENGTH       = {cfg.MIN_ACTUATOR_LENGTH}")
    print(f"MAX_ACTUATOR_LENGTH       = {cfg.MAX_ACTUATOR_LENGTH}")

    k = Kinematics()

    # Apply geometry and mid-height calculation
    k.set_geometry(cfg.base_coords, cfg.platform_coords_xy, params, cfg.PLATFORM_CLEARANCE_OFFSET)

    # Output diagnostics
    print(f"PLATFORM_MID_HEIGHT = {k.PLATFORM_MID_HEIGHT:.2f}")
    print(f"NEUTRAL_MUSCLE_LENGTHS = {[int(l) for l in k.get_cached_muscle_lengths()]}")
    print(f"NEUTRAL_MUSCLE_LENGTHS = {k.PLATFORM_NEUTRAL_MUSCLE_LENGTHS}\n")

    # Axis flip and motion intensity setup
    axis_flip_mask = [1, 1, 1, 1, 1, -1]
    k.set_axis_flip_mask(axis_flip_mask)
    
    ##swap_roll_pitch = cfg.SWAP_ROLL_PITCH

    """
    # Heave-only test
    for z_norm in [-1.0, 0.0, 1.0]:
        transform = [0, 0, z_norm, 0, 0, 0]
        real_transform = k.norm_to_real(transform)
        muscle_lengths = k.muscle_lengths(real_transform)
        print(f"heave = {z_norm:+.1f} → lengths = {[int(l) for l in muscle_lengths]}")
        
    """
    dof_labels = ["surge", "sway", "heave", "roll", "pitch", "yaw"]
    test_values = [-1.0, 0.0, 1.0] 
   
    def test_all_dofs():
        for i in range(6):
            print(f"--- {dof_labels[i]} ---")
            for val in test_values:
                transform = [0.0] * 6
                transform[i] = val
                real_transform = k.norm_to_real(transform)
                muscle_lengths = k.muscle_lengths(real_transform)
                print(f"{dof_labels[i]} = {val:+.1f} → lengths = {[int(l) for l in muscle_lengths]}")
            print()

    # Run test
    test_all_dofs() 
   