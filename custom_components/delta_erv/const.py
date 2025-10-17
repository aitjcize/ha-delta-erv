"""Constants for the Delta ERV integration."""

DOMAIN = "delta_erv"

# Configuration
CONF_NAME = "name"
CONF_SLAVE_ID = "slave_id"
CONF_PORT = "port"
CONF_BAUDRATE = "baudrate"
CONF_BYTESIZE = "bytesize"
CONF_PARITY = "parity"
CONF_STOPBITS = "stopbits"

# Connection type
CONF_CONNECTION_TYPE = "connection_type"
CONNECTION_TYPE_SERIAL = "serial"
CONNECTION_TYPE_TCP = "tcp"
CONNECTION_TYPE_RTUOVERTCP = "rtuovertcp"

# TCP Configuration
CONF_HOST = "host"
CONF_TCP_PORT = "tcp_port"

# Default values
DEFAULT_SLAVE_ID = 100  # 0x64 - Default for Delta ERV
DEFAULT_BAUDRATE = 9600
DEFAULT_BYTESIZE = 8
DEFAULT_PARITY = "N"
DEFAULT_STOPBITS = 1
DEFAULT_TCP_PORT = 502

# Modbus registers for Delta ERV (from specification document)
# Main control registers
REG_MACHINE_ADDRESS = 0x00  # 本機地址
REG_OUTLET_EDITOR_1 = 0x01  # 出廠編號 1
REG_OUTLET_EDITOR_2 = 0x02  # 出廠編號 2
REG_OUTLET_EDITOR_3 = 0x03  # 出廠編號 3
REG_MACHINE_ADDRESS_UPDATE = 0x04  # 本機地址變更旗標
REG_POWER = 0x05  # 開關機 (0x00: 關機, 0x01: 開機)
REG_FAN_SPEED = 0x06  # 風量設定 (0x01: 風量1, 0x02: 風量2, 0x03: 風量3)

# Airflow percentage registers
REG_SUPPLY_AIR_1_PCT = 0x07  # 送風機風量 1 (%)
REG_SUPPLY_AIR_2_PCT = 0x08  # 送風機風量 2 (%)
REG_SUPPLY_AIR_3_PCT = 0x09  # 送風機風量 3 (%)
REG_EXHAUST_AIR_1_PCT = 0x0A  # 排風機風量 1 (%)
REG_EXHAUST_AIR_2_PCT = 0x0B  # 排風機風量 2 (%)
REG_EXHAUST_AIR_3_PCT = 0x0C  # 排風機風量 3 (%)

# Speed control registers
REG_SUPPLY_FAN_SPEED = 0x0D  # 送風機轉速
REG_EXHAUST_FAN_SPEED = 0x0E  # 排風機轉速
REG_BYPASS_FUNCTION = 0x0F  # 旁通功能

# Function registers
REG_ABNORMAL_STATUS = 0x10  # 異常狀態
REG_OUTDOOR_TEMP = 0x11  # 外氣溫度
REG_INDOOR_RETURN_TEMP = 0x12  # 室內回風溫度
REG_SYSTEM_STATUS = 0x13  # 系統狀態

# Advanced control registers
REG_INTERNAL_CIRCULATION = 0x14  # 內循環功能
REG_FAN_CONTROL_INTERNAL_CIRCULATION = 0x15  # 風量控制與內循環功能輸入狀態
REG_RS485_CONTROL = 0x16  # RS485控制設定
REG_SYSTEM_WEIGHT = 0x17  # 系統重量
REG_TEMP_DETECTION = 0x18  # 溫度偵測

# Bypass function values (register 0x0F)
BYPASS_HEAT_EXCHANGE = 0x00  # 全熱交換
BYPASS_BYPASS = 0x01  # 旁通功能
BYPASS_AUTO = 0x02  # 自動模式 (出廠設定)

# Internal circulation values (register 0x14)
INTERNAL_CIRC_HEAT_EXCHANGE = 0x00  # 熱交換 (出廠設定)
INTERNAL_CIRC_INTERNAL = 0x01  # 內循環

# Fan speed values for register 0x06 (風量設定)
# We use Custom 1 exclusively for fine-grained percentage control
FAN_SPEED_CUSTOM_1 = 0x01  # Custom 1 - programmable via registers 0x07 & 0x0A

# Percentage registers accept values 0x00-0x64 (0-100%)
# Fan RPM ranges (observed from device)
EXHAUST_MIN_RPM = 400
EXHAUST_MAX_RPM = 1840
SUPPLY_MIN_RPM = 380
SUPPLY_MAX_RPM = 2300

# Percentage register ranges (observed - fans hit max RPM at these register values)
EXHAUST_MIN_REGISTER_PCT = 1  # Minimum register value for operation (400 rpm)
EXHAUST_MAX_REGISTER_PCT = (
    50  # Exhaust reaches max RPM at 50% register value (1840 rpm)
)
SUPPLY_MIN_REGISTER_PCT = 1  # Minimum register value for operation (380 rpm)
SUPPLY_MAX_REGISTER_PCT = (
    60  # Supply reaches max RPM at 60% register value (2300 rpm)
)

# Maintain 25% faster supply RPM to create positive indoor pressure
SUPPLY_RPM_MULTIPLIER = 1.25

# Power control values for register 0x05 (開關機)
POWER_OFF = 0x00  # 關機 (出廠設定)
POWER_ON = 0x01  # 開機

# Status register bit masks (register 0x10 異常狀態)
STATUS_EEPROM_ERROR = 0x08  # Bit3: EEPROM 異常
STATUS_INDOOR_TEMP_ERROR = 0x10  # Bit4: 室內回風溫度異常
STATUS_OUTDOOR_TEMP_ERROR = 0x20  # Bit5: 外氣溫度異常
STATUS_EXHAUST_FAN_ERROR = 0x40  # Bit6: 排風機異常
STATUS_SUPPLY_FAN_ERROR = 0x80  # Bit7: 送風機異常

# Fan control register bit masks (register 0x15)
FAN_CONTROL_LOW_SPEED = 0x01  # Bit0: 低風量
FAN_CONTROL_MED_SPEED = 0x02  # Bit1: 中風量
FAN_CONTROL_HIGH_SPEED = 0x04  # Bit2: 高風量
FAN_CONTROL_INTERNAL_CIRC = 0x08  # Bit3: 內循環
