'''红色交通锥的识别
为了保证图像处理算法在树莓派上的实时性, 用颜色阈值来检测
'''
import math
import cv2
import numpy as np
from cv_camera import Camera
from config import *

class TrafficConeDetect:
    '''交通锥检测'''
    # 图像缩放因子
    IMG_SCALE_FACTOR = 0.2

    def __init__(self, cam):
        self.cam = cam

    def find_contours(self, img_bin):
        '''寻找连通域(兼容不同的CV版本)'''
        if cv2.__version__[0] == '4':
            contours, hierarchy = cv2.findContours(img_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        else:
            img, contours, hierarchy =  cv2.findContours(img_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours

    def preprocessing(self, img, w_threshold=None):
        '''图像预处理'''
        has_cone = False # 画面中是否有交通锥
        # 将彩图缩放为小图
        img_small_bgr = cv2.resize(img, dsize=None, fx=self.IMG_SCALE_FACTOR, fy=self.IMG_SCALE_FACTOR)
        # 获取图像的高度与宽度
        img_h, img_w= img_small_bgr.shape[:2]
        # 根据颜色获取交通锥的二值化图像
        bin_cone = cv2.inRange(img_small_bgr, lowerb=CONE_RED_LOWERB, upperb=CONE_RED_UPPERB)
        # 获取最大的contour
        contours = self.find_contours(bin_cone)

        if len(contours) > 0:
            # 进一步, 根据连通域判断是否合法
            # 获取宽度最大的连通域
            cone_rect = max([cv2.boundingRect(cnt) for cnt in contours], key=lambda rect: rect[2])
            if w_threshold is None:
                w_threshold =  CONE_WIDTH_RATIO
            # 交通锥的宽度需要大于画面宽度的40%
            if (cone_rect[2]/img_w) > w_threshold:
                has_cone = True
                # logging.info('RECT SMALL: {}'.format(cone_rect))
                
                # 将外接矩形,恢复到原来的尺寸
                sx, sy, sw, sh = cone_rect
                bx = int(sx / self.IMG_SCALE_FACTOR)
                by = int(sy / self.IMG_SCALE_FACTOR)
                bw = int(sw / self.IMG_SCALE_FACTOR)
                bh = int(sh / self.IMG_SCALE_FACTOR)
                cone_rect = (bx, by, bw, bh)
                # logging.info('RECT BIG: {}'.format(cone_rect))
                return has_cone, bin_cone, cone_rect
        return has_cone, bin_cone, None

    def cone_measure(self, cone_rect):
        '''计算机器人与交通锥之间的距离'''
        # 计算矩形底部中心的坐标
        x, y, w, h = cone_rect
        btm_x, btm_y = int(x+w/2), int(y+h)
        # 透视逆变换 计算该点在机器人基坐标系下的位置
        rx, ry = self.cam.inverse_projection_mapping2(btm_x, btm_y)
        # 计算距离
        distance = math.sqrt(rx**2 + ry**2)
        return distance, (rx, ry)
    
    def visualization(self, has_cone, canvas, cone_rect=None, distance=None, cone_posi=None):
        '''圆锥识别可视化'''
        font = cv2.FONT_HERSHEY_SIMPLEX # 选择字体
        font_size = 1
        font_color = (0, 255, 255)
        # 创建画布
        # canvas = cv2.cvtColor(bin_cone, cv2.COLOR_GRAY2BGR)
        # 绘制是否存在交通锥
        cv2.putText(canvas, text="Has Cone: {}".format(has_cone), org=(20, 370), \
            fontFace=font, fontScale=font_size, thickness=2, lineType=cv2.LINE_AA, color=font_color)

        # 绘制外接矩形
        if cone_rect is not None:
            # 计算矩形底部中心的坐标
            x, y, w, h = cone_rect
            btm_x, btm_y = int(x+w/2), int(y+h)

            # 绘制一个边缘宽度为5的矩形
            cv2.rectangle(img=canvas, pt1=(x, y), pt2=(x+w, y+h), color=(0, 255, 0), thickness=5)
            # 绘制底部中心点
            # 绘制一个红色圆 边缘宽度(thickness = 5)
            cv2.circle(img=canvas, center=(btm_x, btm_y), radius=5, color=(0, 0, 255), thickness=-1)

        if distance is not None:
            cv2.putText(canvas, text="Dis: {:.1f} cm".format(distance), org=(20, 400), \
                fontFace=font, fontScale=font_size, thickness=2, lineType=cv2.LINE_AA, color=font_color)

        if cone_posi is not None:
            cv2.putText(canvas, text="rx :{:.1f} cm ; ry: {:.1f} cm".format(*cone_posi), org=(20, 430), \
                fontFace=font, fontScale=font_size, thickness=2, lineType=cv2.LINE_AA, color=font_color)
        
        return canvas

def main(argv):
    '''测试交通锥识别'''
    # 创建相机对象
    cam = Camera(FLAGS.device)
    # 初始相机
    cam.init_camera()
    capture = cam.get_video_capture()
    # 载入标定数据
    cam.load_cam_calib_data()
    # 载入透视逆变换矩阵
    cam.load_ipm_remap(calc_online=FLAGS.ipm_calc_online)

    # 图像预处理窗口
    cv2.namedWindow('img_raw',flags=cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO | cv2.WINDOW_GUI_EXPANDED)
    # 
    cv2.namedWindow('bin_cone',flags=cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO | cv2.WINDOW_GUI_EXPANDED)
    # 图像预处理窗口
    cv2.namedWindow('cone_detect',flags=cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO | cv2.WINDOW_GUI_EXPANDED)

    cone_detect = TrafficConeDetect(cam)
    
    img_cnt = 0
    while True:
        # 获取图像
        ret, img = capture.read()
        # 交通锥检测
        has_cone, bin_cone, cone_rect = cone_detect.preprocessing(img)

        distance = None
        cone_posi = None
        if has_cone:
            # 交通锥测量
            distance, cone_posi = cone_detect.cone_measure(cone_rect)
        # 可视化
        canvas = cone_detect.visualization(has_cone, np.copy(img), cone_rect=cone_rect, distance=distance, cone_posi=cone_posi)

        cv2.imshow('img_raw', img)
        cv2.imshow('bin_cone', bin_cone)
        cv2.imshow('cone_detect', canvas)

        key = cv2.waitKey(1)

        if key == ord('q'):
            # 如果按键为q 代表quit 退出程序
            break  
        elif key == ord('s'):
            # s键代表保存数据
            cv2.imwrite('{}/{}.png'.format(FLAGS.img_path, img_cnt), img)
            logging.info("截图，并保存在  {}/{}.png".format(FLAGS.img_path, img_cnt))
            img_cnt += 1
    # 关闭摄像头
    capture.release()
    # 销毁所有的窗口
    cv2.destroyAllWindows()

if __name__ == '__main__':
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
    flags.DEFINE_string('img_path', 'data/traffic_cone', '图像的保存地址')
    flags.DEFINE_boolean('rm_distortion', False, '载入相机标定数据, 去除图像畸变')
    flags.DEFINE_boolean('ipm_calc_online', False, '是否在线计算透视逆变换矩阵')
    app.run(main)
