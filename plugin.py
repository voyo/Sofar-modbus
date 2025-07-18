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
<plugin key="Sofar" name="Sofar" version="0.3" author="voyo@no-ip.pl">
    <params>
        <param field="SerialPort" label="Modbus Port" width="200px" required="true" default="/dev/ttyUSB0" />
        <param field="Address" label="IP Address" width="200px" required="true" default="127.0.0.1"/>
        <param field="Port" label="Port" width="30px" required="true" default="502"/>
        <param field="Mode1" label="Baud rate" width="40px" required="true" default="9600"  />
        <param field="Mode2" label="Device ID" width="40px" required="true" default="1" />
        <param field="Mode3" label="Reading Interval * 10s." width="40px" required="true" default="1" />
        <param field="Mode4" label="Modbus type" width="75px">
            <description><h2>Modbus type</h2>Select the desired type of modbus connection</description>
            <options>
                <option label="TCP" value="TCP" default="true" />
                <option label="RTU" value="RTU" />
            </options>
        </param>
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

# for TCP modbus connection
from pyModbusTCP.client import ModbusClient
from pymodbus.constants import Endian

# Domoticz shows graphs with intervals of 5 minutes.
# When collecting information from the inverter more frequently than that, then it makes no sense to only show the last value.
#
# The Average class can be used to calculate the average value based on a sliding window of samples.
# The number of samples stored depends on the interval used to collect the value from the inverter itself.
#
# borrowed from https://github.com/xbeaudouin/domoticz-ds238-modbus-tcp
class Average:
    def __init__(self):
        self.samples = []
        self.max_samples = 30

    def set_max_samples(self, max):
        self.max_samples = max
        if self.max_samples < 1:
            self.max_samples = 1

    def update(self, new_value, scale = 0):
        self.samples.append(new_value * (10 ** scale))
        while (len(self.samples) > self.max_samples):
            del self.samples[0]
        Domoticz.Debug("Average: {} - {} values".format(self.get(), len(self.samples)))

    def get(self):
        if len(self.samples) == 0:
            return 0
        return int(sum(self.samples) / len(self.samples))

class Dev:
    def __init__(self,ID,name,nod,register,size=1,functioncode: int = 3,options=None, Used: int = 1, Description=None, signed: bool = False, TypeName=None,Type: int = 0, SubType:int = 0 , SwitchType:int = 0, multipler=1):
        self.ID = ID
        self.name = name
        self.TypeName = TypeName if TypeName is not None else ""
        self.Type = Type
        self.SubType = SubType
        self.SwitchType = SwitchType
        self.nod = nod
        self.value = 0
        self.signed = signed
        self.register = register
        self.size = size
        self.multipler = multipler
        self.functioncode = functioncode
        self.options = options if options is not None else None
        self.Used=Used
        self.Description = Description if Description is not None else ""
        Domoticz.Log("DEV: "+self.name+" "+str(self.ID)+" "+self.TypeName+"  Description: "+str(self.Description))
        if self.ID not in Devices:
            msg = "Registering device: "+self.name+" "+str(self.ID)+" "+self.TypeName+"  Description: "+str(self.Description);
            Domoticz.Log(msg)
            if self.TypeName != "":
                 Domoticz.Log("adding Dev with TypeName, "+self.TypeName)
                 Domoticz.Device(Name=self.name, Unit=self.ID, TypeName=self.TypeName,Used=self.Used,Options=self.options,Description=self.Description).Create()
            else:
                 Domoticz.Device(Name=self.name, Unit=self.ID,Type=self.Type, Subtype=self.SubType, Switchtype=self.SwitchType, Used=self.Used,Options=self.options,Description=self.Description).Create()
                 Domoticz.Log("adding Dev with Type, "+str(self.Type))

    def UpdateSensorValue(self, modbusClient, isTCP, outerClass):
        if isTCP: #pyModbus
            Domoticz.Log("modbus client: "+str(modbusClient))
            Domoticz.Log("SIZE: "+str(self.size))
            
            try:
                # Read registers first
                registers = modbusClient.read_holding_registers(self.register, self.size)
                if not registers or len(registers) < self.size:
                    Domoticz.Log(f"Failed to read {self.size} registers from {self.register} - skipping update")
                    return
                
                # FIXED: Use direct register access instead of deprecated BinaryPayloadDecoder
                if self.size == 1:
                    Domoticz.Log("SIZE 1")
                    result = registers[0]  # Direct 16-bit access
                elif self.size == 2:
                    Domoticz.Log("SIZE 2")
                    # Convert two 16-bit registers to 32-bit value (Big Endian)
                    result = (registers[0] << 16) | registers[1]
                else:
                    Domoticz.Log(f"Unsupported register size: {self.size}")
                    return
                    
                Domoticz.Log("TCP Modbus read: register=" + str(self.register) + " size=" + str(self.size) + " functioncode=" + str(self.functioncode))
                Domoticz.Log("value: "+str(result))

                # Apply the multipler before updating the value
                data = result * self.multipler
                
            except Exception as e:
                Domoticz.Log(f"TCP Modbus read failed for {self.name}: {str(e)}")
                return
                
        else:   # minimalmodbus - need access to outerClass.RS485
            try:
                if self.functioncode == 3 or self.functioncode == 4:
                    if self.size == 1:
                        payload = outerClass.RS485.read_register(self.register,number_of_decimals=self.nod,functioncode=self.functioncode,signed=self.signed)
                    elif self.size == 2:
                        payload = outerClass.RS485.read_long(self.register,number_of_decimals=self.nod,functioncode=self.functioncode,signed=self.signed)

                Domoticz.Log("DEV.UPDATUJE wartosc z rejestru: "+str(self.register)+" value: "+str(payload)+" signed: "+str(self.signed))
                data = payload * self.multipler
                
            except Exception as e:
                Domoticz.Log(f"RTU Modbus read failed for {self.name}: {str(e)}")
                return

        if Parameters["Mode6"] == 'Debug':
            Domoticz.Log("Device:"+self.name+" data="+str(data)+" from register: "+str(hex(self.register)) )

        # mamy naszą wartość w 'data'

        if (self.name == "PV_Generation_Total"):
            Domoticz.Debug("DEBUG. Updating value for PV_Generation_Total")
            outerClass.production=int(data)

        if (self.name == "ActivePower_PCC_Total"):
            Domoticz.Debug("DEBUG. Updating value and averages for ActivePower_PCC_Total")
            outerClass.active_power.update(int(data))
            outerClass.forward_power.update(int(data))

        if (self.name == "ReactivePower_PCC_Total"):
            Domoticz.Debug("DEBUG. ReactivePower_PCC_Total")
            v=int(abs( data*1000))
            outerClass.reactive_power.update(v)

        if (self.name == "Total PV Energy"):
            Domoticz.Debug("DEBUG. Total PV Energy, ID="+str(self.ID))
            USAGE1=str(0)
            USAGE2=str(0)
            RETURN1=str(0)
            RETURN2=str(0)
            CONS=str(0)
            PROD=str(0)

            POWER = int(outerClass.active_power.get())
            Domoticz.Debug("DEBUG in UpdateValue, "+self.name+" POWER: "+str(POWER))
            CONS1 = str(abs(outerClass.reverse_power.get()))
            PROD1 = str(abs(outerClass.forward_power.get()))
            Domoticz.Log("TUTAJ DEBUG, CONS1:"+str(CONS1)+" PROD1:"+str(PROD1) )
            RETURN1=str(outerClass.production)
            PROD=str(abs(outerClass.forward_power.get()))

            Domoticz.Log("TUTAJ DEBUG in UpdateValue, "+self.name+" USAGE1: "+USAGE1+" USAGE2: "+USAGE2+" RETURN1: "+RETURN1+" RETURN2: "+RETURN2+" CONS: "+CONS+" PROD: "+PROD)

            Devices[self.ID].Update(nValue=1,sValue=str(USAGE1+';'+USAGE2+';'+RETURN1+';'+RETURN2+';'+CONS+';'+PROD) )
        else:
            Domoticz.Debug("DEBUG. ELSE, ID="+str(self.ID))
            Devices[self.ID].Update(sValue=str(data),nValue=int(data))

class BasePlugin:
    def __init__(self):
        self.runInterval = 1
        self.RS485 = ""
        self.modbusClient = None
        self.sensors = []  # Initialize empty sensors list
        # Active power for last 5 minutes
        self.active_power=Average()
        # Reactive power for last 5 minutes
        self.reactive_power=Average()
        # Forward power for last 5 minutes
        self.forward_power=Average()
        self.reverse_power=Average()
        self.consumption=0
        self.production=0
        return

    def onStart(self):
        DumpConfigToLog()
        DeviceID= int(Parameters["Mode2"])
        if Parameters["Mode6"] == 'Debug':
            Domoticz.Debugging(1)
            Domoticz.Debug("Debugging mode is enabled")
            
        # Set up the Modbus client based on selected connection type
        if Parameters["Mode4"] == "TCP":
            self.modbusClient = ModbusClient(host=Parameters["Address"], port=int(Parameters["Port"]), unit_id=int(DeviceID), auto_open=True)
            Domoticz.Log("Modbus TCP client created")
        else:
            self.modbusClient = None
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

        self.sensors = [
            Dev(1, "Temperature_Env1", 0, 0x418, functioncode=3, TypeName="Temperature", Description="Temperature of Environment Sensor 1", signed=True),
            Dev(9, "Temperature_Inv1", 0, 0x420, functioncode=3, TypeName="Temperature", Description="Temperature of Inverter Sensor 1", signed=True),
            Dev(12, "GenerationTime_Today", 0, 0x426, functioncode=3, TypeName="Counter", SubType=5, Description="Generation Time for Today", signed=False),
            Dev(13, "GenerationTime_Total", 0, 0x427, functioncode=3, TypeName="Counter", SubType=5, Description="Total Generation Time", signed=False),
            Dev(15, "Frequency_grid", 2, 0x484, functioncode=3, TypeName="Custom", Description="Grid Frequency in Hz", options={"Custom": "1;Hz"}, multipler=0.01),
            Dev(16, "ActivePower_Output_Total", 0, 0x485, functioncode=3, TypeName="Usage", Description="Total Active Power Output", signed=True, multipler=10),
            Dev(17, "ReactivePower_Output_Total", 0, 0x486, functioncode=3, options={"Custom":"1;kVArh"},Type=250,SubType=6, Description="Total Reactive Power Output", signed=True, multipler=10),
            Dev(19, "ActivePower_PCC_Total", 0, 0x488, functioncode=3, TypeName="Usage", Description="Total Active Power at PCC (Point of Common Coupling)", signed=True, multipler=10),

            # Phase R
            Dev(22, "Voltage_Phase_R", 1, 0x48D, functioncode=3, TypeName="Voltage", Description="Voltage of Phase R", multipler=0.1),
            Dev(23, "Current_Output_R", 0, 0x48E, functioncode=3, Type=243, SubType=23, Description="Current Output of Phase R", multipler=0.01),
            Dev(24, "ActivePower_Output_R", 0, 0x48F, functioncode=3, TypeName="Usage", Description="Active Power Output of Phase R", signed=True, multipler=10),

            # Phase S
            Dev(31, "Voltage_Phase_S", 1, 0x498, functioncode=3, TypeName="Voltage", Description="Voltage of Phase S", multipler=0.1),
            Dev(32, "Current_Output_S", 0, 0x499, functioncode=3, Type=243, SubType=23, Description="Current Output of Phase S", multipler=0.01),
            Dev(33, "ActivePower_Output_S", 0, 0x49A, functioncode=3, TypeName="Usage", Description="Active Power Output of Phase S", signed=True, multipler=10),

            # Phase T
            Dev(40, "Voltage_Phase_T", 1, 0x4A3, functioncode=3, TypeName="Voltage", Description="Voltage of Phase T", multipler=0.1),
            Dev(41, "Current_Output_T", 0, 0x4A4, functioncode=3, Type=243, SubType=23, Description="Current Output of Phase T", signed=True, multipler=0.01),
            Dev(42, "ActivePower_Output_T", 0, 0x4A5, functioncode=3, TypeName="Usage", Description="Active Power Output of Phase T", signed=True, multipler=10),

            # PV Data
            Dev(69, "Voltage_PV1", 1, 0x584, functioncode=3, TypeName="Voltage", Description="Voltage of PV Panel 1", multipler=0.1),
            Dev(70, "Current_PV1", 0, 0x585, functioncode=3, Type=243, SubType=23, Description="Current of PV Panel 1", multipler=0.01),
            Dev(71, "Power_PV1", 0, 0x586, functioncode=3, TypeName="Usage", Description="Power Generated by PV Panel 1", signed=True, multipler=10),
            Dev(72, "Voltage_PV2", 1, 0x587, functioncode=3, TypeName="Voltage", Description="Voltage of PV Panel 2", multipler=0.1),
            Dev(73, "Current_PV2", 0, 0x588, functioncode=3, Type=243, SubType=23, Description="Current of PV Panel 2", multipler=0.01),
            Dev(74, "Power_PV2", 0, 0x589, functioncode=3, TypeName="Usage", Description="Power Generated by PV Panel 2", signed=True, multipler=10),

            # PV Generation
            Dev(81, "PV_Generation_Today", 2, 0x684, size=2, functioncode=3, TypeName="Usage", Description="Total PV Generation Today", signed=False, multipler=10),
            Dev(82, "PV_Generation_Total", 2, 0x686, size=2, functioncode=3, TypeName="Usage", Description="Total PV Generation to Date", signed=False, multipler=10),

            # Load Consumption
            Dev(83, "Load_Consumption_Today", 2, 0x688, functioncode=3, TypeName="Usage", Description="Total Load Consumption Today", signed=True),
            Dev(84, "Load_Consumption_Total", 2, 0x68A, functioncode=3, TypeName="Usage", Description="Total Load Consumption to Date", signed=True),
            Dev(85, "Total PV power", 0, 0x5C4, functioncode=3, TypeName="Usage", Description="Total PV power", signed=True, multipler=100),
            # virtual device, not updating from register
            Dev(86, "Total PV Energy", 0, 0, functioncode=3, Type=250, SubType=1, Description="Total PV power", signed=True, multipler=100)
        ]

    def onStop(self):
        Domoticz.Log("onStop called")
        Domoticz.Debugging(0)
        Domoticz.Debug("onStop called")

    def onHeartbeat(self):
        self.runInterval -=1;
        pluginClass = self
        if self.runInterval <= 0:
            for dev in self.sensors:
                dev.UpdateSensorValue(self.modbusClient, Parameters["Mode4"] == "TCP",pluginClass)

                if self.runInterval <= 0:
                    self.runInterval = int(Parameters["Mode3"])
                    if Parameters["Mode6"] == 'Debug':
                        Domoticz.Debug("Resetting runInterval to: "+str(self.runInterval))
        return True

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

