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

LEER_SENSORES = 13

# ================= CONFIG CARTESIANO =================
PASOS_POR_MM = 5

ESPACIOS_X = 10
DX_MM = 154
DY_MM = 156

Y_INICIAL_MM = 235
X_INICIAL_MM = 15
Y_ESTACION_MM = 45

X_ESTACIONES_MM = {
    3: 163,
    2: 165 + 465,
    1: 170 + 465 + 615
}

ALTURAS_MM = [160, 155, 157.5, 155, 155]

ALGORITMO_ACTUAL = "zonas"

# ================= POSICIÓN ACTUAL DEL CARRO =================
pos_actual_x = 0
pos_actual_y = 0

# ================= ARREGLOS DEL SISTEMA =================
TOTAL_CELDAS = 50

# 0 vacío | 1 ocupado
presencia = [0] * TOTAL_CELDAS

# 0 sin color | 1 rojo | 2 verde | 3 azul
color = [0] * TOTAL_CELDAS

# 0 vacío | 1 rojo | 2 verde | 3 azul | 4 desconocido
estado_logico = [0] * TOTAL_CELDAS


# ================= SERIAL =================
try:
    puerto = serial.Serial('COM4', 115200, timeout=1)
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


# ================= ESTADO LOGICO =================
def actualizar_estado_logico():
    for i in range(TOTAL_CELDAS):

        if presencia[i] == 0 and color[i] == 0:
            estado_logico[i] = 0

        elif presencia[i] == 1 and color[i] in (1, 2, 3):
            estado_logico[i] = color[i]

        else:
            estado_logico[i] = 4

    log("Estado lógico actualizado")


# ================= SERIAL CORE =================
def enviar_comando(op, pasos=0):

    if puerto is None or not puerto.is_open:
        log("ERROR: Puerto serial no disponible")
        return

    mensaje = f"op:{op},pasos:{pasos}\n"
    puerto.write(mensaje.encode())

    log(f"→ {mensaje.strip()}")
    set_estado(False)

    color_detectado = None

    ack_recibido = False
    color_recibido = False

    # ⭐ comandos que DEVUELVEN color
    requiere_color = op in (7, 8, 9)

    while True:

        if puerto.in_waiting:
            resp = puerto.readline().decode().strip()
            log(f"Arduino → {resp}")

            # ---- COLOR ----
            if resp.startswith("C:"):
                color_detectado = int(resp.split(":")[1])
                color_recibido = True

            # ---- ACK ----
            elif resp == "ACK:1":
                ack_recibido = True

                if op == HOME:
                    global pos_actual_x, pos_actual_y
                    pos_actual_x = 0
                    pos_actual_y = 0

        # ⭐ lógica de salida
        if requiere_color:
            if ack_recibido and color_recibido:
                break
        else:
            if ack_recibido:
                break

        time.sleep(0.01)

    set_estado(True)
    return color_detectado




# ================= LECTURA SENSORES =================
def leer_sensores():

    if puerto is None or not puerto.is_open:
        return

    puerto.write(f"op:{LEER_SENSORES},pasos:0\n".encode())

    inicio = time.time()

    while time.time() - inicio < 3:

        if puerto.in_waiting:

            linea = puerto.readline().decode().strip()
            log(f"Arduino → {linea}")

            if linea.startswith("SENSORS:"):

                datos = linea.replace("SENSORS:", "").split(',')

                for i in range(min(len(datos), TOTAL_CELDAS)):
                    presencia[i] = int(datos[i])

                actualizar_estado_logico()
                actualizar_grid()
                log("Sensores OK")
                return

        time.sleep(0.01)

    log("Sensores tardaron pero continuo sin bloquear")




# ================= MOVIMIENTOS BASE =================
def ir_a_estacion(estacion):
    global pos_actual_x, pos_actual_y
    enviar_comando(HOME)
    pos_actual_x = 0
    pos_actual_y = 0

    enviar_comando(SUBIR, mm_a_pasos(Y_ESTACION_MM))
    enviar_comando(DERECHA, mm_a_pasos(X_ESTACIONES_MM[estacion]))
    pos_actual_x = X_ESTACIONES_MM[estacion]
    pos_actual_y = Y_ESTACION_MM

def ir_a_estacion_directo(estacion):
    x = X_ESTACIONES_MM[estacion]
    y = Y_ESTACION_MM
    mover_a(x, y)
    global pos_actual_x, pos_actual_y

    pos_actual_x = x
    pos_actual_y = y

def ir_a_storage(posicion):
    global pos_actual_x, pos_actual_y

    fila = (posicion - 1) // ESPACIOS_X
    columna = (posicion - 1) % ESPACIOS_X

    y_mm = Y_INICIAL_MM + sum(ALTURAS_MM[:fila])
    x_mm = X_INICIAL_MM + columna * DX_MM

    enviar_comando(HOME)
    pos_actual_x = 0
    pos_actual_y = 0

    enviar_comando(SUBIR, mm_a_pasos(y_mm))
    enviar_comando(DERECHA, mm_a_pasos(x_mm))
    pos_actual_x = x_mm
    pos_actual_y = y_mm


def ir_a_storage_directo(posicion):
    fila = (posicion - 1) // ESPACIOS_X
    columna = (posicion - 1) % ESPACIOS_X

    y = Y_INICIAL_MM + sum(ALTURAS_MM[:fila])
    x = X_INICIAL_MM + columna * DX_MM

    mover_a(x, y)
    global pos_actual_x, pos_actual_y

    pos_actual_x = x
    pos_actual_y = y
    
# ================= MOVIMIENTO RELATIVO REAL =================
def mover_a(x_dest_mm, y_dest_mm):
    global pos_actual_x, pos_actual_y

    dx = x_dest_mm - pos_actual_x
    dy = y_dest_mm - pos_actual_y

    if dy > 0:
        enviar_comando(SUBIR, mm_a_pasos(dy))
    elif dy < 0:
        enviar_comando(BAJAR, mm_a_pasos(abs(dy)))

    if dx > 0:
        enviar_comando(DERECHA, mm_a_pasos(dx))
    elif dx < 0:
        enviar_comando(IZQUIERDA, mm_a_pasos(abs(dx)))

    pos_actual_x = x_dest_mm
    pos_actual_y = y_dest_mm
    
def buscar_caja_mas_cercana(color_objetivo, x0, y0):

    mejor_pos = None
    mejor_dist = 1e9

    for i in range(TOTAL_CELDAS):

        # solo cajas válidas del color solicitado
        if estado_logico[i] == color_objetivo:

            fila = i // ESPACIOS_X
            col  = i % ESPACIOS_X

            x_mm = X_INICIAL_MM + col * DX_MM
            y_mm = Y_INICIAL_MM + sum(ALTURAS_MM[:fila])

            dist = abs(x_mm - x0) + abs(y_mm - y0)

            if dist < mejor_dist:
                mejor_dist = dist
                mejor_pos = i + 1

    return mejor_pos



# ================= CICLOS =================
def ciclo_carga(estacion):
    global pos_actual_x, pos_actual_y

    ir_a_estacion_directo(estacion)

    color_detectado = enviar_comando(CARGA_ESTACION[estacion])

    if color_detectado is None:
        log("Color no detectado → zona segura")
        color_detectado = 4

    posicion = elegir_posicion(color_detectado)

    ir_a_storage_directo(posicion)

    enviar_comando(SACAR_GARRA)
    enviar_comando(BAJAR, mm_a_pasos(20))
    enviar_comando(METER_GARRA)
    presencia[posicion-1] = 1
    color[posicion-1] = color_detectado
    actualizar_estado_logico()
    actualizar_grid()
    enviar_comando(HOME)
    pos_actual_x = 0
    pos_actual_y = 0

    leer_sensores()



def ciclo_descarga(estacion, color_solicitado):
    global pos_actual_x, pos_actual_y

    pos = buscar_caja_mas_cercana(color_solicitado, pos_actual_x, pos_actual_y)

    if pos is None:
        log("No hay cajas de ese color")
        return
    
    ir_a_storage_directo(pos)

    enviar_comando(BAJAR, mm_a_pasos(20))
    enviar_comando(SACAR_GARRA)
    enviar_comando(SUBIR, mm_a_pasos(20))
    enviar_comando(METER_GARRA)

    color[pos - 1] = 0
    presencia[pos-1] = 0
    color[pos-1] = 0
    actualizar_estado_logico()
    actualizar_grid()

    ir_a_estacion_directo(estacion)

    enviar_comando(SUBIR, mm_a_pasos(10))
    enviar_comando(DESCARGA_ESTACION[estacion])

    enviar_comando(HOME)
    pos_actual_x = 0
    pos_actual_y = 0
    leer_sensores()

# =============== SELECCION DE ALGORITMO ==============
def elegir_posicion(color_detectado):

    if ALGORITMO_ACTUAL == "zonas":
        return buscar_celda_libre_zona(color_detectado, pos_actual_x, pos_actual_y)

    #elif ALGORITMO_ACTUAL == "producto":
    #    return buscar_por_producto(color_detectado)

    #elif ALGORITMO_ACTUAL == "frecuencia":
    #    return buscar_por_frecuencia(color_detectado)

    else:
        return None


# ================ ALGORITMO POR ZONAS ================

def distancia(a, b):
    ax, ay = divmod(a, ESPACIOS_X)
    bx, by = divmod(b, ESPACIOS_X)
    return abs(ax - bx) + abs(ay - by)

def columna_de_pos(pos): 
    return (pos - 1) % ESPACIOS_X 

def zona_por_columna(pos):
    col = columna_de_pos(pos)
    if 0 <= col <= 2:
        return 1   # rojo
    elif 4 <= col <= 6:
        return 2   # verde
    elif 7 <= col <= 9:
        return 3   # azul
    else:
        return 4   # desconocido (columna 3)


def buscar_celda_libre_zona(color_objetivo, x0, y0):
    if color_objetivo == 0 or color_objetivo is None:
        color_objetivo = 4

        
    mejor_pos = None
    mejor_dist = 1e9

    for i in range(TOTAL_CELDAS):

        if estado_logico[i] == 0 and zona_por_columna(i+1) == color_objetivo:

            fila = i // ESPACIOS_X
            col  = i % ESPACIOS_X

            x_mm = X_INICIAL_MM + col * DX_MM
            y_mm = Y_INICIAL_MM + sum(ALTURAS_MM[:fila])

            dist = abs(x_mm - x0) + abs(y_mm - y0)

            if dist < mejor_dist:
                mejor_dist = dist
                mejor_pos = i + 1

    log(f"Zona {color_objetivo} -> pos elegida {mejor_pos}")
    return mejor_pos




# ================= FUNCIÓN UNIFICADA =================
def movimiento_auto(estacion, accion, color_sel):

    if accion == "carga":
        ciclo_carga(estacion)

    elif accion == "descarga":

        # 🔥 buscar la caja MÁS CERCANA del color elegido
        pos = buscar_caja_mas_cercana(  color_sel,
                                        pos_actual_x,
                                        pos_actual_y)

        if pos:
            ciclo_descarga(estacion, color_sel)

        else:
            log("No hay cajas de ese color")



# ================= HMI =================
def ejecutar_movimiento():
    try:
        est = int(entry_est.get())
        acc = accion_var.get()
    except ValueError:
        messagebox.showerror("Error", "Datos inválidos")
        return

    threading.Thread(target=movimiento_auto, args=(est, acc), daemon=True).start()

def ejecutar_auto(*args):
    try:
        est = int(entry_est.get())
        acc = accion_var.get()
        col = color_var.get()
    except:
        return

    threading.Thread(
        target=movimiento_auto,
        args=(est, acc, col),
        daemon=True
    ).start()


def leer_sensores_hmi():
    threading.Thread(target=leer_sensores, daemon=True).start()


# ================= ESTADO ACK / WAIT =================
def set_estado(txt):
    lbl_estado.config(text=txt)

    if txt == "ACK":
        lbl_estado.config(bg="green")
    else:
        lbl_estado.config(bg="red")


# ================= LOG SERIAL =================
def log(msg):
    text_log.insert(tk.END, msg + "\n")
    text_log.see(tk.END)


# ================= STORAGE GRID =================
FILAS = 5
COLUMNAS = 10

celdas_ui = []


def color_celda(v):
    if v == 0:
        return "gray"     # vacío
    elif v == 1:
        return "red"      # rojo
    elif v == 2:
        return "green"    # verde
    elif v == 3:
        return "blue"     # azul
    elif v == 4:
        return "yellow"   # desconocido
    return "black"



def actualizar_grid():
    for i, valor in enumerate(estado_logico):
        celdas_ui[i].config(bg=color_celda(valor))


def crear_grid(parent):

    for r in range(FILAS):
        for c in range(COLUMNAS):

            lbl = tk.Label(
                parent,
                width=4,
                height=2,
                bg="gray",
                relief="ridge",
                bd=1
            )

            # 🔥 invertir eje Y
            lbl.grid(row=FILAS-1-r, column=c, padx=2, pady=2)

            celdas_ui.append(lbl)





# ================= CERRAR =================
def cerrar():
    if puerto:
        puerto.close()
    root.destroy()


# ====================================================
# ===================== UI NUEVO =====================
# ====================================================

root = tk.Tk()
root.title("Storage Cartesiano HMI")
root.geometry("1080x720")
root.resizable(False, False)


# ====== ZONA SUPERIOR (CONTROLES) ======
frame_top = tk.Frame(root)
frame_top.pack(pady=10)

# ================= FILA 1 → ALGORITMO =================
algoritmo_var = tk.StringVar(value="zonas")

tk.Label(frame_top, text="Algoritmo").grid(row=0, column=0, padx=5)

tk.Radiobutton(frame_top, text="Zonas",
               variable=algoritmo_var, value="zonas").grid(row=0, column=1)

tk.Radiobutton(frame_top, text="Producto",
               variable=algoritmo_var, value="producto").grid(row=0, column=2)

tk.Radiobutton(frame_top, text="Frecuencia",
               variable=algoritmo_var, value="frecuencia").grid(row=0, column=3)


# ================= FILA 2 → ACCIÓN =================
accion_var = tk.StringVar(value="carga")

tk.Label(frame_top, text="Acción").grid(row=1, column=0, padx=5)

tk.Radiobutton(frame_top, text="Carga",
               variable=accion_var, value="carga").grid(row=1, column=1)

tk.Radiobutton(frame_top, text="Descarga",
               variable=accion_var, value="descarga").grid(row=1, column=2)


# ================= FILA 3 → ESTACIÓN =================
tk.Label(frame_top, text="Estación").grid(row=2, column=0)

entry_est = tk.Entry(frame_top, width=5)
entry_est.grid(row=2, column=1)


# ================= FILA 4 → COLOR =================
color_var = tk.IntVar(value=1)

tk.Label(frame_top, text="Color").grid(row=3, column=0)

tk.Radiobutton(frame_top, text="Rojo",  bg="red",
               variable=color_var, value=1).grid(row=3, column=1)

tk.Radiobutton(frame_top, text="Verde", bg="green",
               variable=color_var, value=2).grid(row=3, column=2)

tk.Radiobutton(frame_top, text="Azul",  bg="yellow",
               variable=color_var, value=3).grid(row=3, column=3)

# estado
lbl_estado = tk.Label(frame_top, text="WAIT", width=8, bg="red", fg="white")
lbl_estado.grid(row=0, column=12, padx=20)


# ====== ZONA CENTRAL (GRID STORAGE) ======
frame_grid = tk.Frame(root)
frame_grid.pack(pady=15)

crear_grid(frame_grid)


# ====== ZONA INFERIOR (LOG SERIAL) ======
frame_bottom = tk.Frame(root)
frame_bottom.pack(fill="both", expand=True, padx=10, pady=10)

text_log = tk.Text(frame_bottom, height=8)
text_log.pack(fill="both", expand=True)

accion_var.trace_add("write", ejecutar_auto)
entry_est.bind("<Return>", ejecutar_auto)


# ====================================================
root.protocol("WM_DELETE_WINDOW", cerrar)
root.mainloop()
