# sim.py (complete version with state machine integration)

import os, sys
import socket
import struct
import traceback
import copy
import time
import logging
from enum import Enum

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from . import xplane_cfg as config
from .xplane_cfg import TELEMETRY_CMD_PORT, TELEMETRY_EVT_PORT, HEARTBEAT_PORT
from .xplane_state_machine import SimStateMachine, SimState
from .shared_types import AircraftInfo
from .xplane_beacon import XplaneBeacon
from .xplane_telemetry import XplaneTelemetry
from common.heartbeat_client import HeartbeatClient

log = logging.getLogger(__name__)


class Sim:
    def __init__(self, sleep_func, frame, report_state_cb, sim_ip=None):
        self.sleep_func = sleep_func
        self.frame = frame
        self.report_state_cb = report_state_cb
        self.name = "X-Plane"
        self.prev_yaw = None
        self.washout_callback = None
        self.raw_transform = [None]*6 # transform as received from xplane
        self.xplane_ip = sim_ip
        self.xplane_addr = None
        self.init_telemetry()
        self.aircraft_info = AircraftInfo(status="nogo", name="Aircraft")
        self.state_machine = SimStateMachine(self)
        self.heartbeat_ok = False
        self.xplane_running = False
        self.state = SimState.WAITING_HEARTBEAT
        self.HEARTBEAT_INTERVAL = 1.0  # seconds
        heartbeat_addr = (sim_ip, HEARTBEAT_PORT)
        self.heartbeat = HeartbeatClient(heartbeat_addr, target_app="xplane_running", interval=self.HEARTBEAT_INTERVAL)
        self.last_initcoms_time = 0
        self.INITCOMS_INTERVAL = 1.0  # seconds
        self.last_ping_time = 0
        self.PING_INTERVAL = 1.0  # seconds
        self.beacon = XplaneBeacon()

        self.situation_load_started = False
        self.pause_after_startup = True
        
    def init_telemetry(self):
         telemetry_keys = [
             "g_axil",   # X translation
             "g_side",   # Y translation
             "g_nrml",   # Z translation
             "phi",      # Roll angle
             "theta",    # Pitch angle
             "Rrad"      # Yaw rate
         ]
         air_factors = config.norm_factors
         ground_factors = config.norm_factors.copy()
         ground_factors[5]  = air_factors[5] * 0.2
         print(air_factors, ground_factors)
         self.telemetry = XplaneTelemetry((self.xplane_ip, TELEMETRY_EVT_PORT), telemetry_keys)
         self.telemetry.update_normalization_factors(air_factors, ground_factors)

    def service(self, washout_callback=None):
        return self.state_machine.handle(washout_callback)     

    def read(self):
        return self.service(self.washout_callback)

    def connect(self, server_addr=None):
        self.service(self.washout_callback)

    def set_default_address(self, ip_address):
        pass

    def set_state_callback(self, callback):
        self.report_state_cb = callback

    def set_washout_callback(self, callback):
        self.washout_callback = callback

    def get_washout_config(self):
        return config.washout_time

    def get_axis_flip_mask(self):
        return config.axis_flip_mask

    def is_Connected(self):
        return True

    def get_connection_state(self):
        if not self.heartbeat_ok:
            connection_status = "nogo"
        elif not self.xplane_running:
            connection_status = "warning"
        else:
            connection_status = "ok"
         
        if self.state == SimState.RECEIVING_DATAREFS:
            data_status = "ok"
        elif self.state == SimState.WAITING_DATAREFS:
            data_status = "warning"
        else:
            data_status = "nogo"

        if self.state != SimState.RECEIVING_DATAREFS:
            aircraft_info = AircraftInfo(status="nogo", name="Aircraft")
        else:
            name = self.aircraft_info.name
            status = "ok" if self.is_icao_supported() else "nogo"
            aircraft_info = AircraftInfo(status=status, name=name)

        return connection_status, data_status, aircraft_info

    def is_icao_supported(self):
        icao = self.telemetry.get_icao()
        return icao.startswith("C172")  # Placeholder – replace with config-based check

    def run(self):
        self._send_command('Run')

    def play(self):
        self._send_command('Play')

    def pause(self):
        self._send_command('Pause')

    def reset_playback(self):
        self._send_command('Reset_playback')

    def set_flight_mode(self, mode):
        self.situation_load_started = True
        self.pause()
        self._send_command(f'FlightMode,{mode}')

    def set_pilot_assist(self, level):
        self._send_command(f'AssistLevel,{level}')

    def _send_command(self, msg):
        if self.state == SimState.RECEIVING_DATAREFS:
            self.telemetry.send(msg)
        else:
            log.warning(f"X-Plane not connected when sending {msg}")

    def ui_action(self, action):
        if action.endswith('sit'):
            print("do situation", action)
            self.set_situation(action)
        elif action.endswith('rep'):
            print("do replay", action)
            self.replay(action)

    def set_situation(self, filename):
        msg = f"Situation,{filename}"
        print(f"sending {msg} to {self.xplane_ip}:{TELEMETRY_CMD_PORT}")
        self.telemetry.send(msg)

    def replay(self, filename):
        self.send_SIMO(3, filename)

    def send_SIMO(self, command, filename):
        filename_bytes = filename.encode('utf-8') + b'\x00'
        filename_padded = filename_bytes.ljust(153, b'\x00')
        msg = struct.pack('<4s i 153s', b'SIMO', command, filename_padded)
        self.beacon.send_bytes(msg, self.xplane_addr)
        print(f"sent {filename} to {self.xplane_addr} encoded as {msg}")

    def send_CMND(self, command_str):
        msg = 'CMND\x00' + command_str
        self.beacon.send_bytes(msg, self.xplane_addr)

    def fin(self):
        self.telemetry.close()
        self.beacon.close()
        self.heartbeat.close()

    def init_plot(self):
        from .washout import motionCueing
        from common.plot_itf import PlotItf
        nbr_plots = 6
        traces_per_plot = 2
        titles = ('x (surge)', 'y (sway)', 'z (heave)', 'roll', 'pitch', 'yaw')
        legends = ('from xplane', 'washed')
        main_title = "Translations and Rotation washouts from XPlane"
        self.plotter = PlotItf(main_title, nbr_plots, titles, traces_per_plot, legends=legends, minmax=(-1, 1), grouping='traces')
        self.mca = motionCueing()

    def plot(self, raw, rates):
        washed = self.mca.wash(rates)
        self.plotter.plot([raw, rates])
