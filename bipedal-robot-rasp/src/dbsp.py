'''
PyDBSP：Fashion Star DBSP舵机开发板的Python SDK
'''
import serial
import struct
import time
import threading

class DBSPUtil:
    '''DBSP通用工具类'''
    @staticmethod
    def print_bytes_as_hex(bytes_data):
        '''格式化输出Bytes类型数据'''
        print(''.join(['0x%02x ' % b for b in bytes_data]))
    @staticmethod
    def servo_id2stream_order(servo_id):
        '''舵机ID转换为(Sream, Order)'''
        stream = servo_id >> 4
        order = 0x41 & 0x0F
        return (stream, order)
    @staticmethod
    def stream_order2servo_id(stream, order):
        '''舵机编号(Stream, Order)转换为ID'''
        return stream << 4 | order

class Packet:
    '''数据包'''
    HEADER_LEN = 4 # 帧头校验数据的字节长度
    HEADER = b'\x13\x4c\x05\x1d' # 帧头校验数据
    CODE_LEN = 2 # 功能编号长度
    SIZE_LEN = 2 # 字节长度
    CHECKSUM_LEN = 1 # 校验和长度

    @classmethod
    def calc_checksum(cls, code, param_bytes=b''):
        '''计算校验和'''
        return sum(cls.HEADER + struct.pack('<HH', code, len(param_bytes)) + param_bytes) %256

    @classmethod
    def verify(cls, packet_bytes):
        '''检验数据是否合法'''
        # 帧头检验
        if packet_bytes[:4] != cls.HEADER:
            return False
        code, size = struct.unpack('<HH', packet_bytes[4:8])
        
        # 长度校验
        if len(packet_bytes[8:-1]) != size:
            return False

        # 校验和检验
        param_bytes = packet_bytes[8:-1]
        checksum = packet_bytes[-1]
        if checksum != cls.calc_checksum(code , param_bytes):
            return False

        # 数据检验合格
        return True

    @classmethod
    def pack(cls, code, param_bytes=b''):
        '''数据打包为二进制数据'''
        size = len(param_bytes)
        checksum = cls.calc_checksum(code, param_bytes)
        frame_bytes = cls.HEADER + struct.pack('<HH', code, size) + param_bytes + struct.pack('<B', checksum)
        return frame_bytes
    
    @classmethod
    def unpack(cls, packet_bytes):
        '''二进制数据解包为所需参数'''
        if not cls.verify(packet_bytes):
            # 数据非法
            return None
        code = struct.unpack('<H', packet_bytes[4:6])[0]
        param_bytes = packet_bytes[8:-1]
        return code, param_bytes      

class PacketBuffer:
    '''Packet中转站'''
    def __init__(self, is_debug=False):
        self.is_debug = is_debug
        self.packet_bytes_list = []
        # 清空缓存区域
        self.empty_buffer()
    
    def update(self, next_byte):
        '''将新的字节添加到Packet中转站'''
        # print(next_byte)
        if not self.header_flag:
            # 填充头部字节
            if len(self.header) < Packet.HEADER_LEN:
                # 向Header追加字节
                self.header += next_byte
                if len(self.header) == Packet.HEADER_LEN and self.header == Packet.HEADER:
                    self.header_flag = True
            elif len(self.header) == Packet.HEADER_LEN:
                # 首字节出队列
                self.header = self.header[1:] + next_byte
                # 查看Header是否匹配
                if self.header == Packet.HEADER:
                    self.header_flag = True
        elif not self.code_flag:
            # 填充Code
            if len(self.code) < Packet.CODE_LEN:
                self.code += next_byte
                if len(self.code) == Packet.CODE_LEN:
                    self.code_flag = True
        elif not self.size_flag:
            # 填充参数尺寸
            if len(self.size) < Packet.SIZE_LEN:
                self.size += next_byte
                if len(self.size) == Packet.SIZE_LEN:
                    self.size_flag = True
                    # 更新参数个数
                    self.param_len = struct.unpack('<H', self.size)[0]        
        elif not self.param_bytes_flag:
            # 填充参数
            if len(self.param_bytes) < self.param_len:
                self.param_bytes += next_byte
                if len(self.param_bytes) == self.param_len:
                    self.param_bytes_flag = True
        else:
            # 计算校验和
            # 构建一个完整的Packet
            tmp_packet_bytes = self.header + self.code + self.size + self.param_bytes + next_byte
            ret = Packet.verify(tmp_packet_bytes)
            if ret:
                self.checksum_flag = True
                # 将新的Packet数据添加到中转列表里
                self.packet_bytes_list.append(tmp_packet_bytes)
                if self.is_debug:
                    print('[INFO] receive: {} bytes'.format(len(tmp_packet_bytes)))
            # 重新清空缓冲区
            self.empty_buffer()
        
    def empty_buffer(self):
        # 数据帧是否准备好
        self.param_len = None
        self.header = b''
        self.header_flag = False
        self.code = b''
        self.code_flag = False
        self.size = b''
        self.size_flag = False
        self.param_bytes = b''
        self.param_bytes_flag = False
    
    def has_valid_packet(self):
        '''是否有有效的包'''
        return len(self.packet_bytes_list) > 0
    
    def get_packet(self):
        '''获取对首的Bytes'''
        # TODO 添加Code的优先级队列
        return self.packet_bytes_list.pop(0)

class EventManager(object):
    '''时间管理'''
    # 设置为 200ms更新一次
    # UPDATE_INTERVAL_MS = 200 # ms 
    RESPONSE_CODE_NEGLECT = [30091]
    def __init__(self, is_debug=False):
        self.is_debug = is_debug
        self.uart = None
        # 永久订阅  每个code只能有一个订阅者
        self.permanent_channel = {}
        # 单次有效　按照注册顺序发送
        self.temporary_channel = []
        # 立即相应的队列(查询,设置)
        self.immediate_event_queue = []
        # 耗时的请求队列(延时,运动)
        self.motion_event_queue = []
        # 当前的延时/动作事件
        self.cur_motion = None
        # 接收数据缓冲
        self.response_buffer = PacketBuffer()
        # 时间记录 最近一次更新的时间
        self.last_time = time.time()

    def attach_event(self, event):
        '''添加一个EVENT事件'''
        if event.EVENT_TYPE in ['QUERY', 'SETTING']:
            self.immediate_event_queue.append(event)
        elif event.EVENT_TYPE ==  'MOTION':
            self.motion_event_queue.append(event)
        elif event.EVENT_TYPE == 'SUBSCRIBE':
            if self.is_debug:
                print('[INFO] add a subscribe event')
            self.permanent_channel[event.RESPONSE_CODE] = event
        else:
            print('[ERROR] Unkown Event Type: {}'.format(event.EVENT_TYPE))
    
    def update(self):
        '''检查串口数据看有没有新的消息'''
        # 读取有效的返回数据
        while True:
            candi_byte = self.uart.read(1)
            # print(candi_byte)
            # print(len(candi_byte))
            if len(candi_byte) == 0:
                break
            self.response_buffer.update(candi_byte)
        
        # 读取请求数据, 通知相关的事件
        while self.response_buffer.has_valid_packet():
            # 获取字节数据
            packet_bytes  = self.response_buffer.get_packet()
            # 解析字节数据
            code, param_bytes = Packet.unpack(packet_bytes)
            
            if self.is_debug:
                print('[INFO] response code : {}'.format(code))
                DBSPUtil.print_bytes_as_hex(param_bytes)
            # 通知相关的事件
            self.notify(code, param_bytes)
        
        # 发送请求
        if len(self.immediate_event_queue) > 0:
            event = self.immediate_event_queue.pop(0)
            event.send_request_bytes()
            self.temporary_channel.append(event)

        # 动作更新
        if self.cur_motion is None and len(self.motion_event_queue) > 0:
            # 当前动作执行完毕, 载入下一个动作
            self.cur_motion = self.motion_event_queue.pop(0)
            if self.is_debug:
                print('[INFO] Event Start at  {}'.format(time.time()))
                print('-->' + str(self.cur_motion))
            
            self.cur_motion.send_request_bytes() # 发送指令立即执行
            # 开始计时
            self.cur_motion.begin()
        elif self.cur_motion is not None:
            # 更新当前的运动
            # self.cur_motion.tick(time_pass_ms)
            if self.cur_motion.is_done():
                # 当前的动作执行完毕
                if self.is_debug:
                    print('[INFO] Event Finished at : {}'.format(time.time()))
                    print(self.cur_motion)
                    print('[INFO] prepare to load next motion')
                self.cur_motion = None

    def notify(self, code, param_bytes):
        '''通知主题订阅者'''
        # 忽略部分返回码
        if code in self.RESPONSE_CODE_NEGLECT:
            return

        if code in self.permanent_channel.keys():
            event = self.permanent_channel[code]
            event.process_response_bytes(param_bytes)
            if event.callback is not None:
                event.callback(*event.response_args)
            return True
        else:
            event_idx = -1
            for idx, event in enumerate(self.temporary_channel):
                if event.RESPONSE_CODE is not None and event.RESPONSE_CODE == code:
                    event.process_response_bytes(param_bytes)
                    if event.callback is not None:
                        event.callback(*event.response_args)
                    event_idx = idx
                    break
            
            # 没有找到此主题的订阅者
            if event_idx == -1:
                if self.is_debug:
                    print('[WARRING] unkown response code :{}'.format(code))
                return False
            else:
                # 从临时订阅者的位置删除此订阅者
                self.temporary_channel.pop(event_idx)

class DBSP:
    # 配置参数
    uart = None
    timer = None
    event_manager = None
    @classmethod
    def init(cls, uart, is_debug=False):
        
        cls.uart = uart
    
        cls.event_manager = EventManager()
        cls.event_manager.uart = cls.uart
        # ms 转换为s
        # cls.interval_s  = float(cls.event_manager.UPDATE_INTERVAL_MS)/1000
        # 10ms执行依次
        # cls.timer = threading.Timer(cls.interval_s, cls.update)
        # cls.timer.start()

        if is_debug:
            print('[INFO] init uart')
            print('[INFO] init event manager')

    @classmethod
    def update(cls):
        # 初始化检查
        if cls.uart is None:
            cls.init()
        cls.event_manager.update()
        # 创建一个新的定时器
        # cls.timer = threading.Timer(cls.interval_s, cls.update)
        # cls.timer.start()

    @classmethod
    def add(cls, event):
        cls.event_manager.attach_event(event)

    @classmethod
    def deinit(cls):
        '''销毁定时器资源'''
        # cls.timer.cancel()
        pass

class Event:
    '''事件'''
    EVENT_TYPE = 'UnkownType'
    REQUEST_CODE = None # 请求码
    RESPONSE_CODE = None # 相应码

    def __init__(self, is_debug=False):
        self.is_debug = is_debug # 调试模式
        self.callback = None # 回调函数
        self.request_args = [] # 请求的参数列表
        self.response_args = [] #回传的数据

    def set_request_args(self, *request_args):
        '''设置请求参数'''
        self.request_args = request_args

    def generate_request_bytes(self):
        '''将请求数据转换为二进制数据'''
        pass

    def send_request_bytes(self):
        '''发送请求数据'''
        if self.REQUEST_CODE is not None:
            packet_bytes = self.generate_request_bytes()
            DBSP.uart.write(packet_bytes)

    
    def process_response_bytes(self, param_bytes):
        '''响应回调二进制数据'''
        # 解析二进制数据
        # 赋值response_args
        # 将response_args发送给回调函数
        pass

    def set_callback(self, callback):
        self.callback = callback

class MotionEvent(Event):
    EVENT_TYPE = 'MOTION'
    '''运动类事件'''
    def __init__(self, delay_ms):
        self.delay_ms = delay_ms
        # 整个事件的周期
        self.start = None
        # 当前的时间
        self.cur_time = None
        super().__init__()
    
    def begin(self):
        # 运动开始执行
        self.start = time.time()

    def is_done(self):
        '''判断事件是否执行完毕'''
        if self.start is None:
            self.begin()
        cur_time = time.time()
        time_pass_ms = int((cur_time - self.start) * 1000)
        return time_pass_ms >= self.delay_ms

    def send_request_bytes(self):
        '''发送请求数据'''
        if self.REQUEST_CODE is not None:
            packet_bytes = self.generate_request_bytes()
            DBSP.uart.write(packet_bytes)

class DelayEvent(MotionEvent):
    def __init__(self, delay_ms):
        super().__init__(delay_ms)
    
    def __str__(self):
        return 'Delay Event: delay {}ms'.format(self.delay_ms)

class ActionEvent(MotionEvent):
    REQUEST_CODE = 20060
    
    def __init__(self, action_id, interval):
        self.action_id = action_id
        self.interval = interval # Marco周期认为指定
        delay_ms = interval
        super().__init__(delay_ms)

    def generate_request_bytes(self):
        '''将请求数据转换为二进制数据'''
        param_bytes = struct.pack('<L', self.action_id)
        return Packet.pack(self.REQUEST_CODE, param_bytes=param_bytes)

    def __str__(self):
        return 'Action Event, Action ID={} Interval:{}'.format(self.action_id, self.interval)

class MarcoEvent(MotionEvent):
    REQUEST_CODE = 30090
    def __init__(self, marco_id, interval):
        self.marco_id = marco_id
        self.interval = interval # Marco周期认为指定
        delay_ms = interval
        super().__init__(delay_ms)

    def generate_request_bytes(self):
        '''将请求数据转换为二进制数据'''
        param_bytes = struct.pack('<L', self.marco_id)
        return Packet.pack(self.REQUEST_CODE, param_bytes=param_bytes)

    def __str__(self):
        return 'Marco Event, Marco ID={} Interval:{}'.format(self.marco_id, self.interval)

class ServoAngleControlEvent(MotionEvent):
    '''控制多个舵机的角度'''
    REQUEST_CODE = 20050
    
    def __init__(self, servo_angle_list):
        self.servo_num = len(servo_angle_list)
        self.servo_angle_list = []
        for srv_angle_ctl in servo_angle_list:
            srv_id, angle, interval = srv_angle_ctl
            # 重新修改时间单位1ms -> 10ms
            interval = int(interval/10)
            self.servo_angle_list.append((srv_id, angle, interval))
        
        # 计算得到最长的interval
        self.interval = max(self.servo_angle_list, key=lambda srv_angle: srv_angle[2])[2]
        delay_ms = self.interval

        super().__init__(delay_ms)

    def generate_request_bytes(self):
        '''将请求数据转换为二进制数据'''
        param_bytes = struct.pack('<B', self.servo_num)
        for srv_angle in self.servo_angle_list:
            servo_id, angle, interval = srv_angle
            param_bytes += struct.pack('<BhH', servo_id, angle, interval)

        return Packet.pack(self.REQUEST_CODE, param_bytes=param_bytes)
    
    def __str__(self):
        srv_ctl_str = 'Set Servos Angle (Servo Num: {})\n'.format(self.servo_num) 
        for srv_angle in self.servo_angle_list:
            servo_id, angle, interval = srv_angle
            srv_ctl_str += ' ' * 2 + 'ID: {} Angle: {} Interval: {}\n'.format(servo_id, angle, interval)
        return srv_ctl_str

class QueryEvent(Event):
    '''信息查询类事件'''
    EVENT_TYPE = 'QUERY'
    def __init__(self):
        super().__init__()

class QueryServoList(QueryEvent):
    REQUEST_CODE = 20010
    RESPONSE_CODE = 20011

    def __init__(self):
        super().__init__()

    def generate_request_bytes(self):
        '''将请求数据转换为二进制数据'''
        return Packet.pack(self.REQUEST_CODE)

    def send_request_bytes(self):
        '''发送请求数据'''
        if self.REQUEST_CODE is not None:
            packet_bytes = self.generate_request_bytes()
            # print('发送请求数据')
            # print(packet_bytes)
            DBSP.uart.write(packet_bytes)

    def process_response_bytes(self, param_bytes):
        '''处理返回的数据'''
        # 获取舵机的个数
        servo_num = param_bytes[0]
        # 获取舵机的ID
        servo_id_list = struct.unpack('<'+'B'*servo_num, param_bytes[1:])
        self.response_args = servo_num, servo_id_list

        if self.is_debug:
            print(self)

    def __str__(self):
        
        if len(self.response_args) != 0:
            servo_num, servo_id_list = self.response_args
            response_str = '[INFO] Query Servo ID List '
            response_str += 'Servo Num: {}\n'.format(servo_num)
            response_str += '    Servo List:\n'
            response_str += ''.join(['0x%02x ' % b for b in servo_id_list]) + '\n'
            return response_str
        else:
            return '[Request] Query Servo ID List...'

class ServoInfo:
    SERVO_INFO_BYTE_LEN = 11
    def __init__(self):
        self.servo_id = 0
        self.angle = 0 # 舵机角度
        self.current = 0 # 舵机电流
        self.temperature = 0 # 舵机温度
        self.servo_type = 0 # 舵机类型
        self.is_start = True # 舵机启动/停止
        self.is_hold = True # 舵机锁定

    def load_from_bytes(self, param_bytes):
        '''从字节数据导入'''
        try:
            results = struct.unpack('<BhHHHBB', param_bytes)
            self.servo_id = results[0]
            self.angle = results[1]
            self.current = results[2]
            self.temperature = results[3]
            self.servo_type = results[4]
            self.is_start = bool(results[5])
            self.is_hold = bool(results[6])
            return True
        except:
            print('[ERROR]舵机不存在，请查看舵机是否下线, 或填入了错误的舵机ID')
            return False
            
    def __str__(self):
        srv_info_str = ' ' * 2 + 'Servo {} = {}\n'.format(self.servo_id, '0x%02x' % self.servo_id)
        srv_info_str += ' ' * 4 + 'angle        : {}\n'.format(self.angle)
        srv_info_str += ' ' * 4 + 'current      : {}\n'.format(self.current)
        srv_info_str += ' ' * 4 + 'temperature  : {}\n'.format(self.temperature)
        srv_info_str += ' ' * 4 + 'servo type   : {}\n'.format(self.servo_type)
        srv_info_str += ' ' * 4 + 'is start     : {}\n'.format(self.is_start)
        srv_info_str += ' ' * 4 + 'is hold      : {}\n'.format(self.is_hold)
        return srv_info_str


class QueryServoInfo(QueryEvent):
    '''查询舵机信息'''
    REQUEST_CODE = 20020
    RESPONSE_CODE = 20021

    def __init__(self, servo_id=0xff):
        # servo_id = 0xff 的时候代表查询所有的舵机信息
        self.servo_id = servo_id
        super().__init__()

    def generate_request_bytes(self):
        '''将请求数据转换为二进制数据'''
        param_bytes = struct.pack('<B', self.servo_id)
        return Packet.pack(self.REQUEST_CODE, param_bytes)
    
    def send_request_bytes(self):
        '''发送请求数据'''
        if self.REQUEST_CODE is not None:
            packet_bytes = self.generate_request_bytes()
            DBSP.uart.write(packet_bytes)
    
    def process_response_bytes(self, param_bytes):
        '''处理回传数据'''
        self.servo_num = param_bytes[0]
        self.servo_info_list = []

        param_bytes = param_bytes[1:]
        for srv_idx in range(self.servo_num):
            srv_info_bytes = param_bytes[: ServoInfo.SERVO_INFO_BYTE_LEN]
            srv_info = ServoInfo()
            srv_info.load_from_bytes(srv_info_bytes)
            self.servo_info_list.append(srv_info)

            param_bytes = param_bytes[ServoInfo.SERVO_INFO_BYTE_LEN:]

        self.response_args = self.servo_num, self.servo_info_list

        if self.is_debug:
            print(self)

    def __str__(self):
        srv_info_list_str = '[INFO] Servo Info List (Servo CNT: {})\n'.format(self.servo_num)
        for srv_info in self.servo_info_list:
            srv_info_list_str += str(srv_info)
        return srv_info_list_str

class QueryMarcoList(QueryEvent):
    '''查询Marco列表'''
    REQUEST_CODE = 30050
    RESPONSE_CODE = 30051

    MARCO_INFO_LEN = 36
    MARCO_NUM_TYPE = 'H'
    MARCO_NUM_LEN = 2
    MARCO_ID_TYPE = 'L'
    MARCO_ID_LEN = 4
    MARCO_CAPTION_LEN = 32

    def __init__(self):
        super().__init__()
        
    def generate_request_bytes(self):
        '''将请求数据转换为二进制数据'''
        return Packet.pack(self.REQUEST_CODE)

    def send_request_bytes(self):
        '''发送请求数据'''
        if self.REQUEST_CODE is not None:
            packet_bytes = self.generate_request_bytes()
            DBSP.uart.write(packet_bytes)

    def marco_caption_filter(self, marco_caption):
        '''从字节数据中提取Caption'''
        for end_idx in range(len(marco_caption)-1, 0, -1):
            if marco_caption[end_idx] != 0:
                break
        marco_caption = marco_caption[: end_idx+1]
        new_marco_caption = b''
        # 获取Marco的标题 (两个字节表示一个字母，所以需要删减)
        for cidx in range(0, len(marco_caption), 2):
            new_marco_caption += bytes([marco_caption[cidx]])

        return new_marco_caption

    def process_response_bytes(self, param_bytes):
        '''处理返回的数据'''
        # 获取舵机的个数
        self.marco_num = struct.unpack('<'+self.MARCO_NUM_TYPE, param_bytes[:self.MARCO_NUM_LEN])[0]
        param_bytes = param_bytes[self.MARCO_NUM_LEN:]
        self.marco_list = []
        for marco_idx in range(self.marco_num):
            # 获取MarcoID
            marco_id = struct.unpack('<'+self.MARCO_ID_TYPE, param_bytes[:self.MARCO_ID_LEN])[0]
            marco_caption = param_bytes[self.MARCO_ID_LEN:self.MARCO_INFO_LEN]
            marco_caption = self.marco_caption_filter(marco_caption)
            self.marco_list.append((marco_id, marco_caption))
            param_bytes = param_bytes[self.MARCO_INFO_LEN:]

        self.response_args = self.marco_num, self.marco_list

        if self.is_debug:
            print(self)

    def __str__(self):
        if len(self.response_args) != 0:
            
            response_str = '[INFO] Query Marco List '
            response_str += 'Marco Num: {}\n'.format(self.marco_num)
            response_str += '    Marco List:\n'
            for marco_info in self.marco_list:
                marco_id, marco_caption = marco_info
                response_str += 'MarcoID: {} , MarcoCaption: {}\n'.format(marco_id, marco_caption)
            return response_str
        else:
            return '[Request] Query Marco List...'


class SettingEvent(Event):
    '''设置类事件'''
    EVENT_TYPE = 'SETTING'
    def __init__(self):
        self.is_ok = False
        super().__init__()

class SetTranmissionMode(SettingEvent):
    '''设置协议模式'''
    REQUEST_CODE = 10010
    RESPONSE_CODE = 10011
    
    def __init__(self, trans_mode=1):
        self.trans_mode = trans_mode
        super().__init__()
    
    def generate_request_bytes(self):
        '''将请求数据转换为二进制数据'''
        param_bytes = struct.pack('<B', self.trans_mode)
        return Packet.pack(self.REQUEST_CODE, param_bytes)
    
    def send_request_bytes(self):
        '''发送请求数据'''
        if self.REQUEST_CODE is not None:
            packet_bytes = self.generate_request_bytes()
            DBSP.uart.write(packet_bytes)
            
    def process_response_bytes(self, param_bytes):
        '''处理返回的数据'''
        
        trans_mode = bool(param_bytes[0])
        self.is_ok = trans_mode == self.trans_mode
        self.trans_mode = trans_mode
        self.response_args = [self.is_ok, self.trans_mode]
        
        if self.is_debug:
            print(self)

    def __str__(self):
        return '[INFO] set transmission mode event, mode={}, is ok? {}'.format(self.trans_mode, self.is_ok)

class SetServoParam(SettingEvent):
    '''设置舵机参数'''
    REQUEST_CODE = 20030
    RESPONSE_CODE = 20031
    
    def __init__(self, servo_id=0xff,is_start=True, is_hold=True):
        self.servo_id = servo_id
        self.is_start = is_start
        self.is_hold = is_hold
        super().__init__()
    
    def generate_request_bytes(self):
        '''将请求数据转换为二进制数据'''
        param_bytes = struct.pack('<BBB', self.servo_id, self.is_start, self.is_hold)
        return Packet.pack(self.REQUEST_CODE, param_bytes)
    
    def send_request_bytes(self):
        '''发送请求数据'''
        if self.REQUEST_CODE is not None:
            packet_bytes = self.generate_request_bytes()
            DBSP.uart.write(packet_bytes)
            
    def process_response_bytes(self, param_bytes):
        '''处理返回的数据'''
        
        servo_id, is_start, is_hold = struct.unpack('<BBB', param_bytes)
        self.is_ok = (is_start == self.is_start) and (is_hold == self.is_hold)
        self.response_args = [self.is_ok, servo_id, is_start, is_hold]
        
        if self.is_debug:
            print(self)

    def __str__(self):
        return '[INFO] set servo param, id={}, is_start={}, is_hold, is ok? {}'.format(self.servo_id, self.is_start, self.is_hold, self.is_ok)
       

class SubscribeButtonEvent(SettingEvent):
    '''订阅或取消订阅按钮时间'''
    REQUEST_CODE = 40070
    RESPONSE_CODE = 40071

    def __init__(self, is_subscribe=True):
        self.is_subscribe = is_subscribe
        super().__init__()

    def generate_request_bytes(self):
        '''将请求数据转换为二进制数据'''
        param_bytes = struct.pack('<B', self.is_subscribe)
        return Packet.pack(self.REQUEST_CODE, param_bytes)

    def send_request_bytes(self):
        '''发送请求数据'''
        if self.REQUEST_CODE is not None:
            packet_bytes = self.generate_request_bytes()
            DBSP.uart.write(packet_bytes)

    def process_response_bytes(self, param_bytes):
        '''处理返回的数据'''
        self.is_ok = bool(param_bytes[0])
        self.response_args = [self.is_subscribe, self.is_ok]

        if self.is_debug:
            print(self)

    def __str__(self):
        if self.is_subscribe:
            return '[INFO] subscribe button event {}'.format(self.is_ok)
        else:
            return '[INFO] unsubscribe button event {}'.format(self.is_ok)

class SubscribeEvent(Event):
    EVENT_TYPE = 'SUBSCRIBE'
    def __init__(self):
        super().__init__()

class ButtonEvent(SubscribeEvent):
    '''按钮事件'''
    RESPONSE_CODE = 40081
    BUTTON_PRESS = 1
    BUTTON_LONG_PRESS = 2
    BUTTON_RELEASE = 4

    def __init__(self):
        self.button_id = 0
        self.button_state = 0 
        super().__init__()

    def process_response_bytes(self, param_bytes):
        '''响应回调二进制数据'''
        self.button_id, self.button_state = struct.unpack('<LB', param_bytes)
        self.response_args = [self.button_id, self.button_state]

        if self.is_debug:
            print(self)
    def __str__(self):
        evt_str = '[INFO]Button Event, STATE = '
        if self.button_state == 1:
            evt_str += 'BUTTON_PRESS'
        elif self.button_state == 2:
            evt_str += 'BUTTON_LONG_PRESS'
        elif self.button_state == 4:
            evt_str += 'BUTTON_RELEASE'
        return evt_str

