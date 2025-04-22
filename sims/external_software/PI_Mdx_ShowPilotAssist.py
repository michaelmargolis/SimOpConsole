# PI_show_pilot_assist.py
# Displays current values of accessibility datarefs in a GUI window, and allows editing one value at a time

from XPPython3 import xp
from accessibility import load_accessibility_settings, set_accessibility
import os

ACCESSIBILITY_FILE = os.path.join(os.path.dirname(__file__), "accessibility.txt")
LEVELS = ["HIGH", "MODERATE", "NONE"]

class PythonInterface:
    def XPluginStart(self):
        self.Name = "PI_show_pilot_assist"
        self.Sig = "Mdx.Python.ShowPilotAssist"
        self.Desc = "Interactive display and control for pilot assist datarefs."

        self.settings = load_accessibility_settings(ACCESSIBILITY_FILE)
        self.monitored_refs = {}
        for level in LEVELS:
            for dataref in self.settings[level]:
                if dataref not in self.monitored_refs:
                    ref = xp.findDataRef(dataref)
                    if ref:
                        self.monitored_refs[dataref] = ref

        self.selected_dataref = None
        self.input_buffer = ""

        self.left = 100
        self.top = 600
        self.right = 800
        self.bottom = 300

        self.win_id = xp.createWindowEx(
            dict(
                structSize=xp.WindowExCreateStructs,  # corrected usage of createWindowEx
                left=self.left,
                top=self.top,
                right=self.right,
                bottom=self.bottom,
                visible=1,
                drawWindowFunc=self.draw_window,
                handleMouseClickFunc=self.handle_mouse_click,
                handleKeyFunc=self.handle_key,
                handleRightClickFunc=None,
                decoration=xp.WindowDecorationRoundRectangle,
                layer=xp.WindowLayerFloatingWindows,
                refcon=0,
                windowTitle="Pilot Assist Monitor"
            )
        )

        xp.registerFlightLoopCallback(self.update_display, 0.5, 0)
        return self.Name, self.Sig, self.Desc

    def XPluginStop(self):
        xp.unregisterFlightLoopCallback(self.update_display, 0)
        xp.destroyWindow(self.win_id)

    def XPluginEnable(self):
        return 1

    def XPluginDisable(self):
        pass

    def XPluginReceiveMessage(self, inFromWho, inMessage, inParam):
        pass

    def update_display(self, el, es, c, r):
        xp.setWindowPositioningMode(self.win_id, xp.WindowPositionFree, -1)
        xp.setWindowTitle(self.win_id, "Pilot Assist Monitor")
        return 0.5

    def draw_window(self, window_id, refcon):
        l, t, r, b = xp.getWindowGeometry(window_id)
        y = t - 20

        xp.drawString((1.0, 1.0, 1.0), l + 10, y, "DataRef", 0, xp.Font_Basic)
        xp.drawString((1.0, 1.0, 1.0), l + 350, y, "Value", 0, xp.Font_Basic)
        y -= 20

        for dataref, handle in sorted(self.monitored_refs.items()):
            val = xp.getDataf(handle) if isinstance(self.settings["HIGH"].get(dataref, 0), float) else xp.getDatai(handle)
            label = dataref.split("/")[-1].split("=")[0]

            color = (1.0, 1.0, 0.5) if dataref == self.selected_dataref else (1.0, 1.0, 1.0)
            xp.drawString(color, l + 10, y, label, 0, xp.Font_Basic)
            xp.drawString(color, l + 350, y, str(val), 0, xp.Font_Basic)
            y -= 20

        if self.selected_dataref:
            xp.drawString((0.7, 1.0, 0.7), l + 10, b + 20, f"Editing: {self.selected_dataref} = {self.input_buffer}", 0, xp.Font_Basic)

    def handle_mouse_click(self, window_id, x, y, refcon):
        l, t, r, b = xp.getWindowGeometry(window_id)
        y_cursor = t - 40
        i = 0
        for dataref in sorted(self.monitored_refs.keys()):
            if y_cursor - 20 <= y <= y_cursor:
                self.selected_dataref = dataref
                self.input_buffer = ""
                break
            y_cursor -= 20
            i += 1
        return 1

    def handle_key(self, window_id, key, flags, virtual, refcon, losing):
        if self.selected_dataref is None:
            return 0

        if key == chr(13):  # Enter key
            try:
                ref = self.monitored_refs[self.selected_dataref]
                if "." in self.input_buffer:
                    xp.setDataf(ref, float(self.input_buffer))
                else:
                    xp.setDatai(ref, int(self.input_buffer))
            except Exception as e:
                xp.log(f"[ERROR] Invalid input: {e}")
            self.selected_dataref = None
            self.input_buffer = ""
        elif key == chr(27):  # Escape
            self.selected_dataref = None
            self.input_buffer = ""
        elif key in ("\b", chr(8)):  # Backspace
            self.input_buffer = self.input_buffer[:-1]
        elif key.isprintable():
            self.input_buffer += key
        return 1
