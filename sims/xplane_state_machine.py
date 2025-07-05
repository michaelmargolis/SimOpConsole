import time
import logging
import copy
from abc import ABC, abstractmethod
from enum import Enum
from .shared_types import AircraftInfo

NO_TRANSFORM = [None]*6

class SimState(Enum):
    WAITING_HEARTBEAT = "Waiting for heartbeat"
    WAITING_XPLANE = "Waiting for X-Plane"
    WAITING_DATAREFS = "Waiting for datarefs"
    RECEIVING_DATAREFS = "Receiving datarefs"


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

    def send_control_message_if_due(self, now, message_type: str):
        if message_type == "ping":
            if now - self.sim.last_ping_time > self.sim.PING_INTERVAL:
                try:
                    self.sim.telemetry.send("ping")
                    self.sim.last_ping_time = now
                except Exception as e:
                    logging.warning(f"[ping] Send failed: {e}")                    
        elif message_type == "InitComs":
            if now - self.sim.last_initcoms_time > self.sim.INITCOMS_INTERVAL:
                try:
                    self.sim.telemetry.send("InitComs")
                    self.sim.last_initcoms_time = now
                    logging.debug("Sent InitComs to X-Plane")
                except Exception as e:
                    logging.warning(f"[InitComs] Send failed: {e}")

                
    def no_transform(self):
         self.sim.raw_transform = NO_TRANSFORM
         return NO_TRANSFORM


class SimStateMachine:
    def __init__(self, sim):
        self.sim = sim
        self.states = {
            SimState.WAITING_HEARTBEAT: WaitingHeartbeatState(self),
            SimState.WAITING_XPLANE: WaitingXplaneState(self),
            SimState.WAITING_DATAREFS: WaitingDatarefsState(self),
            SimState.RECEIVING_DATAREFS: ReceivingDatarefsState(self)
        }
        self.current_state = self.states[SimState.WAITING_HEARTBEAT]
        self.sim.state = SimState.WAITING_HEARTBEAT
        self.current_state.on_enter()

    def transition_to(self, state_enum):
        self.current_state.on_exit()
        self.current_state = self.states[state_enum]
        self.sim.state = state_enum
        self.current_state.on_enter()

    def handle(self, washout_callback):
        return self.current_state.handle(washout_callback)


class WaitingHeartbeatState(BaseState):
    def handle(self, washout_callback):
        self.sim.report_state_cb("Waiting for heartbeat...")

        now = time.time()
        hb_ok, app_running = self.sim.heartbeat.query_status(now)
        self.sim.heartbeat_ok = hb_ok
        self.sim.xplane_running = app_running

        if hb_ok:
            self.machine.transition_to(SimState.WAITING_XPLANE)

        return self.no_transform() 


class WaitingXplaneState(BaseState):
    def handle(self, washout_callback):
        self.sim.report_state_cb("Waiting for X-Plane...")

        now = time.time()
        hb_ok, app_running = self.sim.heartbeat.query_status(now)
        self.sim.heartbeat_ok = hb_ok
        self.sim.xplane_running = app_running

        if not hb_ok:
            self.machine.transition_to(SimState.WAITING_HEARTBEAT)
        elif app_running:
            self.machine.transition_to(SimState.WAITING_DATAREFS)
            logging.info("X-Plane connected, waiting for telemetry")

        return self.no_transform() 


class WaitingDatarefsState(BaseState):
    def handle(self, washout_callback):
        self.sim.report_state_cb(" Waiting for telemetry...")

        now = time.time()
        hb_ok, app_running = self.sim.heartbeat.query_status(now)
        self.sim.heartbeat_ok = hb_ok
        self.sim.xplane_running = app_running
 
        self.send_control_message_if_due(now, "InitComs")

        if not hb_ok:
            self.machine.transition_to(SimState.WAITING_HEARTBEAT)
            return self.no_transform() 

        if not app_running:
            self.machine.transition_to(SimState.WAITING_XPLANE)
            return self.no_transform() 

        xyzrpy = self.sim.telemetry.get_telemetry()
        if xyzrpy:
            self.sim.report_state_cb("Telemetry received")
            if self.sim.situation_load_started:
                logging.info("Flight mode load completed — pausing sim")
                self.sim.pause()
                self.sim.situation_load_started = False
            logging.info("X-Plane telemetry received")    
            self.machine.transition_to(SimState.RECEIVING_DATAREFS)
            if washout_callback:
                return washout_callback(copy.copy(xyzrpy))
            return xyzrpy
        return self.no_transform() 


class ReceivingDatarefsState(BaseState):
    def handle(self, washout_callback):
        try:
            now = time.time()
            hb_ok, app_running = self.sim.heartbeat.query_status(now)
            self.sim.heartbeat_ok = hb_ok
            self.sim.xplane_running = app_running

            if not hb_ok or not app_running:
                self.machine.transition_to(SimState.WAITING_HEARTBEAT)
                return self.no_transform()
                
            self.send_control_message_if_due(now, "ping")    
            try:
                xyzrpy = self.sim.telemetry.get_telemetry()
                if xyzrpy == None:
                    self.machine.transition_to(SimState.WAITING_DATAREFS)
                    return self.no_transform()
                # print("in receiving datarefs", xyzrpy, now)
                """
                if xyzrpy:
                    self.sim.report_state_cb(" " + " ".join(f"{x:8.2f}" for x in xyzrpy))
                 """   
                supported = self.sim.is_icao_supported()
                self.sim.aircraft_info = AircraftInfo(
                    status="ok" if supported else "nogo",
                    name=self.sim.telemetry.get_icao()
                )

                self.sim.raw_transform = xyzrpy
                if washout_callback:
                    return washout_callback(copy.copy(xyzrpy))
                return xyzrpy
            except JSONDecodeError as e: 
                log.error(f"telemetry format error {e}")
                self.sim.raw_transform = self.no_transform() 
                self.machine.transition_to(SimState.WAITING_DATAREFS)
                return self.no_transform() 

        except Exception as e:
            logging.error("Exception in ReceivingDatarefsState:", exc_info=True)
            return self.no_transform() 
