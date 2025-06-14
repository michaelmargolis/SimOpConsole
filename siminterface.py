#!/usr/bin/env python3
 
# sim_interface_core.py 

import os
import sys
import math
import platform
import traceback
import time
import logging
import importlib
import socket

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import QTimer, Qt

""" directory structure

These modules provide the core source code for this application 

├── siminterface.py                       # Core applicaiton logic (this module) 
├── SimInterface_ui.py                    # user interface code
├── SimInterface_1280.ui                  # user interface definitions and layout
├── sim_config.py                         # runtime configuration options
├── sims/
│   ├── xplane.py                         # high level X-Plane interface
│   ├── xplane_telemetry.py               # low level telemetry interface
│   ├── xplane_state_machine.py           # manages x-plane state 
│   ├── xplane_cfg.py                     # x-plane specific runtime configuration 
│   └── ...
├── kinematics/
│   ├── kinematicsV2SP.py                 # converts sim transform and accelerations to actuator lengths 
│   ├── dynamics.py                       # manages intensity and washout   
│   ├── cfg_SuspendedPlatform.py          # platform configuration parameters used by kinematics
│   └── ...
├── output/
│   ├── muscle_output.py                  # provides drive to pneumatic actuators 
│   ├── d_to_p.py                         # converts acutator lengths to pressures 
│   └── ...
├── common/
│   ├── udp_tx_rx.py                      # UDP helper class   
│   ├── heartbeat_client.py               # receives heartbeat from heartbeat server running on x-plane PC 
│   ├── serial_switch_json_reader.py      # switch press handler
│   └── ...
└── ...
"""


import sim_config
# from sim_config import selected_sim, platform_config, switches_comport
from siminterface_ui import MainWindow
#naming#from kinematics.kinematicsV2 import Kinematics
from kinematics.kinematics_V2SP import Kinematics
from kinematics.dynamics import Dynamics

import output.d_to_p as d_to_p
from common.get_local_ip import get_local_ip

#naming#from output.muscle_output import MuscleOutput
from output.muscle_output import MuscleOutput
from typing import NamedTuple
from sims.shared_types import SimUpdate, ActivationTransition

echo_port = 10020 # port used by optional external Unity visualizer

class SimInterfaceCore(QtCore.QObject):
    """
    Core logic for controlling platform from simulations.

    Responsibilities:
      - Loading platform config (chair/slider).
      =	Handles platform state management, simulation data updates, and communication with xplane.py
      - Runs a QTimer to periodically read sim data (data_update).
      -	Handles intensity, assist, and mode changes (intensityChanged(), modeChanged(), assistLevelChanged()).
      - Notifies the UI of simulation state (simStatusChanged).
      - Converting transforms -> muscle movements via kinematics, d_to_p, etc.
    """

    # Signals to inform the UI
    simStatusChanged = QtCore.pyqtSignal(str)          # e.g., "Connected", "Not Connected", ...
    fatal_error = QtCore.pyqtSignal(str)               # fatal error forcing exit of application
    logMessage = QtCore.pyqtSignal(str)                # general logs or warnings to display in UI
    dataUpdated = QtCore.pyqtSignal(object)            # passing transforms or status to the UI
    activationLevelUpdated = QtCore.pyqtSignal(object) # activation percent passed in slow moved  
    platformStateChanged = QtCore.pyqtSignal(str)      # "enabled", "deactivated", "running", "paused"

    def __init__(self, parent=None):
        super().__init__(parent)

        # Simulation references
        self.sim = None # the sim to run (xplane 11)
        self.current_pilot_assist_level = None
        self.current_mode = None # this is the currently selected flight situation (or ride if roller coaster) 

        # Timer for periodic data updates
        self.data_timer = QTimer(self)
        self.data_timer.timeout.connect(self.data_update)
        self.data_timer.setTimerType(QtCore.Qt.PreciseTimer)
        self.data_period_ms = 50
        
        # performance timer
        self.last_frame_time = time.perf_counter()
        self.last_loop_start = None

        # Basic flags and states
        self.is_started = False      # True after platform config and sim are loaded
        self.state = 'initialized'    # runtime platform states: disabled, enabled, running, paused

        # Default transforms
        self.transform = [0, 0, 0, 0, 0, 0]

        # Kinematics, dynamics, distance->pressure references
        self.k = None
        self.dynam = None
        self.DtoP = None
        self.muscle_output = None
        self.cfg = None
        self.is_slider = False
        self.invert_axis = (1, 1, 1, 1, 1, 1)   # can be set by config
        self.swap_roll_pitch = False
        self.gains = [1.0]*6
        self.master_gain = 1.0
        self.intensity_percent = 100 
        
        # Transition control (new version)
        self.transition_state = None            # "activating" or "deactivating"
        self.transition_step_index = 0
        self.transition_steps = 0
        self.transition_start_lengths = []
        self.transition_end_lengths = []
        self.transition_delta_lengths = []

        self._block_sim_control = False         # Used to suppress sim input during transition
        self.virtual_only_mode = False          # If true, Unity only — no physical output


       
        # temperature monitor        
        self.temperature = None
        self.temp_timer = QtCore.QTimer(self)
        self.temp_timer.setInterval(10000)  # 10 seconds
        self.temp_timer.timeout.connect(self.read_temperature)
        self.is_pi = platform.system() == "Linux" and os.path.exists("/sys/class/thermal/thermal_zone0/temp")
        if self.is_pi:
            self.temp_timer.start()
            log.info("SimInterfaceCore: temperature timer started (10s)")
        
        # performance monitor   
        self.processing_percent = 0
        self.jitter_percent = 0

    # --------------------------------------------------------------------------
    # set up configurations
    # --------------------------------------------------------------------------
    def setup(self):
        self.load_config()
        self.load_sim()
        
        if self.is_started:
            # Start the data update timer if the sim interface class for xplane loaded successfully
            self.data_timer.start(self.data_period_ms)
            log.debug("Core: data timer started at %d ms period", self.data_period_ms)
    
        logging.debug("Core: Initialization complete. Emitting 'initialized' state.")
        self.platformStateChanged.emit("initialized")  
        
        self.echo_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.echo_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.local_ip = get_local_ip()
        
    # --------------------------------------------------------------------------
    # Platform Config
    # --------------------------------------------------------------------------
    def load_config(self):
        """
        Imports the platform config (chair or slider). Then sets up Kinematics, DtoP, MuscleOutput.
        """
        try:
            import importlib
            selected_platform, description = sim_config.AVAILABLE_PLATFORMS[sim_config.DEFAULT_PLATFORM_INDEX]
            cfg_module = importlib.import_module(selected_platform)       
            self.cfg = cfg_module.PlatformConfig()
            log.info(f"Core: Imported cfg from {selected_platform}: {description}")
            self.FESTO_IP = sim_config.FESTO_IP
        except Exception as e:
            self.handle_error(e, f"Unable to import platform config from {cfg_module}, check sim_config.py")
            return

        # Initialize the distance->pressure converter
        self.DtoP = d_to_p.DistanceToPressure(self.cfg.MUSCLE_LENGTH_RANGE+1, self.cfg.MUSCLE_MAX_LENGTH)
        self.muscle_output = MuscleOutput(self.DtoP.muscle_length_to_pressure, sleep_qt,
                            self.FESTO_IP, self.cfg.MUSCLE_MAX_LENGTH, self.cfg.MUSCLE_LENGTH_RANGE ) 
                
        # Hardcoded Festo IP in example above—change if needed or pass as param

        # Setup kinematics
        self.k = Kinematics()
        self.cfg.calculate_coords()
        self.k.set_geometry(self.cfg.BASE_POS, self.cfg.PLATFORM_POS)
        self.muscle_lengths = self.cfg.DEACTIVATED_MUSCLE_LENGTHS.copy()
        

        if self.cfg.PLATFORM_TYPE == "SLIDER":
            self.k.set_slider_params(
                self.cfg.joint_min_offset,
                self.cfg.joint_max_offset,
                self.cfg.strut_length,
                self.cfg.slider_angles,
                self.cfg.slider_endpoints
            )
            self.is_slider = True
        else:
            self.k.set_platform_params(
                self.cfg.MIN_ACTUATOR_LENGTH,
                self.cfg.MAX_ACTUATOR_LENGTH,
                self.cfg.FIXED_HARDWARE_LENGTH
            )
            self.is_slider = False
        
        self.payload_weights = [int((w + self.cfg.UNLOADED_PLATFORM_WEIGHT) / 6) for w in self.cfg.PAYLOAD_WEIGHTS]
        log.debug(f"Core: Payload weights in kg per muscle: {self.payload_weights}")
        
        self.invert_axis = self.cfg.INVERT_AXIS
        self.swap_roll_pitch = self.cfg.SWAP_ROLL_PITCH

        self.dynam = Dynamics()
        self.dynam.begin(self.cfg.LIMITS_1DOF_TRANFORM, "shape.cfg")
        
        
        # Load distance->pressure file
        try:
            if self.DtoP.load_data(self.cfg.MUSCLE_PRESSURE_MAPPING_FILE):
                log.debug("Core: Muscle pressure mapping table loaded.")
                self.DtoP.set_load(self.payload_weights[1])  # default is middle weight 
        except Exception as e:
            self.handle_error(e, "Error loading Muscle pressure mapping table ")

        log.debug("Core: %s config data loaded", description)
        self.simStatusChanged.emit("Config Loaded")

    # --------------------------------------------------------------------------
    # Simulation Management
    # --------------------------------------------------------------------------
    def load_sim(self):
        """
        Loads or re-loads a simulation by index from available_sims.
        """
        self.sim_name, self.sim_class, self.sim_image, self.sim_ip_address = sim_config.AVAILABLE_SIMS[sim_config.DEFAULT_SIM_INDEX]
        sim_path = "sims." + self.sim_class

        try:
            sim_module = importlib.import_module(sim_path)
            frame = None # this version does not allocate a UI frame
            self.sim = sim_module.Sim(sleep_qt, frame, self.emit_status, self.sim_ip_address )
            if self.sim:
                self.is_started = True
                log.debug("Core: Instantiated sim '%s' from class '%s'", self.sim.name, self.sim_class)

            self.simStatusChanged.emit(f"Sim '{self.sim_name}' loaded.")
            self.sim.set_default_address(self.sim_ip_address)
            log.info(f"Ready to connect to {self.sim_name} at {self.sim_ip_address}")    
        except Exception as e:
            self.handle_error(e, f"Unable to load sim from {sim_path}")


    # --------------------------------------------------------------------------
    # QTimer Update Loop
    # --------------------------------------------------------------------------

    def data_update(self):
        frame_start = time.perf_counter()
        frame_interval = frame_start - self.last_frame_time
        self.last_frame_time = frame_start

        if not self.is_started:
            self.simStatusChanged.emit("Sim interface failed to start")
            print("Sim interface failed to start")
            return
        # Handle any platform motion state (activation/deactivation transitions)
        if self.handle_transition_step():
            return  # skip sim-driven control during transition
        
        if self._block_sim_control or self.sim.aircraft_info.status != "ok" or self.state == 'deactivated':
            transform = self.transform
            self.sim.service()
        else:
            transform = self.sim.read()
            if transform:               
                for idx in range(6):
                    base_gain = self.gains[idx] * self.master_gain
                    attenuated_gain = base_gain * (self.intensity_percent / 100.0)
                    self.transform[idx] = transform[idx] * attenuated_gain
                self.move_platform(self.transform)

        # Emit update for UI + Unity twin
        temperature = self.temperature
        conn_status, data_status, aircraft_info = self.sim.get_connection_state()
  
        self.dataUpdated.emit(SimUpdate(
            raw_transform=tuple(self.sim.raw_transform ),
            processed_transform=tuple(self.transform),
            muscle_lengths=tuple(self.muscle_lengths),
            sent_pressures=tuple(self.muscle_output.sent_pressures),
            conn_status=conn_status,
            data_status=data_status,
            aircraft_info=aircraft_info,
            temperature=temperature,
            processing_percent=self.processing_percent,
            jitter_percent=self.jitter_percent
        ))


        # Performance monitoring
        loop_duration = time.perf_counter() - frame_start
        self.processing_percent = int((loop_duration / 0.050) * 100)
        self.jitter_percent = int(abs(frame_interval - 0.050) / 0.050 * 100)


    # following is used to drive slow moves on activation and deactivation
    def handle_transition_step(self):
        if not self.transition_state:
            return False

        if self.transition_step_index >= self.transition_steps:
            # Capture mode BEFORE clearing state
            mode = self.transition_state

            self.muscle_lengths = self.transition_end_lengths
            self.muscle_output.set_muscle_lengths(self.muscle_lengths)

            final_percent = 100 if mode == "activating" else 0
            self.update_activate_transition(final_percent, self.muscle_lengths)

            self.transition_state = None
            self.block_sim_control = False

            # Now use captured mode
            if mode == "activating":
                self.update_state("enabled")
            elif mode == "deactivating":
                self.update_state("deactivated")
            log.info(f"[Transition Complete] {mode} → {self.state}")

            return False

        # Interpolate muscle lengths
        self.muscle_lengths = [
            s + self.transition_step_index * d
            for s, d in zip(self.transition_start_lengths, self.transition_delta_lengths)
        ]

        if not self.virtual_only_mode:
            self.muscle_output.set_muscle_lengths(self.muscle_lengths)

        progress = self.transition_step_index / self.transition_steps
        percent = int(progress * 100) if self.transition_state == "activating" else int(100 - progress * 100)
        self.update_activate_transition(percent, self.muscle_lengths)

        self.transition_step_index += 1
        return True



    def start_transition(self, mode: str, end_lengths: list):
        self.transition_state = mode
        self.transition_step_index = 0
        self.transition_start_lengths = (
            self.cfg.DEACTIVATED_MUSCLE_LENGTHS
            if mode == "activating"
            else self.muscle_lengths
        )
        self.transition_end_lengths = end_lengths

        max_dist = max(abs(e - s) for s, e in zip(self.transition_start_lengths, self.transition_end_lengths))
        self.transition_steps = max(1, int(max_dist / (50 * 0.05)))
        self.transition_delta_lengths = [
            (e - s) / self.transition_steps for s, e in zip(self.transition_start_lengths, self.transition_end_lengths)
        ]

        self.block_sim_control = True
        log.info(f"[Init Transition] {mode}: {self.transition_steps} steps from {self.transition_start_lengths} to {self.transition_end_lengths}")

   
    def update_activate_transition(self, percent,  muscle_lengths=None):
        """
        Emits activation progress including muscle lengths.
        If muscle_lengths not provided, falls back to current physical state.
        """
        if muscle_lengths is None:
            muscle_lengths = self.muscle_lengths

        self.activationLevelUpdated.emit(ActivationTransition(
            activation_percent = percent,
            muscle_lengths=tuple(muscle_lengths),
            sent_pressures=tuple(self.muscle_output.sent_pressures)
        ))

    """  
    def start_slow_move(self, start_lengths, end_lengths, mode):
        log.info(f"[Init Slow Move] {mode}: {self._slow_move_steps} steps from {start_lengths} to {end_lengths}")
        self._motion_state = mode
        self._requested_motion_state = mode
        self._slow_move_step_index = 0
        self._slow_move_steps = max(1, int(max(abs(j - i) for i, j in zip(start_lengths, end_lengths)) / (50 * 0.05)))
        self._slow_move_muscle_len = list(start_lengths)
        self._delta_muscle_len = [(j - i) / self._slow_move_steps for i, j in zip(start_lengths, end_lengths)]
        self._block_sim_control = True
    """

    def read_temperature(self):
        """Read CPU temperature on Raspberry Pi if available."""
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                raw = f.readline().strip()
                self.temperature = round(int(raw) / 1000.0, 1)
        except Exception as e:
            log.warning(f"Failed to read temperature: {e}")
            self.temperature = None
            
    def echo(self, transform, distances, pose):
        t = [""] * 6
        for idx, val in enumerate(transform):
            if idx < 3:
                # Invert z if idx == 2?
                if idx == 2:
                    val = -val
                t[idx] = str(round(val))
            else:
                t[idx] = str(round(val * 180 / math.pi, 1))

        req_msg = "request," + ",".join(t)
        dist_msg = ",distances," + ",".join(str(int(d)) for d in distances)
        pose_msg = ",pose," + ",".join([";".join(map(lambda x: format(x, ".1f"), row)) for row in pose])
        msg = req_msg + dist_msg + pose_msg + "\n"
        # print(msg)
        self.echo_sock.sendto(bytes(msg, "utf-8"), ('<broadcast>', echo_port))
        
    def update_gain(self, index, value):
        """
        Updates the gain based on the slider change.
        """
        if index == 6:  # index 6 corresponds to the master gain
            self.master_gain = value *.01
        else:
            self.gains[index] = value *.01
        
    def intensityChanged(self, percent):
        if self.is_started:
            self.intensity_percent = percent
            log.debug(f"Core: intensity set to {percent}%")
        
    def loadLevelChanged(self, load_level):
        if self.is_started:
            if load_level>=0 and load_level <=2:   
                load = self.payload_weights[load_level]     
                self.DtoP.set_load(load)            
                log.info(f"load level changed to {load_level},({load})kg per muscle, {load*6}kg total inc platform")

    def modeChanged(self, mode_id):
        """
        Handles mode changes and ensures it is sent to X-Plane.
        """
        if self.sim:
            self.current_mode = mode_id
            log.debug(f"Flight mode changed to {mode_id}")
            self.sim.set_flight_mode(self.current_mode)

    def assistLevelChanged(self, pilotAssistLevel):
        """
        Handles assist level changes and ensures it is sent to X-Plane.
        """
        if self.sim:
            self.current_pilot_assist_level = pilotAssistLevel
            log.debug(f"Pilot assist level changed to {pilotAssistLevel}")
            self.sim.set_pilot_assist(self.current_pilot_assist_level)

    # --------------------------------------------------------------------------
    # Platform Movement
    # --------------------------------------------------------------------------
    def move_platform(self, transform):
        """
        Convert transform to muscle moves.
        """
        if self.state == "deactivated":
            return
        # apply inversion
        transform = [inv * axis for inv, axis in zip(self.invert_axis, transform)]
        request = self.dynam.regulate(transform)
        if self.swap_roll_pitch:
            # swap roll/pitch
            request[0], request[1], request[3], request[4] = request[1], request[0], request[4], request[3]

        muscle_lengths = self.k.muscle_lengths(request)
        if not all(x == y for x, y in zip(muscle_lengths, self.muscle_lengths)):
            # print(f"Muscle Lengths: {muscle_lengths}")
            self.muscle_lengths = muscle_lengths
        #self.muscle_lengths = self.k.muscle_lengths(request)
        
        # output actuator command (physical platform) only if enabled
        if not self.virtual_only_mode:
            self.muscle_output.set_muscle_lengths(self.muscle_lengths)

        # Always echo to Unity for digital twin sync
        pose = self.k.get_pose()
        self.echo(request, self.muscle_lengths, pose)

        return self.muscle_lengths
        
    # --------------------------------------------------------------------------
    # Platform State Machine 
    # --------------------------------------------------------------------------
     
    def update_state(self, new_state):
        """
        Valid transitions:
          initialized → deactivated  
          deactivating → deactivated  
          deactivated → activating  
          activating → enabled  
          enabled → running, paused, deactivating  
          running → paused, deactivating  
          paused → running, deactivating
        """

        if new_state == self.state:
            return  # No state change needed

        log.debug(f"in update_state, new state is {new_state}")

        # Define valid state transitions
        valid_transitions = {
            "initialized": ["deactivated", "deactivating"],
            "deactivating": ["deactivated"],
            "deactivated": ["activating"],
            "activating": ["enabled"],
            "enabled": ["running", "paused", "deactivating"],
            "running": ["paused", "deactivating"],
            "paused": ["running", "deactivating"]
        }

        if new_state not in valid_transitions.get(self.state, []):
            log.warning("Invalid transition: %s → %s", self.state, new_state)
            return

        old_state = self.state
        self.state = new_state
        log.debug("Core: Platform state changed from %s to %s", old_state, new_state)
        self.platformStateChanged.emit(self.state)

        # State-specific handling
        if new_state == 'activating':
            transform = self.sim.read()
            log.debug(f"in activating, transforms: {transform}")
            if transform:
                transform = [
                    transform[i] * self.gains[i] * self.master_gain * (self.intensity_percent / 100.0)
                    for i in range(6)
                ]
                end_lengths = self.k.muscle_lengths(self.dynam.regulate(transform))
                
            else:
                end_lengths = self.cfg.PLATFORM_NEUTRAL_MUSCLE_LENGTHS
            self.start_transition("activating", end_lengths)    

        elif new_state == 'enabled':
            log.info("Platform is now enabled.")

        elif new_state == 'deactivating':
            self.start_transition("deactivating", self.cfg.DEACTIVATED_MUSCLE_LENGTHS)

        elif new_state == 'deactivated':
            log.debug("Platform is now fully deactivated.")

        elif new_state == 'running':
            self.sim.run()

        elif new_state == 'paused':
            self.sim.pause()



    # --------------------------------------------------------------------------
    # Error Handling
    # --------------------------------------------------------------------------
    def handle_error(self, exc, context=""):
        msg = f"{context} - {exc}"
        log.error(msg)
        log.error(traceback.format_exc())
        self.fatal_error.emit(msg)
        self.simStatusChanged.emit(msg)

    def emit_status(self, status):
        self.simStatusChanged.emit(status)

    # --------------------------------------------------------------------------
    # Additional methods: slow_move, echo, remote controls, etc. 
    # (Omitted here for brevity but you can copy them in full from original code.)
    # --------------------------------------------------------------------------

    def cleanup_on_exit(self):
        print("cleaning up")   

def sleep_qt(delay):
    """ 
    Sleep for the specified delay in seconds using Qt event loop.
    Ensures the GUI remains responsive during the sleep period.
    """
    loop = QtCore.QEventLoop()
    timer = QtCore.QTimer()
    timer.setInterval(int(delay*1000))
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start()
    loop.exec_()
    

# Configure logging
def setup_logging():
    # Check if running on Windows
    is_windows = os.name == 'nt'

    # Ensure proper line endings only on Unix-like systems
    if not is_windows:
        sys.stdout.reconfigure(encoding='utf-8', newline='\n')

    # Define logging format
    log_format = "%(asctime)s [%(levelname)s] %(message)s"
    if not is_windows:
        log_format += '\n'  # Append newline only if NOT Windows

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt="%H:%M:%S"
    )

if __name__ == "__main__":
    setup_logging()
    log = logging.getLogger(__name__)  

    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # app.setAttribute(Qt.AA_EnableHighDpiScaling)
    # app.setAttribute(Qt.AA_UseHighDpiPixmaps)
    # QtWidgets.QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)


    core = SimInterfaceCore()
    ui = MainWindow(core)

    switches_comport = sim_config.get_switch_comport(os.name)
    if switches_comport != None:
        ui.switches_begin(switches_comport)
    
    core.setup()
    if os.name == 'posix':
        ui.showFullScreen()
    else:    
        ui.show()
    sys.exit(app.exec_())
