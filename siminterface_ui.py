import os
import platform
import logging
import configparser
from PyQt5 import QtWidgets, uic, QtCore, QtGui
from PyQt5.QtGui import QMovie
from typing import NamedTuple
# from common.serial_switch_json_reader import SerialSwitchReader
from switch_ui_controller import SwitchUIController
from sims.shared_types import SimUpdate, AircraftInfo, ActivationTransition
from washout.washout_ui import WashoutUI
from show_washout import WashoutScope 
from ui_widgets import ActivationButton, ButtonGroupHelper,  FatalErrDialog

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
        self.error_dialog = FatalErrDialog()
        self.core = core
        self.setupUi(self)
        self.state = None
        self.MAX_ACTUATOR_RANGE = 100
        self.activation_percent = 0 # steps between 0 and 100 in slow moves when activated/deactivated  
        self.deferred_physical_toggle_state = None  # Tracks activation toggle that happened during transition


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
        self.init_input_controls()
        self.init_telemetry_format_string()
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
        self.core.fatal_error.connect(self.on_fatal_error)
        self.core.dataUpdated.connect(self.on_data_updated)
        self.core.activationLevelUpdated.connect(self.on_activation_transition)
        self.core.platformStateChanged.connect(self.on_platform_state_changed)
        self.btn_fly.clicked.connect(self.on_btn_fly_clicked)
        self.btn_pause.clicked.connect(self.on_btn_pause_clicked)
        self.chk_activate.clicked.connect(self.on_activate_toggled)
        self.btn_save_gains.clicked.connect(self.on_save_gains)
        self.btn_reset_gains.clicked.connect(self.on_reset_gains)

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
        # print("xfrom ps:", self.front_pos, self.side_pos, self.top_pos)
        self.muscle_bars = [getattr(self, f"muscle_{i}") for i in range(6)]
        self.txt_muscles = [getattr(self, f"txt_muscle_{i}") for i in range(6)]
        self.cache_status_icons()
        # store right edge of muscle bar display
        self.muscle_base_right = []
        for i in range(6):
            line = getattr(self, f"muscle_{i}")
            right_edge = line.x() + line.width()
            self.muscle_base_right.append(right_edge)
            
        self.busy_spinner_movie = QMovie("images/busy_spinner.gif")
        self.lbl_busy_spinner.setMovie(self.busy_spinner_movie)
        self.lbl_busy_spinner.hide() 
         

    def init_input_controls(self):
        self.washout_ui = WashoutUI(self.grp_washout, config_path="washout/washout.cfg", on_activate=self.core.apply_washout_configuration)
        self.transform_viewer = WashoutScope(self.frm_transform_viewer)
     
        # init gain sliders         
        self.gain_sliders = [] 
        slider_names = [f'sld_gain_{i}' for i in range(6)] + ['sld_gain_master']
        for name in slider_names:
            slider = getattr(self, name)
            slider.valueChanged.connect(lambda value, s=name: self.on_slider_value_changed(s, value))
            self.gain_sliders.append(slider) 

        self.gain_labels = [getattr(self, f'lbl_gain_{i}') for i in range(7)]

        self.load_gains() # set gains sliders
        
        self.transform_tracks = [getattr(self, f'transform_track_{i}') for i in range(6)]
        self.transform_blocks = [getattr(self, f'transform_block_{i}') for i in range(6)]

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

    def init_telemetry_format_string(self):    
        font_metrics = QtGui.QFontMetrics(self.lbl_sim_status.font())
        char_width = font_metrics.horizontalAdvance("5") # we assume fixed width font
        avail_width = self.lbl_sim_status.width() - (char_width*6*5) # 6 values each 5 chars wide
        avail_pixels = avail_width // 5 # 5 gaps between values
        self.telem_str_spacing = 5 + (avail_pixels//char_width)
        # print(f"spacing: {self.telem_str_spacing},avail_pixels: {avail_pixels}, avail width {avail_width}, char width {char_width}, total width: {self.lbl_sim_status.width()}")
        
        
    def on_fatal_error(self, err_context):
        self.error_dialog.fatal_err(err_context)
            
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
             
    def load_gains(self, config_path='gains.cfg'):
        config = configparser.ConfigParser()
        config.read(config_path)

        # Use default section if not present
        section = config['Gains'] if 'Gains' in config else {}

        for i in range(6):
            if self.gain_sliders[i]:
                val = int(section.get(f'gain_{i}', 100))
                self.gain_sliders[i].setValue(max(0, min(200, val)))  # Clamp within range

        if hasattr(self, 'sld_gain_master'):
            master_val = int(section.get('master_gain', 100))
            self.sld_gain_master.setValue(max(0, min(100, master_val)))

    def save_gains(self, config_path='gains.cfg'):
        config = configparser.ConfigParser()
        config['Gains'] = {}

        for i in range(6):
            slider = getattr(self, f'sld_gain_{i}', None)
            if slider:
                config['Gains'][f'gain_{i}'] = str(slider.value())

        if hasattr(self, 'sld_gain_master'):
            config['Gains']['master_gain'] = str(self.sld_gain_master.value())

        with open(config_path, 'w') as f:
            config.write(f)


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
        Handles activation toggle logic from UI or hardware.
        - Blocks UI toggles during transitions.
        - Defers hardware toggles during transitions.
        - Enforces startup condition: switch must be OFF (DOWN).
        """
        if not self.state or self.state == 'initialized':
            return

        # --- Enforce switch state at startup ---
        if physical_state is None:
            actual_switch_state = self.get_hardware_activate_state()
            logging.info(f"DEBUG: Hardware activation switch at startup = {actual_switch_state}")

            if actual_switch_state:
                self.activate_warning_dialog = QtWidgets.QMessageBox.warning(
                    self,
                    "Initialization Warning",
                    "Activate switch must be DOWN for initialization. Flip switch down to proceed."
                )
                return

        # --- Defer toggle during transition (activating or deactivating) ---
        if self.state in ["activating", "deactivating"]:
            if physical_state is not None:
                self.deferred_physical_toggle_state = physical_state
                logging.warning(f"Physical toggle deferred during '{self.state}' (queued = {physical_state})")

                self.chk_activate.blockSignals(True)
                self.chk_activate.setChecked(self.state == "activating")
                self.chk_activate.blockSignals(False)
            else:
                logging.info("UI toggle attempt ignored during transition.")
            return

        # --- Sync toggle state if physical input given ---
        if physical_state is not None:
            self.chk_activate.setChecked(physical_state)

        # --- Trigger activation or deactivation ---
        if self.chk_activate.isChecked():
            self.chk_activate.setText("ACTIVATING...")
            self.btn_fly.setEnabled(False)
            self.btn_pause.setEnabled(False)
            self.core.update_state("activating")
        else:
            self.chk_activate.setText("DEACTIVATING...")
            self.btn_fly.setEnabled(False)
            self.btn_pause.setEnabled(False)
            self.core.update_state("deactivating")
            self.sync_ui_with_switches()

    def on_slider_value_changed(self, slider_name, value):
        index = 6 if slider_name == 'sld_gain_master' else int(slider_name.split('_')[-1])
        self.gain_labels[index].setText(str(value))
        self.core.update_gain(index, value)

    def on_reset_gains(self):
        for i in range(7):
            self.gain_sliders[i].setValue(100)
    
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

    def on_save_gains(self):
        self.save_gains('gains.cfg')
        
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
        if transform and transform[0] != None:   
            surge, sway, heave, roll, pitch, yaw = transform
            self.do_transform(self.lbl_front_view, self.front_pixmap, self.front_pos,
                              int(sway * XLATE_SCALE), int(-heave * XLATE_SCALE), -roll * ROTATE_SCALE)
            self.do_transform(self.lbl_side_view, self.side_pixmap, self.side_pos,
                              int(surge * XLATE_SCALE), int(-heave * XLATE_SCALE), -pitch * ROTATE_SCALE)
            self.do_transform(self.lbl_top_view, self.top_pixmap, self.top_pos,
                              int(sway * XLATE_SCALE), int(surge * XLATE_SCALE), yaw * ROTATE_SCALE)

    def show_muscles(self, muscle_lengths, sent_pressures):
        if self.rb_contractions.isChecked():
            for i in range(6):
                line = getattr(self, f"muscle_{i}", None)
                if line:
                    full_visual_width = 500
                    contraction = 1000 - muscle_lengths[i] # todo remove hard coded muscle lengths
                    new_width = max(0, min(int(contraction * 2 ), full_visual_width))

                    # Align right by adjusting the x position based on new width
                    new_x = self.muscle_base_right[i] - new_width
                    line.setGeometry(new_x, line.y(), new_width, line.height())
                    line.update()
        elif self.rb_pressures.isChecked():   
            for i in range(6):
                line = getattr(self, f"muscle_{i}", None)
                if line:
                    full_visual_width = 500
                    width =  int((sent_pressures[i] / 6000) * full_visual_width)
                    line.setGeometry(0, line.y(), width, line.height())
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
        """
        Called during activation/deactivation transitions.
        Updates progress fill and label text according to transition state.
        """
        self.activate_percent = transition.activation_percent
        self.chk_activate.set_activation_percent(self.activate_percent)

        if self.activate_percent == 100:
            self.chk_activate.setText("ACTIVATED")
        elif self.activate_percent == 0:
            self.chk_activate.setText("INACTIVE")
        else:
            if self.core.transition_state == "activating":
                self.chk_activate.setText(f"ACTIVATING...") #  {self.activate_percent}%")
            elif self.core.transition_state == "deactivating":
                self.chk_activate.setText(f"DEACTIVATING...") #  {self.activate_percent}%")

        self.show_muscles(transition.muscle_lengths, transition.sent_pressures)

       

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
            for idx in range(6):
                self.update_transform_blocks(update.processed_transform)
        elif current_tab == 'tab_transform_viewer':
            self.transform_viewer.update(update.raw_transform, update.processed_transform)
        elif current_tab == 'tab_output': 
            self.txt_this_ip.setText(self.core.local_ip)
            self.txt_xplane_ip.setText(self.core.sim_ip_address)
            self.txt_festo_ip.setText(self.core.FESTO_IP)
            self.txt_visualizer_ip.setText(self.core.VISUALIZER_IP)
            if not self.cb_supress_graphics.isChecked():
                self.show_transform(update.raw_transform)
                self.show_muscles(update.muscle_lengths, update.sent_pressures)
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
        
        if update.aircraft_info.status != "ok":
            if not self.lbl_busy_spinner.isVisible():
                # color was mistyrose
                self.lbl_sim_status.setStyleSheet("background-color:  papayawhip; color: black;")
                self.lbl_busy_spinner.show()
                self.busy_spinner_movie.start()
        else:
            if self.lbl_busy_spinner.isVisible():
                self.lbl_busy_spinner.hide()
                self.busy_spinner_movie.stop()
                self.lbl_sim_status.setStyleSheet("background-color: lightgreen; color: black;")
 
            if update.raw_transform[0] != None:   
                self.lbl_sim_status.setText(" Receiving X-Plane telemetry") 
                # self.lbl_sim_status.setText( " " + " ".join(f"{x:={self.telem_str_spacing}.2f}" for x in update.raw_transform))
   

    @QtCore.pyqtSlot(str)
    def on_platform_state_changed(self, new_state):
        """
        Reflect platform states in the UI, including intermediate transitions.
        Reapplies any deferred physical toggle input once a transition completes.
        """
        log.debug("UI: platform state is now '%s'", new_state)
        self.state = new_state

        activate_state = self.chk_activate.isChecked()
        logging.debug(f"DEBUG: chk_activate state = {activate_state} (True = Activated, False = Deactivated)")

        if new_state == "initialized":
            if self.chk_activate.isChecked():
                QtWidgets.QMessageBox.warning(
                    self,
                    "Initialization Warning",
                    "Activate switch must be DOWN for initialization. Flip switch down to proceed."
                )
                return
            logging.debug("UI: Activate switch is OFF. Transitioning to 'deactivated' state.")
            self.core.update_state("deactivated")
            return

        # Handle transition states
        if new_state == "activating":
            self.chk_activate.setText("ACTIVATING...")
            self.btn_fly.setEnabled(False)
            self.btn_pause.setEnabled(False)

        elif new_state == "deactivating":
            self.chk_activate.setText("DEACTIVATING...")
            self.btn_fly.setEnabled(False)
            self.btn_pause.setEnabled(False)

        elif new_state == "enabled":
            self.chk_activate.setText("ACTIVATED")
            self.btn_fly.setEnabled(True)
            self.btn_pause.setEnabled(True)

        elif new_state == "deactivated":
            self.chk_activate.setText("INACTIVE")
            self.btn_fly.setEnabled(False)
            self.btn_pause.setEnabled(False)

        # Update Fly button style
        if new_state == "running":
            self.update_button_style(self.btn_fly, "active", "green", "white", "darkgreen")
        else:
            self.update_button_style(self.btn_fly, "default", "green", "green", "green")

        # Update Pause button style
        if new_state == "paused":
            self.update_button_style(self.btn_pause, "active", "orange", "black", "darkorange")
        else:
            self.update_button_style(self.btn_pause, "default", "orange", "orange", "orange")

        # Reapply deferred physical toggle if needed
        if new_state in ["enabled", "deactivated"] and self.deferred_physical_toggle_state is not None:
            expected = self.deferred_physical_toggle_state
            current_checked = self.chk_activate.isChecked()

            if expected != current_checked:
                log.info(f"[Deferred Toggle] Reapplying physical switch state: {expected}")
                self.deferred_physical_toggle_state = None
                self.on_activate_toggled(physical_state=expected)
            else:
                self.deferred_physical_toggle_state = None  # Clear if matched anyway

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
