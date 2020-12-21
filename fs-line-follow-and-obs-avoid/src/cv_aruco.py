'''ArucoTag检测'''
import numpy as np
import cv2
from cv2 import aruco

from cv_camera import Camera
from geometry import Geometry
from config import *

class ArucoDetect:
    def __init__(self, cam):
        self.cam = cam
        # 选择ArucoTag的字典
        self.aruco_dict = aruco.Dictionary_get(aruco.DICT_6X6_250)
        # 采用默认的Aruco参数
        self.aruco_params = aruco.DetectorParameters_create()
        # ArucoTag的尺寸
        self.marker_size = ARUCO_SIZE
        # 有效的ArucoID
        # self.known_arucos = [LEFT_ARUCO_ID, RIGHT_ARUCO_ID]

    def find_aruco(self, img, canvas=None):
        # 创建画布
        if canvas is None:
            canvas = np.copy(img)
        # 转换为灰度图
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # 图像去除畸变
        gray = self.cam.remove_distortion(gray)
        # 检测画面中的ArucoTag
        corners, aruco_ids, rejected_img_pts = aruco.detectMarkers(gray, \
            self.aruco_dict, parameters=self.aruco_params)

        if aruco_ids is None:
            # 画面中没有检测到ArucoTag
            return False, canvas, None, None

        # 获取画面中的ArucoID  
        aruco_id = aruco_ids[0]
        # 获取旋转矩阵跟平移矩阵
        rvect, tvect, object_points = aruco.estimatePoseSingleMarkers(corners, self.marker_size, \
            self.cam.intrinsic, self.cam.distortion)
        # Aruco在相机坐标系下的坐标(单位 cm)
        t_cam2aruco = np.array(tvect[0,0,:]).reshape((-1, 1))
        # 计算摄像头跟ArucoTag的直线距离
        dis_cam2aruco = np.linalg.norm(t_cam2aruco)
        
        # 可视化
        # 绘制Marker的边框与绘制编号
        canvas = aruco.drawDetectedMarkers(canvas, corners, aruco_ids,  (0,255,0))
        # 绘制坐标系
        canvas = aruco.drawAxis(canvas, self.cam.intrinsic, \
            self.cam.distortion, rvect[0], tvect[0], 4)


        return True, canvas, aruco_id, dis_cam2aruco


def main(argv):
    # 创建相机对象
    cam = Camera(FLAGS.device)
    # 初始相机
    cam.init_camera()
    capture = cam.get_video_capture()
    # 载入标定数据
    cam.load_cam_calib_data()
    # 载入透视逆变换矩阵
    cam.load_ipm_remap(calc_online=False)

    # 图像预处理窗口
    cv2.namedWindow('aruco',flags=cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO | cv2.WINDOW_GUI_EXPANDED)

    # 创建ArucoTag检测器
    aruco_detect = ArucoDetect(cam)
    while True:
        ret, img = capture.read()
        has_aruco, canvas, aruco_id, dis_cam2aruco = aruco_detect.find_aruco(img)
        if has_aruco:
            logging.info('[Aruco] ID: {} 距离摄像头的距离: {:.1f} cm'.format(aruco_id, dis_cam2aruco))
        
        cv2.imshow('aruco', canvas)
        
        key = cv2.waitKey(1)
        if key == ord('q'):
            # 如果按键为q 代表quit 退出程序
            break  
        elif key == ord('s'):
            # s键代表保存数据
            cv2.imwrite('{}/{}.png'.format(FLAGS.img_path, img_cnt), canvas)
            logging.info("截图，并保存在  {}/{}.png".format(FLAGS.img_path, img_cnt))
            img_cnt += 1

if __name__ == "__main__":
    import logging
    import sys
    from absl import app
    from absl import flags

    # 设置日志等
    logging.basicConfig(level=logging.INFO)
    # 定义参数
    FLAGS = flags.FLAGS
    flags.DEFINE_string('device', '/dev/video0', '摄像头的设备号')
    flags.DEFINE_integer('img_cnt', 0, '图像计数的起始数值')
    flags.DEFINE_string('img_path', 'data/img_with_aruco', '图像的保存地址')
    app.run(main)
