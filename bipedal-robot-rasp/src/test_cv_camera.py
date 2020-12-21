import time
from cv_camera import Camera

start = time.time()

camera = Camera(device='/dev/video1')
# 初始相机
camera.init_camera()
capture = camera.get_video_capture()
# 载入标定数据
camera.load_cam_calib_data()
# 载入透视逆变换矩阵
# 从二进制数据中读取
camera.load_ipm_remap(calc_online=False)

end=time.time()

print('载入标定数据所需时间: {}s'.format(end-start))