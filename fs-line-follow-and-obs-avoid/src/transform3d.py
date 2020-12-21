import math
from math import cos,sin
import numpy as np
from mpl_toolkits.mplot3d import axes3d
from matplotlib import pyplot as plt

def draw_vector3d(axes, vector, start=np.array([0, 0, 0]), color='r', name=None):
    '''绘制向量3D'''
    # 向量起点
    x, y, z, *_ = start.reshape(1, -1)[0]
    # 向量在各个坐标轴上的投影
    u, v, w, *_ = vector.reshape(1, -1)[0]
    # 绘制向量
    axes.quiver([x], [y], [z], [u], [v], [w],color=color)
    if name is not None:
        axes.text(x+u, y+v, z+w, s=name)


def draw_axes3d(axes, frame, name=''):
    '''绘制3D坐标系'''
    start = frame[:, 3]
    unit_x = frame[:, 0]
    unit_y = frame[:, 1]
    unit_z = frame[: ,2]
    
    draw_vector3d(axes, unit_x, start, color='r', name='X{}'.format(name))
    draw_vector3d(axes, unit_y, start, color='g', name='Y{}'.format(name))
    draw_vector3d(axes, unit_z, start, color='b', name='Z{}'.format(name))


def draw_base_axes3d(axes):
    frame = np.eye(4,4)
    draw_axes3d(axes, frame, name='A')


def D(qx, qy, qz):
    return  np.array([
        [1, 0, 0, qx],
        [0, 1, 0, qy],
        [0, 0, 1, qz],
        [0, 0, 0, 1]])

def RZ(alpha):
    '''绕Z轴旋转的矩阵'''
    return np.array([
        [cos(alpha), -sin(alpha), 0, 0],
        [sin(alpha),  cos(alpha), 0, 0],
        [0,           0,          1, 0],
        [0,           0,          0, 1]])

def RY(beta):
    '''绕Y轴旋转的矩阵'''
    return np.array([
        [cos(beta),  0,  sin(beta), 0],
        [0,          1,  0,         0],
        [-sin(beta), 0,  cos(beta), 0],
        [0,           0,  0,         1]])
    
def RX(gamma):
    '''绕X轴旋转的矩阵'''
    return np.array([
        [1, 0,           0,          0],
        [0, cos(gamma), -sin(gamma), 0],
        [0, sin(gamma),  cos(gamma), 0],
        [0, 0,           0,          1]])

