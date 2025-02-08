"""
Mdx_Telemetry
Written by Michael Margolis

Sends 6DoF Xplane telemetry over UDP.

# xplane uses OpenGL coordinates - x is right, y up, z back

Mdx coordinate frame follows ROS conventions, positive values: X is forward, Y is left, Z is up,
roll is right side down, pitch is nose down, yaw is CCW; all from perspective of person on platform.

datarefs:
    xplane translation acc are in g 
        axil = surge = x  (invert)
        side = sway = y   (invert) 
        nrml = heave = z  
    xplane roll and pitch are in degrees
    rotation velocities are rad/sec
        roll               (deg to rad, invert)  
        pitch              (deg to rad   invert
        yaw                (invert) 
    

        // Translation
        double acc_axial;               // [G] backward +
        double acc_lateral;             // [G] right +
        double acc_normal;              // [G] up +, +1.0 normal g

        // Rotation
        double vel_roll;                // [rad/sec] clockwise + (Rechtskurve)
        double vel_pitch;               // [rad/sec] nose up +
        double vel_yaw;                 // [rad/sec] clockwise + (Rechtskurve)
        double roll;                    // [deg] clockwise +
        double pitch;                   // [deg] nose up +
 

   msg format:
        surge accel, sway accel, heave accel, roll vel, pitch vel, yaw vel, roll, pitch 
"""


#"D:\Program Files\X-Plane 12\X-Plane.exe" --load_rep="D:\MdxCessnaFlight.rep"

from XPPython3 import xp
from collections import namedtuple
from math import radians #, pi, degrees, sqrt
from udp_tx_rx import UdpReceive
import XPLMDataAccess

transform_refs = namedtuple('transform_refs', \
                   ('DR_g_axil', 'DR_g_side', 'DR_g_nrml', \
                    'DR_Prad', 'DR_Qrad',  'DR_Rrad', \
                    'DR_theta', 'DR_psi', 'DR_phi', \
                    'DR_groundspeed'))
                     
TARGET_PORT = 10022 # port of sim interface controller telemetry socket 

xplm_key_pause = 0


class PythonInterface:
    def XPluginStart(self):
        self.Name = "PlatformItf v1.01"
        self.Sig = "Mdx.Python.UdpTelemetry"
        self.Desc = "A plug-in for the Mdx platform that sends telemetry data over UDP."
        LISTEN_PORT = 10023
        self.controller_addr = []
        self.udp = UdpReceive(LISTEN_PORT)
        
        self.init_drefs()
 
        # Create our menu
        Item = xp.appendMenuItem(xp.findPluginsMenu(), "Flight transforms", 0)
        self.InputOutputMenuHandlerCB = self.InputOutputMenuHandler
        self.Id = xp.createMenu("Platform Interface", xp.findPluginsMenu(), Item, self.InputOutputMenuHandlerCB, 0)
        xp.appendMenuItem(self.Id, "View Transforms", 1)
     
        self.IsWidgetVisible = 0  # Flag indicating if widget is being displayed.

        self.OutputDataRef = []
        for Item in range(len(self.xform_drefs)):
            self.OutputDataRef.append(xp.findDataRef(self.xform_drefs[Item]))

        # Register our FL callbadk with initial callback freq of 1 second
        self.InputOutputLoopCB = self.InputOutputLoopCallback
        xp.registerFlightLoopCallback(self.InputOutputLoopCB, 1.0, 0)

        return self.Name, self.Sig, self.Desc

    def XPluginStop(self):
        # Unregister the callback
        xp.unregisterFlightLoopCallback(self.InputOutputLoopCB, 0)

        if self.IsWidgetVisible == 1:
            xp.destroyWidget(self.InputOutputWidget, 1)
            self.IsWidgetVisible = 0

        xp.destroyMenu(self.Id)
        self.udp.close()

    def XPluginEnable(self):
        return 1

    def XPluginDisable(self):
        pass

    def XPluginReceiveMessage(self, inFromWho, inMessage, inParam):
        pass 

                    
    def init_drefs(self):
        self.xform_drefs = []
        # the following must match transform_refs namedtuple       
        self.xform_drefs.append('sim/flightmodel/forces/g_axil') 
        self.xform_drefs.append('sim/flightmodel/forces/g_side')
        self.xform_drefs.append('sim/flightmodel/forces/g_nrml')
        self.xform_drefs.append("sim/flightmodel/position/Prad") # roll rate rad/sec
        self.xform_drefs.append("sim/flightmodel/position/Qrad") # pitch rate rad/sec
        self.xform_drefs.append("sim/flightmodel/position/Rrad") # yaw rate  rad/sec
        self.xform_drefs.append("sim/flightmodel/position/theta") # pitch degrees
        self.xform_drefs.append("sim/flightmodel/position/psi") # heading degrees
        self.xform_drefs.append("sim/flightmodel/position/phi") # bank angle degrees
        self.xform_drefs.append("sim/flightmodel/position/groundspeed") # not yet used
        
       
        self.NumberOfDatarefs = len(self.xform_drefs)
        if self.NumberOfDatarefs != len(transform_refs._fields) :
            xp.log("invalid nbr drefs {} != {}".format(len(self.NumberOfDatarefs), len(transform_refs)))
                
        # self.XformDesc =  ('X (surge)', 'Y (sway)', 'Z (heave)', 'Roll', 'Pitch', 'Yaw')
        self.XformDesc =  ('Surge (g)', 'Sway (g)', 'Heave (g)', 'Roll rate (rad/s)', 'Pitch rate (rad/s)', 'Yaw rate (rad/s)', 'Roll angle (rad)', 'Pitch angle (rad)' )

        self.toggle_replay =  xp.findCommand('sim/replay/replay_toggle') # toggle replay mode on/off.
        self.replay_off = xp.findCommand('sim/replay/replay_off')  # Replay mode off.
       	self.go_to_replay_begin = xp.findCommand('sim/replay/rep_begin') # Replay mode: go to beginning.
        self.go_to_replay_end = xp.findCommand('sim/replay/rep_end') # Replay mode: go to end.
        self.replay_pause = xp.findCommand('sim/replay/rep_pause') # Replay mode: pause. 
        self.replay_play = xp.findCommand('sim/replay/rep_play_rf') # Replay mode: play forward.        
        self.pauseCmd =  xp.findCommand('sim/operation/pause_toggle')
        self.pauseStateDR =  xp.findDataRef('sim/time/paused')    # boolean int, 1 when paused
        
        # self.norm_factors = [2.0, 2.0, .5, -.02, .15, .15]
        self.norm_factors = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
     
        self.replay_mode = xp.findDataRef("sim/time/replay_mode");
    
    def InputOutputLoopCallback(self, elapsedMe, elapsedSim, counter, refcon):
        telemetry = self.read_telemetry()
        telemetry_str = ['{:.3f}'.format(x) for x in telemetry]
        msg = "xplane_telemetry," + ",".join(s for s in telemetry_str)     
        msg =   msg + '\n' 
        try:
            for addr in self.controller_addr:        
                self.udp.send(msg, (addr, TARGET_PORT))
        except:
            pass
        
        while self.udp.available() > 0:
            addr, payload = self.udp.get()
            msg = payload.split(',')
            cmd = msg[0]
            print(msg,cmd)
            if cmd == 'InitComs':
                self.controller_addr.append(addr[0])
                print("Added controller IP address " + addr[0])              
            elif cmd == 'Run':
                xp.commandOnce(self.replay_play)
            elif cmd == 'PauseToggle':                    
                xp.commandOnce(self.pauseCmd)
            elif cmd == 'Pause':
                is_paused = xp.getDataf(self.pauseStateDR)
                print("is_paused={} {}".format(is_paused, is_paused == 1))
                if not is_paused:                 
                    xp.commandOnce(self.pauseCmd)            
            elif cmd == 'Reset':
                 xp.commandOnce(self.go_to_replay_begin)
            elif cmd == 'Replay':
                filepath = msg[1]
                # XPLMDataAccess.XPLMLoadDataFile(XPLMDataAccess.xplm_DataFile_Replay, filepath)
                ret = xp.loadDataFile(xp.DataFile_ReplayMovie, filepath)
                print(ret, msg, filepath)
                # XPLMDataAccess.XPLMSetDatai(self.replay_mode, 1)
            elif cmd == 'Situation':
                filepath = msg[1]
                # XPLMDataAccess.XPLMLoadDataFile(XPLMDataAccess.xplm_DataFile_Replay, filepath)
                ret = xp.loadDataFile(xp.DataFile_Situation, filepath)
                print(ret, msg, filepath)
                # XPLMDataAccess.XPLMSetDatai(self.replay_mode, 1)       
            else:
                print(msg)
                
        if self.IsWidgetVisible != 0:  # Don't update dialog if widget not visible
            for Item in range(len(telemetry_str)): 
                xp.setWidgetDescriptor(self.OutputEdit[Item], telemetry_str[Item])
                
        return 0.025 # callback every 25ms.

    def InputOutputMenuHandler(self, inMenuRef, inItemRef):
        # If menu selected create our widget dialog
        if inItemRef == 1:
            if self.IsWidgetVisible == 0:
                self.CreateInputOutputWidget(300, 550, 350, 350)
                self.IsWidgetVisible = 1
            else:
                if not xp.isWidgetVisible(self.InputOutputWidget):
                    xp.showWidget(self.InputOutputWidget)

    def CreateInputOutputWidget(self, x, y, w, h):
        x2 = x + w
        y2 = y - h

        # Create the Main Widget window
        self.InputOutputWidget = xp.createWidget(x, y, x2, y2, 1, "Python - Mdx Platform Interface",
                                                 1, 0, xp.WidgetClass_MainWindow)

        # Add Close Box decorations to the Main Widget
        xp.setWidgetProperty(self.InputOutputWidget, xp.Property_MainWindowHasCloseBoxes, 1)

        # Create the Sub Widget window
        InputOutputWindow = xp.createWidget(x + 50, y - 50, x2 - 50, y2 + 50, 1, "",
                                            0, self.InputOutputWidget, xp.WidgetClass_SubWindow)

        # Set the style to sub window
        xp.setWidgetProperty(InputOutputWindow, xp.Property_SubWindowType, xp.SubWindowStyle_SubWindow)

        CaptionText = []
        self.InputEdit = []
        self.OutputEdit = []
        for Item in range(len(self.XformDesc)):
            # Create a text widget

            CaptionText.append(xp.createWidget(x + 60, y - (60 + (Item * 30)), x + 90, y - (82 + (Item * 30)), 1,
                         self.XformDesc[Item], 0, self.InputOutputWidget, xp.WidgetClass_Caption))
            self.OutputEdit.append(xp.createWidget(x + 190, y - (60 + (Item * 30)), x + 270, y - (82 + (Item * 30)), 1,
                         "?", 0, self.InputOutputWidget, xp.WidgetClass_TextField))  

        # Register our widget handler
        self.InputOutputHandlerCB = self.InputOutputHandler
        xp.addWidgetCallback(self.InputOutputWidget, self.InputOutputHandlerCB)

    def InputOutputHandler(self, inMessage, inWidget, inParam1, inParam2):
        if inMessage == xp.Message_CloseButtonPushed:
            if self.IsWidgetVisible == 1:
                xp.hideWidget(self.InputOutputWidget)
            return 1
        return 0        
        
    def read_telemetry(self):
        try:       
            datarefs = [] 
            for Item in range(self.NumberOfDatarefs): 
                datarefs.append( xp.getDataf(self.OutputDataRef[Item]))
        
            raw_data = tuple(datarefs)
            named_data = transform_refs._make(raw_data) # load namedtuple with values 

            # see https://developer.x-plane.com/code-sample/motionplatformdata/
            telemetry = []
            telemetry.append(named_data.DR_g_axil * -1) # surge_accel
            telemetry.append(named_data.DR_g_side * -1) # sway_accel
            telemetry.append(named_data.DR_g_nrml-1) # heave_accel
            telemetry.append(named_data.DR_Prad * -1) # roll_rate
            telemetry.append(named_data.DR_Qrad * -1) # pitch_rate
            telemetry.append(named_data.DR_Rrad * -1)  # yaw_rate
            telemetry.append(radians(named_data.DR_phi)) # bank angle
            telemetry.append(radians(named_data.DR_theta) * -1) # pitch angle
      

            return telemetry
        except Exception as e:
            xp.log(str(e) + " reading datarefs")
            return [0,0,0,0,0,0,0,0]
