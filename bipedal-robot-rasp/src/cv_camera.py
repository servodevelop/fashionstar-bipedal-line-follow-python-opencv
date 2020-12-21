'''摄像头 Camera
功能列表
1. 相机拍摄画面预览
1. 图像采集并保存在特定的路径
2. UVC相机参数的可视化调参

备注:
1. 不同摄像头型号的可设置的参数及取值范围各不相同.
   当前的参数设置仅对机型KS2A418适用
'''
import time
import cv2
import numpy as np
import pickle
import subprocess
import math
from config import *

class Camera:
	'''Camera全局曝光全局快门UVC免驱摄像头'''	
	# 设置图像分辨率
	IMG_WIDTH = CAM_IMG_WIDTH # 图像宽度
	IMG_HEIGHT = CAM_IMG_HEIGHT # 图像高度
	BRIGHNESS = CAM_BRIGHNESS # 图像亮度 取值 [-64, 64]
	CONTRUST = CAM_CONTRUST # 对比度
	HUE = CAM_HUE # 相机色调
	SATURATION = CAM_SATURATION # 图像饱和度
	SHARPNESS = CAM_SHARPNESS # 图像清晰度锐度
	GAMMA = CAM_GAMMA
	AWB = CAM_AWB # 自动白平衡
	WHITE_BALANCE_TEMPRATURE = CAM_WHITE_BALANCE_TEMPRATURE
	EXPOSURE_AUTO = CAM_EXPOSURE_AUTO #　是否自动曝光
	EXPOSURE_ABSOLUTE = CAM_EXPOSURE_ABSOLUTE # 相对曝光
	FPS = CAM_FPS # 帧率 (实际上达不到)
	IS_DEBUG = False
	# 相机摆放位置相关的参数
	# 单位cm
	h = CAM_H 
	# 相机光心与水平面的夹角 (俯仰角) 单位弧度
	theta = np.radians(CAM_PITCH)
	def __init__(self, device):
		self.device = device
	
	def init_camera(self):
		# 设置分辨率
		subprocess.call("v4l2-ctl -d {} --set-fmt-video=width={},height={},pixelformat=MJPG".format(self.device,self.IMG_WIDTH,self.IMG_HEIGHT), shell=True)
		# 设置帧率
		subprocess.call("v4l2-ctl -d {} -p {}".format(self.device, self.FPS), shell=True)
		# 打开自动白平衡
		subprocess.call("v4l2-ctl -d {} --set-ctrl white_balance_temperature_auto={}".format(self.device, self.AWB), shell=True)
		if not self.AWB:
			subprocess.call("v4l2-ctl -d {} --set-ctrl white_balance_temperature={}".format(self.device, self.WHITE_BALANCE_TEMPRATURE), shell=True)
		# 设置亮度
		subprocess.call("v4l2-ctl -d {} --set-ctrl brightness={}".format(self.device, self.BRIGHNESS), shell=True)
		# 设置饱和度
		subprocess.call("v4l2-ctl -d {} --set-ctrl saturation={}".format(self.device, self.SATURATION), shell=True)
		# 设置锐度(图像清晰度)
		subprocess.call("v4l2-ctl -d {} --set-ctrl sharpness={}".format(self.device, self.SHARPNESS), shell=True)
		# 设置色调
		subprocess.call("v4l2-ctl -d {} --set-ctrl hue={}".format(self.device, self.HUE), shell=True)
		# 设置对比度
		subprocess.call("v4l2-ctl -d {} --set-ctrl contrast={}".format(self.device, self.CONTRUST), shell=True)
		# 设置Gamma
		subprocess.call("v4l2-ctl -d {} --set-ctrl gamma={}".format(self.device, self.GAMMA), shell=True)

		if not self.EXPOSURE_AUTO:
			subprocess.call("v4l2-ctl -d {} --set-ctrl exposure_auto=1".format(self.device), shell=True)
			# 设置绝对曝光时间
			# 取值范围1 - 8188
			subprocess.call("v4l2-ctl -d {} --set-ctrl exposure_absolute={}".format(self.device, self.EXPOSURE_ABSOLUTE), shell=True)
		else:
			# 自动曝光
			subprocess.call("v4l2-ctl -d {} --set-ctrl exposure_auto=3".format(self.device), shell=True)
		
		# time.sleep(2)
		if self.IS_DEBUG:
			# 打印配置结果
			subprocess.call("v4l2-ctl -d {} --all".format(self.device), shell=True)

	def get_video_capture(self):
		'''生成Capture对象'''
		capture = None
		try:
			capture = cv2.VideoCapture(int(self.device[-1]), cv2.CAP_V4L2)
		except TypeError as e:
			capture = cv2.VideoCapture(int(self.device[-1]))
			# capture = cv2.VideoCapture(0)
			
		# capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.IMG_HEIGHT) #设置图像高度
		# capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.IMG_WIDTH) #设置图像宽度
		capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G')) # 设置编码方式	
		# 缓冲区设置为1结果就是帧率只有 15fps
		# 缓冲区设置为2之后帧率提升到40FPS
		capture.set(cv2.CAP_PROP_BUFFERSIZE, 2) #设置视频缓冲区为1
		return capture
	
	def load_cam_calib_data(self, file_path='config/camera_info.bin'):
		'''载入相机标定数据'''
		# 读取标定参数
		with open(file_path, 'rb') as f:
			camera_info = pickle.load(f)
			# 获取摄像头内参
			self.intrinsic = camera_info['intrinsic']
			# 获取摄像头的畸变系数
			self.distortion = camera_info['distortion']
			# x轴的映射
			self.remap_x = camera_info['remap_x']
			# y轴映射
			self.remap_y = camera_info['remap_y']
			# 根据相机标定参数
			# 提取图像中心(cx, cy)与焦距f(单位：像素)
			self.f = (self.intrinsic[0, 0] + self.intrinsic[1, 1])/2
			# 图像中心的坐标
			self.cx = self.intrinsic[0, 2]
			self.cy = self.intrinsic[1, 2]
			# 生成视场角等相关参数
			self.alpha1 = np.arctan(self.cy/self.f)
			self.alpha2 = np.arctan((self.IMG_HEIGHT-self.cy)/self.f)
			self.beta1 = np.arctan(self.cx/self.f)
			self.beta2 = np.arctan((self.IMG_WIDTH-self.cx)/self.f)
	

	def load_ipm_remap(self, calc_online=True, file_path='config/ipm_remap.bin'):
		'''载入IPM映射矩阵'''
		if calc_online:
			print('计算IPM映射矩阵, 并存储在 {}'.format(file_path))
			# 构造透视逆变换矩阵
			self.ipm_remap_x = np.zeros((self.IMG_HEIGHT, self.IMG_WIDTH))
			self.ipm_remap_y = np.zeros((self.IMG_HEIGHT, self.IMG_WIDTH))
			# 修改每一个元素里面的值
			for px in range(self.IMG_WIDTH):
				for py in range(self.IMG_HEIGHT):
					self.ipm_remap_x[py][px],self.ipm_remap_y[py][px] = self.inverse_projection_mapping(px, py)
			# 保存数据
			ipm_remap_data = {}
			ipm_remap_data['ipm_remap_x'] = self.ipm_remap_x
			ipm_remap_data['ipm_remap_y'] = self.ipm_remap_y

			with open(file_path, 'wb') as f:
				f.write(pickle.dumps(ipm_remap_data))
			print('更新完成')
		else:
			# 从二进制文件中载入
			with open(file_path, 'rb') as f:
				ipm_remap_data = pickle.load(f)
				self.ipm_remap_x = ipm_remap_data['ipm_remap_x']
				self.ipm_remap_y = ipm_remap_data['ipm_remap_y']
		
	def remove_distortion(self, image):
		'''图像去除畸变'''
		return cv2.remap(image, self.remap_x, self.remap_y, cv2.INTER_LINEAR)
	
	def inverse_projection_mapping(self, px, py):
		'''逆向透视映射
		px, py 可以是单个数值, 也可以是列向量
		支持批量映射
		'''
		up = -1 * (py - self.cy)
		vp = px - self.cx
		angle_puOg = np.arctan(up/self.f)
		tan_puOp =  vp/self.f * np.cos(angle_puOg)
		Xp = self.h / np.tan(self.theta - angle_puOg)
		# 注意: 这里需要乘上一个负号
		Yp = -1*np.sqrt(self.h**2 + Xp**2) * tan_puOp
		return Xp, Yp

	def inverse_projection_mapping2(self, px, py):
		'''透视逆变换, 直接从矩阵里面读取'''
		return self.ipm_remap_x[py][px], self.ipm_remap_y[py][px]

	
def update_camera_param(camera, win_name='image_win'):
	'''更新摄像头参数'''
	# 获取更新前的数值
	camera.HUE = cv2.getTrackbarPos('HUE', win_name)
	camera.SATURATION = cv2.getTrackbarPos('SATURATION', win_name)
	camera.CONTRUST = cv2.getTrackbarPos('CONTRUST', win_name)
	camera.SHARPNESS = cv2.getTrackbarPos('SHARPNESS', win_name)
	# 相机重新初始化
	camera.init_camera()
	
	log_info = '\n==========更新之后的相机参数============\n'
	log_info += '色调(HUE): {}\n'.format(camera.HUE)
	log_info += '饱和度(SATURATION): {}\n'.format(camera.SATURATION)
	log_info += '对比度(CONTRUST): {}\n'.format(camera.CONTRUST)
	log_info += '锐度(SHARPNESS): {}\n'.format(camera.SHARPNESS)
	log_info += '\n\n'

	logging.info(log_info)

def main(argv):
	'''调整相机参数, 预览图像'''
	img_cnt = FLAGS.img_cnt
	# 创建相机对象
	camera = Camera(FLAGS.device)
	# 初始相机
	camera.init_camera()
	capture = camera.get_video_capture()
	
	if FLAGS.rm_distortion:
		# 载入标定数据
		camera.load_cam_calib_data()
	# 创建一个名字叫做 “image_win” 的窗口
	win_name = 'image_win'
	cv2.namedWindow(win_name,flags=cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO | cv2.WINDOW_GUI_EXPANDED)
	# 创建滑动条
	is_trackbar_update = False # 滑动条是否发生变化
	# 色调
	cv2.createTrackbar('HUE', win_name, -2000, 2000,lambda x: update_camera_param(camera))
	cv2.setTrackbarPos('HUE', win_name, Camera.HUE)
	# 饱和度
	cv2.createTrackbar('SATURATION', win_name, 0, 100,lambda x: update_camera_param(camera))
	cv2.setTrackbarPos('SATURATION', win_name, Camera.SATURATION)
	# 对比度
	cv2.createTrackbar('CONTRUST', win_name, 0, 95,lambda x: update_camera_param(camera))
	cv2.setTrackbarPos('CONTRUST', win_name, Camera.CONTRUST)
	# 锐度
	cv2.createTrackbar('SHARPNESS', win_name, 1, 100,lambda x: update_camera_param(camera))
	cv2.setTrackbarPos('SHARPNESS', win_name, Camera.SHARPNESS)
	
	fps = 40 # 设定一个初始值
	while True:
		start = time.time()
		ret, image = capture.read()
		end = time.time()
		fps = int(0.9*fps +  0.1*1/(end-start))
		
		if not ret:
			logging.error('图像获取失败')
			break
		if FLAGS.rm_distortion:
			# 图像去除畸变
			image = camera.remove_distortion(image)
		# 创建画布
		canvas = np.copy(image)
		# 在画布上添加帧率的信息
		cv2.putText(canvas, text='FPS: {}'.format(fps),\
			 	org=(50, 50), fontFace=cv2.FONT_HERSHEY_SIMPLEX, \
				fontScale=1, thickness=2, lineType=cv2.LINE_AA, color=(0, 0, 255))
		# 添加帮助信息
		cv2.putText(canvas, text='S:Save Image',\
			 	org=(50, camera.IMG_HEIGHT-100), fontFace=cv2.FONT_HERSHEY_SIMPLEX, \
				fontScale=1, thickness=2, lineType=cv2.LINE_AA, color=(0, 0, 255))
		cv2.putText(canvas, text='Q: Quit',\
			 	org=(50, camera.IMG_HEIGHT-50), fontFace=cv2.FONT_HERSHEY_SIMPLEX, \
				fontScale=1, thickness=2, lineType=cv2.LINE_AA, color=(0, 0, 255))

		# 更新窗口“image_win”中的图片
		cv2.imshow('image_win', canvas)
		key = cv2.waitKey(1)

		if key == ord('q'):
			# 如果按键为q 代表quit 退出程序
			break
		elif key == ord('s'):
			# s键代表保存数据
			cv2.imwrite('{}/{}.png'.format(FLAGS.img_path, img_cnt), image)
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
	flags.DEFINE_string('device', CAM_PORT_NAME, '摄像头的设备号')
	flags.DEFINE_integer('img_cnt', 0, '图像计数的起始数值')
	flags.DEFINE_string('img_path', 'data/image_raw', '图像的保存地址')
	flags.DEFINE_boolean('rm_distortion', False, '载入相机标定数据, 去除图像畸变')
	
	# 运行主程序
	app.run(main)
	
