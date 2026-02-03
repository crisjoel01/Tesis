from serial_comm import SerialManager
from movimientos import Movimientos
from hmi_ui import HMI

serial_mgr = SerialManager("COM3", 115200)
mov = Movimientos(serial_mgr)

app = HMI(mov, serial_mgr)
app.run()

