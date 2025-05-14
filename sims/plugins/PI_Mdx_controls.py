"""
PI_Mdx_controls.py
flight sim panael Input / Output

command msg format:  'cmd;{"Parking_brake":(0/1),"Landing_gear":(0/1),"Flaps":(0..1),"Throttle":(0..1),"Mixture":(0..1)}\n'  
event msg format     'evt;{"Parking_brake":(0/1),"Landing_gear":(0/1),"Flaps":(0..1),"Throttle":(0..1),"Mixture":(0..1)}\n'  

"""

from XPPython3 import xp
from udp_tx_rx import UdpReceive
import json

LISTEN_PORT = 10024  # port to listen on, default sender is 10025
                         

class PythonInterface:
    def XPluginStart(self):
        self.Name = "InputOutput1 v.01"
        self.Sig = "FlightPanel.Python.InputOutput1"
        self.Desc = "A plug-in that handles data Input/Output."


        self.udp = UdpReceive(LISTEN_PORT)
        self.sender = None # address,port tuple  of command message senser
        
        self.fields =  ('Parking_brake', 'Landing_gear', 'Flaps', 'Throttle', 'Mixture')
        self.cmd_cache = [0,              0,              0,       0,          0] # cache received command values

        # Command dref inputs

        self.cmd_parkbrake =  xp.findDataRef("sim/flightmodel/controls/parkbrake") # float 0..1
        self.cmd_gear_deploy = xp.findDataRef("sim/multiplayer/position/plane1_gear_deploy") # float ration 0=up, 1 = down
        self.cmd_flaps= xp.findDataRef("sim/flightmodel/controls/flaprqst")  # float 0..1         
        self.cmd_throttle = xp.findDataRef("sim/cockpit2/engine/actuators/throttle_ratio_all") # 1.0 is max
        self.cmd_mixture = xp.findDataRef("sim/cockpit2/engine/actuators/mixture_ratio_all") # 0 cutoff, 1.0 full rich
        
        # sim/flightmodel/engine/ENGN_thro  # float 0..1

        # toggle sim/operation/override/override_throttles so not fighting with the joystick?

        
        self.cmd_drefs = [self.cmd_parkbrake, self.cmd_gear_deploy, self.cmd_flaps, self.cmd_throttle, self.cmd_mixture ]
        self.cmd_array_size = [0, 0, 0, 0, 0] # 0 is no array, 1 is array with index [0]
        self.cmd_values = [0, 0, 0, 0, 0]  # these are set from panel messages  

        # Event drefs

        self.evt_parkbrake =  xp.findDataRef("sim/flightmodel/controls/parkbrake") # float 0..1
        self.evt_gear_deploy = xp.findDataRef("sim/multiplayer/position/plane1_gear_deploy") # float ration 0=up, 1 = down
        # "sim/flightmodel2/gear/deploy_ratio"
        # "sim/aircraft/parts/acf_gear_deploy"  arrays!
        self.evt_flaps= xp.findDataRef("sim/flightmodel/controls/flaprat" )  # float ?
        # "sim/flightmodel2/wing/flap1_deg"
        self.evt_throttle = xp.findDataRef("sim/cockpit2/engine/actuators/throttle_ratio_all")  # float 0..1
        self.evt_mixture = xp.findDataRef("sim/cockpit2/engine/actuators/mixture_ratio_all")
        
        self.evt_drefs = [self.evt_parkbrake, self.evt_gear_deploy, self.evt_flaps, self.evt_throttle, self.evt_mixture ] 

        # overrides
        
        self.ovr_parkbrake = None #  xp.findDataRef("sim/flightmodel/controls/parkbrake") # float 0..1
        self.ovr_gear_deploy = None # xp.findDataRef("sim/multiplayer/position/plane1_gear_deploy") # float 0=up, 1 = down
        self.ovr_flaps = None # xp.findDataRef("sim/flightmodel/controls/flaprat" )  # float ?
        self.ovr_throttle = xp.findDataRef("sim/operation/override/override_throttles")  # float 0..1
        self.ovr_mixture = xp.findDataRef("sim/operation/override/override_mixture")

        self.ovr_drefs = [self.ovr_parkbrake, self.ovr_gear_deploy, self.ovr_flaps, self.ovr_throttle, self.ovr_mixture ] 

        """
        for Item in range(len(self.ovr_drefs)): 
            if self.ovr_drefs[Item]:
                self.SetDataRefState(self.ovr_drefs[Item], True)
        """ 
        # Create our menu
        Item = xp.appendMenuItem(xp.findPluginsMenu(), "Python - Input/Output 1", 0)
        self.InputOutputMenuHandlerCB = self.InputOutputMenuHandler
        self.Id = xp.createMenu("Input/Output 1", xp.findPluginsMenu(), Item, self.InputOutputMenuHandlerCB, 0)
        xp.appendMenuItem(self.Id, "Data", 1)

        # Flag to tell us if the widget is being displayed.
        self.MenuItem1 = 0
       
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
        self.udp.close()

    def XPluginEnable(self):
        return 1

    def XPluginDisable(self):
        pass

    def XPluginReceiveMessage(self, inFromWho, inMessage, inParam):
        pass

    def InputOutputLoopCallback(self, elapsedMe, elapsedSim, counter, refcon):
        self.service_msgs()
        # Process each field
        evt_msg = 'evt;{' # start of message
        for Item in range(len(self.fields)):
            # This gets the left side widget column with the panel values
            #value = xp.getWidgetDescriptor(self.InputEdit[Item])
            value = self.cmd_cache[Item]
            try:
                value = float(value)
                if value != self.cmd_values[Item]:
                    self.cmd_values[Item] = value
                    #  xp.log("setting {} to {}".format(self.fields[Item], value))
                    if self.cmd_array_size[Item] == 1:
                        xp.setDataf(self.cmd_drefs[Item][0], value)
                    else:
                        xp.setDataf(self.cmd_drefs[Item], value)
            except ValueError:
                pass # value is not a number
                # xp.log("unable to set {} to {}".format(self.fields[Item], value))
                value = None
            
            if True: # value:            
                xplane_value = xp.getDataf(self.evt_drefs[Item])
                if self.MenuItem1 != 0:  # Don't update dialog if widget not visible
                    # This updates the right side widget column with xplane values
                    xp.setWidgetDescriptor(self.OutputEdit[Item], str(xplane_value))
                    xp.setWidgetDescriptor(self.InputEdit[Item], '{:.3f}'.format(self.cmd_cache[Item]))
                evt_msg +=  '"{}":{:.3f},'.format(self.fields[Item], xplane_value)

        evt_msg += '}\n'
        if self.sender:
            self.udp.send(evt_msg, self.sender)
        
        return 0.1  

    def InputOutputMenuHandler(self, inMenuRef, inItemRef):
        # If menu selected create our widget dialog
        if inItemRef == 1:
            if self.MenuItem1 == 0:
                self.CreateInputOutputWidget(300, 550, 400, 300)
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
        self.InputOutputWidget = xp.createWidget(x, y, x2, y2, 1, "Flight Control interface by Middlesex University",
                                                 1, 0, xp.WidgetClass_MainWindow)

        # Add Close Box decorations to the Main Widget
        xp.setWidgetProperty(self.InputOutputWidget, xp.Property_MainWindowHasCloseBoxes, 1)

        # Create the Sub Widget window
        InputOutputWindow = xp.createWidget(x + 50, y - 50, x2 - 50, y2 + 50, 1, "",
                                            0, self.InputOutputWidget, xp.WidgetClass_SubWindow)

        # Set the style to sub window
        xp.setWidgetProperty(InputOutputWindow, xp.Property_SubWindowType, xp.SubWindowStyle_SubWindow)

        # For each field
        InputText = []
        self.InputEdit = [] # commands to xplane
        self.OutputEdit = [] # values from xplane
        for Item in range(len(self.fields)):
            # Create a text widget
            InputText.append(xp.createWidget(x + 60, y - (60 + (Item * 30)), x + 90, y - (82 + (Item * 30)), 1,
                                             self.fields[Item], 0, self.InputOutputWidget, xp.WidgetClass_Caption))

            # Create an edit widget for values from the panel
            self.InputEdit.append(xp.createWidget(x + 150, y - (60 + (Item * 30)), x + 230, y - (82 + (Item * 30)), 1,
                                                  "", 0, self.InputOutputWidget, xp.WidgetClass_TextField))

            # Set it to be text entry
            xp.setWidgetProperty(self.InputEdit[Item], xp.Property_TextFieldType, xp.TextEntryField)

            # Create an edit widget values to the panel
            self.OutputEdit.append(xp.createWidget(x + 240, y - (60 + (Item * 30)), x + 320, y - (82 + (Item * 30)), 1,
                                                   "", 0, self.InputOutputWidget, xp.WidgetClass_TextField))

            # Set it to be text entry
            xp.setWidgetProperty(self.OutputEdit[Item], xp.Property_TextFieldType, xp.TextEntryField)

        yIndex = len(self.fields)
        xp.createWidget(x + 60, y - (60 + (yIndex * 30)), x + 90, y - (82 + (yIndex * 30)), 1,
                                             'Listening on port {}'.format(LISTEN_PORT), 0, self.InputOutputWidget, xp.WidgetClass_Caption)
                                             
        # Register our widget handler
        self.InputOutputHandlerCB = self.InputOutputHandler
        xp.addWidgetCallback(self.InputOutputWidget, self.InputOutputHandlerCB)

    def InputOutputHandler(self, inMessage, inWidget, inParam1, inParam2):
        if inMessage == xp.Message_CloseButtonPushed:
            if self.MenuItem1 == 1:
                xp.hideWidget(self.InputOutputWidget)
            return 1

        return 0

    def GetDataRefState(self, DataRefID, isArray = False):
        if isArray:
            self.IntVals = []
            xp.getDatavi(DataRefID, self.IntVals, 0, 8)
            DataRefi = self.IntVals[0]
        else:
            DataRefi = xp.getDatai(DataRefID)

        return DataRefi

    def SetDataRefState(self, DataRefID, State, isArray = False):
        if isArray:
            IntVals = [State, 0, 0, 0, 0, 0, 0, 0]
            xp.setDatavi(DataRefID, IntVals, 0, 8)
        else:
            xp.setDatai(DataRefID, State)
            
    def service_msgs(self):
        while self.udp.available() > 0:
            self.sender,payload = self.udp.get()
            # print( self.sender,payload)
            try:
                msg = payload.split(';') 
                if len(msg) == 2 and msg[0] == 'cmd':
                    json_cmds = json.loads(msg[1])
                    for field in json_cmds:
                        try:
                            Index = self.fields.index(field) 
                            if self.cmd_cache[Index] != json_cmds[field]:
                                self.cmd_cache[Index] = json_cmds[field]
                                #  xp.setWidgetDescriptor(self.InputEdit[Index], '{:.3f}'.format(self.cmd_cache[Index]))
                                #print(field, self.cmd_dict[field], 'index=', self.fields.index(field), 'sender', got[0])
                        except ValueError:
                            xp.log('unexpected field: {}'.format(field)) 
                            pass # field is not one of our commands
            except Exception as e:
                xp.log(str(e)) 