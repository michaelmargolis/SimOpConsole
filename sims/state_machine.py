# state_machine.py (single-module version with all handlers)

import copy
import time
import traceback
import logging
from abc import ABC, abstractmethod
from enum import Enum
from .xplane_cfg import TELEMETRY_CMD_PORT, HEARTBEAT_PORT
from .shared_types import AircraftInfo

class SimState(Enum):
    INITIALIZED = 'Initialized'
    BEACON_RECEIVED = 'Beacon Received'
    RECEIVING_DATAREFS = 'Receiving Datarefs'
    DATAREFS_LOST = 'Datarefs Lost'


class BaseState(ABC):
    def __init__(self, machine):
        self.machine = machine
        self.sim = machine.sim

    def on_enter(self):
        pass

    def on_exit(self):
        pass

    @abstractmethod
    def handle(self, washout_callback):
        pass


class SimStateMachine:
    def __init__(self, sim):
        self.sim = sim
        self.states = {
            SimState.INITIALIZED: InitializedState(self),
            SimState.BEACON_RECEIVED: BeaconReceivedState(self),
            SimState.RECEIVING_DATAREFS: ReceivingDatarefsState(self),
            SimState.DATAREFS_LOST: DatarefsLostState(self)
        }
        self.current_state = self.states[SimState.INITIALIZED]
        self.sim.state = SimState.INITIALIZED
        self.current_state.on_enter()

    def transition_to(self, state_enum):
        self.current_state.on_exit()
        self.current_state = self.states[state_enum]
        self.sim.state = state_enum
        self.current_state.on_enter()

    def handle(self, washout_callback):
        ###if self.sim.state.name != 'RECEIVING_DATAREFS' and self.sim.last_beacon_time:
        ###    print(f"{self.sim.state.name}:  {time.time()-self.sim.last_beacon_time}")
        return self.current_state.handle(washout_callback)


class InitializedState(BaseState):
    def handle(self, washout_callback):
        print("Initialized - Waiting for beacon...")
        self.sim.report_state_cb("Initialized - Waiting for beacon...")
        beacon = self.sim.receive_beacon_message()
        if beacon:
            self.sim.xplane_ip = beacon['ip']
            self.sim.xplane_addr = (self.sim.xplane_ip, beacon['port'])
            print("X-Plane command address: {}".format(self.sim.xplane_addr))
            self.machine.transition_to(SimState.BEACON_RECEIVED)
        return (0, 0, 0, 0, 0, 0)


class BeaconReceivedState(BaseState):
    def handle(self, washout_callback):
        self.sim.report_state_cb("X-Plane is busy preparing data...")
        self.sim.xplane_udp.send('InitComs', (self.sim.xplane_ip, TELEMETRY_CMD_PORT))
        self.sim.sleep_func(0.5)
        if self.sim.xplane_udp.available() > 2:
            self.sim.report_state_cb("Receiving telemetry events")
            logging.getLogger(__name__).info("Receiving telemetry events")
            self.machine.transition_to(SimState.RECEIVING_DATAREFS)
        return (0, 0, 0, 0, 0, 0)


class ReceivingDatarefsState(BaseState):
    def handle(self, washout_callback):
        try:
            msg = None
            xyzrpy = [0] * 6
            while self.sim.xplane_udp.available() > 0:
                msg = self.sim.xplane_udp.get()
            if msg is not None:
                data = msg[1].split(',')
                if len(data) > 8 and data[0] == 'xplane_telemetry':
                    telemetry = [float(ele) for ele in data[1:9]]
                    nf = self.sim.norm_factors
                    xyzrpy[0] = telemetry[0] * nf[0]
                    xyzrpy[1] = telemetry[1] * nf[1]
                    xyzrpy[2] = telemetry[2] * nf[2]
                    xyzrpy[3] = telemetry[6] * nf[3]
                    xyzrpy[4] = telemetry[7] * nf[4]
                    xyzrpy[5] = telemetry[5] * nf[5]
                    
                    if len(data) > 9:
                        icao = data[9].strip() or "Aircraft"
                        self.sim.ICAO_type = icao
                        supported = self.sim.is_icao_supported(icao)
                        self.sim.aircraft_info = AircraftInfo(
                            status="ok" if supported else "nogo",
                            name=icao
                        )

                    if washout_callback:
                        return washout_callback(copy.copy(xyzrpy))
                return xyzrpy
            else:
                self.machine.transition_to(SimState.DATAREFS_LOST)
                return xyzrpy
        except Exception as e:
            print("in xplane read:", str(e))
            print(traceback.format_exc())
            return (0, 0, 0, 0, 0, 0)

class DatarefsLostState(BaseState):
    def on_enter(self):
        self.sim.report_state_cb("Datarefs lost - attempting recovery...")
        self.enter_time = time.time()

    def handle(self, washout_callback):
        current_time = time.time()

        # 1. Check if telemetry resumed
        if self.sim.xplane_udp.available() > 0:
            msg = self.sim.xplane_udp.get()
            if msg and msg[1].startswith("xplane_telemetry"):
                self.sim.report_state_cb("Telemetry restored - resuming.")
                self.machine.transition_to(SimState.RECEIVING_DATAREFS)
                return (0, 0, 0, 0, 0, 0)

        # 2. Send heartbeat ping periodically
        if self.sim.xplane_ip and current_time - self.sim.last_heartbeat_ping_time > self.sim.HEARTBEAT_INTERVAL:
            try:
                self.sim.heartbeat.send("ping", (self.sim.xplane_ip, HEARTBEAT_PORT))
                self.sim.last_heartbeat_ping_time = current_time
            except Exception as e:
                logging.warning(f"[Heartbeat] Send failed: {e}")

        # 3. Update heartbeat status
        self.sim.query_heartbeat_status()

        # 4. Handle heartbeat timeout
        if not self.sim.heartbeat_ok:
            self.sim.report_state_cb("Heartbeat lost - resetting connection...")
            self.sim.xplane_ip = None
            self.sim.xplane_addr = None
            self.sim.last_beacon_time = None
            self.machine.transition_to(SimState.INITIALIZED)

        return (0, 0, 0, 0, 0, 0)


# ------------------------------------------------------------------------

