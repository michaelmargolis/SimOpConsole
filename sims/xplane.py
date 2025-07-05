# sim.py (complete version with state machine integration)

import os, sys
import socket
import struct
import traceback
import copy
import time
import logging
import configparser
from enum import Enum

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# from .xplane_cfg import TELEMETRY_CMD_PORT, TELEMETRY_EVT_PORT, HEARTBEAT_PORT
from .xplane_state_machine import SimStateMachine, SimState
from .shared_types import AircraftInfo
from .xplane_beacon import XplaneBeacon
from .xplane_telemetry import XplaneTelemetry
from common.heartbeat_client import HeartbeatClient

TELEMETRY_CONFIG_FILE = "sims/telemetry_config.ini"

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

        self.aircraft_info = AircraftInfo(status="nogo", name="Aircraft")
        self.state_machine = SimStateMachine(self)
        self.heartbeat_ok = False
        self.xplane_running = False
        self.state = SimState.WAITING_HEARTBEAT
        self.HEARTBEAT_INTERVAL = 1.0  # seconds
        self.last_initcoms_time = 0
        self.INITCOMS_INTERVAL = 1.0  # seconds
        self.last_ping_time = 0
        self.PING_INTERVAL = 1.0  # seconds
        self.init_telemetry()
        
        self.beacon = XplaneBeacon()

        self.situation_load_started = False
        self.pause_after_startup = True
        
    def init_telemetry(self):
         default_telemetry_keys = [
             "g_axil",   # X translation
             "g_side",   # Y translation
             "g_nrml",   # Z translation
             "phi",      # Roll angle
             "theta",    # Pitch angle
             "Rrad"      # Yaw rate
         ]
         self.telemetry_keys, self.air_factors, self.ground_factors, settings = self.load_telemetry_config(default_telemetry_keys)
         log.info(f"Normalization factors loaded from: {TELEMETRY_CONFIG_FILE}")
         self.telemetry_evt_port = settings["TELEMETRY_EVT_PORT"]
         self.heartbeat_port = settings["HEARTBEAT_PORT"]
         self.heartbeat_addr = (self.xplane_ip ,  self.heartbeat_port)
         self.heartbeat = HeartbeatClient(self.heartbeat_addr, target_app="xplane_running", interval=self.HEARTBEAT_INTERVAL)
         self.axis_flip_mask = settings["axis_flip_mask"]
         
         self.telemetry = XplaneTelemetry((self.xplane_ip, self.telemetry_evt_port), self.telemetry_keys)
         self.telemetry.update_normalization_factors(self.air_factors, self.ground_factors)

    def get_norm_factors(self):
        return self.telemetry.air_factors, self.telemetry.ground_factors
    
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

    def get_axis_flip_mask(self):
        return self.axis_flip_mask

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


    def load_telemetry_config(self, default_telemetry_keys):
        config = configparser.ConfigParser()
        config.read(TELEMETRY_CONFIG_FILE)

        # Load keys or use default fallback
        keys_str = config.get("telemetry", "keys", fallback=",".join(default_telemetry_keys))
        telemetry_keys = [k.strip() for k in keys_str.split(",")]

        # Load normalization factors for air and ground
        def load_factors(section):
            if not config.has_section(section):
                raise ValueError(f"Missing section: [{section}] in config file")
            return [float(config.get(section, f"f{i}", fallback="1.0")) for i in range(len(telemetry_keys))]

        air_factors = load_factors("air_factors")
        ground_factors = load_factors("ground_factors")

        settings = config["telemetry_settings"]
        evt_port = int(settings.get("TELEMETRY_EVT_PORT", "10022"))
        cmd_port = int(settings.get("TELEMETRY_CMD_PORT", str(evt_port + 1)))
        hb_port  = int(settings.get("HEARTBEAT_PORT", "10030"))
        flip_mask = [int(v.strip()) for v in settings.get("axis_flip_mask", "1,1,1,1,1,1").split(",")]
    
        return telemetry_keys, air_factors, ground_factors, {
            "TELEMETRY_EVT_PORT": evt_port,
            "TELEMETRY_CMD_PORT": cmd_port,
            "HEARTBEAT_PORT": hb_port,
            "axis_flip_mask": flip_mask
        }


    def save_telemetry_config(self, air_factor_values, ground_factor_values, telemetry_keys=None, telemetry_settings=None):
        """
        Save telemetry normalization factors (and optional keys) to an INI config file.

        Parameters:
        - air_factor_values (list or tuple of str): Airside normalization factor values (as strings).
        - ground_factor_values (list or tuple of str): Groundside normalization factor values (as strings).
        - telemetry_keys (optional list or tuple of str): If given, saves under [telemetry] section.
        """
 
        if len(air_factor_values) != len(ground_factor_values):
            raise ValueError("Air and ground factor lists must be the same length")

        config = configparser.ConfigParser()
        config.read(TELEMETRY_CONFIG_FILE)

        config["air_factors"] = {
            f"f{i}": air_factor_values[i] for i in range(len(air_factor_values))
        }

        config["ground_factors"] = {
            f"f{i}": ground_factor_values[i] for i in range(len(ground_factor_values))
        }

        if telemetry_keys:
            config["telemetry"] = {
                "keys": ", ".join(telemetry_keys)
            }

        if telemetry_settings:
            config["telemetry_settings"] = {
                "TELEMETRY_EVT_PORT": str(telemetry_settings["TELEMETRY_EVT_PORT"]),
                "TELEMETRY_CMD_PORT": str(telemetry_settings["TELEMETRY_CMD_PORT"]),
                "HEARTBEAT_PORT": str(telemetry_settings["HEARTBEAT_PORT"]),
                "axis_flip_mask": ", ".join(str(v) for v in telemetry_settings["axis_flip_mask"])
            }
        
        with open(TELEMETRY_CONFIG_FILE, "w") as f:
            config.write(f)
            

