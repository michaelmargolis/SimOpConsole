"""
D_to_P.py  Distance to Pressure runtime routines

The module comprises runtime routines to convert platform kinematic distances to festo pressures.
Previously obtained distance to pressure lookup tables for various loads are interrogated at runtime to determine
 the closest match to the current load.


The D_to_P  class is instantiated with an argument specifying the number of distance values (200 for old chairs, 250 for new platform)

    load_DtoP(fname) loads distance to pressure lookup tables
       returns True if valid data has been loaded 
       If successful, the lookup tables are available as class attributes named d_to_p_up  and d_to_p_down.
       It is expected that each up and down table will have six to ten rows containing data for the range of working loads 
       the set_index method described below is used to determine the curve that best fits the current platform load

"""
import os
import traceback
import numpy as np
import logging

log = logging.getLogger(__name__)

MAX_PRESSURE = 6000

class D_to_P(object):
    def __init__(self, max_contraction, max_length):
        self.nbr_columns = max_contraction + 1
        self.d_to_p_up = None  # up-going distance to pressure curves - muscles contract
        self.d_to_p_down = None
        self.up_curve_idx = [0] * 6  # index of the up-going curve closest to the current load
        self.down_curve_idx = [0] * 6
        self.curve_set_direction = 1  # 1 uses up moving curves, -1 down curves
        self.rows = 0  # number of load values in the DtoP file
        self.prev_distances = [0] * 6
        self.max_muscle_length = max_length
        self.max_muscle_contraction = max_contraction
    
    def load(self, fname=os.path.join("output", "DtoP.csv")):
        log.info("Using distance to Pressure file: %s" , fname)
        print("TODO impliment d to p file for new muscles")
        return True
        try:
            d_to_p = np.loadtxt(fname, delimiter=',', dtype=int)
            if d_to_p.shape[1] != self.nbr_columns:
                raise ValueError(f"Expected {self.nbr_columns} distance values, but found {d_to_p.shape[1]}")
            self.d_to_p_up, self.d_to_p_down = np.split(d_to_p, 2)
            if self.d_to_p_up.shape[0] != self.d_to_p_down.shape[0]:
                raise ValueError("Up and down DtoP rows don't match")
            self.rows = self.d_to_p_up.shape[0]
            return True
        except Exception as e:
            log.error("Error loading file: %s\n%s", e, traceback.format_exc())
            raise
    
    def set_index(self, pressure, distances, dir):
        if self.d_to_p_up is None or self.d_to_p_down is None:
            raise ValueError("Distance-to-pressure tables are not loaded")
        
        if dir == "up":
            distances_in_curves = np.abs(self.d_to_p_up - pressure).argmin(axis=1)
            self.up_curve_idx = [np.abs(distances_in_curves - distances[i]).argmin(axis=0) for i in range(6)]
        elif dir == "down":
            distances_in_curves = np.abs(self.d_to_p_down - pressure).argmin(axis=1)
            self.down_curve_idx = [np.abs(distances_in_curves - distances[i]).argmin(axis=0) for i in range(6)]
        else:
            print("Invalid direction in set_index")
  
    def muscle_length_to_pressure(self, muscle_lengths):
        """
        this code is for testing only.
        it uses the polynomial 35x^2 + 15x + 0.03 to calulate the approx pressure for a given muscle length
        the value is clamped to an integer value between 0 and MAX_PRESSURE (6000 millibars) 
        replace this with Omars code.
        """
        pressures = [
            max(0, min(int(35 * percent**2 + 15 * percent + 0.03), MAX_PRESSURE))
            for percent in [(self.max_muscle_length - length) / (self.max_muscle_length * (1 - self.max_muscle_contraction / 100)) *
            100 for length in muscle_lengths]
        ]
        return pressures
          
    # code used for slider platform
    def _distance_to_pressure(self, distances):

        distance_threshold = 5  # distances must be greater than this to trigger a direction change
        pressures = [0]*6
        for i in range(6):
            delta = distances[i] - self.prev_distances[i]
            if abs(delta) > distance_threshold:
                if np.sign(delta) != np.sign(self.curve_set_direction):
                    if delta > 0:
                        self.curve_set_direction = 1
                        index = self.up_curve_idx[i]
                    else:
                        self.curve_set_direction = -1
                        index = self.down_curve_idx[i]
            
            curve_set = self.d_to_p_up if self.curve_set_direction == 1 else self.d_to_p_down
            index = self.up_curve_idx[i] if self.curve_set_direction == 1 else self.down_curve_idx[i]
            
            
            try:
                p = self.interpolate(index, distances[i], curve_set)
                pressures[i] = p
            except Exception as e:
                log.error("Error in distance_to_pressure: %s\n%s", e, traceback.format_exc())
                print("-> Has 'output/DtoP.csv' been loaded?")
        
        self.prev_distances = distances
        return pressures
    
    def interpolate(self, index, distance, curves):
        """
        Interpolates the pressure for a given distance using the lookup table.
        Handles both integer and fractional index values for interpolation between curves.
        """
        if index < self.rows:
            distance = int(distance)
            if distance > 200:
                distance = 200
            if distance >= curves.shape[1]:
                distance = curves.shape[1] - 1
            if index >= curves.shape[0]:
                index = curves.shape[0] - 1
            
            if index == int(index) or index >= self.rows - 1:
                try:
                    return curves[int(index)][distance]
                except Exception as e:
                    log.error("Interpolation error: %s", e)
                    print(index, distance, len(curves[index]))
            else:
                # Linear interpolation between adjacent curves
                frac = index - int(index)
                delta = curves[int(index + 1)][distance] - curves[int(index)][distance]
                return curves[int(index)][distance] + delta * frac
        else:
            log.error("Distance to pressure index value out of range")

if __name__ == "__main__":
    d_to_p = D_to_P(200)
    curves = np.array([[1, 2, 3, 4, 5], [6, 7, 8, 9, 10], [11, 12, 13, 14, 15], [21, 22, 23, 24, 25]])
    d_to_p.rows = len(curves)
    print(d_to_p.interpolate(0.9, 1, curves))

