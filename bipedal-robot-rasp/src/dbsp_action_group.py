'''双足机器人动作组'''
import time
import logging
from dbsp import *
from config import *

class ActionGroup(object):
    '''动作组'''
    name = 'NAME' # 运动的名称
    marco_id = 0 # 巨集的ID号
    marco_interval = 0 # 巨集的时间间隔

class StandUp(ActionGroup):
    # 站立
    name = 'STAND_UP'
    marco_id = MARCO_STAND_UP_ID
    marco_interval = MARCO_STAND_UP_INTERVAL

class StandUpPre(ActionGroup):
    # 站立预备
    # 前进前的预备动作
    name = 'STAND_UP_PRE'
    marco_id = MARCO_STAND_UP_PRE_ID
    marco_interval = MARCO_STAND_UP_PRE_INTERVAL

class GoForward(ActionGroup):
    # 前进
    name = 'GO_FORWARD'
    marco_id = MARCO_GO_FORWARD_ID
    marco_interval = MARCO_GO_FORWARD_INTERVAL

class GoLeft(ActionGroup):
    # 前进左偏
    name = 'GO_LEFT'
    marco_id = MARCO_GO_LEFT_ID
    marco_interval = MARCO_GO_LEFT_INTERVAL

class GoRight(ActionGroup):
    # 前进右偏
    name = 'GO_RIGHT'
    marco_id = MARCO_GO_RIGHT_ID
    marco_interval = MARCO_GO_RIGHT_INTERVAL

class ActionGroupManager:
    '''动作管理器'''
    def __init__(self, uart, callback=None):
        self.uart= uart
        # 在等待的时候, 执行的回调函数
        self.callback = callback
        # 上一次执行的Marco
        self.last_marco = None

    def _execute(self, marco):
        '''执行动作组'''
        logging.info('excute marco : {}'.format(marco.name))
        # 生成请求数据
        marco_event = MarcoEvent(marco.marco_id, marco.marco_interval)
        request_info = marco_event.generate_request_bytes()
        # 通过串口发送指令
        self.uart.write(request_info)
        # 阻塞式等待
        interval_s = marco.marco_interval / 1000.0 # 等待的时间
        if self.callback is None:
            time.sleep(interval_s)
        else:
            start = time.time()
            while (time.time() - start) < interval_s:
                # 在等待的时候一直执行着回调函数
                self.callback()
        # 更新上一次的Marco
        self.last_marco = marco

    def execute(self, marco, n_repeat=1):
        # if marco in ['GO_LEFT', 'GO_RIGHT', 'GO_FORWARD'] and not(self.last_marco is None or self.last_marco.name == marco.name):
        #    # 不同的动作组之间需要缓冲动作
        #    self._execute(StandUp())
        #    self._execute(StandUpPre())
        # 重新执行多次
        for rep_i in range(n_repeat):
            self._execute(marco)

    def relax(self):
        '''机器人释放锁力'''
        logging.info('机器人释放锁力')
        event = SetServoParam(is_start=False, is_hold=False)
        self.uart.write(event.generate_request_bytes())

def test_exec_action_group():
    # 创建串口对象
    uart = serial.Serial(port=DBSP_PORT_NAME, \
        baudrate=DBSP_BAUDRATE, parity=serial.PARITY_NONE, \
        stopbits=1, bytesize=8, timeout=0)

    # 动作组管理器
    am = ActionGroupManager(uart)
    # 机器人站立
    am.execute(StandUp())
    # 等待5s
    time.sleep(5)
    # 前进5步
    am.execute(GoForward(), n_repeat=5)
    # 左偏2步
    am.execute(GoLeft(), n_repeat=2)
    # 前进1步
    am.execute(GoForward())
    # 右偏
    am.execute(GoRight())
    # 前进3步
    am.execute(GoForward(), n_repeat=3)

    am.execute(StandUp())
    # 等待3s
    time.sleep(3)
    # 机器人释放锁力
    am.relax()

if __name__ == "__main__":
    # 设置日志等级
    logging.basicConfig(level=logging.INFO)
    # 执行动作组的测试程序
    test_exec_action_group()
    
