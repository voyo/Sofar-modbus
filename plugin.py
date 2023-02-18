#!/usr/bin/env python
"""
Sofar Domoticz plugin.

Author: Wojtek Sawasciuk  <voyo@no-ip.pl>

Requirements: 
    1.python module minimalmodbus -> http://minimalmodbus.readthedocs.io/en/master/
        (pi@raspberrypi:~$ sudo pip3 install minimalmodbus)
    2.Communication module Modbus USB to RS485 converter module
"""
"""
<plugin key="Sofar" name="Sofar" version="0.1" author="voyo@no-ip.pl">
    <params>
        <param field="SerialPort" label="Modbus Port" width="200px" required="true" default="/dev/ttyUSB0" />
        <param field="Mode1" label="Baud rate" width="40px" required="true" default="9600"  />
        <param field="Mode2" label="Device ID" width="40px" required="true" default="1" />
        <param field="Mode3" label="Reading Interval min." width="40px" required="true" default="1" />
        <param field="Mode6" label="Debug" width="75px">
            <options>
                <option label="True" value="Debug"/>
                <option label="False" value="Normal"  default="false" />
            </options>
        </param>
    </params>
</plugin>

"""

import Domoticz
import minimalmodbus
import serial



class BasePlugin:
    def __init__(self):
        self.runInterval = 1
        self.RS485 = ""
        return

    def onStart(self):
        self.RS485 = minimalmodbus.Instrument(Parameters["SerialPort"], int(Parameters["Mode2"]))
        self.RS485.serial.baudrate = Parameters["Mode1"]
        self.RS485.serial.bytesize = 8
        self.RS485.serial.parity = minimalmodbus.serial.PARITY_NONE
        self.RS485.serial.stopbits = 1
        self.RS485.serial.timeout = 1
        self.RS485.debug = False
        self.RS485.mode = minimalmodbus.MODE_RTU
        
        devicecreated = []
        Domoticz.Log("Sofar-Modbus plugin start")
        
#     def __init__(self,    ID,name,nod,register,functioncode: int = 3,options=None, Used: int = 1, Description=None, TypeName=None,Type: int = 0, SubType:int = 0 , SwitchType:int = 0  ):
        self.sensors = [
                Dev(1,"Temperature_Env1",0,1048,functioncode=3,TypeName="Temperature",Description="Temperature_Env1",signed=True),
                Dev(2,"Temperature_Env2",0,1049,functioncode=3,TypeName="Temperature",Description="Temperature_Env2",signed=True),
                Dev(3,"Temperature_HeatSink1",0,1050,functioncode=3,TypeName="Temperature",Description="Temperature_HeatSink1",signed=True),
                Dev(4,"Temperature_HeatSink2",0,1051,functioncode=3,TypeName="Temperature",Description="Temperature_HeatSink2",signed=True),
                Dev(5,"Temperature_HeatSink3",0,1052,functioncode=3,TypeName="Temperature",Description="Temperature_HeatSink3",signed=True),
                Dev(6,"Temperature_HeatSink4",0,1053,functioncode=3,TypeName="Temperature",Description="Temperature_HeatSink4",signed=True),
                Dev(7,"Temperature_HeatSink5",0,1054,functioncode=3,TypeName="Temperature",Description="Temperature_HeatSink5",signed=True),
                Dev(8,"Temperature_HeatSink6",0,1055,functioncode=3,TypeName="Temperature",Description="Temperature_HeatSink6",signed=True),
                Dev(9,"Temperature_Inv1",0,1056,functioncode=3,TypeName="Temperature",Description="Temperature_Inv1",signed=True),
                Dev(10,"Temperature_Inv2",0,1057,functioncode=3,TypeName="Temperature",Description="Temperature_Inv2",signed=True),
                Dev(11,"Temperature_Inv3",0,1058,functioncode=3,TypeName="Temperature",Description="Temperature_Inv3",signed=True),
                Dev(12,"GenerationTime_Today",0,1062,functioncode=3,TypeName="Counter",SubType=5,Description="GenerationTime_Today"),
                Dev(13,"GenerationTime_Total",0,1063,functioncode=3,TypeName="Counter",SubType=5,Description="GenerationTime_Total"),
                Dev(14,"ServiceTime_Total",0,1064,functioncode=3,TypeName="Counter",SubType=5,Description="ServiceTime_Total"),
                Dev(15,"Frequency_grid",0,1156,functioncode=3,TypeName="Frequency",Description="Frequency_grid"),
                Dev(16,"ActivePower_Output_Total",0,1157,functioncode=3,TypeName="Usage",Description="ActivePower_Output_Total",signed=True),
                Dev(17,"ReactivePower_Output_Total",0,1158,functioncode=3,TypeName="Usage",Description="ReactivePower_Output_Total",signed=True),
                Dev(18,"ApparentPower_Output_Total",0,1159,functioncode=3,TypeName="Usage",Description="ApparentPower_Output_Total"),
                Dev(19,"ActivePower_PCC_Total",0,1160,functioncode=3,TypeName="Usage",Description="ActivePower_PCC_Total",signed=True),
                Dev(20,"ReactivePower_PCC_Total",0,1161,functioncode=3,TypeName="Usage",Description="ReactivePower_PCC_Total",signed=True),
                Dev(21,"ApparentPower_PCC_Total",0,1162,functioncode=3,TypeName="Usage",Description="ApparentPower_PCC_Total"),
   # phase R
                Dev(22,"Voltage_Phase_R",0,1165,functioncode=3,TypeName="Voltage",Description="Voltage_Phase_R"),
                Dev(23,"Current_Output_R",0,1166,functioncode=3,TypeName="Current",Description="Current_Output_R"),
                Dev(24,"ActivePower_Output_R",0,1167,functioncode=3,TypeName="Usage",Description="ActivePower_Output_R",signed=True),
                Dev(25,"ReactivePower_Output_R",0,1168,functioncode=3,TypeName="Usage",Description="ReactivePower_Output_R",signed=True),
                Dev(26,"PowerFactor_Output_R",0,1169,functioncode=3,TypeName="Percentage",Description="PowerFactor_Output_R",signed=True),
                Dev(27,"Current_PCC_R",0,1170,functioncode=3,TypeName="Current",Description="Current_PCC_R"),
                Dev(28,"ActivePower_PCC_R",0,1171,functioncode=3,TypeName="Usage",Description="ActivePower_PCC_R",signed=True),
                Dev(29,"ReactivePower_PCC_R",0,1172,functioncode=3,TypeName="Usage",Description="ReactivePower_PCC_R",signed=True),
                Dev(30,"PowerFactor_PCC_R",0,1173,functioncode=3,TypeName="Percentage",Description="PowerFactor_PCC_R",signed=True),
    # phase S
                Dev(31,"Voltage_Phase_S",0,1176,functioncode=3,TypeName="Voltage",Description="Voltage_Phase_S"),
                Dev(32,"Current_Output_S",0,1177,functioncode=3,TypeName="Current",Description="Current_Output_S"),
                Dev(33,"ActivePower_Output_S",0,1178,functioncode=3,TypeName="Usage",Description="ActivePower_Output_S",signed=True),
                Dev(34,"ReactivePower_Output_S",0,1179,functioncode=3,TypeName="Usage",Description="ReactivePower_Output_S",signed=True),
                Dev(35,"PowerFactor_Output_S",0,1180,functioncode=3,TypeName="Percentage",Description="PowerFactor_Output_S",signed=True),
                Dev(36,"Current_PCC_S",0,1181,functioncode=3,TypeName="Current",Description="Current_PCC_S"),
                Dev(37,"ActivePower_PCC_S",0,1182,functioncode=3,TypeName="Usage",Description="ActivePower_PCC_S",signed=True),
                Dev(38,"ReactivePower_PCC_S",0,1183,functioncode=3,TypeName="Usage",Description="ReactivePower_PCC_S",signed=True),
                Dev(39,"PowerFactor_PCC_S",0,1184,functioncode=3,TypeName="Percentage",Description="PowerFactor_PCC_S",signed=True),
    # phase T
                Dev(40,"Voltage_Phase_T",0,1187,functioncode=3,TypeName="Voltage",Description="Voltage_Phase_T"),
                Dev(41,"Current_Output_T",0,1188,functioncode=3,TypeName="Current",Description="Current_Output_T"),
                Dev(42,"ActivePower_Output_T",0,1189,functioncode=3,TypeName="Usage",Description="ActivePower_Output_T",signed=True),
                Dev(43,"ReactivePower_Output_T",0,1190,functioncode=3,TypeName="Usage",Description="ReactivePower_Output_T",signed=True),
                Dev(44,"PowerFactor_Output_T",0,1191,functioncode=3,TypeName="Percentage",Description="PowerFactor_Output_T",signed=True),
                Dev(45,"Current_PCC_T",0,1192,functioncode=3,TypeName="Current",Description="Current_PCC_T"),
                Dev(46,"ActivePower_PCC_T",0,1193,functioncode=3,TypeName="Usage",Description="ActivePower_PCC_T",signed=True),
                Dev(47,"ReactivePower_PCC_T",0,1194,functioncode=3,TypeName="Usage",Description="ReactivePower_PCC_T",signed=True),
                Dev(48,"PowerFactor_PCC_T",0,1195,functioncode=3,TypeName="Percentage",Description="PowerFactor_PCC_T",signed=True),
    # ext
                Dev(49,"ActivePower_PV_Ext",0,1198,functioncode=3,TypeName="Usage",Description="ActivePower_PV_Ext",signed=True),
                Dev(50,"ActivePower_Load_Sys",0,1199,functioncode=3,TypeName="Usage",Description="ActivePower_Load_Sys",signed=True),
    # phase R
                Dev(51,"Voltage_Output_R",0,1290,functioncode=3,TypeName="Voltage",Description="Voltage_Output_R"),
                Dev(52,"Current_Load_R",0,1291,functioncode=3,TypeName="Current",Description="Current_Load_R",signed=True),
                Dev(53,"ActivePower_Load_R",0,1292,functioncode=3,TypeName="Usage",Description="ActivePower_Load_R",signed=True),
                Dev(54,"ReactivePower_Load_R",0,1293,functioncode=3,TypeName="Usage",Description="ReactivePower_Load_R",signed=True),
                Dev(55,"ApparentPower_Load_R",0,1294,functioncode=3,TypeName="Usage",Description="ApparentPower_Load_R",signed=True),
                Dev(56,"LoadPeakRatio_R",0,1295,functioncode=3,TypeName="Percentage",Description="LoadPeakRatio_R"),
    # phase S
                Dev(57,"Voltage_Output_S",0,1298,functioncode=3,TypeName="Voltage",Description="Voltage_Output_S"),
                Dev(58,"Current_Load_S",0,1299,functioncode=3,TypeName="Current",Description="Current_Load_S",signed=True),
                Dev(59,"ActivePower_Load_S",0,1300,functioncode=3,TypeName="Usage",Description="ActivePower_Load_S",signed=True),
                Dev(60,"ReactivePower_Load_S",0,1301,functioncode=3,TypeName="Usage",Description="ReactivePower_Load_S",signed=True),
                Dev(61,"ApparentPower_Load_S",0,1302,functioncode=3,TypeName="Usage",Description="ApparentPower_Load_S",signed=True),
                Dev(62,"LoadPeakRatio_S",0,1303,functioncode=3,TypeName="Percentage",Description="LoadPeakRatio_S"),
    # phase T
                Dev(63,"Voltage_Output_T",0,1306,functioncode=3,TypeName="Voltage",Description="Voltage_Output_T"),
                Dev(64,"Current_Load_T",0,1307,functioncode=3,TypeName="Current",Description="Current_Load_T",signed=True),
                Dev(65,"ActivePower_Load_T",0,1308,functioncode=3,TypeName="Usage",Description="ActivePower_Load_T",signed=True),
                Dev(66,"ReactivePower_Load_T",0,1309,functioncode=3,TypeName="Usage",Description="ReactivePower_Load_T",signed=True),
                Dev(67,"ApparentPower_Load_T",0,1310,functioncode=3,TypeName="Usage",Description="ApparentPower_Load_T",signed=True),
                Dev(68,"LoadPeakRatio_T",0,1311,functioncode=3,TypeName="Percentage",Description="LoadPeakRatio_T"),
    # PV    
                Dev(69,"Voltage_PV1",0,1412,functioncode=3,TypeName="Voltage",Description="Voltage_PV1"),
                Dev(70,"Current_PV1",0,1413,functioncode=3,TypeName="Current",Description="Current_PV1"),
                Dev(71,"Power_PV1",0,1414,functioncode=3,TypeName="Usage",Description="Power_PV1",signed=True),
                Dev(72,"Voltage_PV2",0,1415,functioncode=3,TypeName="Voltage",Description="Voltage_PV2"),
                Dev(73,"Current_PV2",0,1416,functioncode=3,TypeName="Current",Description="Current_PV2"),
                Dev(74,"Power_PV2",0,1417,functioncode=3,TypeName="Usage",Description="Power_PV2",signed=True),
                Dev(75,"Voltage_PV3",0,1418,functioncode=3,TypeName="Voltage",Description="Voltage_PV3"),
                Dev(76,"Current_PV3",0,1419,functioncode=3,TypeName="Current",Description="Current_PV3"),
                Dev(77,"Power_PV3",0,1420,functioncode=3,TypeName="Usage",Description="Power_PV3",signed=True),
                Dev(78,"Voltage_PV4",0,1421,functioncode=3,TypeName="Voltage",Description="Voltage_PV4"),
                Dev(79,"Current_PV4",0,1422,functioncode=3,TypeName="Current",Description="Current_PV4"),
                Dev(80,"Power_PV4",0,1423,functioncode=3,TypeName="Usage",Description="Power_PV4",signed=True),
    # PV Generation Today
                Dev(81,"PV_Generation_Today",2,1668,functioncode=3,TypeName="Usage",Description="PV_Generation_Today",signed=True),
    # PV Generation Total
                Dev(82,"PV_Generation_Total",2,1670,functioncode=3,TypeName="Usage",Description="PV_Generation_Total",signed=True),
    # load consumption
                Dev(83,"Load_Consumption_Today",2,1672,functioncode=3,TypeName="Usage",Description="Load_Consumption_Today",signed=True),
                Dev(84,"Load_Consumption_Total",2,1674,functioncode=3,TypeName="Usage",Description="Load_Consumption_Total",signed=True)
                ]

    def onStop(self):
        Domoticz.Log("onStop called")
        Domoticz.Debugging(0)
        Domoticz.Debug("onStop called")

    def onHeartbeat(self):
        Domoticz.Debug("onHeartbeat called")
        for dev in Devices:
            if (Devices[dev].DeviceID in [d.DeviceID for d in self.devices]):
                self.readDevice(Devices[dev].DeviceID)




global _plugin
_plugin = BasePlugin()


def onStart():
    global _plugin
    _plugin.onStart()


def onStop():
    global _plugin
    _plugin.onStop()


def onHeartbeat():
    global _plugin
    Domoticz.Log("onHeartbeat called")
    _plugin.onHeartbeat()


def onCommand(Unit, Command, Level, Hue):
    global _plugin
    Domoticz.Log("onCommand called")
    _plugin.onCommand(Unit, Command, Level, Hue)

   

# Generic helper functions
def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Log("'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Log("Device count: " + str(len(Devices)))
    for x in Devices:
        Domoticz.Log("Device:           " + str(x) + " - " + str(Devices[x]))
        Domoticz.Log("Device ID:       '" + str(Devices[x].ID) + "'")
        Domoticz.Log("Device Name:     '" + Devices[x].Name + "'")
        Domoticz.Log("Device nValue:    " + str(Devices[x].nValue))
        Domoticz.Log("Device sValue:   '" + Devices[x].sValue + "'")
        Domoticz.Log("Device LastLevel: " + str(Devices[x].LastLevel))
    return

