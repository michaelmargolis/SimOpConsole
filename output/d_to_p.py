import numpy as np
import traceback
import logging

log = logging.getLogger(__name__)

class DistanceToPressure:
    def __init__(self, nbr_columns, max_length):
        self.nbr_columns = nbr_columns
        self.loads = None    # tuple of loads
        self.previous_compressions = None
        self.max_muscle_lengths = np.full(6, max_length, dtype=int)
        self.table_indices = [0]*6 # default to up index
        self.all_d_to_p_up = None  # numpy rows of all up values
        self.all_d_to_p_down = None  # numpy rows of all down values
        self.d_to_p_up = None  # numpy rows of interpolated up values
        self.d_to_p_down = None  # numpy rows of interpolated down values
        self.d_to_p = None # self.d_to_p[0] → up table, self.d_to_p[1] → down table
        self.threshold = 5

    def _get_loads(self, csv_path):
        # returns first data row, loads tuple (or none if invalid data)
        with open(csv_path, 'r') as file:
            skiped_lines = 0
            for line in file:
                skiped_lines += 1
                if line.startswith('# weights'):
                    fields = line.strip().split(',')[1:] # Extract fields after '# weights'
                    last_non_empty_index = next((i for i in reversed(range(len(fields))) if fields[i] != ''), -1)
                    fields = fields[:last_non_empty_index + 1]
                    loads_tuple = tuple(map(int, fields))
                    return skiped_lines, loads_tuple
            return None, None
   
    def _interpolate_load(self, d_to_p, l):
        """Interpolate d_to_p rows between two nearest loads."""
        d_to_p = np.asarray(d_to_p)

        # Handle edge cases
        if l <= self.loads[0]:
            return d_to_p[0]
        if l >= self.loads[-1]:
            return d_to_p[-1]

        # Find lower/upper bounds 
        idx_upper = np.searchsorted(self.loads, l)
        idx_lower = idx_upper - 1

        l_lower, l_upper = self.loads[idx_lower], self.loads[idx_upper]
        d_lower, d_upper = d_to_p[idx_lower], d_to_p[idx_upper]

        interpolation_factor = (l - l_lower) / (l_upper - l_lower)
        interpolated = (1 - interpolation_factor) * d_lower + interpolation_factor * d_upper
        return np.round(interpolated).astype(int)
        
    def load_data(self, csv_path):
        log.info("Using distance to Pressure file: %s" , csv_path)
        try:
            skiped_lines, loads = self._get_loads(csv_path)
            # print(skiped_lines, loads)
            if loads:
                self.loads = np.asarray(loads)
                # Ensure sorted loads
                if not np.all(np.diff(loads) > 0):
                    raise ValueError("loads must be in strictly ascending order.")
                d_to_p = np.loadtxt(csv_path, delimiter=',', skiprows=skiped_lines, dtype=int)
                # print(d_to_p, d_to_p.shape[1])
                if d_to_p.shape[1] != self.nbr_columns:
                    raise ValueError(f"In {csv_path} expected {int(self.nbr_columns)} distance values, but found {d_to_p.shape[1]}")
                self.all_d_to_p_up, self.all_d_to_p_down = np.split(d_to_p, 2)
                # print( "up", self.all_d_to_p_up)
                # print("down",  self.all_d_to_p_down)
                if self.all_d_to_p_up.shape[0] != self.all_d_to_p_down.shape[0]:
                    raise ValueError("Up and down DtoP rows don't match")
                self.rows = self.all_d_to_p_up.shape[0]
                if self.nbr_columns != self.all_d_to_p_up.shape[1]:
                    print(f"number of columns {self.all_d_to_p_up.shape[1]}, expected {self.nbr_columns} " )
                return True
            return False    
        except Exception as e:
            log.error("Error loading file: %s\n%s", e, traceback.format_exc())
            raise
            
    def set_load(self, load):
        """Set load and calculate interpolation parameters."""
        self.d_to_p_up = self._interpolate_load(self.all_d_to_p_up, load)
        self.d_to_p_down = self._interpolate_load(self.all_d_to_p_down, load)
        self.d_to_p = np.stack([self.d_to_p_up, self.d_to_p_down], axis=0)
       #  print(f"in set_load, d_to_p stack is: {self.d_to_p}")

    def muscle_length_to_pressure(self, muscle_lengths):
        muscle_lengths = np.asarray(muscle_lengths, dtype=int)
        if muscle_lengths.shape != self.max_muscle_lengths.shape:
            raise ValueError("Invalid number of muscle lengths")
        muscle_compressions =  self.max_muscle_lengths - muscle_lengths
        return self.muscle_compression_to_pressure(muscle_compressions)
    
    """  
    muscle_compression_to_pressure takes 6 muscle compression values and returns 6 pressures
        Converts muscle compression to a numpy array.
        If previous_compressions is not initialized, copy it and use down table (first reading).
        Calculate change (delta) compared to last cycle.
        If delta < -threshold, use up table (index 0), else down table (index 1).
        Lookup pressures using numpy indexing.
        Update only the previous_compressions where delta exceeds threshold.

    def muscle_compression_to_pressure(self, muscle_compressions):
        muscle_compressions = np.asarray(muscle_compressions, dtype=int)
        muscle_compressions = np.clip(muscle_compressions, 0, self.nbr_columns-1).astype(int)
         
        if self.previous_compressions is None:
            self.previous_compressions = muscle_compressions.copy()
            return self.d_to_p[0][muscle_compressions]  # Use Up table for first lookup

        delta = muscle_compressions - self.previous_compressions
        if any(delta):
            self.table_indices = np.where(delta > -self.threshold, 0, 1)
            # print("delta:", delta, "delta indices", self.table_indices)
        pressures = self.d_to_p[self.table_indices, muscle_compressions]

        needs_update = np.abs(delta) >= self.threshold
        self.previous_compressions[needs_update] = muscle_compressions[needs_update]
        return pressures
    """
    def muscle_compression_to_pressure(self, compressions):
        """
        Convert six compression values (mm) to pressures using a 2-row hysteresis table.

        self.d_to_p : shape [2, N]  (row 0 = up / increasing-pressure branch,
                                     row 1 = down / decreasing-pressure branch)
        self.threshold : int  ≥ 1   (hysteresis band, same for all muscles)

        Returns
        -------
        pressures : np.ndarray  shape (6,)  – one pressure per muscle
        """
        # Convert to integer indices (truncating) and clip to [0, N-1]
        compressions = np.asarray(compressions, dtype=int)
        indices      = np.clip(compressions, 0, self.d_to_p.shape[1] - 1)

        # First call – initialise state & use the up row (row 0)
        if not hasattr(self, "prev_compressions"):
            self.prev_compressions = compressions.copy()
            self.active_row = np.zeros_like(compressions, dtype=int)   # all start on row 0
            return self.d_to_p[0, indices]

        # Subsequent calls – compute delta & apply symmetric hysteresis switching
        delta      = compressions - self.prev_compressions
        up_mask    = delta >= self.threshold      # switch to row 0
        down_mask  = delta <= -self.threshold     # switch to row 1
        self.active_row[up_mask]   = 0
        self.active_row[down_mask] = 1

        # Lookup pressures and update history
        pressures = self.d_to_p[self.active_row, indices]
        self.prev_compressions = compressions
        # print(f"compressions: {compressions}\ndelta: {delta}\nactive ros: {self.active_row}\npressures: {pressures}")   
        return pressures

# ---------------------------------------------------------
# Test harness
# ---------------------------------------------------------
if __name__ == '__main__':
    max_range = 250
    max_length = 1000
    d2p = DistanceToPressure(max_range+1, max_length)
    if d2p.load_data("wheelchair_DtoP.csv"):
        d2p.set_load(24)  # Set test load

    print(d2p.d_to_p) 
    while True:
        user_input = input("Enter 6 lengths separated by commas or 'l,<load>' to set load (empty input to quit): ").strip()

        if not user_input:
            break

        if user_input.lower().startswith('l,'):
            try:
                load = int(user_input.split(',')[1])
                d2p.set_load(load) 
                print(f"Load updated to: {load}kg")
            except (IndexError, ValueError):
                print("Invalid load format. Use l,<number> (e.g., l,35)")
            continue

        try:
            lengths = [int(val) for val in user_input.split(',')]
            if len(lengths) != 6:
                print("Please enter exactly 6 numbers.")
                continue

            pressures = d2p.muscle_length_to_pressure(lengths)
            print(f"Input lengths: {lengths}")
            print(f"Resulting pressures: {pressures}")

        except ValueError:
            print("Invalid input. Please enter numbers separated by commas.")

