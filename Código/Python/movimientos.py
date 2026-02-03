from config import *

ALTURAS_MM = [160, 155, 157.5, 155, 155]


def mm_a_pasos(mm):
    return int(mm * PASOS_POR_MM)


class Movimientos:

    def __init__(self, serial_mgr):
        self.s = serial_mgr

    # ================= BASE =================
    def ir_a_estacion(self, estacion):
        self.s.enviar(HOME)
        self.s.enviar(SUBIR, mm_a_pasos(Y_ESTACION_MM))
        self.s.enviar(DERECHA, mm_a_pasos(X_ESTACIONES_MM[estacion]))

    def ir_a_storage(self, posicion):
        fila = (posicion - 1) // ESPACIOS_X
        columna = (posicion - 1) % ESPACIOS_X

        y_mm = Y_INICIAL_MM + sum(ALTURAS_MM[:fila])
        x_mm = X_INICIAL_MM + columna * DX_MM

        self.s.enviar(HOME)
        self.s.enviar(SUBIR, mm_a_pasos(y_mm))
        self.s.enviar(DERECHA, mm_a_pasos(x_mm))

    # ================= CICLOS =================
    def ciclo_carga(self, pos, est):
        self.ir_a_estacion(est)
        self.s.enviar(CARGA_ESTACION[est])

        self.ir_a_storage(pos)
        self.s.enviar(SACAR_GARRA)
        self.s.enviar(BAJAR, mm_a_pasos(20))
        self.s.enviar(METER_GARRA)

        self.s.enviar(HOME)

    def ciclo_descarga(self, pos, est):
        self.ir_a_storage(pos)

        self.s.enviar(BAJAR, mm_a_pasos(20))
        self.s.enviar(SACAR_GARRA)
        self.s.enviar(SUBIR, mm_a_pasos(20))
        self.s.enviar(METER_GARRA)

        self.ir_a_estacion(est)
        self.s.enviar(SUBIR, mm_a_pasos(10))
        self.s.enviar(DESCARGA_ESTACION[est])

        self.s.enviar(HOME)

    def movimiento(self, pos, est, accion):
        if accion == "carga":
            self.ciclo_carga(pos, est)
        else:
            self.ciclo_descarga(pos, est)