'''
--------------
| 赛道曲线拟合 |
--------------
颜色: 白底黑线
线宽: 4cm
材质: 广告布,高清喷绘
'''
import time
import math
import cv2
import numpy as np
import matplotlib
from matplotlib import pyplot as plt
from cv_camera import Camera
import logging
import gc
from config import *

class TrackFit:
    '''赛道曲线拟合'''
    # 图像缩放因子
    IMG_SCALE_FACTOR = 0.05
    # IMG_SCALE_FACTOR = 0.1
    # 赛道颜色阈值(白底+黑线 两个阈值的并集)
    # 这个阈值的作用是防止除了赛道之外的颜色干扰, 例如地毯, 地板等
    # 色块的最小连通区域面积(针对32x24的缩略图)
    MIN_CNT_AREA = 10 # 25 # 最小的连通区域的面积(针对缩放之后的图像)
    # 机器人坐标系下点的取值范围
    # 机器人只关注这个范围下的点
    RB_Y_MIN = -30
    RB_Y_MAX = 30
    RB_X_MIN = 5
    RB_X_MAX = 50
    # 滑动窗口
    WIN_W = 6 # 滑动窗口的宽度
    WIN_H = 1 # 滑动窗口的高度
    WIN_MAX_GAP = 10 # 采样点轴方向最大的间隙(距离)
    # 曲线1的尾巴采样窗口, 决定曲线2的滑动窗口采样方向
    # 是沿着Y轴的正方向还是沿着Y轴的负方向
    TAIL_ROI_W = 10
    TAIL_ROI_H = 20
    # 曲线1尾巴采样框内, 未采样到的样本点的个数
    # 决定是否要进行曲线2的采样
    TAIL_ROI_MIN_PT = 4
    # 曲线2的采样方向
    # 向下采样还是向上采样
    DIR_Y_POSI = 0 # 向Y轴的正方向采样
    DIR_Y_NEGI = 1 # 向Y轴的负方向采样
    # 轨道灰度值的最大值(大于这个值的都设置为最大值))
    TRACK_GRAY_MAX = 180
    # 直线灰度的最大值 (仅当做判断当前画面是否有直线使用)
    LINE_GRAY_MAX = 120
    # 在 32x24缩略图中, 直线像素的点(满足像素灰度小于LINE_GRAY_MAX)
    # 的个数的最小值, 如果大于这个值,就认为画面中有直线,否则不予处理.
    LINE_PIXEL_N_MIN = 20
    # 合法的曲线的长度(单位cm)
    # 如果拟合得到的曲线比自身宽度还要小的话是没有意义的
    CURVE_MIN_LEN = 2 # 曲线的最小的长度
    # 机器人前进一步的距离(单位cm)
    RB_STEP = GO_FORWARD_DIS_PER_STEP*0.6
    # 曲线可视化的绘图引擎
    PAINTER = 'CV' # 可选绘图引擎是"Matplotlib"跟 "CV"
                    # Matplotlib绘图质量好但是帧率差

    LANE_MID2EDGE = 25 # 中线距离边界线的距离 25cm

    def __init__(self, cam):
        self.cam = cam
        # 载入摄像头的标定数据
        cam.load_cam_calib_data()
        # 设置绘图引擎
        self.set_painter()
        self.pt_near2org = (self.RB_X_MIN, 0)
        self.last_y_offset = 0

    def set_painter(self):
        if self.PAINTER == 'MATPLOTLIB':
            # Matplotlib初始化
            # 选择后端
            matplotlib.use('Agg')
            # 关闭交互模式
            plt.ioff()
            # 设置分辨率为800x600
            plt.figure(figsize=(8, 6))
            self.fig, self.axes = plt.subplots()
        
    def find_contours(self, img_bin):
        ''' 寻找连通域(兼容不同的CV版本)'''
        if cv2.__version__[0] == '4':
            contours, hierarchy = cv2.findContours(img_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        else:
            img, contours, hierarchy =  cv2.findContours(img_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours

    def img_preprocess(self, img):
        '''图像预处理'''
        # 将彩图缩放为小图
        img_small_bgr = cv2.resize(img, dsize=None, fx=self.IMG_SCALE_FACTOR, fy=self.IMG_SCALE_FACTOR)
        # 根据赛道黑线的BGR阈值,进行图像预处理
        bin_line = cv2.inRange(img_small_bgr, lowerb=TRACK_BLACK_LOERB, upperb=TRACK_BLACK_UPPERB)
        # 对二值化图像进行膨胀
        bin_line = cv2.dilate(bin_line, np.ones((3,3), np.uint8), iterations=1)
        # 彩图转换为灰度图
        gray_small = cv2.cvtColor(img_small_bgr, cv2.COLOR_BGR2GRAY)

        # 通过像素统计判断是否存在直线
        blk_pt_n = np.sum(gray_small < self.LINE_GRAY_MAX)
        if blk_pt_n < self.LINE_PIXEL_N_MIN:
            return False, bin_line

        # 过滤掉较小的连通区域
        line_cnts = self.find_contours(bin_line) # 寻找连通域
        valid_cnt_num = 0
        if len(line_cnts) >= 1:
            # 筛选面积大于阈值的连通域
            bin_line = np.zeros_like(bin_line)
            for cnt in line_cnts:
                if cv2.contourArea(cnt) > self.MIN_CNT_AREA:
                    valid_cnt_num += 1
                    bin_line = cv2.drawContours(image=bin_line, contours=[cnt], contourIdx=0, color=255, thickness=-1)
        
        # 判断画面中是否有直线的区域
        has_line = valid_cnt_num >= 1
        
        return has_line, bin_line
    
    def pixel_ipm(self, bin_line, canvas=None):
        '''
        将缩放后的直线二值化图像中的像素点透视逆变换, 转换到机器人坐标系上
        '''
        # 获取图像中的非零点的坐标
        n0_y, n0_x = bin_line.nonzero()
        # 像素重新映射回(640x480)
        n0_x = np.uint16(n0_x / self.IMG_SCALE_FACTOR)
        n0_y = np.uint16(n0_y / self.IMG_SCALE_FACTOR)
        # 可视化 在原图上标注上采样点
        if canvas is not None:
            # 为了可视化要绘制圆圈
            for i in range(len(n0_x)):
                cx, cy = n0_x[i], n0_y[i]
                cv2.circle(canvas, (cx, cy), 5, thickness=-1, color=(0, 255, 255))
        # 像素点的个数
        n_pt = len(n0_x)
        # 将非零点,投影到机器人基坐标系下
        rb_x = np.zeros(n_pt, dtype=np.float32)
        rb_y = np.zeros(n_pt, dtype=np.float32)
        for i in range(n_pt):
            # 透视逆变换
            rb_x[i], rb_y[i] = self.cam.inverse_projection_mapping2(n0_x[i], n0_y[i])
        # 只选取在机器人坐标系ROI内的点
        legal_pt_idxs = np.bitwise_and(
            np.bitwise_and(rb_y > self.RB_Y_MIN, rb_y < self.RB_Y_MAX),
            np.bitwise_and(rb_x > self.RB_X_MIN, rb_y < self.RB_X_MAX))
        rb_x = rb_x[legal_pt_idxs]
        rb_y = rb_y[legal_pt_idxs]

        return rb_x, rb_y

    def c1_pt_sample(self, rb_x, rb_y):
        '''曲线1通过滑动窗口(x方向)进行采样'''
        # 对x轴的数值进行筛选
        rb_x_unique = np.array(list(set(rb_x)))
        # 从小到大进行排序
        rb_x_unique = np.sort(rb_x_unique)
        # print('rb_x_unique: {}'.format(rb_x_unique))
        # 采样框的记录 
        # sld_win: sliding window
        sld_win_hist = []
        # 记录样本点是否被采样过
        is_pt_visited = np.zeros_like(rb_x, dtype=np.bool)
        # 曲线的采样点的集合
        curve_x = []
        curve_y = []
        # 确定采样点的起始位置
        root_x = rb_x_unique[0] # 找到x的最小值
        root_y = np.mean(rb_y[np.abs(rb_x-root_x) < 1]) # 对root_x上的点的y轴求平均值

        # 曲线点集中添加(root_x, root_y)
        curve_x.append(root_x)
        curve_y.append(root_y)
        # 曲线的长度
        curve_len = 0

        # 添加滑动窗口日志
        sld_win_hist.append((root_x, root_y))
        # 惯性力(斜率)
        k = 0
        # 赋值上一次的点坐标
        last_x, last_y = root_x, root_y
        cur_x, cur_y = None, None
        # 遍历后续的x坐标
        for x_idx in range(1, len(rb_x_unique)):
            cur_x = rb_x_unique[x_idx]
            dx = cur_x - last_x
            if dx > self.WIN_MAX_GAP:
                # 间隔过大,停止采样
                # logging.info('间隔过大 last_x: {} cur_x: {} dx:{}'.format(last_x, cur_x, dx))
                break
            # 根据斜率推断当前窗口的y坐标
            cur_y = last_y + k * dx
            # 添加到滑动窗口日志
            sld_win_hist.append((cur_x, cur_y))
            # 寻找候选点
            roi_pt_idx = np.bitwise_and(
                np.abs(rb_x - cur_x) < self.WIN_H/2,
                np.abs(rb_y - cur_y) < self.WIN_W/2)
            # 计算ROI区域的点的个数
            roi_pt_n = np.sum(roi_pt_idx)
            if roi_pt_n == 0:
                # 继续向后查找
                continue
            # 标记点集的访问记录
            is_pt_visited = np.bitwise_or(is_pt_visited, roi_pt_idx)
            # 计算均值重新修正cur_y
            cur_y = np.mean(rb_y[roi_pt_idx])
            # 添加曲线样本点            
            curve_x.append(cur_x)
            curve_y.append(cur_y)
            # 更新斜率
            k = (cur_y - last_y) / (cur_x - last_x)
            # 增加曲线的长度
            curve_len += math.sqrt((cur_x - last_x)**2 + (cur_y-last_y)**2)
            # print('curve length: {} cur_x={} last_x={} cur_y={} last_y={}'.format(curve_len, cur_x, last_x, cur_y, last_y))
            # 更新上一个点
            last_x, last_y = cur_x, cur_y
        
        curve_x = np.float32(curve_x)
        curve_y = np.float32(curve_y)

        return curve_x, curve_y, curve_len, sld_win_hist, is_pt_visited

    def has_curve2(self, rb_x, rb_y, tail, is_pt_visited):
        '''返回是否存在curve2以及遍历的方向'''
        if tail is None:
            return False
        # tail 曲线1末端的点
        tail_x, tail_y = tail
        # 获得末端点在ROI区域内未被访问到的点
        tail_roi_pt_idx = np.bitwise_and(
            np.abs(rb_x - tail_x) < self.TAIL_ROI_W/2,
            np.abs(rb_y - tail_y) < self.TAIL_ROI_H/2)
        # 必须还是未被访问过的点
        tail_roi_pt_idx = np.bitwise_and(np.bitwise_not(is_pt_visited), tail_roi_pt_idx)
        # 统计ROI区域内未被访问过的点的个数
        roi_n = np.sum(tail_roi_pt_idx)
        if roi_n < self.TAIL_ROI_MIN_PT:
            # 判断没有曲线2
            return False, 0
        # 分别统计采样框上部跟下部的分布
        roi_y = rb_y[tail_roi_pt_idx]
        roi_n_posi = np.sum(roi_y > tail_y)
        roi_n_negi = roi_n - roi_n_posi
        # 获得曲线2的采样方向
        dir_y = self.DIR_Y_POSI if roi_n_posi > roi_n_negi else self.DIR_Y_NEGI
        return True, dir_y

    def c2_pt_sample(self, rb_x, rb_y, root, dir_y):
        '''曲线2通过滑动窗口(y方向)进行采样'''
        # 曲线拟合的起始点
        root_x, root_y = root
        # 根据遍历方向先对y坐标进行初筛
        pt_idx = rb_y > root_y if dir_y == self.DIR_Y_POSI else rb_y < root_y
        # 对y坐标进行筛选排序(默认顺序是从小到大)
        rb_y_unique = np.sort(list(set(rb_y[pt_idx])))
        if dir_y == self.DIR_Y_NEGI:
            # 如果遍历顺序是Y轴负方向, 需要对rb_y_unique倒序 
            rb_y_unique = rb_y_unique[::-1]
        
        # 采样框的记录
        sld_win_hist = []
        # 记录样本点是否被采样过
        is_pt_visited = np.zeros_like(rb_x, dtype=np.bool)
        # 曲线的采样点的集合
        curve_x = [root_x, ]
        curve_y = [root_y, ]
        # 曲线的长度
        curve_len = 0
        # 添加滑动窗口日志
        sld_win_hist.append((root_x, root_y))
        # 惯性力(斜率)
        k = 0
        # 赋值上一次的点坐标
        last_x, last_y = root_x, root_y
        cur_x, cur_y = last_x, last_y
        # 遍历后续的y坐标
        for y_idx in range(1, len(rb_y_unique)):
            cur_y = rb_y_unique[y_idx]
            dy = cur_y - last_y
            if dy > self.WIN_MAX_GAP:
                # 间隙过大,停止采样
                break
            # 根据斜率推算出当前窗口的y坐标
            cur_x = last_x + k * dy
            # 添加到滑动窗口日志
            sld_win_hist.append((cur_x, cur_y))
            # 寻找候选点
            roi_pt_idx = np.bitwise_and(
                np.abs(rb_x - cur_x) < self.WIN_W/2,
                np.abs(rb_y - cur_y) < self.WIN_H/2)
            # 计算窗口内的点的个数
            roi_pt_n = np.sum(roi_pt_idx)
            if roi_pt_n == 0:
                # 继续向后查找
                continue
            # 修改点的访问记录
            is_pt_visited = np.bitwise_or(is_pt_visited, roi_pt_idx)
            # 计算均值 重新修正cur_x
            cur_x = np.mean(rb_x[roi_pt_idx])
            # 添加曲线样本
            curve_x.append(cur_x)
            curve_y.append(cur_y)
            # 更新斜率
            k = (cur_x - last_x) / (cur_y - last_y)
            # 增加曲线长度
            curve_len += math.sqrt((cur_x - last_x)**2 + (cur_y-last_y)**2)
            # 更新上一个点
            last_x, last_y = cur_x, cur_y
        
        curve_x = np.float32(curve_x)
        curve_y = np.float32(curve_y)
        
        return curve_x, curve_y, curve_len, sld_win_hist, is_pt_visited

    def rb2pixel(self, rx, ry, x_offset=20, y_offset=30, scale=10):
        '''机器人坐标系到像素坐标系的转换'''
        if type(rx) == np.ndarray:
            rx[rx > 60] = 60
            rx[rx < -20] = -20
            ry[ry > 30] = 30
            ry[ry < -30] = -30
        else:
            rx = 60 if rx > 60 else rx
            rx = -20 if rx < -20 else rx
            ry = 30 if ry > 30 else ry
            ry = -30 if ry < -30 else ry

        px = np.uint16(np.round(rx + x_offset) * scale)
        # 注意y轴是反向的
        py = np.uint16(np.round(-ry + y_offset) * scale)
        
        return px, py
        
    def curve_fit(self, rb_x, rb_y, is_draw=False):
        '''曲线拟合'''
        canvas = None # 画布
        has_c1 = False # 曲线1是否存在
        has_c2 = False # 曲线2是否存在
        c1_a, c1_b, c1_c = 0, 0, 0 #　曲线1的系数
        c2_a, c2_b, c2_c = 0, 0, 0 # 曲线2的系数
        # 曲线1上的所有点
        c1_x_arr, c1_y_arr = None, None
        # 曲线2上的所有点
        c2_x_arr, c2_y_arr = None, None
        cross_ab = 0 # 向量a跟向量b的叉乘的结果

        # 曲线2的采样数据
        c2_x, c2_y, c2_len, c2_sld_win_hist, c2_pt_visited = None, None, None, None, None
        # 曲线上距离原点最近的点
        pt_near2org = (0, 0)
        # 下一刻的机器人目标位置
        pt_next = (0, 0)
        # 下一刻的目标偏航角,机器人坐标系中目标向量的夹角
        next_yaw = 0
        tail = None

        if len(rb_x) >=1:
            # 对曲线1进行拟合 采样相关的点
            c1_x, c1_y, c1_len, c1_sld_win_hist, c1_pt_visited = self.c1_pt_sample(rb_x, rb_y)
            # logging.info('曲线1的长度: {}'.format(c1_len))
            # 判断曲线1的长度是否合法
            has_c1 = c1_len >= self.CURVE_MIN_LEN
            # 获取曲线1的末端点tail
            tail = (c1_x[-1], c1_y[-1])
        if has_c1:
            # 对采集的点进行二次曲线拟合
            # 输入是x 输出是y
            c1_a, c1_b, c1_c = np.polyfit(c1_x, c1_y, 2)
            # 求解直线上的点集
            c1_x_arr = np.linspace(self.RB_X_MIN, self.RB_X_MAX, num=20)
            c1_y_arr = c1_a*c1_x_arr*c1_x_arr + c1_b*c1_x_arr + c1_c


        

        # 判断是否存在曲线2
        has_c2, y_dir = self.has_curve2(rb_x, rb_y, tail, c1_pt_visited)
        if has_c2:
            # 对线段2的数据点进行采样 
            c2_x, c2_y, c2_len, c2_sld_win_hist, c2_pt_visited = self.c2_pt_sample(rb_x, rb_y, tail, y_dir)
            # 根据曲线2的长度再次判断曲线2是否合法
            has_c2 = c2_len >= self.CURVE_MIN_LEN

        if has_c2:
            # 对曲线2进行数据拟合
            # 输入是y 输出为x
            c2_a, c2_b, c2_c = np.polyfit(c2_y, c2_x, 2)
            # 求解曲线2上的点集
            c2_y_arr = np.linspace(self.RB_Y_MIN, self.RB_Y_MAX, num=20)
            c2_x_arr = c2_a*c2_y_arr*c2_y_arr + c2_b*c2_y_arr + c2_c
        
        if has_c1:
            # 只有拟合曲线1存在,或者拟合曲线1跟2同时存在
            # 找到在定义域内, 距离原点最近的坐标
            pt_near2org_idx = np.argmin(c1_x_arr**2 + c1_y_arr**2)
            # 求得最靠近原点的位置
            pt_near2org = (c1_x_arr[pt_near2org_idx], c1_y_arr[pt_near2org_idx])            
            
            # 添加建议版本的限幅滤波
            # 通过y坐标的距离判断是哪根线
            y_err = (pt_near2org[1] - self.pt_near2org[1])
            # 从3种情况中挑选一个比较接近的
            # candi_y_offsets = np.float32([self.LANE_MID2EDGE*2, self.LANE_MID2EDGE, 0,  self.LANE_MID2EDGE, 2*self.LANE_MID2EDGE])
            
            candi_y_offsets = None
            if LINE_TYPE == 1:
                # 单轨曲线
                candi_y_offsets = np.float32([0])
            elif LINE_TYPE == 3:
                # 三轨曲线
                if(abs(pt_near2org[1]) < 5):
                    candi_y_offsets = np.float32([-1*self.LANE_MID2EDGE, 0,  self.LANE_MID2EDGE])
                elif (pt_near2org[1] > 5):
                    # 看到的可能是中线跟左边界
                    candi_y_offsets = np.float32([-1*self.LANE_MID2EDGE, 0])
                else:
                    # 看到的可能是中线跟右边界
                    candi_y_offsets = np.float32([self.LANE_MID2EDGE, 0])
            
            y_offset = candi_y_offsets[np.argmin(np.abs(pt_near2org[1] + candi_y_offsets))]
            # 修正c1_y_arr中的偏移量
            c1_y_arr += y_offset
            # 修正c1_c
            c1_c += y_offset
            
            # 更新上次的距离原点最近的曲线上的点坐标
            pt_near2org = (c1_x_arr[pt_near2org_idx], c1_y_arr[pt_near2org_idx] + y_offset)
            self.pt_near2org = pt_near2org
            self.last_y_offset = y_offset

            # 计算下一步的位置
            pt_next_idx = int(pt_near2org_idx + self.RB_STEP) # 计算索引
            # 修正下一步的位置
            pt_next_idx = (len(c1_x_arr) - 1) if pt_next_idx >= len(c1_x_arr) else pt_next_idx
            
            if has_c2 and c1_x_arr[pt_next_idx] > tail[0]:
                # 存在拐点,且距离拐点比较接近的时候, 走向拐点
                # 防止走过头
                pt_next = tail
            else:
                # 赋值给后续的一步
                pt_next = (c1_x_arr[pt_next_idx], c1_y_arr[pt_next_idx]) 
            # 后续的偏航角
            next_yaw = math.degrees(math.atan2(pt_next[1], pt_next[0]))
        else:
            # 重置pt_near2org
            self.pt_near2org = (self.RB_X_MIN, 0)
            self.y_offset = 0
        # elif has_c2:
        #     # 只有曲线2没有曲线1
        #     # 只有拟合曲线2存在或者拟合曲线1跟拟合曲线2都不存在视为目标丢失
        #     # 通过转向进行解决
        #     # TODO
        #     pass
        
        if has_c1 and has_c2:
            # 通过叉乘判断旋转的大趋势
            # axb > 0 左转
            # axb < 0 右转
            ax, ay = tail # 向量a
            bx, by = c2_x[-1]-tail[0], c2_y[-1]-tail[1] # 向量b
            cross_ab = ax*by - bx*ay # 计算叉乘的结果
            
        if is_draw and self.PAINTER == 'CV':
            # 使用OpenCV进行图形绘制
            scale = 10 # 图像放大的倍数 1cm对象多少个像素点
            # 创建一个空白地图
            canvas = np.ones((60*scale, 80*scale, 3), dtype=np.uint8) * 255
            # 绘制坐标系
            x0, y0 = self.rb2pixel(0, 0)
            x1, y1 = self.rb2pixel(4, 0)
            x2, y2 = self.rb2pixel(0, 4)
            # 绘制x轴
            canvas = cv2.line(canvas, (x0, y0), (x1, y1), thickness=6, color=(0, 0, 255))
            # 绘制y轴
            canvas = cv2.line(canvas, (x0, y0), (x2, y2), thickness=6, color=(0, 255, 0))
            # 绘制透视逆变换的点
            px, py = self.rb2pixel(rb_x, rb_y)
            for idx in range(len(px)):
                # 绘制采样点(灰色)
                # canvas[py[idx], px[idx]] = (125, 125, 125)
                cv2.circle(canvas, (px[idx], py[idx]), radius=3, thickness=-1, color=(125, 125, 125))
            if has_c1:
                # 绘制曲线
                p_c1_x_arr, p_c1_y_arr = self.rb2pixel(c1_x_arr, c1_y_arr)
                for idx in range(1, len(p_c1_x_arr)):
                    x0 = p_c1_x_arr[idx-1]
                    x1 = p_c1_x_arr[idx]
                    y0 = p_c1_y_arr[idx-1]
                    y1 = p_c1_y_arr[idx]
                    cv2.line(canvas, (x0, y0), (x1, y1), thickness=3, color=(255, 0, 0))
                # 绘制最近点跟后继点
                x1, y1 = self.rb2pixel(pt_near2org[0], pt_near2org[1])
                x2, y2 = self.rb2pixel(pt_next[0], pt_next[1])
                cv2.circle(canvas, (x1, y1), radius=8, thickness=-1, color=(0, 125, 125))
                cv2.circle(canvas, (x2, y2), radius=8, thickness=-1, color=(0, 0, 255))
                x0, y0 = self.rb2pixel(0, 0) # 坐标系原点
                cv2.line(canvas, (x0, y0), (x2, y2), color=(125, 125, 0), thickness=6, lineType=1)
                # 绘制偏航角
                cv2.putText(canvas, text='Yaw {:.1f}'.format(next_yaw),\
                        org=(0, 25), fontFace=cv2.FONT_HERSHEY_SIMPLEX, \
                        fontScale=1, thickness=1, lineType=cv2.LINE_AA, color=(0, 0, 255))

            if has_c2:
                # 绘制曲线
                # 加上之后显得很杂乱
                # p_c2_x_arr, p_c2_y_arr = self.rb2pixel(c2_x_arr, c2_y_arr)
                # for idx in range(1, len(p_c1_x_arr)):
                #     x0 = p_c2_x_arr[idx-1]
                #     x1 = p_c2_x_arr[idx]
                #     y0 = p_c2_y_arr[idx-1]
                #     y1 = p_c2_y_arr[idx]
                #     cv2.line(canvas, (x0, y0), (x1, y1), thickness=3, color=(255, 0, 255))
                # 尾巴
                px_t, py_t = self.rb2pixel(tail[0], tail[1])
                cv2.circle(canvas, (px_t, py_t), radius=8, thickness=-1, color=(0, 255, 0))
            
            if has_c1 and has_c2:
                cv2.putText(canvas, text='Cross {:.0f}'.format(cross_ab),\
                        org=(0, 50), fontFace=cv2.FONT_HERSHEY_SIMPLEX, \
                        fontScale=1, thickness=1, lineType=cv2.LINE_AA, color=(0, 0, 255))

        elif is_draw and self.PAINTER == 'MATPLOTLIB':
            fig = self.fig
            axes = self.axes
            # 使用Matplotlib绘图
            # 注: Matplotlib画出来的效果很好看, 但是绘图太过费时 放弃次方法
            # 清除axes画布
            axes.clear()
            # 可视化部分
            # 绘制机器人坐标系
            axes.plot([0, 4], [0, 0], linewidth=4, color='red')
            axes.plot([0, 0], [0, 4], linewidth=4, color='green')
            # 绘制原始数据点在机器人坐标系下的投影
            axes.scatter(rb_x, rb_y, color='orange', alpha=0.1)
            
            if has_c1:
                # 绘制曲线1的滑动窗口
                for wx, wy in c1_sld_win_hist:
                    axes.plot([wx, wx], [wy - self.WIN_W, wy + self.WIN_W], color='orange', alpha=0.1)
                # 绘制曲线1上的采样点
                axes.scatter(c1_x, c1_y, color='orange', alpha=0.6)
                # 绘制曲线1
                axes.plot(c1_x_arr, c1_y_arr, color='blue', linewidth=2, linestyle='--')
                # 书写曲线1的公式
                axes.text(0, 25, r'L1 $y = {:.2f}*x^2 + {:.2f}*x + {:.2f}$'.format(c1_a, c1_b, c1_c))

                # 绘制最近点跟后继点
                axes.scatter([pt_near2org[0], pt_next[0]],[pt_near2org[1], pt_next[1]], color='black', alpha=1)
                # 绘制方向向量
                axes.quiver([0], [0], [pt_next[0]], [pt_next[1]],angles='xy',scale_units='xy', scale=1, color='black')
            
            if has_c2:
                # 绘制曲线2的滑动窗口
                for wx, wy in c2_sld_win_hist:
                    axes.plot([wx-self.WIN_W, wx+self.WIN_W], [wy, wy], color='orange', alpha=0.1)
                # 绘制曲线2的采样点
                axes.scatter(c2_x, c2_y, color='orange', alpha=0.6)
                # 绘制曲线2
                axes.plot(c2_x_arr, c2_y_arr, color='red', linewidth=2, linestyle='--')
                # 拐点
                axes.scatter([tail[0]], [tail[1]], color='green', s=30, alpha=1)
                # 书写曲线2的公式
                axes.text(0, 20, r'L2 $x = {:.2f}*y^2 + {:.2f}*y + {:.2f}$'.format(c2_a, c2_b, c2_c))
                # 偏航角
                axes.text(0, -20, 'Yaw={:.2f}'.format(next_yaw))
            
            # 标签
            axes.set_title('Lane Fit')
            axes.set_xlabel('x')
            axes.set_ylabel('y')
            plt.axis('equal') # 等比例显示
            # 设置坐标轴的范围
            axes.set_xlim((self.RB_X_MIN-6, self.RB_X_MAX))
            axes.set_ylim((self.RB_Y_MIN, self.RB_Y_MAX))            
            # 将Matplotlib的画布转换为cv2里面的BGR格式
            w, h = fig.canvas.get_width_height()
            # print('图像宽度={} 图像高度h={}'.format(w, h))
            # 在Canvas上绘制
            fig.canvas.draw()
            # 构造numpy对象
            canvas_rgb = np.frombuffer(fig.canvas.tostring_rgb(), dtype=np.uint8)
            # 变形 将h放在前面
            canvas_rgb = canvas_rgb.reshape((h, w, 3))
            # RGB图像转换为BGR格式
            canvas = cv2.cvtColor(canvas_rgb, cv2.COLOR_RGB2BGR)
            
        return has_c1, has_c2, next_yaw, cross_ab, canvas

    def next_pt(self):
        '''计算曲线上下一个目标点在机器人坐标系上的坐标'''
        pass

def main(argv):
    # 主程序, 用来预览图像处理的效果
    img_cnt = FLAGS.img_cnt
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
    cv2.namedWindow('img_preprocess',flags=cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO | cv2.WINDOW_GUI_EXPANDED)
    # 带标记的彩图
    cv2.namedWindow('img_raw',flags=cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO | cv2.WINDOW_GUI_EXPANDED)
    # 机器人坐标系下点图+拟合曲线图
    cv2.namedWindow('canvas_robo',flags=cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO | cv2.WINDOW_GUI_EXPANDED)
    
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
        if FLAGS.rm_distortion:
            # 图像去除畸变
            img = cam.remove_distortion(img)
        # 拷贝图像
        canvas_img = np.copy(img)
        # 图像预处理部分
        has_line, bin_line = tk_curve_fit.img_preprocess(img)

        if has_line:
            # 透视逆变换
            rb_x, rb_y = tk_curve_fit.pixel_ipm(bin_line, canvas=canvas_img)
            # rb_x, rb_y = tk_curve_fit.pixel_ipm(bin_line)
            # 曲线拟合
            has_c1, has_c2, next_yaw, cross_ab, canvas_robo = tk_curve_fit.curve_fit(rb_x, rb_y, is_draw=True)
        else:
            # 黑屏
            canvas_robo = np.zeros_like(canvas_robo, dtype=np.uint8)

        # 停止计时计算帧率
        end = time.time()
        fps = int(0.9*fps +  0.1*1/(end-start))
        
        # 画布绘制
        canvas = cv2.cvtColor(bin_line, cv2.COLOR_GRAY2BGR)
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

	# 设置日志等级
	logging.basicConfig(level=logging.INFO)

	# 定义参数
	FLAGS = flags.FLAGS
	flags.DEFINE_string('device', '/dev/video0', '摄像头的设备号')
	flags.DEFINE_integer('img_cnt', 0, '图像计数的起始数值')
	flags.DEFINE_string('img_path', 'data/image_raw', '图像的保存地址')
	flags.DEFINE_boolean('rm_distortion', False, '载入相机标定数据, 去除图像畸变')
	flags.DEFINE_boolean('ipm_calc_online', False, '是否在线计算透视逆变换矩阵')
    
    # 运行主程序
	app.run(main)
