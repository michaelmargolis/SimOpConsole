# shared_types.py
# data elements shared across modules

from typing import NamedTuple

class AircraftInfo(NamedTuple):
    status: str  # "ok", "warning", "nogo"
    name: str    # ICAO name or "Aircraft"
    
class SimUpdate(NamedTuple):
    raw_transform: tuple
    processed_transform: tuple
    muscle_lengths: tuple
    sent_pressures: tuple
    conn_status: str
    data_status: str
    aircraft_info: "AircraftInfo"
    temperature: float | None
    processing_percent: int
    jitter_percent: int

class ActivationTransition(NamedTuple):
    activation_percent: int
    muscle_lengths: tuple
    sent_pressures: tuple
