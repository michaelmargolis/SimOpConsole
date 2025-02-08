import win32com.client
import pythoncom
swYearLast2Digits = 19 # for sw 2019
sw = win32com.client.Dispatch("SldWorks.Application.%d" % (10+(swYearLast2Digits-2)))  # e.g. 20 is SW2012,  23 is SW2015



model = sw.ActiveDoc
modelExt = model.Extension
selMgr = model.SelectionManager
featureMgr = model.FeatureManager
sketchMgr = model.SketchManager
eqMgr = model.GetEquationMgr

swUpdateMates = 4
swAllConfiguration = 2

def modify_equation(index, name, value):
    ret = eqMgr.SetEquationAndConfigurationOption(index,  format('"%s" = %d' % (name, value)), swAllConfiguration, "")
    if ret  != 1:
        print("Failed to modify a dimension equation:", format('"%s" = %d' % (name, value)))

def set_strut(index, value):
   name = format('"D1@StrutDistance%d"  = %dmm' % (index, int(value)))
   print("setting strut", index,  name)
   #name = format('"strut%d"  = %d' % (index, value))
   eqMgr.Equation(index, name)
   # modify_equation(index, name, value)

def set_struts(struts):
    for idx, strut_len in enumerate(struts):
        set_strut(idx+1, strut_len) # vba index starts at 1
    model.Rebuild (swUpdateMates)

def getGlobalVariables():
    data = {};
    for i in range(eqMgr.getCount;):
        if eqMgr.GlobalVariable(i):
            print(eqMgr.Equation(i))
            data[eqMgr.Equation(i).split('"')[1]] = i

    if len(data.keys()) == 0:
        return None
    else:
        return data;

def modifyGlobalVar(variable, new_value):
    data = self.getGlobalVariables();
    if data:
        eqMgr.Equation(data[variable], "\""+variable+"\" = "+str(new_value)+unit+"");
    self.updatePrt();

if __name__ == '__main__':
    print(getGlobalVariables)

