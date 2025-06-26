# factory.py

from .exponential import ExponentialDecayFilter
from .classical import ClassicalWashoutFilter

def create_washout_filter(filter_type, axis, axis_params, global_params):
    if filter_type.lower() == "no_washout":
        return None

    if axis not in axis_params:
        return None

    axis_config = axis_params[axis]

    if filter_type.lower() == "exponential":
        decay = axis_config.get("decay") or axis_config.get("decay_rate")
        if decay is None:
            return None
        return ExponentialDecayFilter(decay_rate=decay)

    elif filter_type.lower() == "classical":
        tau = axis_config.get("tau") or axis_config.get("time_constant")
        if tau is None:
            return None
        gain = axis_config.get("gain", global_params.get("gain", 1.0))
        clip_range = axis_config.get("clip_range", None)
        return ClassicalWashoutFilter(time_constant=tau, gain=gain, clip_range=clip_range)

    return None


