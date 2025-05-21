import logging
from PyQt5 import QtCore
from common.serial_switch_json_reader import SerialSwitchReader, SwitchIndex

log = logging.getLogger(__name__)

class SwitchUIController(QtCore.QObject):
    activateStateChanged = QtCore.pyqtSignal(bool)
    validActivateReceived = QtCore.pyqtSignal()
    activate_switch_invalid = QtCore.pyqtSignal()

    def __init__(self, core, parent=None, status_callback=None,
                 show_warning_callback=None, close_warning_callback=None):
        super().__init__(parent)
        self.core = core
        self.reader = None
        self.hardware_activate_state = None
        self.status_callback = status_callback
        self.show_warning_callback = show_warning_callback
        self.close_warning_callback = close_warning_callback

        self.switch_callbacks = {
            SwitchIndex.FLY: parent.on_btn_fly_clicked,
            SwitchIndex.PAUSE: parent.on_btn_pause_clicked,
            SwitchIndex.ASSIST: lambda val: parent.on_pilot_assist_level_changed(val, from_hardware=True),
            SwitchIndex.FLIGHT_MODE: lambda val: parent.on_flight_mode_changed(val, from_hardware=True),
            SwitchIndex.LOAD: lambda val: parent.on_load_level_selected(val, from_hardware=True),
            SwitchIndex.INTENSITY: lambda val: parent.on_intensity_changed(val, from_hardware=True),
            SwitchIndex.ACTIVATE: self.update_activate_state,
        }

    def begin(self, port):
        log.info(f"SwitchUIController: Searching for switches on {port}")
        if self.status_callback:
            self.status_callback(f"Searching for switches on port {port}...")

        try:
            self.reader = SerialSwitchReader(self.switch_callbacks, self.status_callback)
            if self.reader.begin(port):
                log.info("Hardware switch reader initialized.")
                log.info("Waiting for valid activate switch state...")
                while self.hardware_activate_state is None:
                    self.poll()
                    QtCore.QCoreApplication.processEvents()

                if self.hardware_activate_state == 1:
                    if self.show_warning_callback:
                        QtCore.QTimer.singleShot(0, self.show_warning_callback)
                    while self.hardware_activate_state != 0:
                        self.poll()
                        QtCore.QCoreApplication.processEvents()
                    if self.close_warning_callback:
                        QtCore.QTimer.singleShot(0, self.close_warning_callback)

                log.info("Activate switch is in valid position.")
                self.validActivateReceived.emit()
                return True
            else:
                if self.status_callback:
                    self.status_callback("Hardware switches not connected.")
                    self.reader = None
                parent = self.parent()
                if parent:
                    QtCore.QTimer.singleShot(0, parent.show_hardware_connection_error)

        except Exception as e:
            log.error(f"Serial port error: {port}: {e}")
        return False    

    def poll(self):
        if self.reader:
            self.reader.poll()

    def update_activate_state(self, state):
        if self.hardware_activate_state != state:
            self.hardware_activate_state = state
            self.activateStateChanged.emit(state)

    def get_flight_mode(self):
        return self.reader.last_known_state[SwitchIndex.FLIGHT_MODE] if self.reader else 0

    def get_assist_level(self):
        return self.reader.last_known_state[SwitchIndex.ASSIST] if self.reader else 0

    def get_load_level(self):
        return self.reader.last_known_state[SwitchIndex.LOAD] if self.reader else 0

    def get_intensity_level(self):
        return self.reader.last_known_state[SwitchIndex.INTENSITY] if self.reader else 0

    def get_activate_state(self):
        return self.hardware_activate_state
