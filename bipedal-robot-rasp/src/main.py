'''
主程序-双足机器人巡线
-------------------
赛道规格
* 线宽: 4cm
* 颜色: 黑线
* 背景色: 白色
* 材质: 广告纸高清喷绘
'''
import time
import multiprocessing as mp
import numpy as np
import logging
import serial # 串口通信
from gpiozero import LED
import cv2

from dbsp import ServoAngleControlEvent
from dbsp_action_group import *
from cv_camera import Camera
from cv_track_fit import TrackFit
from config import *

# 设置日志输出等级
logging.basicConfig(level=logging.INFO)

def worker_cv_line(robo_init_evt, cam_data_load_evt, action_done_evt, \
        has_line_info_evt, line_info_dict, game_interrupt_evt):
    '''子进程-图像处理'''
    
    # 图像预处理窗口
    cv2.namedWindow('img_preprocess',flags=cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO | cv2.WINDOW_GUI_EXPANDED)
    # 带标记的彩图
    cv2.namedWindow('img_raw',flags=cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO | cv2.WINDOW_GUI_EXPANDED)
    # 机器人坐标系下点图+拟合曲线图
    cv2.namedWindow('canvas_robo',flags=cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO | cv2.WINDOW_GUI_EXPANDED)

    # 初始化相机
    cam = Camera(device=CAM_PORT_NAME)
    # 相机初始化
    cam.init_camera()
    capture = cam.get_video_capture()
    # 载入标定参数
    cam.load_cam_calib_data()
    # 载入透视逆变换矩阵
    cam.load_ipm_remap(calc_online=False)
    # 设置相机初始化事件
    cam_data_load_evt.set()
    
    # 等待机器人动作初始化
    while not robo_init_evt.is_set():
        # 单纯刷新图像
        ret, frame = capture.read()
        cv2.imshow('img_raw', frame)
        # 更新显示的图像
        key = cv2.waitKey(1)
        if key == ord('q'):
            break
    
    # 创建赛道曲线拟合的对象
    tk_curve_fit = TrackFit(cam)

    fps = 40 # 设定一个初始值
    canvas_robo = np.zeros((600, 800, 3), dtype=np.uint8) # 机器人坐标系下的画布

    
    while True:
        # 开始计时
        start = time.time()
        # 图像采集
        ret, img = capture.read()
        if not ret:
            logging.error('图像获取失败')
            break
        # 图像去除畸变
        # img = cam.remove_distortion(img)
        if not action_done_evt.is_set():
            # 动作进行中, 不进行图像处理
            # 更新窗口“image_win”中的图片
            key = cv2.waitKey(1)
            if key == ord('q'):
                # 如果按键为q 代表quit 退出程序
                break
            continue
        
        # 拷贝图像
        canvas_img = np.copy(img)
        # 图像预处理部分
        has_line, gray_small, bin_track, bin_ostu_close, line_bin = tk_curve_fit.img_preprocess(img)

        if has_line:
            # 透视逆变换
            rb_x, rb_y = tk_curve_fit.pixel_ipm(line_bin, canvas=canvas_img)
            # rb_x, rb_y = tk_curve_fit.pixel_ipm(line_bin)
            # 曲线拟合
            has_c1, has_c2, next_yaw, cross_ab, canvas_robo = tk_curve_fit.curve_fit(rb_x, rb_y, is_draw=True)
            # 更新line_info_dict
            line_info_dict['next_yaw'] = next_yaw
            line_info_dict['has_c1'] = has_c1
            line_info_dict['has_c2'] = has_c2
            line_info_dict['cross_ab'] = cross_ab
        else:
            # 黑屏
            canvas_robo = np.zeros_like(canvas_robo, dtype=np.uint8)

        # 停止计时计算帧率
        end = time.time()
        fps = int(0.9*fps +  0.1*1/(end-start))
        
        # 将识别到的结果赋值给字典
        line_info_dict['has_line'] = has_line
        
        
        # 设置有新的直线信息的事件
        has_line_info_evt.set()

        # 画布绘制
        canvas = tk_curve_fit.visual_img_preprocess(has_line, gray_small, bin_track, bin_ostu_close, line_bin)
        ch, cw = canvas.shape[:2]
        # 在画布下方添加一个小条
        canvas = np.vstack((np.zeros((30, cw, 3),dtype=np.uint8), canvas))
        # 在画布上添加帧率的信息
        cv2.putText(canvas, text='{}'.format(fps),\
                org=(0, 25), fontFace=cv2.FONT_HERSHEY_SIMPLEX, \
                fontScale=0.5, thickness=1, lineType=cv2.LINE_AA, color=(0, 0, 255))
        # 显示画面中是否存在直线
        cv2.putText(canvas, text='{}'.format('T' if has_line else 'F'),\
            org=(cw-30, 25), fontFace=cv2.FONT_HERSHEY_SIMPLEX, \
            fontScale=0.5, thickness=1, lineType=cv2.LINE_AA, color=(0, 0, 255))
        
        # 更新窗口“image_win”中的图片
        cv2.imshow('img_raw', canvas_img) # 显示原始图像(上面附带标记点)
        cv2.imshow('img_preprocess', canvas) # 显示图像预处理之后的图像
        cv2.imshow('canvas_robo', canvas_robo)
        key = cv2.waitKey(1)
        if key == ord('q'):
            # 如果按键为q 代表quit 退出程序
            break

    # 关闭摄像头
    capture.release()
    # 销毁所有的窗口
    cv2.destroyAllWindows()
    # 设置游戏中断
    game_interrupt_evt.set()
    time.sleep(5)

def worker_dbsp_action_group(robo_init_evt, cam_data_load_evt, \
        action_done_evt, has_line_info_evt, line_info_dict, game_interrupt_evt):
    # 串口初始化
    uart = serial.Serial(port=DBSP_PORT_NAME, \
        baudrate=DBSP_BAUDRATE, parity=serial.PARITY_NONE, \
        stopbits=1, bytesize=8, timeout=0)
    # 设置头部舵机的角度
    angle_ctl_event = ServoAngleControlEvent([[HEAD_SERVO_ID, HEAD_SERVO_ANGLE, 100]])
    uart.write(angle_ctl_event.generate_request_bytes())

    # 动作组管理器
    am = ActionGroupManager(uart)
    # 动作初始化(站立)
    am.execute(StandUp())
    am.execute(StandUpPre())
    logging.info('机器人动作初始化, 请将机器人放置与赛道起点')
    # 设置机器人初始化动作事件
    robo_init_evt.set()
    # 设置当前机器人的所有动作组已完成
    action_done_evt.set()

    # 等待相机参数载入
    cam_data_load_evt.wait()

    has_line = False
    next_yaw = 0
    has_c1 = False
    has_c2 = False
    cross_ab = 0
    while True:
        if game_interrupt_evt.is_set():
            # 游戏被中断
            am.execute(StandUp())
            # 机器人卸力
            am.relax()
            break
        # 等待新的直线检测信息
        has_line_info_evt.wait()
        # 读取字典, 更新数据
        has_line = line_info_dict['has_line']
        has_c1 = line_info_dict['has_c1']
        has_c2 = line_info_dict['has_c2']

        if has_line and has_c1:
            # 存在曲线1的时候才更新next_yaw
            next_yaw = line_info_dict['next_yaw']
        if has_c1 and has_c2:
            # 只有同时存在曲线1还有曲线2的时候
            # 才更新叉乘的结果
            cross_ab = line_info_dict['cross_ab']
        has_line_info_evt.clear() # 标记为已读取

        if not has_line:
            logging.info('line lost hist_yaw = {:.1f}  hist cross_ab={:.0f}'.format(next_yaw, cross_ab))
            # 机器人根据next yaw 调用不同的动作
            action_done_evt.clear()
            if cross_ab > 0:
                logging.info('cross_ab > 0 --> Turn Left')
                am.execute(GoLeft())
            elif cross_ab < 0:
                logging.info('cross_ab < 0 -> Turn Right')
                am.execute(GoRight())
            else:
                if next_yaw > 0:
                    logging.info('next_yaw > 0 -> Turn Left')
                    am.execute(GoLeft())
                elif next_yaw > 0:
                    logging.info('next_yaw < 0 -> Turn Right')
                    am.execute(GoRight())
                else:
                    # 没有任何依据, 可以辅助判断
                    logging.info('what ever ... -> Go Forward')
                    am.execute(GoForward())
            # 动作执行完成, 设置标识位
            action_done_evt.set()
            continue
            
        # 机器人根据next yaw 调用不同的动作
        action_done_evt.clear()
        
        if abs(next_yaw) < 15:
            am.execute(GoForward(), n_repeat=2)
        elif next_yaw > 0:
            am.execute(GoLeft())
        else:
            am.execute(GoRight())
        # 动作执行完成, 设置标识位
        action_done_evt.set()

if __name__ == "__main__":
    # 创建补光灯对象
    lamp = LED(LAMP_GPIO)
    # 机器人位姿初始化事件
    robo_init_evt = mp.Event()
    # 相机数据载入事件
    cam_data_load_evt = mp.Event()
    # 机器人动作组执行完成事件
    action_done_evt = mp.Event()
    # 有新的直线数据事件
    has_line_info_evt = mp.Event()
    line_info_manager = mp.Manager()
    # 存放直线相关参数的字典
    line_info_dict = line_info_manager.dict()
    line_info_dict['has_line'] = False
    line_info_dict['next_yaw'] = 0
    line_info_dict['has_c1'] = False
    line_info_dict['has_c2'] = False
    line_info_dict['cross_ab'] = 0    

    # 竞赛被中断的标志
    game_interrupt_evt = mp.Event()
    # 创建图像处理进程
    process_cv = mp.Process(target=worker_cv_line, \
        args=(robo_init_evt, cam_data_load_evt, action_done_evt,\
        has_line_info_evt, line_info_dict, game_interrupt_evt))
    # DBSP动作管理进程
    process_dbsp = mp.Process(target=worker_dbsp_action_group,\
        args=(robo_init_evt, cam_data_load_evt, action_done_evt,\
        has_line_info_evt, line_info_dict, game_interrupt_evt))
    
    # 开启补光灯
    lamp.on()
    # 进程开始运行
    process_cv.start()
    process_dbsp.start()
    # 主进程需要等待子进程都结束再退出
    process_cv.join()
    process_dbsp.join()
    # 关闭补光灯
    lamp.off()
