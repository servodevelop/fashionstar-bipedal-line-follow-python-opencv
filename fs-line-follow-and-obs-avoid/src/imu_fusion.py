'''
IMU数据融合节点
进行数据融合, 每隔100ms发布一下当前的姿态与位置
'''
import time
import math
import numpy as np
from imu_mpu6050 import RaspMPU6050

class IMUPose:
    GYRO_KI = 0.0
    GYRO_KP = 0.5

    def __init__(self, imu):
        self.imu = imu
        #　初始化位姿
        self.pose_init()
        # 开始的时间
        self.last_time = time.time()
        
    def is_static(self, accel_m, gyro_m):
        '''判断IMU是否是静止'''
        # 陀螺仪测量数据的模长>0.08就认为当前是静止的
        return np.linalg.norm(gyro_m) < 0.08

    def pose_init(self):
        '''位姿初始化'''
        # 初始化位置
        self.p = np.array([0, 0, 0]).reshape((-1, 1))
        # 初始化速度
        self.v = np.array([0, 0, 0]).reshape((-1, 1))
        # 初始化旋转角(四元数)
        self.q = np.array([1, 0, 0, 0]).reshape((-1, 1))
        # 误差项之和
        self.gyro_err_sum = np.array([0, 0, 0]).reshape(-1, 1)
        # 时间初始化 更新最近一次时间
        self.last_time = time.time()

    def pose_update(self):
        '''更新位姿'''
        # 获取当前的时刻
        cur_time = time.time()
        # 计算时间间隔
        dt = (cur_time - self.last_time)
        self.last_time = cur_time
        
        # 更新测量数据
        # 测量的加速度计读数
        am = np.array(self.imu.get_accel_real()).reshape((-1, 1))
        # 测量得到的陀螺仪读数
        gm = np.array(self.imu.get_gyro_real()).reshape((-1, 1))
        
        if self.is_static(am, gm):
                # 静止时不更新防止漂移
                return
        # 提取数据
        qw, qx, qy, qz = self.q.reshape(-1)
        # 根据四元数预估当前的重力加速度的方向
        apx, apy, apz = 2.0 * np.array([qx*qz - qw*qy, qw*qx + qy*qz, qw*qw + qz*qz - 0.5])
        # 重力加速度归一化向量 am_norm
        # 用这个来预估当前的重力加速度方向
        # 这里也有一个问题, 当线加速度作为主导的时候,
        # 该方向跟加速度方向偏差就比较大了, 所以对加速度有约束,不能过大
        amx, amy, amz = am/np.linalg.norm(am)
        
        # 求误差项
        ae = np.array([amy*apz - amz*apy, amz*apx - amx*apz, amx*apy - amy*apx])
        ae = ae.reshape((-1, 1))
        # 更新误差项积分
        if self.GYRO_KI > 0.0:
            self.gyro_err_sum += self.GYRO_KI * ae * dt
            gm += self.gyro_err_sum
        # 修正陀螺仪数据
        gm += self.GYRO_KP * ae
        # 预先乘上1/2*dt
        gm *= 0.5*dt
        gmx, gmy, gmz = gm.reshape(-1)
        # 更新四元数
        self.q[0][0] += - gmx*qx - gmy*qy - gmz*qz
        self.q[1][0] += gmx*qw + gmz*qy - gmy*qz
        self.q[2][0] += gmy*qw - gmz*qx + gmx*qz
        self.q[3][0] += gmz*qw + gmy*qx - gmx*qy
        # 四元数归一化
        self.q = self.q /  np.linalg.norm(self.q)

