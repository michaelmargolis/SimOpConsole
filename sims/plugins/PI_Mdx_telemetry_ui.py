import json
import time
from XPPython3 import xp
from collections import namedtuple
from math import radians
from udp_tx_rx import UdpReceive
from situation_loader import SituationLoader
from accessibility import load_accessibility_settings, set_accessibility

# === Configuration Constants ===
TARGET_PORT = 10022
LISTEN_PORT = 10023
FLIGHT_LOOP_INTERVAL = 0.025
ICAO_BUFFER_SIZE = 40

transform_refs = namedtuple('transform_refs', (
    'DR_g_axil', 'DR_g_side', 'DR_g_nrml',
    'DR_Prad', 'DR_Qrad', 'DR_Rrad',
    'DR_theta', 'DR_psi', 'DR_phi',
    'DR_groundspeed'
))

class PythonInterface:
    def XPluginStart(self):
        self.Name = "PlatformItf v1.01"
        self.Sig = "Mdx.Python.UdpTelemetry"
        self.Desc = "Sends json 6DoF telemetry + ICAO code over UDP to platform."

        self.controller_addr = []
        self.udp = UdpReceive(LISTEN_PORT)
        self.situation_loader = SituationLoader()
        self.settings = load_accessibility_settings()

        self.init_drefs()
        self.init_command_handlers()

        self.last_sent_named = None
        self.is_ui_visible = False
        self.jitter_intervals = []
        self.last_loop_time = None
        self.max_jitter_samples = 50
        self.telemetry_widget_id = None

        self.OutputEdit = []
        self.jitter_avg = None
        self.jitter_min = None
        self.jitter_max = None
        self.jitter_caption = None

        # Create menu with dialog
        Item = xp.appendMenuItem(xp.findPluginsMenu(), "Flight transforms", 0)
        self.InputOutputMenuHandlerCB = self.InputOutputMenuHandler
        self.Id = xp.createMenu("MDX Platform Interface", xp.findPluginsMenu(), Item, self.InputOutputMenuHandlerCB, 0)
        xp.appendMenuItem(self.Id, "View Transforms", 1)

        xp.registerFlightLoopCallback(self.InputOutputLoopCallback, 1.0, 0)
        return self.Name, self.Sig, self.Desc

    def XPluginStop(self):
        xp.unregisterFlightLoopCallback(self.InputOutputLoopCallback, 0)
        if self.is_ui_visible and self.telemetry_widget_id:
            xp.destroyWidget(self.telemetry_widget_id, 1)
            self.is_ui_visible = False
        xp.destroyMenu(self.Id)
        self.udp.close()

    def XPluginEnable(self):
        return 1

    def XPluginDisable(self):
        pass

    def XPluginReceiveMessage(self, inFromWho, inMessage, inParam):
        pass

    def InputOutputLoopCallback(self, elapsedMe, elapsedSim, counter, refcon):
        try:
            telemetry = self.read_telemetry()
            for addr in self.controller_addr:
                self.udp.send(telemetry, (addr, TARGET_PORT))
        except Exception as e:
            xp.log(f"[PlatformItf] ERROR: Telemetry send failed: {e}")

        if self.is_ui_visible and self.last_sent_named:
            telemetry_str = [f"{getattr(self.last_sent_named, f):.3f}" for f in self.last_sent_named._fields]
            for i, val in enumerate(telemetry_str):
                xp.setWidgetDescriptor(self.OutputEdit[i], val)

            now = time.perf_counter()
            if self.last_loop_time is not None:
                delta = now - self.last_loop_time
                self.jitter_intervals.append(delta)
                if len(self.jitter_intervals) > self.max_jitter_samples:
                    self.jitter_intervals.pop(0)

                intervals_ms = [x * 1000 for x in self.jitter_intervals]
                self.jitter_avg = sum(intervals_ms) / len(intervals_ms)
                self.jitter_min = min(intervals_ms)
                self.jitter_max = max(intervals_ms)

                jitter_text = f"Jitter Avg: {self.jitter_avg:.2f} ms | Min: {self.jitter_min:.2f} ms | Max: {self.jitter_max:.2f} ms"
                xp.setWidgetDescriptor(self.jitter_caption, jitter_text)
                controller_text = "Controllers: " + ", ".join(self.controller_addr) if self.controller_addr else "Controllers: None"
                xp.setWidgetDescriptor(self.controller_caption, controller_text)

            self.last_loop_time = now

        # Process incoming UDP messages
        while self.udp.available() > 0:
            try:
                addr, payload = self.udp.get()
                msg = payload.split(',')
                cmd = msg[0].strip()
                if cmd in self.command_handlers:
                    self.command_handlers[cmd](addr, msg)
                else:
                    xp.log(f"[PlatformItf] WARN: Unknown command received: {cmd}")
            except Exception as e:
                xp.log(f"[PlatformItf] ERROR: UDP command handling failed: {e}")

        return FLIGHT_LOOP_INTERVAL

    def InputOutputMenuHandler(self, inMenuRef, inItemRef):
        if inItemRef == 1:
            if not self.is_ui_visible:
                self.createTelemetryWidget(300, 600, 420, 380)
                self.is_ui_visible = True
            elif not xp.isWidgetVisible(self.telemetry_widget_id):
                xp.showWidget(self.telemetry_widget_id)

    def createTelemetryWidget(self, x, y, w, h):
        x2 = x + w
        y2 = y - h

        self.telemetry_widget_id = xp.createWidget(x, y, x2, y2, 1, "Telemetry Debug Info", 1, 0, xp.WidgetClass_MainWindow)
        xp.setWidgetProperty(self.telemetry_widget_id, xp.Property_MainWindowHasCloseBoxes, 1)

        sub_window = xp.createWidget(x + 10, y - 30, x2 - 10, y2 + 10, 1, "", 0, self.telemetry_widget_id, xp.WidgetClass_SubWindow)
        xp.setWidgetProperty(sub_window, xp.Property_SubWindowType, xp.SubWindowStyle_SubWindow)

        self.OutputEdit.clear()
        label_width = 120
        field_width = 80
        row_height = 25
        for i, label in enumerate(transform_refs._fields):
            top = y - (40 + i * row_height)
            bottom = top - 20
            xp.createWidget(x + 20, top, x + 20 + label_width, bottom, 1, label, 0, self.telemetry_widget_id, xp.WidgetClass_Caption)
            self.OutputEdit.append(xp.createWidget(x + 30 + label_width, top, x + 30 + label_width + field_width, bottom, 1, "?", 0, self.telemetry_widget_id, xp.WidgetClass_TextField))

        # Add jitter caption below transform fields
        top = y - (40 + len(transform_refs._fields) * row_height)
        bottom = top - 20
        self.jitter_caption = xp.createWidget(x + 20, top, x + 20 + 360, bottom, 1, "Jitter: ---", 0, self.telemetry_widget_id, xp.WidgetClass_Caption)
        # Add controller list caption below jitter info
        top = bottom - 25
        bottom = top - 20
        self.controller_caption = xp.createWidget(x + 20, top, x + 20 + 360, bottom, 1, "Controllers: ---", 0, self.telemetry_widget_id, xp.WidgetClass_Caption)

        xp.addWidgetCallback(self.telemetry_widget_id, self.widgetCallback)
        
    def widgetCallback(self, inMessage, inWidget, inParam1, inParam2):
        # xp.log(f"{inMessage == xp.Message_CloseButtonPushed}, {inWidget == self.telemetry_widget_id}")
        if inMessage == xp.Message_CloseButtonPushed and inWidget == self.telemetry_widget_id:
            xp.hideWidget(self.telemetry_widget_id)
            self.is_ui_visible = False
            return 1


    def read_icao_code(self):
        if self.acf_icao_ref:
            buf = [0] * ICAO_BUFFER_SIZE
            xp.getDatab(self.acf_icao_ref, buf, 0, ICAO_BUFFER_SIZE)
            return bytes(buf).decode('utf-8').strip('\x00')
        return "unknown"

    def build_telemetry_dict(self, named, icao):
        return {
            "header": "xplane_telemetry",
            "g_axil":  -named.DR_Rrad,
            "g_side":  -named.DR_Qrad,
            "g_nrml":  -named.DR_Prad,
            "Prad":    named.DR_g_nrml - 1.0,
            "Qrad":    -named.DR_g_side,
            "Rrad":    -named.DR_g_axil,
            "phi":     radians(named.DR_phi),
            "theta":   -radians(named.DR_theta),
            "icao":    icao
        }

    def read_telemetry(self):
        try:
            icao = self.read_icao_code()
        except Exception:
            icao = "unknown"

        data = [xp.getDataf(ref) for ref in self.OutputDataRef]
        named = transform_refs._make(data)
        self.last_sent_named = named
        telemetry_dict = self.build_telemetry_dict(named, icao)
        return json.dumps(telemetry_dict)

    def init_drefs(self):
        self.xform_drefs = [
            'sim/flightmodel/forces/g_axil',
            'sim/flightmodel/forces/g_side',
            'sim/flightmodel/forces/g_nrml',
            'sim/flightmodel/position/Prad',
            'sim/flightmodel/position/Qrad',
            'sim/flightmodel/position/Rrad',
            'sim/flightmodel/position/theta',
            'sim/flightmodel/position/psi',
            'sim/flightmodel/position/phi',
            'sim/flightmodel/position/groundspeed'
        ]
        self.OutputDataRef = [xp.findDataRef(ref) for ref in self.xform_drefs]
        self.NumberOfDatarefs = len(self.OutputDataRef)

        missing = [ref for ref, dr in zip(self.xform_drefs, self.OutputDataRef) if dr is None]
        if missing:
            xp.log(f"[PlatformItf] ERROR: Missing datarefs: {missing}")

        self.pauseCmd = xp.findCommand("sim/operation/pause_toggle")
        self.pauseStateDR = xp.findDataRef("sim/time/paused")
        self.replay_play = xp.findCommand("sim/replay/rep_play_rf")
        self.go_to_replay_begin = xp.findCommand("sim/replay/rep_begin")
        self.acf_icao_ref = xp.findDataRef("sim/aircraft/view/acf_ICAO")

    def init_command_handlers(self):
        self.command_handlers = {
            'InitComs': self.cmd_init_coms,
            'Run': self.cmd_run,
            'PauseToggle': self.cmd_pause_toggle,
            'Pause': self.cmd_pause,
            'Play': self.cmd_play,
            'Reset_playback': self.cmd_reset_playback,
            'Replay': self.cmd_replay,
            'Situation': self.cmd_situation,
            'FlightMode': self.cmd_flight_mode,
            'AssistLevel': self.cmd_assist_level
        }

    def cmd_init_coms(self, addr, msg):
        if addr[0] not in self.controller_addr:
            self.controller_addr.append(addr[0])
            xp.log(f"[PlatformItf] INFO: Controller added: {addr[0]}")

    def cmd_run(self, addr, msg):
        if xp.getDatai(self.pauseStateDR):
            xp.log("[PlatformItf] INFO: Run command received. Unpausing X-Plane.")
            xp.commandOnce(self.pauseCmd)

    def cmd_pause_toggle(self, addr, msg):
        xp.log("[PlatformItf] INFO: Pause toggle command received.")
        xp.commandOnce(self.pauseCmd)

    def cmd_pause(self, addr, msg):
        is_paused = xp.getDatai(self.pauseStateDR)
        xp.log(f"[PlatformItf] INFO: Pause command received. Current pause state: {is_paused}")
        if not is_paused:
            xp.commandOnce(self.pauseCmd)

    def cmd_play(self, addr, msg):
        xp.commandOnce(self.replay_play)

    def cmd_reset_playback(self, addr, msg):
        xp.commandOnce(self.go_to_replay_begin)

    def cmd_replay(self, addr, msg):
        if len(msg) > 1:
            filepath = msg[1].strip()
            ret = xp.loadDataFile(xp.DataFile_ReplayMovie, filepath)
            xp.log(f"[PlatformItf] INFO: Loaded Replay: {filepath}, return={ret}")

    def cmd_situation(self, addr, msg):
        if len(msg) > 1:
            filepath = msg[1].strip()
            ret = xp.loadDataFile(xp.DataFile_Situation, filepath)
            xp.log(f"[PlatformItf] INFO: Loaded Situation: {filepath}, return={ret}")

    def cmd_flight_mode(self, addr, msg):
        if len(msg) > 1:
            try:
                mode = int(msg[1].strip())
                self.situation_loader.load_situation(mode)
            except Exception as e:
                xp.log(f"[PlatformItf] ERROR: FlightMode invalid: {e}")

    def cmd_assist_level(self, addr, msg):
        if len(msg) > 1:
            try:
                level = int(msg[1].strip())
                if 0 <= level <= 2:
                    level_name = ['HIGH', 'MODERATE', 'NONE'][level]
                    xp.log(f"[PlatformItf] INFO: Assist level received: {level}")
                    set_accessibility(level_name)
                    xp.log(f"[PlatformItf] INFO: Set Pilot Assist to: {level_name}")
                else:
                    xp.log(f"[PlatformItf] WARN: AssistLevel out of range: {level}")
            except Exception as e:
                xp.log(f"[PlatformItf] ERROR: AssistLevel invalid: {e}")
