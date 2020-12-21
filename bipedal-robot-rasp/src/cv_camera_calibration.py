'''相机标定 生成标定参数(相机内参与畸变系数)'''
import cv2
import numpy as np
from matplotlib import pyplot as plt
from glob import glob

class CameraCalibration:

    def __init__(self, corner_row, corner_column, img_folder):
        # 棋盘角点矩阵的 行数
        self.corner_row = corner_row
        # 棋盘角点矩阵的 列数
        self.corner_column = corner_column
        # 角点的数量
        self.corner_num = corner_row * corner_column

        # 存放标定素材的文件夹
        self.img_folder = img_folder
        self.img_dict = {}
        self.img_num = 0

        # 随意读入一张照片获取高度跟宽度
        tmp_img = cv2.imread(glob("%s/*.png"%(self.img_folder))[0])
        self.img_width = tmp_img.shape[1] 
        self.img_height = tmp_img.shape[0]

        #　角点坐标集合
        self.corners = None

        # 真实世界(3D)点集 z轴均设为0
        x, y = np.meshgrid(range(self.corner_row), range(self.corner_column))
        self.world_points = np.hstack((x.reshape(self.corner_num, 1), y.reshape(self.corner_num, 1), np.zeros((self.corner_num, 1)))).astype(np.float32)

        self.intrinsic = None # 内参矩阵
        self.distortion = None # 畸变参数
        self.rotate_vects = None
        self.trans_vects = None

        # ReMap Function 映射函数, 用于去除畸变
        self.remap_x = None
        self.remap_y = None

        self.points2d = []
        self.points3d = []


        self.set_img_dict()
        self.set_points()

        self.newcameramtx = None
        self.roi = None

        self.calibrate()
    def set_img_dict(self):
        # 校验图像是否具备完整的角点
        # 如果是部分就排除
        img_paths = glob("%s/*.png"%(self.img_folder))
        print(img_paths)
        for img_path in img_paths:
            img = cv2.imread(img_path)
            ret,corner = cv2.findChessboardCorners(img, (self.corner_row, self.corner_column))
            
            if ret:
                # 判断是否正确获取 所有角点
                self.img_dict[img_path] = {
                    "corner": corner, # 角点
                    "rotate" : None, # 旋转矩阵
                    "trans" : None  # 平移向量
                }
                self.img_num += 1

            else:
                print("图片缺失完整角点 : {}".format(img_path))
    
    def set_points(self):

        # 设置3D与2D的数组
        for img_path,data  in self.img_dict.items():
            self.points2d.append(data["corner"])
            self.points3d.append(self.world_points)
    
    def calibrate(self):
        # 标定相机
        ret, mtx, dist, revecs, tvecs = cv2.calibrateCamera(self.points3d, self.points2d, (self.img_width, self.img_height), None, None)
        
        if ret:
            self.intrinsic = mtx
            self.distortion = dist
            self.rotate_vects = revecs
            self.trans_vects = tvecs
            
            # 畸变矫正相关
            self.newcameramtx, self.roi=cv2.getOptimalNewCameraMatrix(self.intrinsic, self.distortion, (self.img_width, self.img_height),1,(self.img_width,self.img_height))
            self.remap_x, self.remap_y = cv2.initUndistortRectifyMap(self.intrinsic, self.distortion,None,self.newcameramtx,(self.img_width, self.img_height), 5)
            count = 0
            # 设置3D与2D的数组
            for img_path  in self.img_dict:
                self.img_dict[img_path]["rotate"] = self.rotate_vects[count]
                self.img_dict[img_path]["trans"] = self.trans_vects[count]
                count += 1
        else:
            print("Error during camera calibration")

    def print_parameter(self):
        print("相机内参 intrinsic")
        print(self.intrinsic)

        print("畸变参数 distortion")
        print(self.distortion)


    def dump_camera_info(self):
        try:
            import cPickle as pickle
        except ImportError:
            import pickle

        camera_info = {}

        camera_info['intrinsic'] = self.intrinsic
        camera_info['distortion'] = self.distortion
        camera_info['remap_x'] = self.remap_x
        camera_info['remap_y'] = self.remap_y

        f = open('config/camera_info.bin','wb')
        f.write(pickle.dumps(camera_info))
        f.close()

def main(argv):
    cc = CameraCalibration(FLAGS.row, FLAGS.column, FLAGS.img_path)
    cc.print_parameter()
    cc.dump_camera_info()
    
if __name__ == "__main__":
    from absl import app
    from absl import flags

    # 定义参数
    FLAGS = flags.FLAGS
    flags.DEFINE_string('img_path', 'data/caliboard', '棋盘格图像的保存路径')
    flags.DEFINE_integer('row', 7, '棋盘格的角点行数')
    flags.DEFINE_integer('column', 9, '棋盘格的角点列数')
    # 执行主程序
    app.run(main)

    
