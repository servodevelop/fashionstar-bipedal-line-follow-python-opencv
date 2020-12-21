'''
MPU6050 Python SDK (for Raspberry)
Author: 阿凯(Kyle)
Update Time: 2019-09-17
'''
import smbus
import json

class RaspMPU6050:
    # 树莓派I2C设备的地址
    I2C_ADDRESS = 0x68
    I2C_BUS_ID = 1
    # 传感器原始数据寄存器地址位
    # 注: _H 代表高位的意思
    # 加速度计 Accel
    REG_ACCEL_XOUT_H = 0x3B
    REG_ACCEL_YOUT_H = 0x3D
    REG_ACCEL_ZOUT_H = 0x3F
    # 温度 Temp
    REG_TEMP_H = 0x41
    # 陀螺仪
    REG_GYRO_XOUT_H = 0x43
    REG_GYRO_YOUT_H = 0x45
    REG_GYRO_ZOUT_H = 0x47
    # 电源管理
    REG_PWR_MGMT_1 = 0x6B
    # 量程相关
    # 加速度计量程设置：
    # 寄存器地址   写入数据    量程
    # 0x1c          0x00      ±2G
    # 0x1c          0x08      ±4G
    # 0x1c          0x10      ±8G
    # 0x1c          0x18      ±16G
    # 加速度计寄存器设置的地址位
    REG_ACCEL_RANGE = 0x1c
    # 加速度计的取值范围
    # 其中g是重力加速度
    ACCEL_RANGE_2G = 0x00
    ACCEL_RANGE_4G = 0x08
    ACCEL_RANGE_8G = 0x10
    ACCEL_RANGE_16G = 0x18
    # 加速度计读数的敏感度缩放因子
    # 转换后的单位 m/s^2
    # 2*9.8/2^15
    ACCEL_SCALE_2G = 0.00059814453125
    ACCEL_SCALE_4G = 0.0011962890625
    ACCEL_SCALE_8G = 0.002392578125
    ACCEL_SCALE_16G = 0.00478515625
    # 陀螺仪量程设置：
    # 寄存器地址   写入数据    量程
    # 0x1b          0x00      ±250°/s
    # 0x1b          0x08      ±500°/s
    # 0x1b          0x10      ±1000°/s
    # 0x1b          0x18      ±2000°/s
    # 陀螺仪寄存器设置的地址位
    REG_GYRO_RANGE = 0x1b
    # 陀螺仪的量程
    # 单位是 dps: degree per second  度/s
    GYRO_RANGE_250_DPS = 0x00
    GYRO_RANGE_500_DPS = 0x08
    GYRO_RANGE_1000_DPS = 0x10
    GYRO_RANGE_2000_DPS = 0X18
    # 陀螺仪敏感度缩放因子
    # 转换后的单位 rad/s 弧度/s
    # ((250*math.pi)/180)/2**15
    GYRO_SCALE_250DEG = 0.0001331580545039619
    GYRO_SCALE_500DEG = 0.0002663161090079238
    GYRO_SCALE_1000DEG = 0.0005326322180158476
    GYRO_SCALE_2000DEG = 0.0010652644360316951
    
    def __init__(self, accel_scale=None, accel_bias=None, gyro_scale=None, gyro_bias=None):
        self.i2c_address = self.I2C_ADDRESS 
        # 初始化
        self.i2c_bus = smbus.SMBus(self.I2C_BUS_ID)
        # 唤醒MPU6050
        self.wake_up()
        # 设置加速度计的取值范围 [-4g, 4g]
        self.set_accel_range()
        # 设置陀螺仪的取值范围 [-500, 500]
        self.set_gyro_range()

        # 加速度计标定参数
        # 设置加速计的尺度因子
        if accel_scale is not None:
            self.accel_scale = accel_scale # 尺度因子
        else:
            self.accel_scale = (self.ACCEL_RANGE_4G, self.ACCEL_RANGE_4G, self.ACCEL_RANGE_4G)
        # 设置加速度计的偏移量
        if accel_bias is not None:
            self.accel_bias = accel_bias
        else:
            self.accel_bias = (0, 0, 0)

        # 陀螺仪标定参数
        # 设置陀螺仪的尺度因子
        if gyro_scale is not None:
            self.gyro_scale = gyro_scale # 尺度因子
        else:
            self.gyro_scale = (self.GYRO_SCALE_500DEG,self.GYRO_SCALE_500DEG, self.GYRO_SCALE_500DEG)
        if gyro_bias is not None:
            self.gyro_bias = gyro_bias # 偏移量
        else:
            self.gyro_bias = (0, 0, 0)
            
    def load_imu_calib_data(self, data_path='config/imu_calibration.json'):
        '''载入标定数据'''
        with open(data_path, 'r') as f:
            data = json.loads(f.read()) 
            self.accel_scale =  float(data['ax_scale']), \
                                float(data['ay_scale']), \
                                float(data['az_scale'])
            self.accel_bias =   float(data['ax_bias']), \
                                float(data['ay_bias']), \
                                float(data['az_bias'])
            if 'gx_sacle' in data:
                self.gyro_scale = float(data['gx_scale']), \
                                float(data['gy_scale']), \
                                float(data['gz_scale'])
                self.gyro_bias = float(data['gx_bias']), \
                                float(data['gy_bias']), \
                                float(data['gz_bias'])
                                
    def save_imu_calib_data(self, data_path='config/imu_calibration.json'):
        '''保存标定数据'''
        data = {}
        data['ax_scale'], data['ay_scale'], data['az_scale'] = self.accel_scale
        data['ax_bias'], data['ay_bias'], data['az_bias'] = self.accel_bias
        data['gx_scale'], data['gy_scale'], data['gz_scale'] = self.gyro_scale
        data['gx_bias'], data['gy_bias'], data['gz_bias'] = self.gyro_bias
        
        with open(data_path, 'w') as f:
            f.write(json.dumps(data))
        
         
    def write_byte(self, reg, value):
        '''写入数据'''
        self.i2c_bus.write_byte_data(self.i2c_address, reg, value)

    def read_byte(self, reg):
        '''读取数值'''
        return self.i2c_bus.read_byte_data(self.i2c_address, reg)
    
    def read_value(self, reg):
        '''读取连续的两个字节, 组成一个数值'''
        # 设置高位
        high = self.read_byte(reg)
        # 数值低位
        low = self.read_byte(reg+1)
        value = (high << 8) + low

        if (value >= 0x8000):
            return -((65535 - value) + 1)
        else:
            return value

    def wake_up(self):
        '''唤醒MPU6050'''
        self.write_byte(self.REG_PWR_MGMT_1, 0x00)
    
    def set_accel_range(self):
        '''设置加速度计的量程'''
        self.write_byte(self.REG_ACCEL_RANGE, self.ACCEL_RANGE_4G)

    def set_gyro_range(self):
        '''设置陀螺仪的范围'''
        self.write_byte(self.REG_GYRO_RANGE, self.GYRO_RANGE_500_DPS)
    
    def get_accel_raw(self):
        '''读取加速度的原始数据'''
        ax = self.read_value(self.REG_ACCEL_XOUT_H) 
        ay = self.read_value(self.REG_ACCEL_YOUT_H)
        az = self.read_value(self.REG_ACCEL_ZOUT_H)
        return [ax, ay, az]

    def get_gyro_raw(self):
        '''获取陀螺仪的原始数据'''
        gx = self.read_value(self.REG_GYRO_XOUT_H)
        gy = self.read_value(self.REG_GYRO_YOUT_H)
        gz = self.read_value(self.REG_GYRO_ZOUT_H)
        return [gx, gy, gz]
    
    def get_accel_real(self, accel_raw=None):
        '''获取真实的加速度'''
        if accel_raw is None:
            # 读取原始数据
            accel_raw = self.get_accel_raw()
        return [(self.accel_scale[i]*accel_raw[i] - self.accel_bias[i]) for i in range(3)]
    
    def get_gyro_real(self, gyro_raw=None):
        '''获取陀螺仪的真实数据'''
        if gyro_raw is None:
            gyro_raw = self.get_gyro_raw()
        return [(self.gyro_scale[i]*gyro_raw[i] - self.gyro_bias[i]) for i in range(3)]
    
    def stat_accel_value(self, n_repeat=1000):
        '''获得加速度的统计数据'''
        accel_raw_sum = [0, 0, 0]
        for i in range(n_repeat):
            accel_raw = self.get_accel_raw()
            accel_raw_sum[0] += accel_raw[0]
            accel_raw_sum[1] += accel_raw[1]
            accel_raw_sum[2] += accel_raw[2]
            
        return [value/n_repeat for value in  accel_raw_sum]
        
    def update_gyro_bias(self, n_repeat=5000):
        
        gyro_raw_sum = [0, 0, 0]
        
        for i in range(n_repeat):
            gyro_raw = self.get_gyro_raw()
            gyro_raw_sum[0] += gyro_raw[0]
            gyro_raw_sum[1] += gyro_raw[1]
            gyro_raw_sum[2] += gyro_raw[2]
            
        self.gyro_bias = [self.gyro_scale[i]*(gyro_raw_sum[i]/n_repeat) \
            for i in range(3)]
        

        
        
