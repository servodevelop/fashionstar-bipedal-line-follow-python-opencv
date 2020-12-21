'''
补光灯开关控制
'''
from gpiozero import LED
from time import sleep

import logging
import sys
from absl import app
from absl import flags
from config import LAMP_GPIO


def main(argv):
    # 创建补光灯
    lamp = LED(LAMP_GPIO)
    if FLAGS.status:
        # 打开补光灯
        lamp.on()
        while True:
            sleep(10)
    else:
        # 关闭补光灯
        lamp.off()
    
    

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    # 定义参数
    FLAGS = flags.FLAGS
    flags.DEFINE_boolean('status', True, '补光灯的状态, 补光灯是否打开')
    # 运行主程序
    app.run(main)
