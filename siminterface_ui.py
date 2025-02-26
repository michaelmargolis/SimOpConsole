# sim_interface_ui.py


import os
import platform
import logging
from PyQt5 import QtWidgets, uic, QtCore, QtGui 
from common.serial_switch_reader import SerialSwitchReader

log = logging.getLogger(__name__)

Ui_MainWindow, _ = uic.loadUiType("SimInterface_1280.ui")

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
        self.btn_fly.clicked.connect(self.on_btn_fly_clicked)
        self.btn_pause.clicked.connect(self.on_btn_pause_clicked)
        
        #intensity
        self.intensity_button_group = QtWidgets.QButtonGroup(self)
        self.intensity_button_group.addButton(self.btn_intensity_motionless, 0)
        self.intensity_button_group.addButton(self.btn_intensity_mild, 1)
        self.intensity_button_group.addButton(self.btn_intensity_full, 2)
        self.intensity_button_group.buttonClicked[int].connect(self.on_intensity_changed)
        
        # flight selection
        self.flight_button_group = QtWidgets.QButtonGroup(self)
        self.flight_button_group.addButton(self.btn_level, 0)
        self.flight_button_group.addButton(self.btn_takeoff, 1)
        self.flight_button_group.addButton(self.btn_land, 2)
        self.flight_button_group.buttonClicked[int].connect(self.on_flight_changed)
   
        # experience levels
        self.exp_button_group = QtWidgets.QButtonGroup(self)
        self.exp_button_group.addButton(self.btn_novice, 0)
        self.exp_button_group.addButton(self.btn_mid_exp, 1)
        self.exp_button_group.addButton(self.btn_ace, 2)
        self.exp_button_group.buttonClicked[int].connect(self.on_experience_changed)

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
        
        # configure interface to hardware switches
        #switch events: fly, pause, enable, intensity, load, experience, flight 
        event_callbacks = [
            lambda state: self.on_btn_fly_clicked(state),  # Fly
            lambda state: self.on_btn_pause_clicked(state),  # Pause
            lambda state: self.on_activate_toggled(state),  # Activate
            lambda level: self.on_experience_changed(level, from_hardware=True),  # Experience
            lambda flight: self.on_flight_changed(flight, from_hardware=True),  # Flight
            lambda load: self.on_load_level_selected(load, from_hardware=True),  # Load
            lambda intensity: self.on_intensity_changed(intensity, from_hardware=True)  # Intensity
        ]
        self.switch_reader = SerialSwitchReader(event_callbacks, self.on_sim_status_changed)
        
        # Additional initialization
        self.configure_ui_defaults()
        log.info("MainWindow: UI initialized")

    def closeEvent(self, event):
        """ Overriding closeEvent to handle exit actions """
        reply = QtWidgets.QMessageBox.question(
            self,
            "Exit Confirmation",
            "Are you sure you want to exit?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No
        )

        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            self.core.cleanup_on_exit()
            event.accept()  # Proceed with closing
        else:
            event.ignore()  # Prevent closing
            
    def configure_ui_defaults(self):
        """
        Setup initial states or text for the UI elements.
        """
        self.lbl_sim_status.setText("Starting ...")
        self.tab_test.setEnabled(False)


    # --------------------------------------------------------------------------
    # UI -> Core Methods
    # --------------------------------------------------------------------------

    def on_btn_fly_clicked(self, state=None):
        """
        Called when the "Fly" button is pressed (UI) or when the hardware switch state changes.

        :param state: (Optional) Boolean representing the hardware switch state.
        """
        if state is not None and not state:
            return  # Ignore button release

        log.debug("UI: user wants to run platform")
        self.core.update_state("running")

        # Update UI button state
        QtWidgets.QApplication.instance().postEvent(
            self, QtCore.QEvent(QtCore.QEvent.User)
        )
        self.btn_fly.setChecked(True)


    def on_btn_pause_clicked(self, state=None):
        """
        Called when the "Pause" button is pressed (UI) or when the hardware switch state changes.
        """
        if state is not None and not state:
            return  # Ignore button release

        log.debug("UI: user wants to pause platform")
        self.core.update_state("paused")

        # Update UI button state
        QtWidgets.QApplication.instance().postEvent(
            self, QtCore.QEvent(QtCore.QEvent.User)
        )
        self.btn_pause.setChecked(True)

    def on_experience_changed(self, level, from_hardware=False):
        """
        Called when an experience level button is toggled from the UI or hardware.
        """
        log.debug(f"Experience level changed to {level}")

        self.core.experienceLevelChanged(f"experience_{level}")

        # If triggered by hardware, update the UI button
        if from_hardware:
            QtWidgets.QApplication.instance().postEvent(
                self, QtCore.QEvent(QtCore.QEvent.User)
            )
            self.btn_novice.setChecked(level == 0)
            self.btn_mid_exp.setChecked(level == 1)
            self.btn_ace.setChecked(level == 2)


    def on_flight_changed(self, flight_id, from_hardware=False):
        """
        Called when a flight selection button is changed, either from UI or hardware.
        """
        log.debug(f"Flight mode changed to {flight_id}")

        self.core.flightChanged(flight_id)

        # If triggered by hardware, update the UI button
        if from_hardware:
            QtWidgets.QApplication.instance().postEvent(
                self, QtCore.QEvent(QtCore.QEvent.User)
            )
            self.flight_button_group.button(flight_id).setChecked(True)


    def on_intensity_changed(self, intensity_index, from_hardware=False):
        """
        Called when an intensity selection button is changed, either from UI or hardware.
        """
        log.debug(f"Intensity level changed to {intensity_index}")

        # Corrected logic for intensity levels
        intensity_map = {0: 0, 1: 30, 2: 100}
        self.sld_intensity.setValue(intensity_map.get(intensity_index, 0))

        # If triggered by hardware, update the UI button
        if from_hardware:
            QtWidgets.QApplication.instance().postEvent(
                self, QtCore.QEvent(QtCore.QEvent.User)
            )
            self.intensity_button_group.button(intensity_index).setChecked(True)


    def on_load_level_selected(self, load_level, from_hardware=False):
        """
        Called when a load level button is clicked, either from UI or hardware.
        """
        log.debug(f"Load level changed to {load_level}")

        self.core.loadLevelChanged(load_level)

        # If triggered by hardware, update the UI button
        if from_hardware:
            QtWidgets.QApplication.instance().postEvent(
                self, QtCore.QEvent(QtCore.QEvent.User)
            )
            self.load_button_group.button(load_level).setChecked(True)


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
    
    def on_capture_csv_changed(self, state):
        # e.g., user toggles CSV capture
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
        This method now also polls the serial reader for new switch states.

        Args:
            data (tuple): Contains (x, y, z, roll, pitch, yaw) values.
        """
        # Call the serial reader to process all available messages
        self.switch_reader.poll()

        # Existing transform update logic
        transform, conn_status, data_status, system_state = data
        for idx in range(6): 
            self.transfrm_levels[idx].setValue(round(transform[idx] * 100))

        images_dir = 'images'
        status_to_image = {
            'ok': 'ok.png',
            'warning': 'warning.png',
            'nogo': 'nogo.png'
        }

        def load_icon(status):
            image_file = status_to_image.get(status)
            if image_file:
                image_path = os.path.join(images_dir, image_file)
                if os.path.exists(image_path):
                    return QtGui.QIcon(image_path)
            return None

        connection_icon = load_icon(conn_status)
        if connection_icon:
            self.ico_connection.setPixmap(connection_icon.pixmap(32, 32))

        data_icon = load_icon(data_status)
        if data_icon:
            self.ico_data.setPixmap(data_icon.pixmap(32, 32))

    def update_button_style(self, button, state, base_color, text_color, border_color):
        """
        Dynamically updates a button's appearance based on its state.

        :param button: The QPushButton (or QCheckBox) to update.
        :param state: The current state of the button ("default", "active").
        :param base_color: The base color when the button is in the active state.
        :param text_color: The text color when the button is in the default state.
        :param border_color: The border color to apply to the button.
        """
        is_linux = platform.system() == "Linux"
        padding = 10 if is_linux else 8  # Adjust padding for Linux vs Windows

        if state == "active":
            style = f"""
                QPushButton {{
                    background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1,
                                                      stop:0 {base_color}, stop:1 dark{base_color});
                    color: {text_color};
                    border: 2px solid {border_color};
                    border-radius: 5px;
                    padding: {padding}px;
                    font-weight: bold;
                    border-bottom: 3px solid black;
                    border-right: 3px solid {border_color};
                }}
                QPushButton:pressed {{
                    background-color: qlineargradient(spread:pad, x1:0, y1:1, x2:1, y2:0,
                                                      stop:0 dark{base_color}, stop:1 black);
                    border-bottom: 1px solid {border_color};
                    border-right: 1px solid black;
                }}
            """
        else:  # Default state
            style = f"""
                QPushButton {{
                    background-color: none;
                    color: {text_color};
                    border: 2px solid {border_color};
                    border-radius: 5px;
                    padding: {padding}px;
                    font-weight: bold;
                    border-bottom: 3px solid black;
                    border-right: 3px solid {border_color};
                }}
                QPushButton:pressed {{
                    background-color: {base_color};
                    color: {text_color};
                    border-bottom: 1px solid {border_color};
                    border-right: 1px solid black;
                }}
            """

        button.setStyleSheet(style)

    @QtCore.pyqtSlot(str)
    def on_platform_state_changed(self, new_state):
        """
        Reflect platform states in the UI (enabled, disabled, running, paused).
        """
        log.info("UI: platform state is now '%s'", new_state)

        # Enable/Disable Fly & Pause buttons
        if new_state == "enabled":
            self.btn_pause.setEnabled(True)
            self.btn_fly.setEnabled(True)
        elif new_state == "disabled":
            self.btn_pause.setEnabled(False)
            self.btn_fly.setEnabled(False)

        # Update Fly Button Style
        if new_state == "running":
            self.update_button_style(self.btn_fly, "active", "green", "white", "darkgreen")
        else:
            self.update_button_style(self.btn_fly, "default", "green", "green", "green")

        # Update Pause Button Style
        if new_state == "paused":
            self.update_button_style(self.btn_pause, "active", "orange", "black", "darkorange")
        else:
            self.update_button_style(self.btn_pause, "default", "orange", "orange", "orange")


    def on_activate_toggled(self, physical_state=None):
        """
        Called when "Activated/Deactivated" GUI toggle is clicked OR when a physical toggle switch state changes.
        """
        if physical_state is not None:
            self.chk_activate.setChecked(physical_state)

        if self.chk_activate.isChecked():
            self.chk_activate.setText("ACTIVATED")
            self.core.update_state("enabled")
        else:
            self.chk_activate.setText("INACTIVE")
            self.core.update_state("disabled")


    def switches_begin(self, port):
        self.switch_reader.begin(port)

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
        
