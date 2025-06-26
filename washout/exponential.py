# exponential.py

from .base import WashoutFilter

class ExponentialDecayFilter(WashoutFilter):
    def __init__(self, decay_rate: float):
        """
        Initialize an exponential decay filter.
        :param decay_rate: The rate of decay (units: 1/second).
        """
        self.decay_rate = decay_rate
        self.current_value = 0.0

    def update(self, input_value: float, delta_time: float) -> float:
        """
        Apply exponential decay filtering.
        :param input_value: The new input value.
        :param delta_time: Time since the last update (in seconds).
        :return: Filtered output value.
        """
        alpha = self.decay_rate * delta_time
        self.current_value += (input_value - self.current_value) * alpha
        return self.current_value
