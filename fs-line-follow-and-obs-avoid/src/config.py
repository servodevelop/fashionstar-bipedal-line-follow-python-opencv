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
## DBSP拓展板GPIO定义,I/O控制
##
#############################
LAMP_GPIO = 'GPIO4' # 补光灯在拓展板上的GPIO
LAMP_ON = True # 是否打开补光灯
HEAD_SERVO_ID = 0x31    # 舵机头部的ID号
HEAD_SERVO_ANGLE = 60   # 舵机的角度
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
## 双足机器人运动控制参数
## 
#############################
RELEX_AFTER_GAME_OVER = True # 游戏结束的时候, 是否卸力
YAW_CTL_DEADAREA = 10.0 # 偏航角控制的死区,单位°
GO_FORWARD_DIS_PER_STEP = 6.6 # 机器人前进一步的距离, 单位cm

#############################
## IMU位姿融合
## 
#############################
# IMU初始化的时候, 是否开始陀螺仪的标定
IS_CALIB_GYRO = True
PRINT_IMU_POSE = False

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
##  图像处理配置
##
#############################

## 游戏状态空间
GAME_STATE_LINE_FOLLOW = 0 # 巡线模式
GAME_STATE_GO_AROUND_CONE = 1 # 绕桩
GAME_STATE_ARUCO_DETECT = 2 # 检测Aruco码
GAME_STATE_FORK_ROAD = 3 # 分叉路口
GAME_STATE_GAME_END = 4 # 游戏结束

ROBO_PAUSE = True # 机器人暂停运动(未启用)

## 巡线
DISPLAY_IMAGE = True # 是否预览原始图像
DISPLAY_BIN_CONE = False # 是否展示交通锥的二值化图像
DISPLAY_BIN_LINE = False # 是否展示曲线的二值化图像
LINE_TYPE = 1 ## 直线的类型 (1: 单轨 3: 三轨)
# 图像阈值BGR
# 注意!颜色空间是BGR哦, 不是RGB
# 赛道黑色的BGR阈值
TRACK_BLACK_LOERB = (0, 0, 0)
TRACK_BLACK_UPPERB = (77, 77, 77)

## 交通锥
# 交通锥的个数
TRAFFIC_CONE_NUM = 2
# 交通锥红色BGR颜色阈值
CONE_RED_LOWERB = (0, 60, 140)
CONE_RED_UPPERB = (72, 108, 210)
# 交通锥占画面的最小比例
CONE_WIDTH_RATIO = 0.4
#　机器人距离交通锥最近的距离 单位cm
MIN_DIS_ROBO2CONE = 20.0

## ArucoTag
# ARUCO_FAMILY # ArucoTag的家族 6x6
ARUCO_SIZE = 19.0 # ArucoTag的尺寸 单位cm, 打印在A4纸上面
TURN_LEFT_ARUCO_ID = 0 # 向左转对应的ArucoTag ID
TURN_RIGHT_ARUCO_ID = 1 # 向右转对应的ArucoTag ID
DISTANCE_ARUCO2FORK = 100.0 # ArucoTag与交叉点之间的距离,单位cm
ARUCO_H = 18.0 # 
