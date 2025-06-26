# classical.py

from .base import WashoutFilter


class ClassicalWashoutFilter(WashoutFilter):
    def __init__(self, time_constant: float = 1.0, gain: float = 1.0, clip_range: tuple = None, initial_output: float = 0.0):
        """
        Implements a first-order high-pass filter ("classic washout") for motion cueing.
        
        Args:
            time_constant (float): Determines cutoff frequency (τ in seconds).
            gain (float): Optional output gain.
            clip_range (tuple): Optional (min, max) clamp on the output.
            initial_output (float): Starting value for the output.
        """
        self.tau = time_constant
        self.gain = gain
        self.clip_range = clip_range
        self.output = initial_output
        self.prev_input = 0.0

    def update(self, input_value: float, delta_time: float) -> float:
        """
        Applies the washout filter to the new input.
        
        Args:
            input_value (float): Current input from telemetry.
            delta_time (float): Time since last update, in seconds.
        
        Returns:
            float: Filtered output value.
        """
        if delta_time <= 0:
            return self.output  # Avoid divide-by-zero or negative step

        # First-order high-pass filter formula
        alpha = self.tau / (self.tau + delta_time)
        new_output = alpha * (self.output + input_value - self.prev_input)
        new_output *= self.gain

        # Optional clamping
        if self.clip_range is not None:
            min_val, max_val = self.clip_range
            new_output = max(min(new_output, max_val), min_val)

        # Save state
        self.prev_input = input_value
        self.output = new_output
        return new_output
