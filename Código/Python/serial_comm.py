import serial
import time

class SerialManager:

    def __init__(self, port="COM3", baud=115200, timeout=1):
        self.ser = serial.Serial(port, baud, timeout=timeout)
        time.sleep(2)
        self.log_callback = None
        self.estado_callback = None

    def set_callbacks(self, log, estado):
        self.log_callback = log
        self.estado_callback = estado

    def log(self, msg):
        if self.log_callback:
            self.log_callback(msg)

    def set_estado(self, ok):
        if self.estado_callback:
            self.estado_callback(ok)

    def enviar(self, op, pasos=0):
        mensaje = f"op:{op},pasos:{pasos}\n"
        self.ser.write(mensaje.encode())

        self.log(f"→ {mensaje.strip()}")
        self.set_estado(False)

        while True:
            if self.ser.in_waiting:
                resp = self.ser.readline().decode().strip()
                self.log(f"Arduino → {resp}")

                if resp == "ACK:1":
                    self.set_estado(True)
                    break

            time.sleep(0.05)

    def close(self):
        self.ser.close()