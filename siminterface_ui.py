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
        self.state = None

        # connect signals from core to UI
        self.core.simStatusChanged.connect(self.on_sim_status_changed)
        self.core.dataUpdated.connect(self.on_data_updated)
        self.core.platformStateChanged.connect(self.on_platform_state_changed)

        # connect signals from UI to core methods
        self.btn_fly.clicked.connect(self.on_btn_fly_clicked)
        self.btn_pause.clicked.connect(self.on_btn_pause_clicked)
        
        self.initialize_intensity_controls()
        
        # flight mode selection
        self.flight_button_group = QtWidgets.QButtonGroup(self)
        self.flight_button_group.addButton(self.btn_mode_0, 0)
        self.flight_button_group.addButton(self.btn_mode_1, 1)
        self.flight_button_group.addButton(self.btn_mode_2, 2)
        self.flight_button_group.buttonClicked[int].connect(self.on_flight_mode_changed)
   
        # experience levels
        self.exp_button_group = QtWidgets.QButtonGroup(self)
        self.exp_button_group.addButton(self.btn_assist_0, 0)
        self.exp_button_group.addButton(self.btn_assist_1, 1)
        self.exp_button_group.addButton(self.btn_assist_2, 2)
        self.exp_button_group.buttonClicked[int].connect(self.on_pilot_assist_level_changed)

        # Create load setting button Group
        self.load_button_group = QtWidgets.QButtonGroup(self)
        self.load_button_group.addButton(self.btn_light_load, 0)
        self.load_button_group.addButton(self.btn_moderate_load, 1)
        self.load_button_group.addButton(self.btn_heavy_load, 2)
        self.load_button_group.buttonClicked[int].connect(self.on_load_level_selected)
        
        self.chk_activate.clicked.connect(self.on_activate_toggled)

        slider_names = [f'sld_gain_{i}' for i in range(6)] + ['sld_gain_master']
        for name in slider_names:
            slider = getattr(self, name)
            slider.valueChanged.connect(lambda value, s=name: self.on_slider_value_changed(s, value))
        self.transfrm_levels = [self.sld_xform_0, self.sld_xform_1, self.sld_xform_2, self.sld_xform_3, self.sld_xform_4, self.sld_xform_5  ]
        
        # configure interface to hardware switches
        #switch events: fly, pause, enable, intensity, load, skill, flight 
        event_callbacks = [
            lambda state: self.on_btn_fly_clicked(state),  # Fly
            lambda state: self.on_btn_pause_clicked(state),  # Pause
            lambda state: self.on_hardware_activate_toggled(state),  # Activate
            lambda level: self.on_pilot_assist_level_changed(level, from_hardware=True),  # Skill level
            lambda flight: self.on_flight_mode_changed(flight, from_hardware=True),  # Flight
            lambda load: self.on_load_level_selected(load, from_hardware=True),  # Load
            lambda intensity: self.on_intensity_changed(intensity, from_hardware=True)  # Intensity
        ]

        self.switch_reader = SerialSwitchReader(event_callbacks, self.on_sim_status_changed)
        self.hardware_activate_state = None # needed to detect state of physical activate switch at startup
                
        # Additional initialization
        self.configure_ui_defaults()
        # self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.FramelessWindowHint)  # If running in fullscreen
        log.info("MainWindow: UI initialized")
        

    def on_hardware_activate_toggled(self, physical_state):
        """
        Called when the physical activation switch state changes.
        Stores the hardware state and calls on_activate_toggled() to process it.
        """
        logging.info(f"DEBUG: hardware_activate_toggled() called - state = {physical_state}")
 
        self.hardware_activate_state = physical_state  # Store hardware switch state
        self.on_activate_toggled(physical_state)  #  Call existing method to process it

    def keyPressEvent(self, event):
        # if event.key() == Qt.Key_Escape:  # Press Esc to exit
        #     self.close()
        if event.modifiers() == QtCore.Qt.ControlModifier and event.key() == QtCore.Qt.Key_Q:  # Ctrl+Q
            self.close()

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
    
    def inform_button_selections(self):
        # Get checked button ID for flight selection (mode)
        mode_id = self.flight_button_group.checkedId()
        if mode_id != -1:
            self.core.modeChanged(mode_id)

        # Get checked button ID for skill level
        skill_level = self.exp_button_group.checkedId()
        if skill_level != -1:
            self.core.skillLevelChanged(skill_level)

        # Get checked button ID for load level
        load_level = self.load_button_group.checkedId()
        if load_level != -1:
            self.core.loadLevelChanged(load_level)
            
    def configure_ui_defaults(self):
        """
        Setup initial states or text for the UI elements.
        """
        self.lbl_sim_status.setText("Starting ...")

    def initialize_intensity_controls(self):
        """ Sets up intensity buttons, movement controls, and initial positions. """

        # Intensity Button Group (for static, mild, and full)
        self.intensity_button_group = QtWidgets.QButtonGroup(self)
        self.intensity_button_group.addButton(self.btn_intensity_motionless, 0)
        self.intensity_button_group.addButton(self.btn_intensity_mild, 1)
        self.intensity_button_group.addButton(self.btn_intensity_full, 2)
        self.intensity_button_group.buttonClicked[int].connect(self.on_intensity_changed)

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

        # Set mild initial  percent
        self.mild_percent = 40
        self.update_mild_button_position()

        # muscle bars and position labels for platform tab
        self.muscle_bars = [self.muscle_0,self.muscle_1,self.muscle_2,self.muscle_3,self.muscle_4,self.muscle_5]
        # self.txt_muscles = [self.txt_muscle_0,self.txt_muscle_1,self.txt_muscle_2,self.txt_muscle_3,self.txt_muscle_4,self.txt_muscle_5]
        
        self.front_pos =  self.lbl_front_view.pos()
        self.side_pos = self.lbl_side_view.pos()
        self.top_pos = self.lbl_top_view.pos()



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

    def on_pilot_assist_level_changed(self, level, from_hardware=False):
        """
        Called when a skill level button is toggled from the UI or hardware.
        """
        log.debug(f"Skill level changed to {level}")

        self.core.skillLevelChanged(level)

        # If triggered by hardware, update the UI button
        if from_hardware:
            QtWidgets.QApplication.instance().postEvent(
                self, QtCore.QEvent(QtCore.QEvent.User)
            )
            self.btn_assist_0.setChecked(level == 0)
            self.btn_assist_1.setChecked(level == 1)
            self.btn_assist_2.setChecked(level == 2)


    def on_flight_mode_changed(self, mode_id, from_hardware=False):
        """
        Called when a flight selection button is changed, either from UI or hardware.
        """
        log.debug(f"Flight mode changed to {mode_id}")

        self.core.modeChanged(mode_id)

        # If triggered by hardware, update the UI button
        if from_hardware:
            QtWidgets.QApplication.instance().postEvent(
                self, QtCore.QEvent(QtCore.QEvent.User)
            )
            self.flight_button_group.button(mode_id).setChecked(True)


    def on_intensity_changed(self, intensity_index, from_hardware=False):
        """
        Called when an intensity selection button is changed, either from UI or hardware.

        - Sends intensity value to `self.core.on_intensity_changed(value)`.
        - The intensity slider no longer moves when an intensity button is clicked.
        """
        log.debug(f"Intensity level changed to {intensity_index}")

        # Determine intensity value
        if intensity_index == 0:  # Static
            intensity_value = 0
        elif intensity_index == 2:  # Full
            intensity_value = 100
        else:  # Mild, use stored value
             intensity_value = self.mild_percent

        # Inform core about intensity change
        self.core.intensityChanged(intensity_value)

        # If triggered by hardware, update the UI button
        if from_hardware:
            QtWidgets.QApplication.instance().postEvent(
                self, QtCore.QEvent(QtCore.QEvent.User)
            )
            self.intensity_button_group.button(intensity_index).setChecked(True)

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
 
    # code to display transforms and muscles
    def do_transform(self, widget, pixmap, pos,  x, y, angle):
        widget.move(x + pos.x(), y + pos.y())
        xform = QtGui.QTransform().rotate(angle)  # front view: roll
        xformed_pixmap = pixmap.transformed(xform, QtCore.Qt.SmoothTransformation)
        widget.setPixmap(xformed_pixmap)
        # widget.adjustSize()
        
    def show_transform(self, transform):
        print("in ui, xform=", transform)
        # front, side and top views of current transform in platform tab
        """
        for idx, x in enumerate(transform):
            if idx < 3:
                self.txt_xforms[idx].setText(format("%d" % x))
            else:
                angle = x * 57.3
                self.txt_xforms[idx].setText(format("%0.1f" % angle))
        """    
        x = int(transform[0] / 4) 
        y = int(transform[1] / 4)
        z = -int(transform[2] / 4)

        self.do_transform(self.ui.lbl_front_view, self.front_pixmap, self.front_pos, y,z, transform[3] * 57.3) # front view: roll
        self.do_transform(self.ui.lbl_side_view, self.side_pixmap, self.side_pos, x,z, transform[4] * 57.3) # side view: pitch
        self.do_transform(self.ui.lbl_top_view, self.top_pixmap, self.top_pos,  y,x, transform[5] * 57.3)  # top view: yaw

    def show_muscles(self, transform, muscles, processing_percent):  # was passing  pressure_percent
        for i in range(6):
           rect =  self.actuator_bars[i].rect()
           width = muscles[i]            
           rect.setWidth(width)
           self.actuator_bars[i].setFrameRect(rect)
           contraction = self.MAX_ACTUATOR_RANGE - width
           self.txt_muscles[i].setText(format("%d mm" % contraction ))
        self.show_transform(transform) 
        #  processing_dur = int(time.time() % 20) # for testing, todo remove
        self.ui.txt_processing_dur.setText(str(processing_percent))
        rect =  self.ui.rect_dur.rect()
        rect.setWidth(max(2*processing_percent,1) )
        if processing_percent < 50:
            self.ui.rect_dur.setStyleSheet("color: rgb(85, 255, 127)")
        elif processing_percent < 75:
            self.ui.rect_dur.setStyleSheet("color: rgb(255, 170, 0)")
        else:
            self.ui.rect_dur.setStyleSheet("color: rgb(255, 0, 0)")
        self.ui.rect_dur.setFrameRect(rect)
        

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
        tab_index = self.tabWidget.currentIndex()
        current_tab = self.tabWidget.widget(tab_index).objectName()
        if current_tab == 'tab_main':
            for idx in range(6): 
                self.transfrm_levels[idx].setValue(round(transform[idx] * 100))
        elif current_tab == 'tab_platform':
            print("tab platform todo")

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
            self.ico_aircraft.setPixmap(data_icon.pixmap(32, 32)) # HACK to get aircraft to follow data icon, repalce with check for C172
            
        # hack to load the status icons
        status_icon = load_icon('ok')
        self.ico_left_dock.setPixmap(status_icon.pixmap(32, 32))
        self.ico_right_dock.setPixmap(status_icon.pixmap(32, 32))
        self.ico_wheelchair_docked.setPixmap(status_icon.pixmap(32, 32))
        
        
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


    def on_activate_toggled(self, physical_state=None):
        """
        Called when "Activated/Deactivated" GUI toggle is clicked OR when a physical toggle switch state changes.
        """
        print(self.state)
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
            mode_id = self.flight_button_group.checkedId()
            skill_level = self.exp_button_group.checkedId()
            if mode_id != -1 and skill_level != -1:
                logging.info(f"DEBUG: Sending scenario mode={mode_id}, skill={skill_level}")
                self.core.sim.set_scenario(mode_id, skill_level)

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


    def switches_begin(self, port):
        """
        Starts switch polling and waits for valid hardware data before proceeding.
        If the hardware is disconnected, it logs an error and prevents initialization.
        """
        logging.info(f"DEBUG: switches_begin() called - Searching for switches on {port}.")
        self.core.simStatusChanged.emit(f"Searching for switches on port {port}...")  # send status message

        # Start hardware switch reader
        try:
            self.switch_reader.begin(port)  # ✅ Start switch polling
            logging.info("DEBUG: Hardware switch reader initialized.")
        except Exception as e:
            logging.error(f"ERROR: Failed to open serial port {port}. Hardware switches not connected.")
            self.core.simStatusChanged.emit("Hardware switches not connected.")
            QtWidgets.QMessageBox.critical(
                self,
                "Hardware Switch Coms Error",
                f"Failed to open serial port {port}.\n\nPlease check the connection and restart the application"
                " if you want the hardware switch interface."
            )
            return  # ❌ Prevents further execution

        # ✅ Wait until a valid switch state (0 or 1) is received
        logging.info("DEBUG: Waiting for valid activate switch state.")
        self.activate_warning_dialog = None  # Store reference to dialog

        while self.hardware_activate_state is None:
            self.switch_reader.poll()  # ✅ Read initial switch state
            QtWidgets.QApplication.processEvents()  # ✅ Keep UI responsive

        # ✅ Now that we have a valid state, only show the dialog if the switch is UP (1)
        if self.hardware_activate_state == 1:
            logging.info("DEBUG: Showing activation warning dialog.")

            # ✅ Load the background image
            background_image_path = "images/activate_warning.png"  # Update with actual path

            # ✅ Create a custom dialog
            self.activate_warning_dialog = QtWidgets.QDialog(self)
            self.activate_warning_dialog.setWindowTitle("Initialization Warning")

            # ✅ Set the dialog size to match the image
            image_pixmap = QtGui.QPixmap(background_image_path)
            self.activate_warning_dialog.setFixedSize(image_pixmap.width(), image_pixmap.height())

            # ✅ Create a QLabel to display the background image
            label_background = QtWidgets.QLabel(self.activate_warning_dialog)
            label_background.setPixmap(image_pixmap)
            label_background.setScaledContents(True)
            label_background.setGeometry(0, 0, image_pixmap.width(), image_pixmap.height())

            # ✅ Create a QLabel for the warning text
            label_text = QtWidgets.QLabel("Flip the Activate switch down to proceed.", self.activate_warning_dialog)
            label_text.setAlignment(QtCore.Qt.AlignCenter)
            label_text.setStyleSheet("font-size: 18px; color: red; font-weight: bold;")
            label_text.setGeometry(0, 24, image_pixmap.width(), 40)

            # ✅ Set the dialog to be modal
            self.activate_warning_dialog.setWindowModality(QtCore.Qt.ApplicationModal)
            self.activate_warning_dialog.show()

            # ✅ Keep polling until the switch is flipped down (0)
            while self.hardware_activate_state != 0:
                self.switch_reader.poll()
                QtWidgets.QApplication.processEvents()  # ✅ Keep UI responsive

            # ✅ Close the warning dialog when the switch is flipped down
            logging.info("DEBUG: Closing activation warning dialog.")
            self.activate_warning_dialog.accept()
            self.activate_warning_dialog = None