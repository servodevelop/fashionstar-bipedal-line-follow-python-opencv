'''
巡线+壁障+ArucoTag识别

'''
import math
import time # 时间,延时
import multiprocessing as mp # 多进程
import numpy as np # 矩阵计算
import logging # 日志输出
import serial # 串口通信
# 配置文件
from config import *
# 动作组管理
from dbsp import ServoAngleControlEvent
from dbsp_action_group import *
# IMU位姿融合
from imu_mpu6050 import RaspMPU6050
from imu_fusion import IMUPose
from geometry import Geometry
# 图像处理
import cv2
from cv_camera import Camera
from cv_track_fit  import TrackFit
from cv_traffic_cone import TrafficConeDetect
from cv_aruco import ArucoDetect

# 补光灯 I/O控制
from gpiozero import LED

# 设置日志输出等级
logging.basicConfig(level=logging.INFO)

# 创建全局变量
robo_init_evt = mp.Event() # 机器人初始化事件
game_finish_evt = mp.Event() # 游戏结束事件
imu_init_evt = mp.Event()  # IMU初始化事件
imu_pose_change_evt = mp.Event() # 修改IMU位姿事件
dbsp_action_evt = mp.Event() # DBSP有动作需要执行
dbsp_action_done = mp.Event() # DBSP的动作执行完成
cam_init_evt = mp.Event() # 相机初始化事件

manager = mp.Manager() # 创建Manger
ns = manager.Namespace() # 创建命名空间

# 游戏状态
ns.game_state = GAME_STATE_LINE_FOLLOW # 当前游戏阶段
# IMU位姿融合
imu_pose_dict =manager.dict({'roll': 0.0,'pitch': 0.0, 'yaw': 0.0}) # 当前IMU位姿
new_imu_pose_dict =manager.dict({'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0}) # 新设定的IMU位姿
# DBSP动作组
action_group_list = manager.list() # 动作组指令序列(依次执行)
# 巡线相关变量
ns.cv_update_t = time.time() # 视觉信息的更新时间
ns.cv_track_switch = False # 巡线拟合开关
ns.has_line = False # 画面中是否有曲线
ns.has_c1 = False # 曲线1是否存在
ns.has_c2 = False # 曲线2是否存在
ns.next_yaw = 0 # 下一步的目标偏航
ns.cross_ab = 0 # 向量A跟向量B叉乘的结果
# 交通锥相关变量
ns.cv_cone_switch = False # 交通锥是被开关

ns.cone_cnt = 0 # 绕过的交通锥的个数
ns.has_cone = False # 画面中是否存在交通锥
ns.find_cone_time = 0 # 发现交通锥的时间
ns.go_around_cone_time = time.time()
ns.dis_rb2cone = 150 # 交通锥距离机器人的距离
ns.cone_x = 0 # 圆锥在机器人坐标下的x坐标 
ns.cone_y = 0 # 圆锥在机器人坐标下的x坐标 
ns.cone_w_threshold = CONE_WIDTH_RATIO

# ArucoTag变量
ns.cv_aruco_switch = False # ArucoTag识别开关
ns.has_aruco = False # 画面中是否有ArucoTag
ns.aruco_id = 0 # ArucoTag的ID号
ns.dis_cam2aruco = 0.0 # 
ns.dis_rb2aruco = 0.0  # 机器人距离ArucoTag的距离
ns.dis_rb2fork = 0.0   # 
ns.detect_aruco_time = None # 准备识别ArucoTag的时间

def angle_adjust(angle):
    # 将角度缩放到-180度到180度之间
    angle = angle % 360
    return angle - 360.0  if angle > 180.0 else angle
    
def wait_cv_update():
    # 图像处理信息是否过时
    cur_time = time.time()
    # 一直等待视觉信息更新
    while (cur_time+0.05) > ns.cv_update_t:
        time.sleep(0.001)

def wait_dbsp_done():
    '''等待DBSP动作执行完成'''
    dbsp_action_done.clear()
    dbsp_action_evt.set()
    dbsp_action_done.wait()

def worker_imu_pose():
    '''子进程-IMU位姿融合'''
    robo_init_evt.wait() # 等待机器人进入站立状态
    imu = RaspMPU6050() # 初始化imu
    logging.info('[IMU]载入IMU标定数据') # 标定数据载入
    imu.load_imu_calib_data() # 载入加速度计还有陀螺仪的标定数据
    # 陀螺仪标定
    if IS_CALIB_GYRO:
        logging.info('[IMU] 等待机器人静止,才能进行陀螺仪标定')
        time.sleep(5) # 机器人站立之后会后一定幅度的晃动, 在这里添加延时是为了避免机器人晃动会陀螺仪标定的影响
        logging.info('[IMU] 陀螺仪开始进行标定， 在这个过程中请不要移动机器人， 预计10s')
        imu.update_gyro_bias() # 更新陀螺仪的bias
        logging.info('[IMU] 偏移量测试统计完成, gyro_bias: {}'.format(imu.gyro_bias))
        imu.save_imu_calib_data() # 保存新标定数据
        logging.info('[IMU]保存标定数据')
    
    imu_pose = IMUPose(imu) # 创建IMU位姿对象
    imu_pose.pose_init() # 位姿初始化
    logging.info('[IMU POSE] IMU位姿初始化')
    imu_init_evt.set() # 设定IMU初始化完成标识
    
    while True:
        if imu_pose_change_evt.is_set():
            # IMU姿态被重新设定了, 需要更新IMU位姿
            # 从字典中获取新设定的欧拉角
            roll = new_imu_pose_dict['roll']
            pitch = new_imu_pose_dict['pitch']
            yaw = new_imu_pose_dict['yaw']
            rpy = np.radians(np.float32([roll, pitch, yaw]))
            
            imu_pose.q = Geometry.euler2quat(rpy) # 欧拉角转换为四元数
            imu_pose_change_evt.clear() # 清除位姿设定事件标识
        else:
            try:
                imu_pose.pose_update() # 使用Mahony滤波算法, 进行位姿融合
            except OSError as e:
                logging.error('[IMU POSE]MPU6050 I/O Error, {}'.format(e))
            # 同步更新字典中的位姿
            # 获取当前位姿的欧拉角,单位转换为角度制
            roll, pitch, yaw = np.degrees(Geometry.quat2euler(imu_pose.q)).reshape(-1)
            imu_pose_dict['roll'] = roll
            imu_pose_dict['pitch'] = pitch
            imu_pose_dict['yaw'] = yaw
            if PRINT_IMU_POSE:
                logging.info('[IMU POSE] Roll: {:.1f}, Pitch: {:.1f}, Yaw:{:.1f}'.format(roll, pitch, yaw))

def worker_dbsp_action_group():
    '''子进程-DBSP动作组序列管理'''
    # 串口初始化
    uart = serial.Serial(port=DBSP_PORT_NAME, \
        baudrate=DBSP_BAUDRATE, parity=serial.PARITY_NONE, \
        stopbits=1, bytesize=8, timeout=0)
    
    # 设置头部舵机的角度
    angle_ctl_event = ServoAngleControlEvent([[HEAD_SERVO_ID, HEAD_SERVO_ANGLE, 100]])
    uart.write(angle_ctl_event.generate_request_bytes())

    am = ActionGroupManager(uart) # 动作组管理器
    am.execute(StandUp()) # 动作初始化(站立)
    logging.info('[DBSP] 机器人动作初始化(站立), 请在5s内将机器人放置与赛道起点')
    
    robo_init_evt.set() # 设置机器人初始化动作事件
    imu_init_evt.wait() # 等待IMU标定完成
    
    while True:
        dbsp_action_evt.wait() # 等待新动作
        dbsp_action_done.clear() # 清空动作完成标志位

        if game_finish_evt.is_set():
            am.execute(StandUp()) # 游戏被中断/结束
            if RELEX_AFTER_GAME_OVER:
                am.relax() # 机器人卸力
            break
        
        # 有新的动作组序列要执行,按照顺序依次执行
        while len(action_group_list) > 0:
            # 获取动作组的名称
            action_group_name = str(action_group_list.pop(0))
            if action_group_name in ACTION_GROUP_MAP:
                # 执行动作组
                am.execute(ACTION_GROUP_MAP[action_group_name]())
            elif action_group_name == 'RAISE_HEAD':
                # 机器人抬头
                angle_ctl_event = ServoAngleControlEvent([[HEAD_SERVO_ID, 0, 100]])
                uart.write(angle_ctl_event.generate_request_bytes())
                time.sleep(0.1)
            elif action_group_name == 'LOWER_HEAD':
                # 机器人低头
                angle_ctl_event = ServoAngleControlEvent([[HEAD_SERVO_ID, HEAD_SERVO_ANGLE, 100]])
                uart.write(angle_ctl_event.generate_request_bytes())
                time.sleep(0.1)
            else:
                logging.error('[DBSP] 未知动作组 {}'.format(action_group_name))
                
        
        dbsp_action_evt.clear()
        dbsp_action_done.set()

def worker_cv():
    '''子进程-图像处理'''
    if DISPLAY_IMAGE:
        # 创建图像处理的窗口
        cv2.namedWindow('img_raw',flags=cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO | cv2.WINDOW_GUI_EXPANDED)
        if DISPLAY_BIN_LINE:
            cv2.namedWindow('bin_line',flags=cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO | cv2.WINDOW_GUI_EXPANDED)
        cv2.namedWindow('canvas_robo',flags=cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO | cv2.WINDOW_GUI_EXPANDED)
        if DISPLAY_BIN_CONE:
            cv2.namedWindow('bin_cone',flags=cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO | cv2.WINDOW_GUI_EXPANDED)

    cam = Camera(device=CAM_PORT_NAME) # 初始化相机
    cam.init_camera() # 相机初始化
    capture = cam.get_video_capture() # 创建capture对象
    cam.load_cam_calib_data() # 载入标定参数
    cam.load_ipm_remap(calc_online=False) # 载入透视逆变换矩阵
    cam_init_evt.set() # 设置相机初始化事件

    # 创建赛道曲线拟合的对象
    tk_curve_fit = TrackFit(cam)
    # 检测交通锥
    cone_detect = TrafficConeDetect(cam)
    # ArucoTag检测
    aruco_detect = ArucoDetect(cam)
    
    try:
        while True:
            # 游戏终止
            if game_finish_evt.is_set():
                break

            start = time.time() # 开始计时
            ret, img = capture.read() # 获取原始图像
            if not ret:
                logging.error('[CV] Error 图像获取失败')
                time.sleep(0.1)
                continue
            
            ## 图像处理-曲线拟合
            # img = cam.remove_distortion(img)  # 图像去除畸变        
            ns.has_line, bin_line = tk_curve_fit.img_preprocess(img)
            canvas_img = np.copy(img) # 画布
            canvas_robo =  np.ones((600, 800, 3)) # 机器人坐标系下的实物图
            bin_cone = None
            
            if ns.cv_track_switch and  ns.has_line:
                try:
                    # 透视逆变换
                    rb_x, rb_y = tk_curve_fit.pixel_ipm(bin_line, canvas=canvas_img)
                    # 曲线拟合
                    ns.has_c1, ns.has_c2, ns.next_yaw, ns.cross_ab, canvas_robo = tk_curve_fit.curve_fit(rb_x, rb_y, is_draw=True)
                except np.RankWarning as e:
                    # 拟合的时候, 样本点过少, 直线丢失
                    ns.has_line = False
                    logging.warning(e)

            ## 图像处理-交通锥识别
            if ns.cv_cone_switch and ns.cone_cnt < TRAFFIC_CONE_NUM:
                # 如果绕过的交通锥个数小于指定值
                ns.has_cone, bin_cone, cone_rect = cone_detect.preprocessing(img, w_threshold=ns.cone_w_threshold)
                if ns.has_cone:
                    # 交通锥视觉测量
                    ns.dis_rb2cone, cone_posi = cone_detect.cone_measure(cone_rect)
                    ns.cone_x, ns.cone_y = cone_posi
                    # 可视化
                    canvas_img = cone_detect.visualization(ns.has_cone, canvas_img, \
                        cone_rect=cone_rect, distance=ns.dis_rb2cone, cone_posi=cone_posi)
                    
                    ns.find_cone_time = time.time()
                       
            ## 图像处理-ArucoTag识别
            # 注: ArucoTag只需要识别一次
            if ns.cv_aruco_switch and not ns.has_aruco:
                # TODO has_aruco, canvas, aruco_id, dis_cam2aruco
                ns.has_aruco, canvas_img, ns.aurco_id, ns.dis_cam2aruco = aruco_detect.find_aruco(img, canvas_img)
                if ns.has_aruco:
                    ns.dis_rb2aruco =  math.sqrt(ns.dis_cam2aruco**2 - (CAM_H - ARUCO_H)**2)
                    ns.dis_rb2fork = ns.dis_rb2aruco - DISTANCE_ARUCO2FORK
                
            end = time.time() # 停止计时
            ns.cv_update_t = time.time() # 图像数据更新的时间
            # 画面同步与显示
            if DISPLAY_IMAGE:
                cv2.imshow('img_raw', canvas_img)
                if DISPLAY_BIN_LINE:
                    cv2.imshow('bin_line', bin_line)
                cv2.imshow('canvas_robo', canvas_robo)
                if DISPLAY_BIN_CONE and bin_cone is not None:
                    cv2.imshow('bin_cone', bin_cone)

                key = cv2.waitKey(1)
                if key == ord('q'):
                    # 如果按键为q 代表quit 退出程序
                    break
    except KeyboardInterrupt:
        # 按键中断, 游戏结束
        logging.info('[CV] 按键中断,游戏结束')
        game_finish_evt.set()
    except Exception as e:
        logging.error('[CV] ERROR: {}'.format(e))
    
    capture.release() # 关闭摄像头
    if DISPLAY_IMAGE:
        cv2.destroyAllWindows() # 销毁所有的窗口
    game_finish_evt.set() # 游戏结束标志位设定

def robot_turn(yaw=None, dyaw=None):
    '''机器人旋转特定的角度'''
    # 计算新的偏航角
    target_yaw = yaw
    if yaw is not None:
        target_yaw = yaw
    else:
        target_yaw = imu_pose_dict['yaw'] + dyaw # 计算目标偏航角
    target_yaw = angle_adjust(target_yaw)
    
    while True:    
        cur_yaw = imu_pose_dict['yaw'] # 获取当前的偏航角
        yaw_err = angle_adjust(target_yaw-cur_yaw) # 计算角度误差
        logging.info('[TURN] 当前偏航角:{:.1f} 目标偏航角:{:.1f} error: {:.1f}'.format(cur_yaw, \
            target_yaw, yaw_err))
        if abs(yaw_err) < YAW_CTL_DEADAREA:
            # 误差小于阈值,完成,停止旋转
            # 退出当前的while循环
            break
        is_turn_left = yaw_err > 0 # 计算机器人的旋转方向 (左:True, 右: False)
        if is_turn_left:
            action_group_list.append(GoLeft.name)
        else:
            action_group_list.append(GoRight.name)    
        
        logging.info('[TURN] 旋转方向 '+ action_group_list[0])

        dbsp_action_done.clear()
        dbsp_action_evt.set()
        dbsp_action_done.wait()
        # Wait IMU Stable
        time.sleep(0.2)
        
def robot_go(distance, ref_yaw=None):
    '''前进特定的距离
    distance的单位是cm
    '''
    # if ref_yaw is None:
    #    ref_yaw = imu_pose_dict['yaw'] # 拷贝一下当前的偏航角
    
    n_step = math.ceil(distance / GO_FORWARD_DIS_PER_STEP) # 计算总共需要前进多少步
    for i_step in range(n_step):
        action_group_list.append(GoForward.name) # 添加动作
        # 执行动作
        dbsp_action_done.clear()
        dbsp_action_evt.set()
        dbsp_action_done.wait()
        
        if ref_yaw is not None:
            # 结合IMU,当角度偏差过大的时候, 进行修正
            yaw_err = angle_adjust(ref_yaw - imu_pose_dict['yaw'])
            if abs(yaw_err) > YAW_CTL_DEADAREA:
                robot_turn(yaw=ref_yaw)

def go_around_cone():
    '''机器人绕桩'''
    # 默认从右侧绕桩
    yaw_init = imu_pose_dict['yaw']
    next_yaw = yaw_init
    
    '''
    # 执行绕桩的动作
    next_yaw += -60
    robot_turn(yaw=next_yaw)
    robot_go(30, ref_yaw=next_yaw)
    next_yaw += 120
    robot_turn(yaw=next_yaw)
    robot_go(20, ref_yaw=next_yaw)
    '''
    # 向右转,直到画面中的圆锥消失
    
    # 微调圆锥识别的阈值
    tmp_w_threshold = ns.cone_w_threshold # 备份原来的阈值
    ns.cone_w_threshold = tmp_w_threshold / 2
    while True:
        wait_cv_update()
        if ns.has_cone == False:
            break
        else:
            action_group_list.append(GoRight.name)
            wait_dbsp_done()
    # 前进一段距离
    robot_go(20)

    # 向左旋转直到遇见红色交通锥
    ns.cone_w_threshold = tmp_w_threshold / 4
    while True:
        wait_cv_update()
        if ns.has_cone:
            break
        else:
            action_group_list.append(GoLeft.name)
            wait_dbsp_done()
    # 恢复阈值        
    ns.cone_w_threshold = tmp_w_threshold
    robot_go(40) 
    
    while True:
        wait_cv_update()
        if ns.has_line:
            break
        else:
            action_group_list.append(GoLeft.name)
            wait_dbsp_done()
    robot_go(30)
    
    # 更新绕过圆锥的时间
    ns.go_around_cone_time = time.time()

def game():
    '''游戏'''
    ns.cv_track_switch = True # 打开巡线开关
    ns.cv_cone_switch = True # 识别圆锥
    ns.has_cone = False # 清除交通锥标志

    action_group_list.append(StandUpPre.name)
    wait_dbsp_done()
    # 测试ArucoTag段
    # ns.detect_aruco_time = time.time() + 5

    while True:
        cur_time = time.time()
        

        # 一直等待视觉信息更新
        wait_cv_update()
        
        # 达到检测ArucoTag的时间, 且存在曲线, yaw偏差小于阈值,
        if not ns.cv_aruco_switch and not ns.has_aruco and ns.detect_aruco_time is not None and \
            cur_time > ns.detect_aruco_time and ns.has_line and abs(ns.next_yaw) < YAW_CTL_DEADAREA:
            ref_next_yaw = ns.next_yaw

            logging.info('[GAME] 当前偏航角误差 {}'.format(ns.next_yaw))
            logging.info('[GAME] 准备识别ArucoTag')
            # 调整机器人舵机角度 抬头            
            action_group_list.append('RAISE_HEAD')# 机器人抬头
            wait_dbsp_done()
            # 打开ArucoTag识别的开关
            ns.cv_aruco_switch = True
            # 关闭巡线开关
            ns.cv_track_switch = False
            # 静止1S 让画面稳定 
            time.sleep(1)

            while True:
                # 一直等待视觉信息更新
                wait_cv_update()
                if ns.has_aruco:
                    break
                # 已经抬起头,但是没有找到ArucoTag
                if ref_next_yaw >= 0:
                    logging.info('[GAME] 没有找到ArucoTag, 右转搜寻')
                    action_group_list.append(GoRight.name)
                else:
                    logging.info('[GAME] 没有找到ArucoTag, 左转搜寻')
                    action_group_list.append(GoLeft.name)
                
                wait_dbsp_done()
                # 静止1S 让画面稳定 
                time.sleep(1)
            continue

        if ns.cv_aruco_switch and ns.has_aruco:
            logging.info('[GAME] 识别到ArucoTag, ID={} 继续巡线'.format(ns.aruco_id))
            # 机器人低头重新巡线
            action_group_list.append('LOWER_HEAD')
            wait_dbsp_done()
            # 机器人前进到分叉路口
            robot_go(ns.dis_rb2fork, ref_yaw=imu_pose_dict['yaw'])
            # 调整偏航角(左 or 右)
            
            logging.info('[GAME] 调整到对应的航向')
            if ns.aruco_id == TURN_LEFT_ARUCO_ID:
                logging.info('[GAME] 走左边的分叉路口')
                robot_turn(dyaw=30)
            else:
                logging.info('[GAME] 走右边的分叉路口')
                robot_turn(dyaw=-30)
            # 前进一段时间,防止旁边的线造成干扰
            robot_go(30)

            ns.cv_aruco_switch = False # 关闭ArucoTag识别开关
            ns.cv_track_switch = True # 打开巡线
            continue
        
        if ns.has_cone and ns.cone_cnt < TRAFFIC_CONE_NUM and ns.dis_rb2cone <= MIN_DIS_ROBO2CONE:
            pass_t =  (ns.find_cone_time - ns.go_around_cone_time)
            if pass_t < 20:
                logging.info('[GAME] 发现障碍物, 但是时间间隔太短 {} < 5s'.format(pass_t))
                ns.has_cone = False
            else:
                logging.info('[GAME] 发现障碍物, 序号: {}'.format(ns.cone_cnt+1))
            # 绕桩前进
            go_around_cone()
            # 绕桩完成之后,修改绕过的桩的计数
            ns.cone_cnt += 1
            # 开启图像处理
            ns.cv_track_switch = True
            if ns.cone_cnt < TRAFFIC_CONE_NUM:
                ns.cv_cone_switch = True
            else:
                # 关闭圆锥识别的开关
                ns.cv_cone_switch = False
                # 打开巡线的开关
                ns.cv_track_switch = True
                ns.detect_aruco_time = time.time() + 5
                logging.info('[GAME] 在5s后开始识别ArucoTag')

            ns.has_cone = False # 清楚交通锥识别的标志
            continue

        if ns.has_line:
            # 巡线模式(画面中存在直线)  
            logging.info('[GAME]画面中存在曲线, next_yaw: {:.1f}°'.format(ns.next_yaw))
            if abs(ns.next_yaw) < 20:
                action_group_list.append(GoForward.name)
            elif ns.next_yaw > 0:
                action_group_list.append(GoLeft.name)
            else:
                action_group_list.append(GoRight.name)
            
            ns.has_line = False
        else:
            # 线丢失
            logging.warning('[GAME] 赛道曲线丢失')
            if ns.has_aruco:
                # GO GO GO !!!
                # 赛道终点, 识别不到很正常,向前冲
                action_group_list.append(GoForward.name)
            if ns.cross_ab > 0 or (ns.cross_ab == 0 and ns.next_yaw > 0):
                # 左转
                action_group_list.append(GoLeft.name)
            elif ns.cross_ab < 0 or (ns.cross_ab == 0 and ns.next_yaw < 0):
                # 右转
                action_group_list.append(GoRight.name)
            else:
                # 没有任何其他辅助信息，只能前进
                action_group_list.append(GoForward.name)
        wait_dbsp_done()
        # logging.info('[GAME] waiting 5s')
        # time.sleep(5)
def test_turn():
    '''测试旋转'''
    yaw_init = imu_pose_dict['yaw']
    cur_yaw = yaw_init
    
    cur_yaw += -90
    robot_turn(yaw=cur_yaw)
    time.sleep(5)
    
    cur_yaw += 90
    robot_turn(yaw=cur_yaw)
    time.sleep(5)

def test_go():
    '''测试前进'''
    robot_go(66)

def test_continue_go(n_step):
    for i_step in range(n_step):
        # 添加动作
        action_group_list.append(GoForward.name)
    # 执行动作
    wait_dbsp_done()
    

def main():
    '''主程序'''
    robo_init_evt.wait() # 等待机器人初始化
    imu_init_evt.wait() # 等待IMU标定完成
    game() # 执行游戏
    
    # test_turn() # 测试转弯
    # test_go() # 测试直行
    # test_continue_go(n_step=10)
    # go_around_cone() # 绕桩

if __name__ == '__main__':
    # 创建补光灯对象
    lamp = LED(LAMP_GPIO)

    # DBSP动作管理进程
    process_dbsp = mp.Process(target=worker_dbsp_action_group)
    # IMU位姿融合进程
    process_imu = mp.Process(target=worker_imu_pose)
    # 图像处理进程
    process_cv = mp.Process(target=worker_cv)

    if LAMP_ON:
        lamp.on() # 开启补光灯
    # 开启进程
    process_dbsp.start()
    process_imu.start()
    process_cv.start()

    main() # 执行主程序
    process_imu.terminate()
    game_finish_evt.set() # 设置游戏结束标识
    dbsp_action_evt.set() # 设置有动作执行
    process_dbsp.join() # 等待DBSP进程结束, 机器人卸力
    
    lamp.off() # 关闭补光灯
