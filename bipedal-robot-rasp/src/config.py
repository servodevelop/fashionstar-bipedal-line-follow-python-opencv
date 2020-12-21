'''
双足机器人的配置文件
'''
#############################
## 树莓派版本号
##
#############################
RASP_VERSION = 4

#############################
## DBSP参数
##
#############################
# DBSP树莓派拓展版对应的端口号
DBSP_PORT_NAME = '/dev/ttyAMA0' if RASP_VERSION == 3 else '/dev/ttyS0'

# DBSP串口连接的波特率
DBSP_BAUDRATE = 57600

#############################
## DBSP拓展板GPIO定义
##
#############################
LAMP_GPIO = 'GPIO4' # 补光灯在拓展板上的GPIO
HEAD_SERVO_ID = 0x31    # 舵机头部的ID号
HEAD_SERVO_ANGLE = -60  # 舵机的角度
                        # 注:正负取决于舵机的安装方向

#############################
## DBSP动作组 Marco参数
##
#############################
# 站立的MarcoID
MARCO_STAND_UP_ID = 100000130
# 站立的执行周期(单位: ms)
MARCO_STAND_UP_INTERVAL = 336
# 站立预备的MarcoID
MARCO_STAND_UP_PRE_ID = 935570809
# 站立预备的执行周期(单位: ms)
MARCO_STAND_UP_PRE_INTERVAL = 150
# 前进的MarcoID
MARCO_GO_FORWARD_ID = 100000136
MARCO_GO_FORWARD_INTERVAL = 380 # 500
# 前进左偏的MarcoID
MARCO_GO_LEFT_ID = 1071071745
MARCO_GO_LEFT_INTERVAL = 480
# 前进右偏的MarcoID
MARCO_GO_RIGHT_ID = 542918673
MARCO_GO_RIGHT_INTERVAL = 480

#############################
## 相机参数
##
#############################
# 摄像头的设备号
CAM_PORT_NAME = '/dev/video0'
# 画面宽度
CAM_IMG_WIDTH = 680
# 画面高度
CAM_IMG_HEIGHT = 480
# 亮度
CAM_BRIGHNESS = 4
# 对比度
CAM_CONTRUST = 44
# 色调
CAM_HUE = 322
# 饱和度
CAM_SATURATION = 43
# 锐度
CAM_SHARPNESS = 45
# GAMMA
CAM_GAMMA = 150
# 开启自动白平衡
CAM_AWB = True
# 白平衡的温度
CAM_WHITE_BALANCE_TEMPRATURE = 4600
# 自动曝光
CAM_EXPOSURE_AUTO = True
# 相对曝光
CAM_EXPOSURE_ABSOLUTE = 78
# 相机帧率
CAM_FPS = 30

#############################
## 相机安装位置相关机械参数
## 
#############################
# 相机相对地面安装的高度 (单位:cm)
# 固定在头部是37cm 固定在胸部是29cm
CAM_H = 29 # 37
# 相机的俯仰角 (单位:度)
# 相机光心与水平面的夹角
CAM_PITCH = 60

#############################
## 直线的类型
## 1: 单轨 3: 三轨
#############################
LINE_TYPE = 1