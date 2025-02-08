# sim_interface_core.py

import os
import sys
import math
import traceback
import logging
import importlib

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import QTimer

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
│   ├── TestSim.py
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
│   └── ...
└── ...
"""


from sim_config import selected_sim, platform_config
from siminterface_ui import MainWindow
from kinematics.kinematicsV2 import Kinematics
from kinematics.dynamics import Dynamics
import output.d_to_p as d_to_p
from output.muscle_output import MuscleOutput
from sims.TestSim import Sim as TestSim



class SimInterfaceCore(QtCore.QObject):
    """
    Core logic (business) for controlling platform from simulations.

    Responsibilities:
      - Loading platform config (chair/slider).
      - Loading and connecting to default or selected sim.
      - Running a QTimer to periodically read sim data (data_update).
      - Converting transforms -> muscle movements via kinematics, d_to_p, etc.
      - Platform state machine (enabled, disabled, running, paused).
    """

    # Signals to inform the UI
    simStatusChanged = QtCore.pyqtSignal(str)          # e.g., "Connected", "Not Connected", ...
    logMessage = QtCore.pyqtSignal(str)                # general logs or warnings to display in UI
    dataUpdated = QtCore.pyqtSignal(object)            # passing transforms or status to the UI
    platformStateChanged = QtCore.pyqtSignal(str)      # "enabled", "disabled", "running", "paused"

    def __init__(self, parent=None):
        super().__init__(parent)

        # Simulation references
        self.sim = None
        self.simserver_addr = "127.0.0.1"   # fallback, can be replaced if simserver_cfg found

        # Timer for periodic data updates
        self.data_timer = QTimer(self)
        self.data_timer.timeout.connect(self.data_update)
        self.data_timer.setTimerType(QtCore.Qt.PreciseTimer)
        self.data_period_ms = 50

        # Basic flags and states
        self.is_started = False      # True after platform config and sim are loaded
        self.is_output_enabled = False
        self.state = 'disabled'    # platform states: disabled, enabled, running, paused

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
        self.load_test_tab()
        
        if self.is_started:
            # Start the data update timer if the loading methods succedded
            self.data_timer.start(self.data_period_ms)
            log.info("Core: data timer started at %d ms period", self.data_period_ms)
    

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
        self.DtoP = d_to_p.D_to_P(200)
        self.muscle_output = MuscleOutput(self.DtoP.distance_to_pressure, sleep_qt, "192.168.0.10")
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
                self.cfg.MIN_ACTUATOR_LEN,
                self.cfg.MAX_ACTUATOR_LEN,
                self.cfg.FIXED_LEN
            )
            self.is_slider = False

        self.invert_axis = self.cfg.INVERT_AXIS
        self.swap_roll_pitch = self.cfg.SWAP_ROLL_PITCH

        self.dynam = Dynamics()
        self.dynam.begin(self.cfg.limits_1dof, "shape.cfg")

        # Load distance->pressure file
        try:
            if self.DtoP.load(self.cfg.DISTANCE_TO_PRESSURE_TABLE):
                log.info("Core: Distance to Pressure table loaded.")
        except Exception as e:
            self.handle_error(e, "Error loading DtoP file")

        log.info("Core: %s config data loaded", platform_config)
        self.simStatusChanged.emit("Config Loaded")

    
    def load_test_tab(self):
        return  # TODO
        try:
            frame = MainWindow.frm_tester
            self.tester = testSim(sleep_qt, frame, self.emit_status)
            if self.sim:
                self.is_started = True
                log.info("Core: Instantiated sim '%s' from class '%s'", self.sim.name, self.sim_class)

            self.simStatusChanged.emit(f"Sim '{self.sim_name}' loaded.")
        except Exception as e:
            self.handle_error(e, f"Unable to load tester tab")

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
                self.sim.run()

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

    def loadLevelChanged(self, load_level):
        print(f"load level changed to {load_level}, add code to pass this to output module")

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

        distances = self.k.actuator_lengths(request)
        # slider vs. chair
        if self.is_slider:
            percents = self.k.actuator_percents(request)
            self.muscle_output.move_percent(percents)
        else:
            self.muscle_output.move_distance(distances)

        # Optionally echo or broadcast:
        # self.echo(request, distances, self.k.get_pose())

    # --------------------------------------------------------------------------
    # Platform State Machine
    # --------------------------------------------------------------------------
    def update_state(self, new_state):
        """
        A generic state machine approach for 'disabled', 'enabled', 'running', 'paused'.
        """
        if new_state == self.state:
            return
        old_state = self.state
        self.state = new_state
        log.debug("Core: Platform state changed from %s to %s", old_state, new_state)
        self.platformStateChanged.emit(self.state)

        # handle transitions
        if new_state == 'enabled':
            self.enable_platform()
        elif new_state == 'disabled':
            self.disable_platform()
        elif new_state == 'running':
            self.sim.run()
        elif new_state == 'paused':
            self.sim.pause()

    def enable_platform(self):
        """
        Example code from your original approach.
        """
        log.debug("Core: enabling platform")
        self.is_output_enabled = True
        # If needed, do slow_move from DISABLED_DISTANCES to current transform

    def disable_platform(self):
        log.debug("Core: disabling platform")
        self.is_output_enabled = False
        # If needed, do slow_move from current transform to DISABLED_DISTANCES

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
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )


if __name__ == "__main__":
    setup_logging()
    log = logging.getLogger(__name__)  
    log.info("Starting SimInterface with separated UI and Core")

    app = QtWidgets.QApplication(sys.argv)

    core = SimInterfaceCore()
    ui = MainWindow(core)

    ui.show()
    core.setup()
    
    sys.exit(app.exec_())
