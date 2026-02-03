import sys
import serial
import time
import threading
import tkinter as tk
from tkinter import messagebox

print(sys.executable)

# ================= COMANDOS =================
HOME = 0
SUBIR = 1
BAJAR = 2
IZQUIERDA = 3
DERECHA = 4
METER_GARRA = 5
SACAR_GARRA = 6

CARGA_ESTACION = {1: 7, 2: 8, 3: 9}
DESCARGA_ESTACION = {1: 10, 2: 11, 3: 12}

# ================= CONFIG CARTESIANO =================
PASOS_POR_MM = 5

ESPACIOS_X = 10
DX_MM = 154
DY_MM = 156

Y_INICIAL_MM = 235     # 600 pasos
X_INICIAL_MM = 15
Y_ESTACION_MM = 50     # 300 pasos

X_ESTACIONES_MM = {
    3: 163,
    2: 165 + 465,
    1: 170 + 465 + 615
}

# ================= SERIAL =================
try:
    puerto = serial.Serial('COM3', 115200, timeout=1)
    time.sleep(2)
except Exception as e:
    print("Error abriendo el puerto:", e)
    puerto = None

# ================= UTILIDADES =================
def mm_a_pasos(mm):
    return int(mm * PASOS_POR_MM)

def log(txt):
    text_log.insert(tk.END, txt + "\n")
    text_log.see(tk.END)

def set_estado(ok):
    if ok:
        lbl_estado.config(bg="green", text="ACK")
    else:
        lbl_estado.config(bg="red", text="WAIT")

def enviar_comando(op, pasos=0):
    mensaje = f"op:{op},pasos:{pasos}\n"
    puerto.write(mensaje.encode())
    log(f"→ {mensaje.strip()}")
    set_estado(False)

    while True:
        if puerto.in_waiting:
            resp = puerto.readline().decode().strip()
            log(f"Arduino → {resp}")
            if resp == "ACK:1":
                set_estado(True)
                break
        time.sleep(0.05)

# ================= MOVIMIENTOS BASE =================
def ir_a_estacion(estacion):
    enviar_comando(HOME)
    enviar_comando(SUBIR, mm_a_pasos(Y_ESTACION_MM))
    enviar_comando(DERECHA, mm_a_pasos(X_ESTACIONES_MM[estacion]))

def ir_a_storage(posicion):
    fila = (posicion - 1) // ESPACIOS_X
    columna = (posicion - 1) % ESPACIOS_X

    # Distancias reales entre niveles (mm)
    ALTURAS_MM = [160, 155, 157.5, 155, 155]

    # acumulado vertical
    y_mm = Y_INICIAL_MM + sum(ALTURAS_MM[:fila])

    # horizontal normal
    x_mm = X_INICIAL_MM + columna * DX_MM

    enviar_comando(HOME)
    enviar_comando(SUBIR, mm_a_pasos(y_mm))
    enviar_comando(DERECHA, mm_a_pasos(x_mm))


# ================= CICLOS =================
def ciclo_carga(posicion, estacion):
    ir_a_estacion(estacion)
    enviar_comando(CARGA_ESTACION[estacion])

    ir_a_storage(posicion)
    enviar_comando(SACAR_GARRA)
    enviar_comando(BAJAR, mm_a_pasos(20))
    enviar_comando(METER_GARRA)

    enviar_comando(HOME)

def ciclo_descarga(posicion, estacion):
    ir_a_storage(posicion)

    enviar_comando(BAJAR, mm_a_pasos(20))
    enviar_comando(SACAR_GARRA)
    enviar_comando(SUBIR, mm_a_pasos(20))
    enviar_comando(METER_GARRA)

    ir_a_estacion(estacion)
    enviar_comando(SUBIR, mm_a_pasos(10))
    enviar_comando(DESCARGA_ESTACION[estacion])

    enviar_comando(HOME)

# ================= FUNCIÓN UNIFICADA =================
def movimiento(posicion, estacion, accion):
    if accion == "carga":
        ciclo_carga(posicion, estacion)
    elif accion == "descarga":
        ciclo_descarga(posicion, estacion)
    else:
        raise ValueError("Acción inválida")

# ================= HMI =================
def ejecutar_movimiento():
    try:
        pos = int(entry_pos.get())
        est = int(entry_est.get())
        acc = accion_var.get()
    except ValueError:
        messagebox.showerror("Error", "Datos inválidos")
        return

    threading.Thread(
        target=movimiento,
        args=(pos, est, acc),
        daemon=True
    ).start()


# ===== NUEVOS BOTONES DIRECTOS =====
def ir_storage_hmi():
    try:
        pos = int(entry_pos.get())
    except ValueError:
        messagebox.showerror("Error", "Posición inválida")
        return

    threading.Thread(
        target=ir_a_storage,
        args=(pos,),
        daemon=True
    ).start()


def ir_estacion_hmi():
    try:
        est = int(entry_est.get())
    except ValueError:
        messagebox.showerror("Error", "Estación inválida")
        return

    threading.Thread(
        target=ir_a_estacion,
        args=(est,),
        daemon=True
    ).start()


def cerrar():
    if puerto:
        puerto.close()
    root.destroy()


root = tk.Tk()
root.title("HMI Storage Cartesiano")
root.geometry("460x400")
root.resizable(False, False)

tk.Label(root, text="Posición (1-50):").place(x=20, y=20)
entry_pos = tk.Entry(root, width=10)
entry_pos.place(x=160, y=20)

tk.Label(root, text="Estación (1-3):").place(x=20, y=60)
entry_est = tk.Entry(root, width=10)
entry_est.place(x=160, y=60)

accion_var = tk.StringVar(value="carga")
tk.Radiobutton(root, text="Carga", variable=accion_var, value="carga").place(x=20, y=100)
tk.Radiobutton(root, text="Descarga", variable=accion_var, value="descarga").place(x=120, y=100)

# Botón ciclo completo
btn = tk.Button(root, text="Ejecutar ciclo", width=20, command=ejecutar_movimiento)
btn.place(x=160, y=130)

# NUEVOS BOTONES DIRECTOS
btn_storage = tk.Button(root, text="Ir a Storage", width=20, command=ir_storage_hmi)
btn_storage.place(x=160, y=165)

btn_estacion = tk.Button(root, text="Ir a Estación", width=20, command=ir_estacion_hmi)
btn_estacion.place(x=160, y=200)

tk.Label(root, text="Estado:").place(x=320, y=20)
lbl_estado = tk.Label(root, text="WAIT", width=8, bg="red", fg="white")
lbl_estado.place(x=320, y=50)

text_log = tk.Text(root, width=54, height=9)
text_log.place(x=20, y=240)

root.protocol("WM_DELETE_WINDOW", cerrar)
root.mainloop()
a