# sim_interface_ui.py

import os
import logging
from PyQt5 import QtWidgets, uic, QtCore, QtGui 

log = logging.getLogger(__name__)

Ui_MainWindow, _ = uic.loadUiType("SimInterface.ui")

class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    """
    GUI class that wires user actions to the core logic in SimInterfaceCore.
    """

    def __init__(self, core, parent=None):
        super().__init__(parent)
        self.core = core  # reference to the business logic
        self.setupUi(self)

        # connect signals from core to UI
        self.core.simStatusChanged.connect(self.on_sim_status_changed)
        self.core.dataUpdated.connect(self.on_data_updated)
        self.core.platformStateChanged.connect(self.on_platform_state_changed)

        # connect signals from UI to core methods
        self.btn_run.clicked.connect(self.on_btn_run_clicked)
        self.btn_pause.clicked.connect(self.on_btn_pause_clicked)
        
        self.btn_intensity_motionless.clicked.connect(self.on_btn_motionless)
        self.btn_intensity_gentle.clicked.connect(self.on_btn_gentle)
        self.btn_intensity_moderate.clicked.connect(self.on_btn_moderate)
        self.btn_intensity_full.clicked.connect(self.on_btn_full)

        # Create load setting button Group
        self.load_button_group = QtWidgets.QButtonGroup(self)
        self.load_button_group.addButton(self.btn_light_load, 0)
        self.load_button_group.addButton(self.btn_moderate_load, 1)
        self.load_button_group.addButton(self.btn_heavy_load, 2)
        self.load_button_group.buttonClicked[int].connect(self.on_load_level_selected)
        
        self.chk_activate.clicked.connect(self.on_activate_toggled)
        self.chk_capture_csv.stateChanged.connect(self.on_capture_csv_changed)

        slider_names = [f'sld_gain_{i}' for i in range(6)] + ['sld_gain_master']
        for name in slider_names:
            slider = getattr(self, name)
            slider.valueChanged.connect(lambda value, s=name: self.on_slider_value_changed(s, value))
        self.transfrm_levels = [self.sld_xform_0, self.sld_xform_1, self.sld_xform_2, self.sld_xform_3, self.sld_xform_4, self.sld_xform_5  ]
        
        # Additional initialization
        self.configure_ui_defaults()
        log.info("MainWindow: UI initialized")

    def configure_ui_defaults(self):
        """
        Setup initial states or text for the UI elements.
        """
        self.lbl_sim_status.setText("Starting ...")
        self.tab_test.setEnabled(False)


    # --------------------------------------------------------------------------
    # UI -> Core Methods
    # --------------------------------------------------------------------------

    def on_btn_run_clicked(self):
        """
        Called when "Run" button is pressed.
        Possibly update core's platform state to "running".
        """
        log.debug("UI: user wants to run platform")
        self.core.update_state("running")

    def on_btn_pause_clicked(self):
        """
        Called when "Pause" is pressed.
        """
        log.debug("UI: user wants to pause platform")
        self.core.update_state("paused")

    def on_activate_toggled(self):
        """
        Called when "Activated/Deactivated" toggle is clicked.
        """
        if self.chk_activate.isChecked():
            self.core.update_state("enabled")
        else:
            self.core.update_state("disabled")

    def on_slider_value_changed(self, slider_name, value):
        """
        Handles the gain slider value change event.
        """
        if slider_name == 'sld_gain_master':
            index = 6
        else:
            index = int(slider_name.split('_')[-1])

        # send the slider index and value to the core
        # note value range is +- 100 and is converted to +-1 in core
        self.core.update_gain(index, value)

    def on_load_level_selected(self, load_level):
        """
        Called when a load level button is clicked.
        Emits the selected load level to the core.
        """
        self.core.loadLevelChanged(load_level)
        
    def on_btn_motionless(self):
        self.sld_intensity.setValue(0)

    def on_btn_gentle(self):
        self.sld_intensity.setValue(25)

    def on_btn_moderate(self):
        self.sld_intensity.setValue(60)

    def on_btn_full(self):
        self.sld_intensity.setValue(100)

    def on_capture_csv_changed(self, state):
        # e.g., user toggles CSV capture
        pass

    def on_sim_combo_changed(self, index):
        """
        Combo box changed. We store or pass this to core on "Load Sim".
        """
        pass

    # --------------------------------------------------------------------------
    # Core -> UI Methods (slots)
    # --------------------------------------------------------------------------
    @QtCore.pyqtSlot(str)
    def on_sim_status_changed(self, status_msg):
        self.lbl_sim_status.setText(status_msg)

    @QtCore.pyqtSlot(object)

    def on_data_updated(self, data):
        """
        Called every time the core's data_update fires (every 50 ms if running).
        Updates the transform display and status icons based on the provided statuses.

        Args:
            transform_data (tuple): Contains (x, y, z, roll, pitch, yaw) values.
            conn_status (str): Connection status ("ok", "warning", "nogo").
            data_status (str): Data status ("ok", "nogo").
            system_state (str): Current state of the system.
        """
        transform, conn_status, data_status, system_state = data
        for idx in range(6): 
            self.transfrm_levels[idx].setValue(round(transform[idx] * 100)) # set the UI transform indicators


        images_dir = 'images'
        # Map status to corresponding image filenames
        status_to_image = {
            'ok': 'ok.png',
            'warning': 'warning.png',
            'nogo': 'nogo.png'
        }

        # Helper function to load an icon
        def load_icon(status):
            image_file = status_to_image.get(status)
            if image_file:
                image_path = os.path.join(images_dir, image_file)
                if os.path.exists(image_path):
                    return QtGui.QIcon(image_path)
                else:
                    print(f"Image file '{image_path}' not found.")
            else:
                print(f"No image mapping found for status '{status}'.")
            return None

        # Load and set the connection icon
        connection_icon = load_icon(conn_status)
        if connection_icon:
            self.ico_connection.setPixmap(connection_icon.pixmap(32, 32))

        # Load and set the data icon
        data_icon = load_icon(data_status)
        if data_icon:
            self.ico_data.setPixmap(data_icon.pixmap(32, 32))


    @QtCore.pyqtSlot(str)
    def on_platform_state_changed(self, new_state):
        """
        Reflect platform states in the UI (enabled, disabled, running, paused).
        """
        log.info("UI: platform state is now '%s'", new_state)
        if new_state == "enabled":
            self.btn_pause.setEnabled(True)
            self.btn_run.setEnabled(True)
        elif new_state == "disabled":
            self.btn_pause.setEnabled(False)
            self.btn_run.setEnabled(False)


    # --------------------------------------------------------------------------
    # helper UI Methods 
    # --------------------------------------------------------------------------
    def sleep_qt(delay):
        # delay is time in seconds to sleep
        loop = QtCore.QEventLoop()
        timer = QtCore.QTimer()
        timer.setInterval(int(delay*1000))
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start()
        loop.exec_()
        
