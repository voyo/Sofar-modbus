#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sofar Inverter Domoticz plugin.

Author: Wojtek Sawasciuk <voyo@no-ip.pl>
Version: 0.4.0

Requirements:
    1.python module minimalmodbus -> http://minimalmodbus.readthedocs.io/en/master/
        (pi@raspberrypi:~$ sudo pip3 install minimalmodbus)
    2.Communication module Modbus USB to RS485 converter module
"""
"""
<plugin key="Sofar" name="Sofar" version="0.4.0" author="voyo@no-ip.pl">
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
                <option label="False" value="Normal" default="false" />
            </options>
        </param>
    </params>
</plugin>
"""

import sys
import os
import time

# Add current directory to path for Domoticz
plugin_dir = os.path.dirname(os.path.abspath(__file__))
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)

try:
    import Domoticz
except ImportError:
    print("Error: Domoticz module not available")
    sys.exit(1)

# Import Modbus modules with error handling
minimalmodbus = None
serial = None
ModbusClient = None

try:
    import minimalmodbus
    import serial
except ImportError as e:
    Domoticz.Log(f"Warning: minimalmodbus not available: {e}")

try:
    from pyModbusTCP.client import ModbusClient
except ImportError as e:
    Domoticz.Log(f"Warning: pyModbusTCP not available: {e}")

try:
    from pymodbus.constants import Endian
except ImportError:
    Endian = None

# ==============================================================================
# LOGGER CLASS - Unified logging
# ==============================================================================
class Logger:
    """Unified logger with consistent formatting and debug mode support"""
    
    # ANSI color codes for debug mode
    BLUE = '\033[94m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RESET = '\033[0m'
    
    def __init__(self):
        self.debug_mode = False
    
    def set_debug_mode(self, enabled):
        """Enable or disable debug mode"""
        self.debug_mode = enabled
        if enabled:
            Domoticz.Debugging(1)
        else:
            Domoticz.Debugging(0)
    
    def _log(self, message, level="INFO", color=None):
        """Internal logging method"""
        if self.debug_mode and color:
            formatted_msg = f"{color}{message}{self.RESET}"
        else:
            formatted_msg = message
        
        if level == "ERROR":
            Domoticz.Error(formatted_msg)
        elif level == "DEBUG":
            if self.debug_mode:
                Domoticz.Debug(formatted_msg)
        else:
            Domoticz.Log(formatted_msg)
    
    def info(self, message):
        """Log info message"""
        self._log(message, "INFO")
    
    def error(self, message):
        """Log error message"""
        self._log(message, "ERROR", self.RED if self.debug_mode else None)
    
    def debug(self, message):
        """Log debug message (only in debug mode)"""
        if self.debug_mode:
            self._log(message, "DEBUG")
    
    def warning(self, message):
        """Log warning message"""
        self._log(message, "INFO", self.YELLOW if self.debug_mode else None)
    
    def success(self, message):
        """Log success message"""
        self._log(message, "INFO", self.GREEN if self.debug_mode else None)
    
    def status(self, message):
        """Log status message (blue in debug mode)"""
        self._log(message, "INFO", self.BLUE if self.debug_mode else None)

# Global logger instance
logger = Logger()

# ==============================================================================
# VALIDATION RANGES - Define acceptable ranges for sensor values
# ==============================================================================
VALIDATION_RANGES = {
    # Temperature sensors (°C)
    "Temperature_Env1": (-40, 85),
    "Temperature_Inv1": (-40, 125),
    
    # Voltages (V)
    "Voltage_Phase_R": (180, 260),
    "Voltage_Phase_S": (180, 260),
    "Voltage_Phase_T": (180, 260),
    "Voltage_PV1": (0, 600),
    "Voltage_PV2": (0, 600),
    
    # Currents (A) - after multiplier
    "Current_Output_R": (0, 100),
    "Current_Output_S": (0, 100),
    "Current_Output_T": (0, 100),
    "Current_PV1": (0, 30),
    "Current_PV2": (0, 30),
    
    # Power (W) - after multiplier
    "ActivePower_Output_Total": (-50000, 50000),
    "ActivePower_PCC_Total": (-50000, 50000),
    "Power_PV1": (0, 10000),
    "Power_PV2": (0, 10000),
    "Total PV power": (0, 100000),
    
    # Frequency (Hz)
    "Frequency_grid": (45, 65),
    
    # Energy (Wh)
    "PV_Generation_Today": (0, 1000000),
    "PV_Generation_Total": (0, 100000000),
}

# ==============================================================================
# CONNECTION HEALTH MONITOR
# ==============================================================================
class ConnectionHealthMonitor:
    """Monitor connection health and handle recovery"""
    
    def __init__(self, max_failures=5, reset_cooldown=30):
        self.consecutive_failures = 0
        self.max_failures = max_failures
        self.reset_cooldown = reset_cooldown
        self.last_reset_time = 0
        self.total_reads = 0
        self.failed_reads = 0
        self.successful_reads = 0
        self.last_error = None
        
    def mark_success(self):
        """Mark successful read"""
        self.consecutive_failures = 0
        self.successful_reads += 1
        self.total_reads += 1
        
    def mark_failure(self, error_msg=None):
        """Mark failed read"""
        self.consecutive_failures += 1
        self.failed_reads += 1
        self.total_reads += 1
        self.last_error = error_msg
        
    def should_reset_connection(self):
        """Check if connection should be reset"""
        current_time = time.time()
        
        # Don't reset too frequently
        if current_time - self.last_reset_time < self.reset_cooldown:
            return False
            
        # Reset if too many consecutive failures
        if self.consecutive_failures >= self.max_failures:
            logger.warning(f"Connection needs reset: {self.consecutive_failures} consecutive failures")
            return True
            
        return False
        
    def reset_stats(self):
        """Reset statistics after connection reset"""
        self.last_reset_time = time.time()
        self.consecutive_failures = 0
        logger.info("Connection health stats reset")
        
    def get_stats(self):
        """Get connection health statistics"""
        if self.total_reads == 0:
            return "No reads performed yet"
        
        success_rate = (self.successful_reads / self.total_reads * 100) if self.total_reads > 0 else 0
        return f"Success rate: {success_rate:.1f}% ({self.successful_reads}/{self.total_reads}), Consecutive failures: {self.consecutive_failures}"
    
    def get_detailed_stats(self):
        """Get detailed statistics for debug mode"""
        return {
            "total_reads": self.total_reads,
            "successful": self.successful_reads,
            "failed": self.failed_reads,
            "consecutive_failures": self.consecutive_failures,
            "last_error": self.last_error,
            "success_rate": f"{(self.successful_reads / self.total_reads * 100):.1f}%" if self.total_reads > 0 else "N/A"
        }

# ==============================================================================
# AVERAGE CLASS - Calculate running averages
# ==============================================================================
class Average:
    """Calculate running average with memory limits"""
    
    def __init__(self, max_samples=30):
        self.samples = []
        self.max_samples = min(100, max(1, max_samples))  # Limit between 1-100

    def set_max_samples(self, max_samples):
        """Set maximum number of samples to keep"""
        self.max_samples = min(100, max(1, max_samples))

    def update(self, new_value, scale=0):
        """Update with new value"""
        if new_value is None:
            logger.debug("Average.update: Rejecting None value")
            return
            
        if not isinstance(new_value, (int, float)):
            logger.debug(f"Average.update: Rejecting non-numeric value: {new_value}")
            return
            
        scaled_value = new_value * (10 ** scale)
        self.samples.append(scaled_value)
        
        # Prevent memory leak - enforce max_samples limit
        while len(self.samples) > self.max_samples:
            self.samples.pop(0)
        
        logger.debug(f"Average: {self.get()} - {len(self.samples)} values")

    def get(self):
        """Get current average value"""
        if len(self.samples) == 0:
            return 0
        return int(sum(self.samples) / len(self.samples))

# ==============================================================================
# DEVICE CLASS
# ==============================================================================
class Dev:
    """Device representation with Modbus register mapping"""
    
    def __init__(self, ID, name, nod, register, size=1, functioncode=3, options=None, 
                 Used=1, Description=None, signed=False, TypeName=None, 
                 Type=0, SubType=0, SwitchType=0, multipler=1):
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
        self.Used = Used
        self.Description = Description if Description is not None else ""
        
        logger.debug(f"DEV: {self.name} ID:{self.ID} Type:{self.TypeName} Desc:{self.Description}")
        
        if self.ID not in Devices:
            logger.info(f"Registering device: {self.name} ID:{self.ID} Type:{self.TypeName}")
            if self.TypeName != "":
                logger.debug(f"Adding device with TypeName: {self.TypeName}")
                Domoticz.Device(Name=self.name, Unit=self.ID, TypeName=self.TypeName,
                              Used=self.Used, Options=self.options, Description=self.Description).Create()
            else:
                logger.debug(f"Adding device with Type: {self.Type}")
                Domoticz.Device(Name=self.name, Unit=self.ID, Type=self.Type, 
                              Subtype=self.SubType, Switchtype=self.SwitchType, 
                              Used=self.Used, Options=self.options, Description=self.Description).Create()

    def read_modbus_value(self, modbus_client, is_tcp, plugin_instance):
        """Read value from Modbus register"""
        try:
            if is_tcp:
                # TCP Modbus using pyModbusTCP
                logger.debug(f"{self.name}: Reading TCP Modbus register {self.register:#x} (size={self.size})")
                
                registers = modbus_client.read_holding_registers(self.register, self.size)
                if not registers or len(registers) < self.size:
                    raise Exception(f"Failed to read {self.size} registers from {self.register:#x}")
                
                if self.size == 1:
                    result = registers[0]
                    logger.debug(f"{self.name}: Read 16-bit value: {result} from register {self.register:#x}")
                elif self.size == 2:
                    # Convert two 16-bit registers to 32-bit value (Big Endian)
                    result = (registers[0] << 16) | registers[1]
                    logger.debug(f"{self.name}: Read 32-bit value: {result} from registers {self.register:#x}-{self.register+1:#x}")
                else:
                    raise Exception(f"Unsupported register size: {self.size}")
                
                # Handle signed values
                if self.signed:
                    if self.size == 1 and result > 32767:
                        result -= 65536
                    elif self.size == 2 and result > 2147483647:
                        result -= 4294967296
                    logger.debug(f"{self.name}: Signed value adjustment: {result}")
                
                plugin_instance.health_monitor.mark_success()
                return result
                
            else:
                # RTU Modbus using minimalmodbus
                logger.debug(f"{self.name}: Reading RTU Modbus register {self.register:#x} (size={self.size}, fc={self.functioncode})")
                
                if self.functioncode == 3 or self.functioncode == 4:
                    if self.size == 1:
                        result = plugin_instance.rs485.read_register(
                            self.register, 
                            number_of_decimals=self.nod,
                            functioncode=self.functioncode,
                            signed=self.signed
                        )
                        logger.debug(f"{self.name}: RTU read 16-bit: {result}")
                    elif self.size == 2:
                        result = plugin_instance.rs485.read_long(
                            self.register,
                            number_of_decimals=self.nod,
                            functioncode=self.functioncode,
                            signed=self.signed
                        )
                        logger.debug(f"{self.name}: RTU read 32-bit: {result}")
                    else:
                        raise Exception(f"Unsupported register size: {self.size}")
                    
                    plugin_instance.health_monitor.mark_success()
                    return result
                else:
                    raise Exception(f"Unsupported function code: {self.functioncode}")
                    
        except Exception as e:
            error_msg = f"Modbus read failed for {self.name}: {str(e)}"
            logger.error(error_msg)
            plugin_instance.health_monitor.mark_failure(error_msg)
            raise

    def apply_multiplier(self, raw_value):
        """Apply multiplier to raw value"""
        final_value = raw_value * self.multipler
        logger.debug(f"{self.name}: Applied multiplier: {raw_value} * {self.multipler} = {final_value}")
        return final_value
    
    def validate_value(self, value):
        """Validate if value is within acceptable range"""
        if self.name in VALIDATION_RANGES:
            min_val, max_val = VALIDATION_RANGES[self.name]
            if min_val <= value <= max_val:
                logger.debug(f"{self.name}: Value {value} is within range [{min_val}, {max_val}]")
                return True
            else:
                logger.warning(f"{self.name}: Value {value} outside range [{min_val}, {max_val}]")
                return False
        else:
            # No validation range defined, accept all values
            logger.debug(f"{self.name}: No validation range defined, accepting value {value}")
            return True

    def update_averages(self, value, plugin_instance):
        """Update averaging values for specific devices"""
        if self.name == "PV_Generation_Total":
            logger.debug("Updating value for PV_Generation_Total")
            plugin_instance.production = int(value)
            
        elif self.name == "ActivePower_PCC_Total":
            logger.debug("Updating averages for ActivePower_PCC_Total")
            plugin_instance.active_power.update(int(value))
            plugin_instance.forward_power.update(int(value))
            
        elif self.name == "ReactivePower_PCC_Total":
            logger.debug("Updating ReactivePower_PCC_Total")
            reactive_value = int(abs(value * 1000))
            plugin_instance.reactive_power.update(reactive_value)

    def update_domoticz_device(self, value, plugin_instance):
        """Update Domoticz device with new value"""
        try:
            if self.name == "Total PV Energy":
                # Special handling for Total PV Energy
                logger.debug(f"Updating Total PV Energy, ID={self.ID}")
                
                usage1 = "0"
                usage2 = "0"
                return1 = str(plugin_instance.production)
                return2 = "0"
                cons = "0"
                prod = str(abs(plugin_instance.forward_power.get()))
                
                s_value = f"{usage1};{usage2};{return1};{return2};{cons};{prod}"
                logger.debug(f"Total PV Energy sValue: {s_value}")
                
                Devices[self.ID].Update(nValue=1, sValue=s_value)
                
            elif self.Type == 250:
                # P1 Smart Meter requires specific format
                s_value = f"0;0;0;0;{value};0"
                logger.debug(f"P1 Smart Meter update: {self.name} = {s_value}")
                Devices[self.ID].Update(nValue=0, sValue=s_value)
                
            else:
                # Standard device update
                Devices[self.ID].Update(sValue=str(value), nValue=int(value))
                logger.debug(f"Updated {self.name} with value: {value}")
                
        except Exception as e:
            logger.error(f"Failed to update Domoticz device {self.name}: {str(e)}")

    def UpdateSensorValue(self, modbus_client, is_tcp, plugin_instance):
        """Main update method - orchestrates the update process"""
        try:
            # Step 1: Read raw value from Modbus
            raw_value = self.read_modbus_value(modbus_client, is_tcp, plugin_instance)
            
            # Step 2: Apply multiplier
            final_value = self.apply_multiplier(raw_value)
            
            # Step 3: Validate value
            if not self.validate_value(final_value):
                logger.warning(f"{self.name}: Skipping update due to invalid value: {final_value}")
                return
            
            # Step 4: Update averages if needed
            self.update_averages(final_value, plugin_instance)
            
            # Step 5: Update Domoticz device
            self.update_domoticz_device(final_value, plugin_instance)
            
            logger.success(f"✓ {self.name}: Successfully updated with value {final_value}")
            
        except Exception as e:
            logger.error(f"✗ Failed to update {self.name}: {str(e)}")

# ==============================================================================
# MAIN PLUGIN CLASS
# ==============================================================================
class BasePlugin:
    """Main plugin class for Sofar Inverter"""
    
    def __init__(self):
        self.run_interval = 1
        self.rs485 = None
        self.modbus_client = None
        self.sensors = []
        
        # Averaging values
        self.active_power = Average()
        self.reactive_power = Average()
        self.forward_power = Average()
        self.reverse_power = Average()
        
        # Current values
        self.consumption = 0
        self.production = 0
        
        # Health monitoring
        self.health_monitor = ConnectionHealthMonitor()
        self.update_counter = 0

    def onStart(self):
        """Initialize plugin on start"""
        global logger
        
        # Setup debug mode
        if Parameters["Mode6"] == 'Debug':
            logger.set_debug_mode(True)
            logger.status("="*50)
            logger.status("Sofar Modbus Plugin - Debug Mode Enabled")
            logger.status("="*50)
            self._dump_config_to_log()
        else:
            logger.set_debug_mode(False)
        
        logger.info("Sofar Modbus plugin v0.4.1 starting...")
        
        # Initialize Modbus connection
        if not self._initialize_connection():
            logger.error("Failed to initialize Modbus connection")
            return
        
        # Initialize devices
        self._initialize_devices()
        
        logger.success("✅ Sofar plugin started successfully")
        if logger.debug_mode:
            logger.status(f"📊 Monitoring {len(self.sensors)} sensors")
            logger.status(f"⏱️ Update interval: {Parameters['Mode3']} x 10 seconds")

    def _initialize_connection(self):
        """Initialize Modbus connection (TCP or RTU)"""
        device_id = int(Parameters["Mode2"])
        
        logger.info(f"Initializing {Parameters['Mode4']} connection...")
        
        try:
            if Parameters["Mode4"] == "TCP":
                if ModbusClient is None:
                    logger.error("pyModbusTCP module not installed! Install with: pip3 install pyModbusTCP")
                    return False
                    
                self.modbus_client = ModbusClient(
                    host=Parameters["Address"], 
                    port=int(Parameters["Port"]), 
                    unit_id=device_id, 
                    auto_open=True
                )
                logger.success(f"✅ Modbus TCP client created: {Parameters['Address']}:{Parameters['Port']} (ID: {device_id})")
                return True
                
            else:  # RTU
                if minimalmodbus is None:
                    logger.error("minimalmodbus module not installed! Install with: pip3 install minimalmodbus")
                    return False
                    
                self.modbus_client = None
                self.rs485 = minimalmodbus.Instrument(Parameters["SerialPort"], device_id)
                self.rs485.serial.baudrate = Parameters["Mode1"]
                self.rs485.serial.bytesize = 8
                self.rs485.serial.parity = minimalmodbus.serial.PARITY_NONE
                self.rs485.serial.stopbits = 1
                self.rs485.serial.timeout = 1
                self.rs485.debug = False
                self.rs485.mode = minimalmodbus.MODE_RTU
                logger.success(f"✅ Modbus RTU client created: {Parameters['SerialPort']} @ {Parameters['Mode1']}bps (ID: {device_id})")
                return True
                
        except Exception as e:
            logger.error(f"❌ Connection initialization failed: {str(e)}")
            return False

    def _initialize_devices(self):
        """Initialize device list"""
        logger.info("Initializing Sofar devices...")
        
        self.sensors = [
            # Temperature sensors
            Dev(1, "Temperature_Env1", 0, 0x418, functioncode=3, TypeName="Temperature", 
                Description="Temperature of Environment Sensor 1", signed=True),
            Dev(9, "Temperature_Inv1", 0, 0x420, functioncode=3, TypeName="Temperature", 
                Description="Temperature of Inverter Sensor 1", signed=True),
            
            # Generation time
            Dev(12, "GenerationTime_Today", 0, 0x426, functioncode=3, TypeName="Counter", 
                SubType=5, Description="Generation Time for Today", signed=False),
            Dev(13, "GenerationTime_Total", 0, 0x427, functioncode=3, TypeName="Counter", 
                SubType=5, Description="Total Generation Time", signed=False),
            
            # Grid parameters
            Dev(15, "Frequency_grid", 2, 0x484, functioncode=3, TypeName="Custom", 
                Description="Grid Frequency in Hz", options={"Custom": "1;Hz"}, multipler=0.01),
            Dev(16, "ActivePower_Output_Total", 0, 0x485, functioncode=3, TypeName="Usage", 
                Description="Total Active Power Output", signed=True, multipler=10),
            Dev(17, "ReactivePower_Output_Total", 0, 0x486, functioncode=3, 
                options={"Custom":"1;kVArh"}, Type=250, SubType=6, 
                Description="Total Reactive Power Output", signed=True, multipler=10),
            Dev(19, "ActivePower_PCC_Total", 0, 0x488, functioncode=3, TypeName="Usage", 
                Description="Total Active Power at PCC", signed=True, multipler=10),

            # Phase R
            Dev(22, "Voltage_Phase_R", 1, 0x48D, functioncode=3, TypeName="Voltage", 
                Description="Voltage of Phase R", multipler=0.1),
            Dev(23, "Current_Output_R", 0, 0x48E, functioncode=3, Type=243, SubType=23, 
                Description="Current Output of Phase R", multipler=0.01),
            Dev(24, "ActivePower_Output_R", 0, 0x48F, functioncode=3, TypeName="Usage", 
                Description="Active Power Output of Phase R", signed=True, multipler=10),

            # Phase S
            Dev(31, "Voltage_Phase_S", 1, 0x498, functioncode=3, TypeName="Voltage", 
                Description="Voltage of Phase S", multipler=0.1),
            Dev(32, "Current_Output_S", 0, 0x499, functioncode=3, Type=243, SubType=23, 
                Description="Current Output of Phase S", multipler=0.01),
            Dev(33, "ActivePower_Output_S", 0, 0x49A, functioncode=3, TypeName="Usage", 
                Description="Active Power Output of Phase S", signed=True, multipler=10),

            # Phase T
            Dev(40, "Voltage_Phase_T", 1, 0x4A3, functioncode=3, TypeName="Voltage", 
                Description="Voltage of Phase T", multipler=0.1),
            Dev(41, "Current_Output_T", 0, 0x4A4, functioncode=3, Type=243, SubType=23, 
                Description="Current Output of Phase T", multipler=0.01),
            Dev(42, "ActivePower_Output_T", 0, 0x4A5, functioncode=3, TypeName="Usage", 
                Description="Active Power Output of Phase T", signed=True, multipler=10),

            # PV Data
            Dev(69, "Voltage_PV1", 1, 0x584, functioncode=3, TypeName="Voltage", 
                Description="Voltage of PV Panel 1", multipler=0.1),
            Dev(70, "Current_PV1", 0, 0x585, functioncode=3, Type=243, SubType=23, 
                Description="Current of PV Panel 1", multipler=0.01),
            Dev(71, "Power_PV1", 0, 0x586, functioncode=3, TypeName="Usage", 
                Description="Power Generated by PV Panel 1", signed=True, multipler=10),
            Dev(72, "Voltage_PV2", 1, 0x587, functioncode=3, TypeName="Voltage", 
                Description="Voltage of PV Panel 2", multipler=0.1),
            Dev(73, "Current_PV2", 0, 0x588, functioncode=3, Type=243, SubType=23, 
                Description="Current of PV Panel 2", multipler=0.01),
            Dev(74, "Power_PV2", 0, 0x589, functioncode=3, TypeName="Usage", 
                Description="Power Generated by PV Panel 2", signed=True, multipler=10),

            # PV Generation
            Dev(81, "PV_Generation_Today", 2, 0x684, size=2, functioncode=3, TypeName="Usage", 
                Description="Total PV Generation Today", signed=False, multipler=10),
            Dev(82, "PV_Generation_Total", 2, 0x686, size=2, functioncode=3, TypeName="Usage", 
                Description="Total PV Generation to Date", signed=False, multipler=10),

            # Load Consumption
            Dev(83, "Load_Consumption_Today", 2, 0x688, functioncode=3, TypeName="Usage", 
                Description="Total Load Consumption Today", signed=True),
            Dev(84, "Load_Consumption_Total", 2, 0x68A, functioncode=3, TypeName="Usage", 
                Description="Total Load Consumption to Date", signed=True),
            Dev(85, "Total PV power", 0, 0x5C4, functioncode=3, TypeName="Usage", 
                Description="Total PV power", signed=True, multipler=100),
            
            # Virtual device (not updating from register)
            Dev(86, "Total PV Energy", 0, 0, functioncode=3, Type=250, SubType=1, 
                Description="Total PV power virtual", signed=True, multipler=100)
        ]
        
        logger.info(f"Initialized {len(self.sensors)} devices")

    def onStop(self):
        """Clean up on plugin stop"""
        logger.info("Sofar plugin stopping...")
        logger.set_debug_mode(False)

    def onHeartbeat(self):
        """Called every 10 seconds by Domoticz"""
        self.run_interval -= 1
        
        if self.run_interval <= 0:
            # Reset interval
            self.run_interval = int(Parameters["Mode3"])
            logger.debug(f"Resetting run_interval to: {self.run_interval}")
            
            # Update all sensors
            self._update_all_sensors()

    def _update_all_sensors(self):
        """Update all sensor values"""
        is_tcp = (Parameters["Mode4"] == "TCP")
        
        for sensor in self.sensors:
            try:
                sensor.UpdateSensorValue(self.modbus_client, is_tcp, self)
            except Exception as e:
                logger.error(f"Failed to update sensor {sensor.name}: {str(e)}")

    def _dump_config_to_log(self):
        """Dump configuration to log for debugging"""
        logger.debug("=== Configuration ===")
        for key in Parameters:
            if Parameters[key] != "":
                logger.debug(f"{key}: {Parameters[key]}")
        
        logger.debug(f"Device count: {len(Devices)}")
        for device_id in Devices:
            device = Devices[device_id]
            logger.debug(f"Device {device_id}: {device.Name} - Value: {device.sValue}")

# ==============================================================================
# GLOBAL PLUGIN INSTANCE AND DOMOTICZ CALLBACKS
# ==============================================================================
global _plugin
_plugin = BasePlugin()

def onStart():
    """Domoticz callback: Plugin start"""
    global _plugin
    _plugin.onStart()

def onStop():
    """Domoticz callback: Plugin stop"""
    global _plugin
    _plugin.onStop()

def onHeartbeat():
    """Domoticz callback: Heartbeat"""
    global _plugin
    _plugin.onHeartbeat()

def onCommand(Unit, Command, Level, Hue):
    """Domoticz callback: Command received"""
    global _plugin
    logger.debug("onCommand called")
    # Add command handling if needed

# Additional required Domoticz callbacks
def onConnect(Connection, Status, Description):
    """Domoticz callback: Connection status"""
    pass

def onMessage(Connection, Data):
    """Domoticz callback: Message received"""
    pass

def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    """Domoticz callback: Notification"""
    pass

def onDisconnect(Connection):
    """Domoticz callback: Disconnection"""
    pass
