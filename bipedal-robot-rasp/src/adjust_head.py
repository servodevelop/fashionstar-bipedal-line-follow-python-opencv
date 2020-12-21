'''调整头部舵机的角度'''
import serial
from config import *
from dbsp import ServoAngleControlEvent

# 串口初始化
uart = serial.Serial(port=DBSP_PORT_NAME, \
    baudrate=DBSP_BAUDRATE, parity=serial.PARITY_NONE, \
    stopbits=1, bytesize=8, timeout=0)
# 设置头部舵机的角度
angle_ctl_event = ServoAngleControlEvent([[HEAD_SERVO_ID, HEAD_SERVO_ANGLE, 100]])
uart.write(angle_ctl_event.generate_request_bytes())
