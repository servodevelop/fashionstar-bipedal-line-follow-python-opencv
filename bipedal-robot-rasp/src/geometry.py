'''
存放工具包,旋转的各种表示的相互转换
------------------------------------
Author: 阿凯(Kyle)
Email: kyle.xing@fashionstar.com.hk
Update Time: 2020-08-03
'''
import math
from math import cos, sin
import numpy as np

class Geometry:
	@staticmethod
	def quat2euler(q):
		'''四元数转换为euler角
        Yaw: 偏航角
        Pitch: 俯仰角
        Roll: 横滚角        
		'''
		qw, qx, qy, qz = q.reshape(-1)
		# 绕X轴旋转的角度 Roll
		roll = math.atan2(2*(qw*qx+qy*qz), 1-2*(qx*qx+qy*qy))
    	# 绕Y轴旋转的角度 Pitch
		pitch = math.asin(2*(qw*qy - qx*qz))
		# 绕Z轴旋转的角度 Yaw
		yaw = math.atan2(2*(qx*qy+qw*qz), 1-2*(qy*qy+qz*qz))
		
		return np.array([roll, pitch, yaw]).reshape((-1, 1))
	
	@staticmethod
	def euler2quat(rpy):
		'''euler角转换为四元数'''
		roll, pitch, yaw = rpy.reshape(-1)
		qw = cos(roll/2)*cos(pitch/2)*cos(yaw/2) + sin(roll/2)*sin(pitch/2)*sin(yaw/2)
		qx = sin(roll/2)*cos(pitch/2)*cos(yaw/2) - cos(roll/2)*sin(pitch/2)*sin(yaw/2)
		qy = cos(roll/2)*sin(pitch/2)*cos(yaw/2) + sin(roll/2)*cos(pitch/2)*sin(yaw/2)
		qz = cos(roll/2)*cos(pitch/2)*sin(yaw/2) - sin(roll/2)*sin(pitch/2)*cos(yaw/2)
		return np.array([qw, qx, qy, qz]).reshape((-1, 1))

	@staticmethod
	def quat2rmat(quat):
		'''四元数转换为旋转矩阵'''
		# 对四元数进行归一化操作
		quat = quat/np.linalg.norm(quat)
		qw, qx, qy, qz = quat.reshape(-1)
		r11 = 1 - 2*qy**2 - 2*qz**2
		r12 = 2*qx*qy - 2*qw*qz
		r13 = 2*qx*qz + 2*qw*qy
		r21 = 2*qx*qy + 2*qw*qz
		r22 = 1 - 2*qx**2 - 2*qz**2
		r23 = 2*qy*qz - 2*qw*qx
		r31 = 2*qx*qz - 2*qw*qy
		r32 = 2*qy*qz + 2*qw*qx
		r33 = 1 - 2*qx**2 - 2*qy**2
		return np.array([
			[r11, r12, r13],
			[r21, r22, r23],
			[r31, r32, r33]])
	
	@staticmethod
	def rmat2quat(rmat):
		'''旋转矩阵转换为四元数'''
		r11, r12, r13, r21, r22, r23, r31, r32, r33 = rmat.reshape(-1)
		qw = 1/2*math.sqrt(1 + r11 + r22 + r33)
		qx = (r32-r23)/(4*qw)
		qy = (r13-r31)/(4*qw)
		qz = (r21-r12)/(4*qw)
		return np.array([qw, qx, qy , qz]).reshape((-1, 1))
		
	@staticmethod
	def euler2rmat(rpy):
		'''欧拉角转换为旋转矩阵'''
		roll, pitch, yaw = rpy.reshape(-1)
		r11 = cos(pitch)*cos(yaw)
		r12 = cos(yaw)*sin(roll)*sin(pitch) - cos(roll)*sin(yaw)
		r13 = sin(roll)*sin(yaw) + cos(roll)*cos(yaw)*sin(pitch)
		r21 = cos(pitch)*sin(yaw)
		r22 = cos(roll)*cos(yaw) + sin(roll)*sin(pitch)*sin(yaw)
		r23 = cos(roll)*sin(pitch)*sin(yaw) - sin(roll)*cos(pitch)# cos(yaw)*sin(yaw)
		r31 = -sin(pitch)
		r32 = cos(pitch)*sin(roll)
		r33 = cos(roll)*cos(pitch)
		return np.array([
			[r11, r12, r13],
			[r21, r22, r23],
			[r31, r32, r33]])

	@staticmethod
	def rmat2euler(rmat):
		'''
		旋转矩阵转换为欧拉角
		https://www.cnblogs.com/flyinggod/p/8144100.html
		'''
		r11, r12, r13, r21, r22, r23, r31, r32, r33 = rmat.reshape(-1)
		roll = math.atan2(r32, r33)
		pitch = math.atan2(-r31, math.sqrt(r32**2 + r33**2))
		yaw = math.atan2(r21, r11)
		return np.array([roll, pitch, yaw]).reshape((-1, 1))
	
	@staticmethod
	def vect2quat(vect, ref_vect=None):
		'''从两个向量构造四元数
		参见Eigen里面Quaternion里面的setFromTwoVectors
		'''
		if ref_vect is None:
			# 因为加速度计的测量值是测量的惯性加速度
			# 跟实际的重力加速度相反, 所以z=1
			ref_vect = np.array([0, 0, 1])
		#  四元数描述的是从向量ref_vect到vect的旋转
		ref_vect = ref_vect / np.linalg.norm(ref_vect)
		vect = vect / np.linalg.norm(vect)

		d = ref_vect.T.dot(vect)[0][0]
		if d >= 1:
			# 共线的情况
			return np.array([1, 0, 0, 0]).reshape((-1, 1))
		# TODO 当d <= -1的时候, 需要求奇异值
		# 在我们这个应用场景里面, 暂时不会遇到
		#　向量叉乘得到转轴
		n = np.cross(ref_vect.reshape(-1), vect.reshape(-1))
		# n = n / np.linalg.norm(n)
		nx, ny, nz = n.reshape(-1)
		s = math.sqrt((1+d)*2)
		invs = 1 / s
		qx = nx * invs
		qy = ny * invs
		qz = nz * invs
		qw = 0.5*s

		q = np.array([qw, qx, qy, qz]).reshape((-1, 1))
		# 四元数归一化
		q = q / np.linalg.norm(q)
		return q

	@staticmethod
	def tf_Rt2T(R, t):
		# 变换矩阵的逆变换
		# @R
		# 	旋转矩阵
		# @t
		#	平移向量
		T = np.eye(4)
		T[:3, :3] = R
		T[:3, 3] = t.reshape(-1)
		return T

	@staticmethod
	def tf_T2Rt(T):
		R = T[:3, :3]
		t = T[:3, 3].reshape((-1, 1))
		return R, t

	@staticmethod
	def tf_T_inverse(T):
		# 变换矩阵的逆变换
		return np.linalg.inv(T)

	@staticmethod
	def tf_Rt_inverse(R, t):
		# 变换矩阵的逆变换
		# @R
		# 	旋转矩阵
		# @t
		#	平移向量
		T = Geometry.tf_Rt2T(R, t)
		T_inv = self.tf_T_inverse(T)
		R, t = self.tf_T2Rt(T_inv)
		return R.T, -R.T.dot(t)	
