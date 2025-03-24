#!/usr/bin/env python3

# sim_interface_core.py

import os
import sys
import math
import traceback
import logging
import importlib

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import QTimer, Qt

""" directory structure
siminterface folder structure 

├── sim_interface_core.py 
├── sim_interface_ui.py
├── SimInterface.ui
├── sim_config.py
├── sims/
│   ├── xplane.py
│   ├── xplane_itf.py
│   ├── xplane_cfg.py
│   └── ...
├── kinematics/
│   ├── kinematicsV2.py
│   ├── dynamics.py
│   ├── cfg_SuspendedChair.py
│   ├── cfg_SlidingActuators.py
│   └── ...
├── output/
│   ├── d_to_p.py
│   ├── muscle_output.py
│   └── ...
├── common/
│   ├── udp_tx_rx.py
│   ├── serial_switch_reader.py
│   └── ...
└── ...
"""


from sim_config import selected_sim, platform_config, switches_comport
from siminterface_ui import MainWindow
#naming#from kinematics.kinematicsV2 import Kinematics
from kinematics.kinematics_V2SP import Kinematics
from kinematics.dynamics import Dynamics
import output.d_to_p as d_to_p
#naming#from output.muscle_output import MuscleOutput
from output.muscle_output import MuscleOutput


class SimInterfaceCore(QtCore.QObject):
    """
    Core logic for controlling platform from simulations.

    Responsibilities:
      - Loading platform config (chair/slider).
      =	Handles platform state management, simulation data updates, and communication with xplane.py
      - Runs a QTimer to periodically read sim data (data_update).
      -	Handles intensity, skill, and mode changes (intensityChanged(), modeChanged(), skillLevelChanged()).
      - Notifies the UI of simulation state (simStatusChanged).
      - Converting transforms -> muscle movements via kinematics, d_to_p, etc.
    """

    # Signals to inform the UI
    simStatusChanged = QtCore.pyqtSignal(str)          # e.g., "Connected", "Not Connected", ...
    logMessage = QtCore.pyqtSignal(str)                # general logs or warnings to display in UI
    dataUpdated = QtCore.pyqtSignal(object)            # passing transforms or status to the UI
    platformStateChanged = QtCore.pyqtSignal(str)      # "enabled", "disabled", "running", "paused"

    def __init__(self, parent=None):
        super().__init__(parent)

        # Simulation references
        self.sim = None # the sim to run (xplane 11)
        self.current_skill_level = None
        self.current_mode = None # this is the currently selected flight situation (or ride if roller coaster) 

        # Timer for periodic data updates
        self.data_timer = QTimer(self)
        self.data_timer.timeout.connect(self.data_update)
        self.data_timer.setTimerType(QtCore.Qt.PreciseTimer)
        self.data_period_ms = 50

        # Basic flags and states
        self.is_started = False      # True after platform config and sim are loaded
        self.is_output_enabled = False
        self.state = 'initialized'    # runtime platform states: disabled, enabled, running, paused

        # Default transforms
        self.transform = [0, 0, -1, 0, 0, 0]
        self.prev_distances = [0]*6

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


    # --------------------------------------------------------------------------
    # set up configurations
    # --------------------------------------------------------------------------
    def setup(self):
        self.load_config()
        self.load_sim()
        
        if self.is_started:
            # Start the data update timer if the sim interface class for xplane loaded successfully
            self.data_timer.start(self.data_period_ms)
            log.info("Core: data timer started at %d ms period", self.data_period_ms)
    
        logging.info("Core: Initialization complete. Emitting 'initialized' state.")
        self.platformStateChanged.emit("initialized")  
        
    # --------------------------------------------------------------------------
    # Platform Config
    # --------------------------------------------------------------------------
    def load_config(self):
        """
        Imports the platform config (chair or slider). Then sets up Kinematics, DtoP, MuscleOutput.
        """
        try:
            import importlib
            # platform configuration path (platform_config) is defined in sim_config.py
            cfg_module = importlib.import_module(platform_config) 
            self.cfg = cfg_module.PlatformConfig()
            log.info("Core: Imported cfg from %s", platform_config)
        except Exception as e:
            self.handle_error(e, f"Unable to import platform config from {platform_config}, check sim_config.py")
            return

        # Initialize the distance->pressure converter
        self.DtoP = d_to_p.D_to_P(self.cfg.MUSCLE_LENGTH_RANGE, self.cfg.MAX_MUSCLE_LENGTH)
        self.muscle_output = MuscleOutput(self.DtoP.muscle_length_to_pressure, sleep_qt,
                            "192.168.0.10",self.cfg.MAX_MUSCLE_LENGTH, self.cfg.MUSCLE_LENGTH_RANGE ) 
                
        # Hardcoded Festo IP in example above—change if needed or pass as param

        # Setup kinematics
        self.k = Kinematics()
        self.cfg.calculate_coords()
        self.k.set_geometry(self.cfg.BASE_POS, self.cfg.PLATFORM_POS)

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

        self.invert_axis = self.cfg.INVERT_AXIS
        self.swap_roll_pitch = self.cfg.SWAP_ROLL_PITCH

        self.dynam = Dynamics()
        self.dynam.begin(self.cfg.LIMITS_1DOF_TRANFORM, "shape.cfg")

        # Load distance->pressure file
        try:
            if self.DtoP.load(self.cfg.MUSCLE_PRESSURE_MAPPING_FILE):
                log.info("Core: Muscle pressure mapping table loaded.")
        except Exception as e:
            self.handle_error(e, "Error loading Muscle pressure mapping table ")

        log.info("Core: %s config data loaded", platform_config)
        self.simStatusChanged.emit("Config Loaded")

    # --------------------------------------------------------------------------
    # Simulation Management
    # --------------------------------------------------------------------------
    def load_sim(self):
        """
        Loads or re-loads a simulation by index from available_sims.
        """
        self.sim_name, self.sim_class, self.sim_image, self.sim_ip_address = selected_sim # see sim_config.py for options
        sim_path = "sims." + self.sim_class

        try:
            sim_module = importlib.import_module(sim_path)
            frame = None # this version does not allocate a UI frame
            self.sim = sim_module.Sim(sleep_qt, frame, self.emit_status)
            if self.sim:
                self.is_started = True
                log.info("Core: Instantiated sim '%s' from class '%s'", self.sim.name, self.sim_class)

            self.simStatusChanged.emit(f"Sim '{self.sim_name}' loaded.")
            self.sim.set_default_address(self.sim_ip_address)
        except Exception as e:
            self.handle_error(e, f"Unable to load sim from {sim_path}")

    def connect_sim(self):
        """
        Connects to the loaded sim. 
        """
        if not self.sim:
            self.simStatusChanged.emit("No sim loaded")
            return
        if not self.sim.is_Connected(): 
            try:
                self.sim.connect()
                # self.simStatusChanged.emit("Sim connected")
                self.state = 'disabled'  # default
                # Possibly set washout times
                washout_times = self.sim.get_washout_config()
                for idx in range(6):
                    self.dynam.set_washout(idx, washout_times[idx])
                self.sim.set_washout_callback(self.dynam.get_washed_telemetry)
                # self.sim.run()

            except Exception as e:
                self.handle_error(e, "Error connecting sim")
                sleep_qt(1)

    # --------------------------------------------------------------------------
    # QTimer Update Loop
    # --------------------------------------------------------------------------
    def data_update(self):

        """
        Periodically called to read from sim and move platform if enabled.
        """
        if not self.is_started:
            # don't do anything if loading config and sim failed
            self.simStatusChanged.emit(f"Sim interface failed to start")
            print("Sim interface failed to start")
            return
            
        # read transform from the sim
        transform = self.sim.read()
        if transform is None:
            return

        for idx in range(6): 
            gain = self.gains[idx] * self.master_gain
            self.transform[idx] = transform[idx] * gain
        # If platform is enabled (self.is_output_enabled), do the kinematics & muscle output
        if self.is_output_enabled:
            self.move_platform(self.transform)   
        # Emit updated data for the UI
        conn_status, data_status, system_state = self.sim.get_connection_state()
        self.dataUpdated.emit((self.transform, conn_status, data_status, system_state))

    def update_gain(self, index, value):
        """
        Updates the gain based on the slider change.
        """
        if index == 6:  # index 6 corresponds to the master gain
            self.master_gain = value *.01
        else:
            self.gains[index] = value *.01

    def intensityChanged(self, percent):
        print(f"intensity changed to {percent}%")
        
    def loadLevelChanged(self, load_level):
        print(f"load level changed to {load_level}, add code to pass this to output module")

    def modeChanged(self, mode_id):
        """
        Handles mode changes and ensures it is sent to X-Plane.
        """
        if mode_id != self.current_mode:
            self.current_mode = mode_id
            log.debug(f"Mode changed to {mode_id}")
            self.sim.set_scenario(self.current_mode, self.current_skill_level)

    def skillLevelChanged(self, skill_level):
        """
        Handles skill level changes and ensures it is sent to X-Plane.
        """
        if skill_level != self.current_skill_level:
            self.current_skill_level = skill_level
            log.debug(f"Skill level changed to {skill_level}")
            self.sim.set_scenario(self.current_mode, self.current_skill_level)

    # --------------------------------------------------------------------------
    # Platform Movement
    # --------------------------------------------------------------------------
    def move_platform(self, transform):
        """
        Convert transform to muscle moves.
        """
        # apply inversion
        transform = [inv * axis for inv, axis in zip(self.invert_axis, transform)]
        request = self.dynam.regulate(transform)
        if self.swap_roll_pitch:
            # swap roll/pitch
            request[0], request[1], request[3], request[4] = request[1], request[0], request[4], request[3]

        muscle_lengths = self.k.muscle_lengths(request)
        # slider vs. chair
        if self.is_slider:
            percents = muscle_lengths
            self.muscle_output.move_percent(percents)
        else:
            self.muscle_output.set_muscle_lengths(muscle_lengths)

        # Optionally echo or broadcast:
        # self.echo(request, distances, self.k.get_pose())

    # --------------------------------------------------------------------------
    # Platform State Machine 
    # --------------------------------------------------------------------------

    def update_state(self, new_state):
        """
        Valid transitions:
        - Disabled → Enabled (only)
        - Enabled → Running, Paused, Disabled
        - Running → Paused, Disabled
        - Paused → Running, Disabled
        """

        if new_state == self.state:
            return  # No change needed
        
        # Enforce allowed transitions
        valid_transitions = {
            "initialized": ["disabled"],  
            "disabled": ["enabled"],
            "enabled": ["running", "paused", "disabled"],
            "running": ["paused", "disabled"],
            "paused": ["running", "disabled"]
        }
        
        if new_state not in valid_transitions.get(self.state, []):
            log.warning("Invalid transition: %s → %s", self.state, new_state)
            return  # Invalid transition

        old_state = self.state
        self.state = new_state
        log.debug("Core: Platform state changed from %s to %s", old_state, new_state)
        self.platformStateChanged.emit(self.state)

        # Handle transitions
        if new_state == 'enabled':
            self.activate_platform()
        elif new_state == 'disabled':
            self.deactivate_platform()
        elif new_state == 'running':
            self.sim.run()
        elif new_state == 'paused':
            self.sim.pause()

    def activate_platform(self):
        log.debug("Core: activating platform")
        self.is_output_enabled = True

        start_pos = self.muscle_output.get_muscle_lengths()  # Get the platform's current position
        end_pos = self.cfg.PLATFORM_MID_MUSCLE_LENGTHS # Target mid position

        def new_target():
            if self.state != "enabled":  # If state changes, return new end position
                return self.cfg.DISABLED_MUSCLE_LENGTHS if self.state == "disabled" else None
            return None

        self.muscle_output.slow_move(start_pos, end_pos, 5, new_target)


    def deactivate_platform(self):
        log.debug("Core: deactivating platform")
        self.is_output_enabled = False
        if not self.muscle_output:
            return # ignore this if output module has not yet been initialized
        start_pos = self.muscle_output.get_muscle_lengths()  # Get current position
        end_pos = self.cfg.DISABLED_MUSCLE_LENGTHS  # Target down position
        def new_target():
            if self.state != "disabled":  # If state changes, return new end position
                return self.cfg.PLATFORM_MID_MUSCLE_LENGTHS if self.state == "enabled" else None
            return None

        self.muscle_output.slow_move(start_pos, end_pos, 5, new_target)

    # --------------------------------------------------------------------------
    # Error Handling
    # --------------------------------------------------------------------------
    def handle_error(self, exc, context=""):
        msg = f"{context} - {exc}"
        log.error(msg)
        log.error(traceback.format_exc())
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
    log.info("Starting SimInterface with separated UI and Core")

    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # app.setAttribute(Qt.AA_EnableHighDpiScaling)
    # app.setAttribute(Qt.AA_UseHighDpiPixmaps)
    # QtWidgets.QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)


    core = SimInterfaceCore()
    ui = MainWindow(core)

    ui.switches_begin(switches_comport)
    core.setup()
    ui.show()
    
    sys.exit(app.exec_())
