import os
import platform
import logging
from PyQt5 import QtWidgets, uic, QtCore, QtGui
from typing import NamedTuple
from common.serial_switch_reader import SerialSwitchReader
from switch_ui_controller import SwitchUIController
from sims.shared_types import SimUpdate, AircraftInfo, ActivationTransition
from ui_widgets import ActivationButton, ButtonGroupHelper 

log = logging.getLogger(__name__)

Ui_MainWindow, _ = uic.loadUiType("SimInterface_1280.ui")

# Constants
XLATE_SCALE = 20
ROTATE_SCALE = 10

# Utility Functions
def load_icon_from_path(image_path):
    if os.path.exists(image_path):
        return QtGui.QIcon(image_path)
    return None


class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self, core=None, parent=None):
        super().__init__(parent)
        self.core = core
        self.setupUi(self)
        self.state = None
        self.MAX_ACTUATOR_RANGE = 100
        self.activation_percent = 0 # steps between 0 and 100 in slow moves when activated/deactivated  

        # Replace chk_activate with ActivationButton
        orig_btn = self.chk_activate
        geometry = orig_btn.geometry()
        style = orig_btn.styleSheet()
        parent = orig_btn.parent()
        activate_font = orig_btn.font()

        from ui_widgets import ActivationButton
        self.chk_activate = ActivationButton(parent)
        self.chk_activate.setGeometry(geometry)
        self.chk_activate.setStyleSheet(style)
        self.chk_activate.setFont(activate_font)
        self.chk_activate.setText("INACTIVE")
        orig_btn.deleteLater()

        self.connect_signals()
        self.init_buttons()
        self.initialize_intensity_controls()
        self.init_images()
        self.init_sliders()
        self.configure_ui()

        self.switch_controller = SwitchUIController(
            self.core,
            parent=self,
            status_callback=self.status_message,
            show_warning_callback=self.show_activate_warning_dialog,
            close_warning_callback=self.close_activate_warning_dialog
        )
        self.switch_controller.activateStateChanged.connect(self.on_hardware_activate_toggled)
        self.switch_controller.validActivateReceived.connect(self.on_valid_activate_received)
        self.switch_controller.activate_switch_invalid.connect(self.show_activate_warning_dialog)


    def connect_signals(self):
        self.core.simStatusChanged.connect(self.on_sim_status_changed)
        self.core.dataUpdated.connect(self.on_data_updated)
        self.core.activationLevelUpdated.connect(self.on_activation_transition)
        self.core.platformStateChanged.connect(self.on_platform_state_changed)
        self.btn_fly.clicked.connect(self.on_btn_fly_clicked)
        self.btn_pause.clicked.connect(self.on_btn_pause_clicked)
        self.chk_activate.clicked.connect(self.on_activate_toggled)

    def init_buttons(self):
        self.flight_button_group = ButtonGroupHelper(self, [(self.btn_mode_0, 0), (self.btn_mode_1, 1), (self.btn_mode_2, 2)], self.on_flight_mode_changed)
        self.exp_button_group = ButtonGroupHelper(self, [(self.btn_assist_0, 0), (self.btn_assist_1, 1), (self.btn_assist_2, 2)], self.on_pilot_assist_level_changed)
        self.load_button_group = ButtonGroupHelper(self, [(self.btn_light_load, 0), (self.btn_moderate_load, 1), (self.btn_heavy_load, 2)], self.on_load_level_selected)
        self.intensity_button_group = ButtonGroupHelper(self, [(self.btn_intensity_motionless, 0), (self.btn_intensity_mild, 1), (self.btn_intensity_full, 2)], self.on_intensity_changed)

    def init_images(self):
        self.front_pixmap = QtGui.QPixmap("images/cessna_rear.jpg")
        self.side_pixmap = QtGui.QPixmap("images/cessna_side_2.jpg")
        self.top_pixmap = QtGui.QPixmap("images/cessna_top.jpg")
        self.front_pos = self.lbl_front_view.pos()
        self.side_pos = self.lbl_side_view.pos()
        self.top_pos = self.lbl_top_view.pos()
        self.muscle_bars = [getattr(self, f"muscle_{i}") for i in range(6)]
        self.txt_muscles = [getattr(self, f"txt_muscle_{i}") for i in range(6)]
        self.cache_status_icons()
        # store right edge of muscle bar display
        self.muscle_base_right = []
        for i in range(6):
            line = getattr(self, f"muscle_{i}")
            right_edge = line.x() + line.width()
            self.muscle_base_right.append(right_edge)

    def init_sliders(self):
        self.transform_tracks = [getattr(self, f'transform_track_{i}') for i in range(6)]
        self.transform_blocks = [getattr(self, f'transform_block_{i}') for i in range(6)]

        # gain sldiers
        slider_names = [f'sld_gain_{i}' for i in range(6)] + ['sld_gain_master']
        for name in slider_names:
            slider = getattr(self, name)
            slider.valueChanged.connect(lambda value, s=name: self.on_slider_value_changed(s, value))
            

    def initialize_intensity_controls(self):
        """ Sets up Up/Down buttons and visual parameters for Mild intensity. """

        # Buttons to move the "Mild" intensity up and down
        self.btn_intensity_up.clicked.connect(lambda: self.move_mild_button(1))   # Move Up
        self.btn_intensity_down.clicked.connect(lambda: self.move_mild_button(-1))  # Move Down

        # Set the initial positions for the Up/Down buttons relative to Mild
        up_x = self.btn_intensity_mild.x()
        up_y = self.btn_intensity_mild.y() - self.btn_intensity_up.height()
        self.btn_intensity_up.move(up_x, up_y)

        down_x = self.btn_intensity_mild.x()
        down_y = self.btn_intensity_mild.y() + self.btn_intensity_mild.height()
        self.btn_intensity_down.move(down_x, down_y)

        # Define min/max limits (20% to 80%)
        self.mild_min_percent = 20
        self.mild_max_percent = 80
        self.mild_step = 10  # Moves by 10% each click

        # Set mild initial percent
        self.mild_percent = 30
        self.update_mild_button_position()

    def configure_ui(self):
        self.lbl_sim_status.setText("Starting ...")

    def cache_status_icons(self):
        self.status_icons = {}
        images_dir = 'images'
        for status in ['ok', 'warning', 'nogo']:
            icon = load_icon_from_path(os.path.join(images_dir, f"{status}.png"))
            if icon:
                self.status_icons[status] = icon

    def switches_begin(self, port):
        if self.switch_controller.begin(port):

            # Wait for valid state
            logging.info("DEBUG: Waiting for valid activate switch state.")
            state = self.get_hardware_activate_state()
            while state is None:
                self.switch_controller.poll()
                QtWidgets.QApplication.processEvents()
                state = self.get_hardware_activate_state()

            # If switch is up (1), show warning and wait until flipped down
            # todo, is this still needed, see switch_ui_contoller begin
            if state == 1:
                self.show_activate_warning_dialog()
                while self.get_hardware_activate_state() != 0:
                    self.switch_controller.poll()
                    QtWidgets.QApplication.processEvents()
                    log.debug(f"Waiting... Current switch state: {self.get_hardware_activate_state()}")

                if self.activate_warning_dialog:
                    self.activate_warning_dialog.accept()
                    self.activate_warning_dialog = None

    # --------------------------------------------------------------------------
    # Status / Communication Utilities
    # These relate to status messages or hardware startup messaging.
    # --------------------------------------------------------------------------
    
    def status_message(self, msg):
        """Forward status messages to the simStatusChanged signal."""
        self.core.simStatusChanged.emit(msg)
 
    def close_activate_warning_dialog(self):
        if self.activate_warning_dialog:
            self.activate_warning_dialog.accept()
            self.activate_warning_dialog = None

    @QtCore.pyqtSlot()
    def show_hardware_connection_error(self):
        QtWidgets.QMessageBox.critical(
            self,
            "Hardware Switch Coms Error",
            "Failed to open serial port.\n\nPlease check the connection and restart the application "
            "if you want the hardware switch interface."
        )   

    def show_activate_warning_dialog(self):
        background_image_path = "images/activate_warning.png"
        image_pixmap = QtGui.QPixmap(background_image_path)

        self.activate_warning_dialog = QtWidgets.QDialog(self)
        self.activate_warning_dialog.setWindowTitle("Initialization Warning")
        self.activate_warning_dialog.setFixedSize(image_pixmap.width(), image_pixmap.height())

        label_background = QtWidgets.QLabel(self.activate_warning_dialog)
        label_background.setPixmap(image_pixmap)
        label_background.setScaledContents(True)
        label_background.setGeometry(0, 0, image_pixmap.width(), image_pixmap.height())

        label_text = QtWidgets.QLabel("Flip the Activate switch down to proceed.", self.activate_warning_dialog)
        label_text.setAlignment(QtCore.Qt.AlignCenter)
        label_text.setStyleSheet("font-size: 18px; color: red; font-weight: bold;")
        label_text.setGeometry(0, 24, image_pixmap.width(), 40)

        self.activate_warning_dialog.setWindowModality(QtCore.Qt.ApplicationModal)
        self.activate_warning_dialog.show()

    @QtCore.pyqtSlot()
    def on_valid_activate_received(self):
        log.info("Hardware activate switch in valid state.")
        # Optionally proceed with initialization or UI updates

    def get_status_icon(self, status):
        return self.status_icons.get(status)
    
    
    # --------------------------------------------------------------------------
    # Button / UI Interaction Handlers
    # These respond to user interactions with GUI widgets (buttons, checkboxes, sliders).
    # --------------------------------------------------------------------------

    def on_btn_fly_clicked(self, state=None):
        if state is not None and not state:
            return
        self.core.update_state("running")
        self.btn_fly.setChecked(True)

    def on_btn_pause_clicked(self, state=None):
        if state is not None and not state:
            return
        self.core.update_state("paused")
        self.btn_pause.setChecked(True)
    
    @QtCore.pyqtSlot(bool)
    def on_hardware_activate_toggled(self, state):
        self.on_activate_toggled(state)

    def on_activate_toggled(self, physical_state=None):
        """
        Called when "Activated/Deactivated" GUI toggle is clicked OR when a physical toggle switch state changes.
        """
        if not self.state or self.state == 'initialized': # only preceed when transitioned beyond init state
            return
        #  Ensure activation switch state is enforced correctly at startup
        if physical_state is None:  # Only check at startup
            actual_switch_state = self.get_hardware_activate_state()  #  Read actual physical switch state
            logging.info(f"DEBUG: Hardware activation switch at startup = {actual_switch_state}")

            if actual_switch_state:  #  Prevent initialization if switch is UP (activated)
                self.activate_warning_dialog = QtWidgets.QMessageBox.warning(
                    self,
                    "Initialization Warning",
                    "Activate switch must be DOWN for initialization. Flip switch down to proceed."
                )
                return  #  Do NOT override the switch state, just prevent proceeding!

        if physical_state is not None:
            self.chk_activate.setChecked(physical_state)  #  Sync UI button with actual switch state

        if self.chk_activate.isChecked():
            #  System is now ACTIVATED
            self.chk_activate.setText("ACTIVATED")
            self.core.update_state("enabled")

            #  Send the currently selected mode & skill to X-Plane
            self.inform_button_selections()

            #  Ensure X-Plane is paused after scenario load
            if self.core.sim:
                logging.info("DEBUG: Pausing X-Plane after scenario load.")
                self.core.sim.pause()

            #  Enable Pause and Fly buttons
            self.btn_fly.setEnabled(True)
            self.btn_pause.setEnabled(True)

        else:
            #  System is now DEACTIVATED
            self.chk_activate.setText("INACTIVE")
            self.core.update_state("disabled")

            #  Pause X-Plane when deactivated
            if self.core.sim:
                logging.info("DEBUG: Pausing X-Plane due to deactivation.")
                self.core.sim.pause()

            #  Disable Pause and Fly buttons (unless override is enabled)
            self.btn_fly.setEnabled(False)
            self.btn_pause.setEnabled(False)
            
            # Sync UI & Sim with switch state
            self.sync_ui_with_switches()


    def on_slider_value_changed(self, slider_name, value):
        index = 6 if slider_name == 'sld_gain_master' else int(slider_name.split('_')[-1])
        self.core.update_gain(index, value)

    def on_flight_mode_changed(self, mode_id, from_hardware=False):
        self.core.modeChanged(mode_id)
        if from_hardware:
            self.flight_button_group.set_checked(mode_id)

    def on_pilot_assist_level_changed(self, level, from_hardware=False):
        self.core.assistLevelChanged(level)
        if from_hardware:
            self.exp_button_group.set_checked(level)

    def on_load_level_selected(self, load_level, from_hardware=False):
        self.core.loadLevelChanged(load_level)
        if from_hardware:
            self.load_button_group.set_checked(load_level)

    def on_intensity_changed(self, intensity_index, from_hardware=False):
        log.debug(f"Intensity level changed to {intensity_index}")

        if intensity_index == 0:
            intensity_value = 0
        elif intensity_index == 2:
            intensity_value = 100
        else:
            intensity_value = self.mild_percent

        self.core.intensityChanged(intensity_value)

        if from_hardware:
            QtWidgets.QApplication.instance().postEvent(
                self, QtCore.QEvent(QtCore.QEvent.User)
            )
            self.intensity_button_group.set_checked(intensity_index)


    def update_mild_button_position(self):
        """ 
        Moves the 'Mild' button, aligns the Up/Down buttons, and updates the mild value label.
        """

        # Define Y-position limits
        full_top = self.btn_intensity_full.y() + self.btn_intensity_full.height()  # Just below "Full"
        static_top = self.btn_intensity_motionless.y()  # Top of "Static"
        mild_height = self.btn_intensity_mild.height()

        # Map percentage to position
        new_y = static_top - mild_height - ((self.mild_percent - self.mild_min_percent) /
                                            (self.mild_max_percent - self.mild_min_percent)) * (static_top - full_top - mild_height)

        #  Move Mild button
        self.btn_intensity_mild.move(self.btn_intensity_mild.x(), int(new_y))

        # Move Up button (bottom aligns with Mild's top)
        up_x = self.btn_intensity_mild.x()
        up_y = int(new_y) - self.btn_intensity_up.height()
        self.btn_intensity_up.move(up_x, up_y)

        # Move Down button (top aligns with Mild's bottom)
        down_x = self.btn_intensity_mild.x()
        down_y = int(new_y) + self.btn_intensity_mild.height()
        self.btn_intensity_down.move(down_x, down_y)

        #Move Mild label to match Mild button Y position
        self.lbl_mild_value.move(self.lbl_mild_value.x(), int(new_y)+8)

        # Update Mild label text
        self.lbl_mild_value.setText(f"{self.mild_percent}%")

        # Hide Up/Down buttons when at limits
        self.btn_intensity_up.setVisible(self.mild_percent < self.mild_max_percent)
        self.btn_intensity_down.setVisible(self.mild_percent > self.mild_min_percent)

        
    def move_mild_button(self, direction):
        """ Moves the 'Mild' button up (+1) or down (-1) in 10% increments. """
        # Calculate new position
        new_percent = self.mild_percent + (self.mild_step * direction)

        # Ensure within limits
        self.mild_percent = max(self.mild_min_percent, min(self.mild_max_percent, new_percent))

        # Update button position
        self.update_mild_button_position()

        # Trigger intensity change
        self.on_intensity_changed(1)


    def inform_button_selections(self):
        # Get checked button ID for flight selection (mode)
        mode_id = self.flight_button_group.checked_id()
        if mode_id != -1:
            self.core.modeChanged(mode_id)

        # Get checked button ID for pilot assist level
        pilot_assist_level = self.exp_button_group.checked_id()
        if pilot_assist_level != -1:
            self.core.assistLevelChanged(pilot_assist_level)

        # Get checked button ID for load level
        load_level = self.load_button_group.checked_id()
        if load_level != -1:
            self.core.loadLevelChanged(load_level)

    def update_transform_blocks(self, values):
        for i in range(6):
            track = self.transform_tracks[i]
            block = self.transform_blocks[i]
            value = max(-1.0, min(1.0, values[i]))  # Clamp value to [-1, 1]

            # Detect orientation
            is_vertical = track.height() > track.width()

            # Move block relative to track position
            if is_vertical:
                track_height = track.height()
                block_y = track.y() + int((1 - (value + 1) / 2) * track_height) - block.height() // 2
                block.move(block.x(), block_y)
            else:
                track_width = track.width()
                block_x = track.x() + int(((value + 1) / 2) * track_width) - block.width() // 2
                block.move(block_x, block.y())



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
        
    def sync_ui_with_switches(self):
        if not self.switch_controller:
            return

        # Sync UI buttons
        self.flight_button_group.set_checked(self.switch_controller.get_flight_mode())
        self.exp_button_group.set_checked(self.switch_controller.get_assist_level())
        self.load_button_group.set_checked(self.switch_controller.get_load_level())
        self.intensity_button_group.set_checked(self.switch_controller.get_intensity_level())

        # Call corresponding slots to sync sim state
        self.on_flight_mode_changed(self.switch_controller.get_flight_mode(), from_hardware=True)
        self.on_pilot_assist_level_changed(self.switch_controller.get_assist_level(), from_hardware=True)
        self.on_load_level_selected(self.switch_controller.get_load_level(), from_hardware=True)
        self.on_intensity_changed(self.switch_controller.get_intensity_level(), from_hardware=True)
   
        
    # --------------------------------------------------------------------------
    # Visual Updates
    # Methods that update graphical UI elements (labels, pixmaps, etc.)
    # --------------------------------------------------------------------------
    
    def apply_icon(self, label, key):
        icon = self.status_icons.get(key)
        if icon:
            label.setPixmap(icon.pixmap(32, 32))

    def do_transform(self, widget, pixmap, base_pos, dx, dy, angle_deg):
        center = QtCore.QPointF(pixmap.width() / 2, pixmap.height() / 2)
        transform = QtGui.QTransform()
        transform.translate(center.x(), center.y())
        transform.rotate(angle_deg)
        transform.translate(-center.x(), -center.y())
        rotated = pixmap.transformed(transform, QtCore.Qt.SmoothTransformation)
        widget.move(base_pos.x() + dx, base_pos.y() + dy)
        widget.setPixmap(rotated)

    def show_transform(self, transform):
        surge, sway, heave, roll, pitch, yaw = transform
        self.do_transform(self.lbl_front_view, self.front_pixmap, self.front_pos,
                          int(sway * XLATE_SCALE), int(-heave * XLATE_SCALE), -roll * ROTATE_SCALE)
        self.do_transform(self.lbl_side_view, self.side_pixmap, self.side_pos,
                          int(surge * XLATE_SCALE), int(-heave * XLATE_SCALE), -pitch * ROTATE_SCALE)
        self.do_transform(self.lbl_top_view, self.top_pixmap, self.top_pos,
                          int(sway * XLATE_SCALE), int(surge * XLATE_SCALE), yaw * ROTATE_SCALE)

    def show_muscles(self, muscle_lengths):
        for i in range(6):
            line = getattr(self, f"muscle_{i}", None)
            if line:
                full_visual_width = 500
                new_width = max(0, min(int(muscle_lengths[i] / 2), full_visual_width))

                # Align right by adjusting the x position based on new width
                new_x = self.muscle_base_right[i] - new_width
                line.setGeometry(new_x, line.y(), new_width, line.height())
                line.update()
                
    def show_performance_bars(self, processing_percent: int, jitter_percent: int):
        """
        Update UI bars representing processing usage and timer jitter.

        :param processing_percent: CPU time spent in data_update as percent of frame (0–100)
        :param jitter_percent: Deviation of actual frame interval vs. expected, as percent (0–100)
        """
        # Processing bar (0–100%, bar length in px up to 500)
        if hasattr(self, "ln_processing_percent"):
            width = min(int((processing_percent / 100.0) * 500), 500)
            self.ln_processing_percent.setGeometry(
                self.ln_processing_percent.x(),
                self.ln_processing_percent.y(),
                width,
                self.ln_processing_percent.height()
            )
            self.ln_processing_percent.update()

        # Jitter bar (0–100%, bar length in px up to 500)
        if hasattr(self, "ln_jitter"):
            jitter_clamped = min(jitter_percent, 100)
            width = int((jitter_clamped / 100.0) * 500)
            self.ln_jitter.setGeometry(
                self.ln_jitter.x(),
                self.ln_jitter.y(),
                width,
                self.ln_jitter.height()
            )
            self.ln_jitter.update()

    
    # --------------------------------------------------------------------------
    # Core Callbacks / Slots
    # These are connected to Qt signals or used by core.
    # --------------------------------------------------------------------------

    @QtCore.pyqtSlot(str)
    def on_sim_status_changed(self, status_msg):
        self.lbl_sim_status.setText(status_msg)

    @QtCore.pyqtSlot(ActivationTransition)
    def on_activation_transition(self, transition: ActivationTransition):
        # Update activation fill on the button
        self.activate_percent = transition.activation_percent
        self.chk_activate.set_activation_percent(self.activate_percent)
        self.chk_activate.setText("ACTIVATED" if self.activate_percent >= 50 else "INACTIVE")
        # Update muscle display
        self.show_muscles(transition.muscle_lengths)

    @QtCore.pyqtSlot(object)
    def on_data_updated(self, update):
        """
        Called every time the core's data_update fires (every 50 ms if running).
        Also polls the serial reader for new switch states.

        Args:
            update (SimUpdate): A namedtuple containing all update info
        """
        self.switch_controller.poll()

        tab_index = self.tabWidget.currentIndex()
        current_tab = self.tabWidget.widget(tab_index).objectName()

        if current_tab == 'tab_main':
            xform = (-1, -.5, 0, .25, .5, 1)
            for idx in range(6):
                self.update_transform_blocks(update.transform)
        else: 
                       
            if not self.cb_supress_graphics.isChecked():   
                self.show_transform(update.transform)
                self.show_muscles(update.muscle_lengths)
            # Update performance metrics
            if hasattr(update, "processing_percent") and hasattr(update, "jitter_percent"):
                self.show_performance_bars(update.processing_percent, update.jitter_percent)

        self.apply_icon(self.ico_connection, update.conn_status)
        self.apply_icon(self.ico_data, update.data_status)
        self.apply_icon(self.ico_aircraft, update.aircraft_info.status)
        self.lbl_aircraft.setText(update.aircraft_info.name)
 
        # Static status icons (placeholders)
        self.apply_icon(self.ico_left_dock, "ok")
        self.apply_icon(self.ico_right_dock, "ok")
        self.apply_icon(self.ico_wheelchair_docked, "ok")

        self.update_temperature_display(update.temperature)


    @QtCore.pyqtSlot(str)
    def on_platform_state_changed(self, new_state):
        """
        Reflect platform states in the UI (enabled, disabled, running, paused).
        """
        log.info("UI: platform state is now '%s'", new_state)
        self.state = new_state

        activate_state = self.chk_activate.isChecked()
        logging.info(f"DEBUG: chk_activate state = {activate_state} (True = Activated, False = Deactivated)")

        if new_state == "initialized":
            if self.chk_activate.isChecked():
                QtWidgets.QMessageBox.warning(
                    self,
                    "Initialization Warning",
                    "Activate switch must be DOWN for initialization. Flip switch down to proceed."
                )
                return
            logging.info("UI: Activate switch is OFF. Transitioning to 'disabled' state.")
            self.core.update_state("disabled")
 

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

    def get_hardware_activate_state(self):
        return self.switch_controller.get_activate_state()
        
    @QtCore.pyqtSlot()
    def update_temperature_display(self, temperature):
        if temperature is None:
            self.lbl_temperature.setVisible(False)
        else:
            self.lbl_temperature.setVisible(True)
            self.lbl_temperature.setText(f"{temperature:.1f} °C")
            if temperature > 80:
                self.lbl_temperature.setStyleSheet("background-color: red; color: white;")
            elif temperature > 60:
                self.lbl_temperature.setStyleSheet("background-color: yellow; color: black;")
            else:
                self.lbl_temperature.setStyleSheet("") 

    # --------------------------------------------------------------------------
    # Event Handling
    # Overrides for Qt's event methods.
    # --------------------------------------------------------------------------
    
    def keyPressEvent(self, event):
        # if event.key() == Qt.Key_Escape:  # Press Esc to exit
        #     self.close()
        if event.modifiers() == QtCore.Qt.ControlModifier and event.key() == QtCore.Qt.Key_Q:  # Ctrl+Q
            self.close()
        elif event.key() == QtCore.Qt.Key_W:
            self.showNormal()  # Exit fullscreen and show windowed mode    

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
