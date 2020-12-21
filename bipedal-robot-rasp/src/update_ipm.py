'''
更新透视逆变换(IPM)矩阵
'''
from cv_camera import Camera
from config import CAM_PORT_NAME

# 创建相机对象
cam = Camera(CAM_PORT_NAME)
# 载入标定数据
cam.load_cam_calib_data()
# 载入透视逆变换矩阵
cam.load_ipm_remap(calc_online=True)