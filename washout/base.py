# base.py

class WashoutFilter:
    def update(self, input_value: float, delta_time: float) -> float:
        """
        Process the input value and return the filtered output.
        :param input_value: The current input value to be filtered.
        :param delta_time: Time elapsed since the last update (in seconds).
        :return: The filtered output value.
        """
        raise NotImplementedError("This method must be overridden by subclasses.")
