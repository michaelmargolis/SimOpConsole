"""
Mdx_Panel.py  interface between sim panel and xplane
Written by Michael Margolis

"""

from XPPython3 import xp
# from collections import namedtuple
from udp_tx_rx import UdpReceive
import json

LISTEN_PORT = 10024

                
class PythonInterface:
    def XPluginStart(self):
        self.Name = "MdxPanel v.01"
        self.Sig = "Mdx.Panel.Gateway"
        self.Desc = "A plug-in that handles Panel I/O."
        


        #command drefs
        self.cmd_parkbrake =  xp.findDataRef("sim/flightmodel/controls/parkbrake") # float 0..1
        self.cmd_gear_deploy = xp.findDataRef("sim/multiplayer/position/plane1_gear_deploy") # float ration 0=up, 1 = down
        self.cmd_flaps= xp.findDataRef("sim/multiplayer/controls/flap_request")  # float 0..1

         
        self.cmd_throttle = xp.findDataRef("sim/multiplayer/controls/engine_throttle_request") # 1.0 is max
        # sim/flightmodel/engine/ENGN_thro  # float 0..1
        # sim/flightmodel/engine/ENGN_thro[x] where x is the engine you wish to control (from 0 to 7). Send it a float percentage: i.e. 0.75f for 75%.
        # You may want to toggle sim/operation/override/override_throttles so you're not fighting with the joystick.
        self.cmd_mixture = xp.findDataRef("sim/cockpit2/engine/actuators/mixture_ratio_all") # 0 cutoff, 1.0 full rich
        
        self.cmd_drefs = [self.parkbrake, self.gear_deploy, self.flaps, self.throttle, self.mixture ]
        self.NumberOfDatarefs = len(self.cmd_drefs)  

        #status drefs
        self.evt_parkbrake =  xp.findDataRef("sim/flightmodel/controls/parkbrake") # float 0..1
        self.evt_gear_deploy = xp.findDataRef("sim/multiplayer/position/plane1_gear_deploy") # float ration 0=up, 1 = down
        # "sim/flightmodel2/gear/deploy_ratio"
        # "sim/aircraft/parts/acf_gear_deploy"  arrays!
        self.evt_flaps= xp.findDataRef("sim/flightmodel/controls/flaprat" )  # float ?
        # "sim/flightmodel2/wing/flap1_deg"
        self.evt_throttle = xp.findDataRef("sim/cockpit2/engine/actuators/throttle_ratio") # 1.0 is max
        # sim/flightmodel/engine/ENGN_thro  # float 0..1
        self.evt_mixture = xp.findDataRef("sim/cockpit2/engine/actuators/mixture_ratio_all") # 0 cutoff, 1.0 full rich

                
        self.Labels =  ('Parking brake', 'Landing gear', 'Flaps', 'Throttle', 'Mixture')


        # Create our menu
        Item = xp.appendMenuItem(xp.findPluginsMenu(), "Flight Panel control", 0)
        self.InputOutputMenuHandlerCB = self.InputOutputMenuHandler
        self.Id = xp.createMenu("Panel Control", xp.findPluginsMenu(), Item, self.InputOutputMenuHandlerCB, 0)
        xp.appendMenuItem(self.Id, "View Datarefs", 1)

        # Flag to tell us if the widget is being displayed.
        self.MenuItem1 = 0

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

        if self.MenuItem1 == 1:
            xp.destroyWidget(self.InputOutputWidget, 1)
            self.MenuItem1 = 0

        xp.destroyMenu(self.Id)

    def XPluginEnable(self):
        return 1

    def XPluginDisable(self):
        pass

    def XPluginReceiveMessage(self, inFromWho, inMessage, inParam):
        pass

    def InputOutputLoopCallback(self, elapsedMe, elapsedSim, counter, refcon):     
        xyzrpy = self.read_transform()
        xyzrpy_str = ['{:.3f}'.format(x) for x in xyzrpy]

        msg = ",".join(s for s in xyzrpy_str)     
        msg =   msg + '\n'     
        self.send_sock.sendto(msg.encode('utf-8') , ('127.0.0.1',10022))

        if self.MenuItem1 == 0:  # Don't update GUI if widget not visible
            for Item in range(len(xyzrpy_str)): 
                xp.setWidgetDescriptor(self.OutputEdit[Item], xyzrpy_str[Item])
        
        # This means call us every 25ms.
        return 0.025

    def InputOutputMenuHandler(self, inMenuRef, inItemRef):
        # If menu selected create our widget dialog
        if inItemRef == 1:
            if self.MenuItem1 == 0:
                self.CreateInputOutputWidget(300, 550, 350, 350)
                self.MenuItem1 = 1
            else:
                if not xp.isWidgetVisible(self.InputOutputWidget):
                    xp.showWidget(self.InputOutputWidget)

    """
    This will create our widget dialog.
    I have made all child widgets relative to the input paramter.
    This makes it easy to position the dialog
    """
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

        # For each engine
        CaptionText = []
        self.InputEdit = []
        self.OutputEdit = []
        for Item in range(len(self.Labels)):
            # Create a text widget

            CaptionText.append(xp.createWidget(x + 60, y - (60 + (Item * 30)), x + 90, y - (82 + (Item * 30)), 1,
                         self.Labels[Item], 0, self.InputOutputWidget, xp.WidgetClass_Caption))
            self.OutputEdit.append(xp.createWidget(x + 190, y - (60 + (Item * 30)), x + 270, y - (82 + (Item * 30)), 1,
                         "?", 0, self.InputOutputWidget, xp.WidgetClass_TextField))  

        # Register our widget handler
        self.InputOutputHandlerCB = self.InputOutputHandler
        xp.addWidgetCallback(self.InputOutputWidget, self.InputOutputHandlerCB)

    def InputOutputHandler(self, inMessage, inWidget, inParam1, inParam2):
        if inMessage == xp.Message_CloseButtonPushed:
            if self.MenuItem1 == 1:
                xp.hideWidget(self.InputOutputWidget)
            return 1

        return 0
        
        
    def read_transform(self):
        try:       
            datarefs = [] 
            for Item in range(self.NumberOfDatarefs): 
                datarefs.append( xp.getDataf(self.OutputDataRef[Item])) 

        
            #    raw_data = self.xpc.getDREFs(self.xform_drefs) # try and get telemetry
            raw_data = tuple(datarefs)
            named_data = transform_refs._make(raw_data) # load namedtuple with values 
            pre_norm = self.calculate_transform(named_data)
            # return (x, y, z, roll, pitch, yaw)

            xyzrpy = [pre_norm[i] * self.norm_factors[i] for i in range(len(pre_norm))]
            return xyzrpy
        except Exception as e:
            xp.log(str(e) + " reading datarefs")
            return (0,0,0,0,0,0)

   
   # method below derived from: https://developer.x-plane.com/code-sample/motionplatformdata/
    def calculate_transform(self, dref):

        #  ratio = self.clamp(dref.DR_groundspeed * 0.2, 0.0, 1.0)
        a_axil = dref.DR_g_axil
        a_side = dref.DR_g_side
        a_nrml = dref.DR_g_nrml -1
        
        roll = radians(dref.DR_P)
        pitch = radians(dref.DR_Q) 
        yaw = radians(dref.DR_R)         

        xyzrpy = [a_axil, a_side, a_nrml, roll, pitch, yaw]
        return xyzrpy
