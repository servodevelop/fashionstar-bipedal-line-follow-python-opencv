# DBSP工程文件格式解析



[TOC]


## 1. 概要
`.svproj`文件本质上是`XML`文件，通过XML格式保存如下信息: 

- Project 工程信息
- Servo 舵机
- Position 位置
- Action 动作
- Marco 指令序列
- Control 控制关系 （XML里面称之为 JoystickTables）

你可以使用文件编辑器直接修改`.svproj`源文件

双足机器人DBSP源文件的保存路径是`src/dbsp/track_man.svproj`



## 2. Project工程文件

Project是最外层的结构，其他部分包含在Project中。

```xml
<?xml version="1.0"?>
<Project ID="1395467470" Version="1" LockScreen="false" IsAngleUnitDegree="true">
	... 工程内容  ...
</Project>
```



## 3. Servo 舵机

**Stream 流** 代表DBSP舵机是接在DBSP开发板的第几个舵机接口上，编号从1-6

**Order 顺序** DBSP舵机是串联的，在一个Stream上的舵机，按照离开发板的距离，直接连在开发板上的舵机编号为1，后续依次递增。

Stream + Order 确定舵机的唯一标识

**Caption 舵机** 的名称，命名方法`#Stream编号-Order顺序`

**Adjust 角度调整**  机器人零点调整的偏移量



**X， Y** 是舵机可视化模型在画布中的坐标，与上位机的显示有关。 **Skin** 应该指的是可视化模型的皮肤颜色

`-1` 均代表默认。



```
<Servos>
    <Servo Stream="1" Order="1" X="-1" Y="-1" Caption="#1-1" Adjust="0" Skin="-1" />
    <Servo Stream="1" Order="2" X="-1" Y="-1" Caption="#1-2" Adjust="0" Skin="-1" />
    <Servo Stream="1" Order="3" X="-1" Y="-1" Caption="#1-3" Adjust="0" Skin="-1" />
    <Servo Stream="1" Order="4" X="-1" Y="-1" Caption="#1-4" Adjust="0" Skin="-1" />
    <Servo Stream="2" Order="1" X="-1" Y="-1" Caption="#2-1" Adjust="0" Skin="-1" />
    <Servo Stream="2" Order="2" X="-1" Y="-1" Caption="#2-2" Adjust="0" Skin="-1" />
    <Servo Stream="2" Order="3" X="-1" Y="-1" Caption="#2-3" Adjust="0" Skin="-1" />
    <Servo Stream="3" Order="1" X="-1" Y="-1" Caption="" Adjust="0" Skin="-1" />
    <Servo Stream="4" Order="1" X="-1" Y="-1" Caption="#4-1" Adjust="0" Skin="-1" />
    <Servo Stream="4" Order="2" X="-1" Y="-1" Caption="#4-2" Adjust="0" Skin="-1" />
    <Servo Stream="4" Order="3" X="-1" Y="-1" Caption="#4-3" Adjust="0" Skin="-1" />
    <Servo Stream="5" Order="1" X="-1" Y="-1" Caption="#5-1" Adjust="0" Skin="-1" />
    <Servo Stream="5" Order="2" X="-1" Y="-1" Caption="#5-2" Adjust="0" Skin="-1" />
    <Servo Stream="6" Order="1" X="-1" Y="-1" Caption="#6-1" Adjust="0" Skin="-1" />
    <Servo Stream="6" Order="2" X="-1" Y="-1" Caption="#6-2" Adjust="0" Skin="-1" />
    <Servo Stream="6" Order="3" X="-1" Y="-1" Caption="#6-3" Adjust="0" Skin="-1" />
    <Servo Stream="6" Order="4" X="-1" Y="-1" Caption="#6-4" Adjust="0" Skin="-1" />
</Servos>
```



##　4. Position 位置

一个位置包含所有舵机的角度。

可以由Position生成`Action`，但不常用。 



## 5. Action动作指令

**Action 动作指令**，是**Command指令**中的一种类型，它包含了各个舵机对应的目标角度，以及花多长时间运动到该目标角度。

每个`Action`都有一个ID号，例如下面的例子Action的ID号就是`494302969`， `Caption` 是`Action`的名字。

```xml
<Actions>
	 <Action ID="494302969" Caption="左转1">
      <Steps>
        <Step Stream="1" Order="1" Degree="-60" Interval="200" />
        <Step Stream="1" Order="2" Degree="-26" Interval="200" />
        <Step Stream="1" Order="3" Degree="-5" Interval="200" />
        <Step Stream="1" Order="4" Degree="-15" Interval="200" />
        <Step Stream="2" Order="1" Degree="-91" Interval="200" />
        <Step Stream="2" Order="2" Degree="-79" Interval="200" />
        <Step Stream="2" Order="3" Degree="-30" Interval="200" />
        <Step Stream="3" Order="1" Degree="4" Interval="200" />
        <Step Stream="4" Order="1" Degree="84" Interval="200" />
        <Step Stream="4" Order="2" Degree="80" Interval="200" />
        <Step Stream="4" Order="3" Degree="-30" Interval="200" />
        <Step Stream="5" Order="1" Degree="40" Interval="200" />
        <Step Stream="5" Order="2" Degree="-45" Interval="200" />
        <Step Stream="6" Order="1" Degree="52" Interval="200" />
        <Step Stream="6" Order="2" Degree="12" Interval="200" />
        <Step Stream="6" Order="3" Degree="6" Interval="200" />
        <Step Stream="6" Order="4" Degree="-10" Interval="200" />
      </Steps>
    </Action>
    ... 其他  Action ...
</Actions>
```



## 6. Marco巨集

**Marco巨集** 由若干个**Command指令**构成，指令按照时间顺序依次执行。

**Command指令**有很多**Type 类型** 

- `Delay` 延时指令

  可以设置不同的延时时间，每个延时时间会创建一个Delay指令，延时多少ms， 它的ID就是多少。

- `Action` 动作指令

- `Marco` 巨集 

  > 没错，Marco也可以由其他的Marco构成，但是只支持单层结构

Type+ID号确定唯一的Command

每个指令都有自己的ID

```xml
<Marcos>
    <Marco ID="1208939356" Caption="左转" Reserved="1">
      <Commands>
        <Command ID="494302969" Type="Action" Ratio="100" Loop="1" />
        <Command ID="50" Type="Delay" Ratio="100" Loop="1" />
        <Command ID="62411324" Type="Action" Ratio="100" Loop="1" />
        <Command ID="50" Type="Delay" Ratio="100" Loop="1" />
        <Command ID="746696029" Type="Action" Ratio="50" Loop="1" />
        <Command ID="300" Type="Delay" Ratio="100" Loop="1" />
      </Commands>
    </Marco>
   	...其他巨集...
</Marcos>
```



##　7. JoystickTable 遥控手柄控制表

**JoystickTable 遥控手柄控制表** 定义了**Joystick 遥控手柄**不同的按键状态与Marco巨集（用Marco的ID号来表示）之间的映射关系。

- 按键按下 `ButtonPress`
- 按键长按`ButtonLongPress`
- 按键释放`ButtonUp`



另外还可以设置按键响应事件是否可以被中断，默认为**interruptible抢占式中断**。

也就是说，如果当前在执行某个动作，按下另外一个按钮，马上中断原来的动作，然后执行新的动作。

**注意 只有在JoystickTable里面编辑了映射关系的Marco才会被保存在DBSP主控板里面**
而且，如果一个按键没有编辑好与之对应的Marco, 在MaixPy订阅了DBSP的按键事件之后, 该按键也不会产生回调函数。　
如果Marco没有出现在JoystickTable里面，它就不会存储在DBSP主板上。当MaixPy查询DBSP的Marco序号列表的时候，该ID也不会出现。

```xml
  <JoystickTables>
    <JoystickTable Caption="PS2 Default-001" ID="1329249999">
      <Buttons>
        <Button Caption="↑" ID="4096" ButtonPress="527894726" ButtonLongPress="527894726" ButtonUp="166367466" Uninterruptible="0" />
        <Button Caption="←" ID="32768" ButtonPress="1208939356" ButtonLongPress="1208939356" ButtonUp="166367466" Uninterruptible="0" />
        <Button Caption="→" ID="8192" ButtonPress="1147399203" ButtonLongPress="1147399203" ButtonUp="166367466" Uninterruptible="0" />
        <Button Caption="↓" ID="16384" ButtonPress="271547521" ButtonLongPress="812612532" ButtonUp="166367466" Uninterruptible="0" />
        <Button Caption="△" ID="1" ButtonPress="0" ButtonLongPress="527894726" ButtonUp="0" Uninterruptible="0" />
        <Button Caption="○" ID="2" ButtonPress="900842961" ButtonLongPress="900842961" ButtonUp="166367466" Uninterruptible="0" />
        <Button Caption="☐" ID="8" ButtonPress="1027294193" ButtonLongPress="1027294193" ButtonUp="166367466" Uninterruptible="0" />
        <Button Caption="✕" ID="4" ButtonPress="0" ButtonLongPress="0" ButtonUp="0" Uninterruptible="0" />
        <Button Caption="L1" ID="16" ButtonPress="0" ButtonLongPress="0" ButtonUp="0" Uninterruptible="0" />
        <Button Caption="L2" ID="64" ButtonPress="0" ButtonLongPress="0" ButtonUp="0" Uninterruptible="0" />
        <Button Caption="L3" ID="1024" ButtonPress="0" ButtonLongPress="0" ButtonUp="0" Uninterruptible="0" />
        <Button Caption="R1" ID="32" ButtonPress="0" ButtonLongPress="0" ButtonUp="0" Uninterruptible="0" />
        <Button Caption="R2" ID="128" ButtonPress="0" ButtonLongPress="0" ButtonUp="0" Uninterruptible="0" />
        <Button Caption="R3" ID="2048" ButtonPress="0" ButtonLongPress="0" ButtonUp="0" Uninterruptible="0" />
      </Buttons>
    </JoystickTable>
  </JoystickTables>
```
