from typing import Tuple, Dict

from typing import Tuple, Dict

def parse_filter_string(filter_str: str) -> Tuple[str, Dict[str, dict]]:
    """
    Parses a washout filter config string into a filter type and per-axis config dict.

    Only axes explicitly configured (e.g., decay_x=..., tau_yaw=...) will be returned.
    Omitted axes will not have filters created.

    Returns:
        filter_type (str)
        per_axis_config (dict of axis name → parameter dict)
    """
    if ":" not in filter_str:
        return filter_str, {}

    parts = filter_str.split(":")
    filter_type = parts[0]
    param_str = ":".join(parts[1:])
    param_pairs = param_str.replace(":", ",").split(",")

    # Supported axes
    axes = ['x', 'y', 'z', 'roll', 'pitch', 'yaw']
    per_axis: Dict[str, Dict[str, float]] = {}
    shared_params: Dict[str, float] = {}

    for pair in param_pairs:
        if "=" not in pair:
            continue
        key, val = pair.strip().split("=")
        val = val.strip()

        # Look for axis-specific keys like decay_yaw, tau_pitch
        matched_axis = None
        for axis in axes:
            suffix = f"_{axis}"
            if key.endswith(suffix):
                param_name = key[:-len(suffix)]
                if axis not in per_axis:
                    per_axis[axis] = {}
                per_axis[axis][param_name] = float(val)
                matched_axis = axis
                break

        # Otherwise it's a shared/global param
        if not matched_axis:
            if key == "clip":
                # Format: clip=-1.0:1.0
                low, high = map(float, val.split(":"))
                for axis in axes:
                    if axis not in per_axis:
                        per_axis[axis] = {}
                    per_axis[axis]["clip_range"] = (low, high)
            else:
                shared_params[key] = float(val)

    # Apply shared params ONLY to axes that are explicitly present
    for axis, params in per_axis.items():
        if filter_type == "exponential" and "decay_rate" not in params and "decay" in shared_params:
            params["decay_rate"] = shared_params["decay"]
        if filter_type == "classical" and "time_constant" not in params and "tau" in shared_params:
            params["time_constant"] = shared_params["tau"]
        if "gain" in shared_params:
            params["gain"] = shared_params["gain"]

    return filter_type, per_axis

