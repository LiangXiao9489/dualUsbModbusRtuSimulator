# 双 USB-RS485 Modbus RTU 回环模拟器

两个 USB-RS485 模块都接到同一组 A/B 总线上：一个作为主站，一个作为从站；外部设备可以并接在这条总线上进行监听。程序不会在两个串口之间转发数据，而是分别打开两个串口并打印各自看到的 RTU 帧。

## 安装与运行

```powershell
python -m pip install -r requirements.txt
python .\modbus_loopback.py
```

打开后可选择主站/从站 COM 口和公共串口参数；“生成随机点表”会为线圈、离散输入、输入寄存器、保持寄存器生成从站地址点。设置操作间隔和循环次数（0 表示无限循环）后点击“开始”，主站会随机读写这些对象并在日志区显示 Modbus RTU 帧。

默认每 2 秒发送一次 `从站 1 / 功能码 03 / 地址 0 / 数量 4` 请求。从站寄存器初值为 `0, 1, 2, ...`，支持功能码 03、04、06、16，并自动校验 CRC16。常见配置示例：

```powershell
py .\modbus_loopback.py --master-port COM3 --slave-port COM4 --unit-id 1 --function 3 --address 0 --quantity 10 --interval 1 --log-file bus.log
```

## 注意事项

- 两个适配器必须使用相同的波特率、数据位、校验位和停止位；示例中的 `--parity E` 需要按现场设备协议调整，默认是 `N`。
- A/B 极性、终端电阻、信号地和 USB-RS485 模块的自动收发方向必须正确。若完全没有 RX，先交换 A/B 排查。
- 主从两端不应同时启用额外的“本地回显”或软件转发，否则日志可能出现重复帧。
- Windows 下可用设备管理器确认两个 COM 口；程序需要独占打开它们，关闭其他串口调试工具。
