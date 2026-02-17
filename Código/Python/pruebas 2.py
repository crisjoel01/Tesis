import sys
import serial
import time
import threading
import datetime
from serial.tools import list_ports
from collections import deque
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import random
import json
import os


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
PASAR_CARTESIANO = {1: 10, 2:11, 3:12}
PASAR_ESTACION = {1: 13, 2: 14, 3: 15}
DESCARGA_ESTACION = {1: 16, 2: 17, 3: 18}

LEER_COLOR_ESTACION = {1: 19, 2: 20, 3: 21}
LEER_SENSORES = 22

# ================= CONFIG CARTESIANO =================
PASOS_POR_MM = 5

ESPACIOS_X = 10
DX_MM = 154
DY_MM = 156

Y_INICIAL_MM = 235
X_INICIAL_MM = 15
Y_ESTACION_MM = {
    3: 54,
    2: 54,
    1: 57
}

X_ESTACIONES_MM = {
    1: 163,
    2: 165 + 465,
    3: 170 + 465 + 610
}

ALTURAS_MM = [160, 155, 157.5, 155, 155]

ALGORITMO_ACTUAL = "zonas"

ocupado = False

lista_instrucciones = []

# ================= GUARDAR DATOS =================
ARCHIVO_ESTADO = "estado_simulacion.json"

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

# Zona activa en algoritmo por zonas
ZONA_ACTIVA = 1

# Varibles en algoritmo de frecuencia
HIST_N = 20          # últimas 20 descargas
HISTERESIS = 3       # margen para cambio de líder
MIN_CAUSAS = 2       # mínimo de cajas en zona frecuente

# historial por estación
historial = {
    1: deque(maxlen=HIST_N),
    2: deque(maxlen=HIST_N),
    3: deque(maxlen=HIST_N)
}

# color dominante actual por estación (etiqueta dinámica)
indices_estacion = {
    1: {1: None, 2: None, 3: None},  # E1: {índice: color}
    2: {1: None, 2: None, 3: None},  # E2
    3: {1: None, 2: None, 3: None}   # E3
}


# ====== zonas físicas ======
ZONAS_FRECUENTES = {
    3: [8,9,10,18,19,20],
    2: [4,5,6,14,15,16],
    1: [1,2,3,11,12,13]
}

ZONA_NEUTRA = [7,17] + list(range(21,31))
ZONA_MENOS_FRECUENTE   = list(range(31,51))

# ========= variable HMI ===============

ciclos_totales = 0
tiempo_total = 0
operacion_actual = "IDLE"

pausado = False

def esperar_si_pausado():
    while pausado:
        root.update()

# ====== guardar estado ======
def guardar_estado():
    data = {
        "presencia": presencia,
        "color": color,
        "estado_logico": estado_logico,
        "lista_instrucciones": lista_instrucciones,
        "indices_estacion": indices_estacion, 
        "historial": {k: list(v) for k, v in historial.items()}
    }

    with open(ARCHIVO_ESTADO, "w") as f:
        json.dump(data, f)

    log("💾 Estado guardado")

def cargar_estado():
    global lista_instrucciones
    global indices_estacion, historial 

    if not os.path.exists(ARCHIVO_ESTADO):
        return

    with open(ARCHIVO_ESTADO, "r") as f:
        data = json.load(f)

    presencia[:] = data["presencia"]
    color[:] = data["color"]
    estado_logico[:] = data["estado_logico"]

    lista_instrucciones[:] = [tuple(x) for x in data["lista_instrucciones"]]

    # Cargar índices (compatible con versión antigua)
    if "indices_estacion" in data:
        for k, v in data["indices_estacion"].items():
            indices_estacion[int(k)] = v
    
    for k, v in data["historial"].items():
        historial[int(k)] = deque(v, maxlen=HIST_N)

    actualizar_grid()
    actualizar_textbox_instrucciones()

    log("📂 Estado restaurado")

# ================= SERIAL =================
puerto = None

# ================= UTILIDADES =================
def mm_a_pasos(mm):
    return int(mm * PASOS_POR_MM)


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

    esperar_si_pausado()
    
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

    # comandos que DEVUELVEN color
    requiere_color = op in (19, 20, 21)

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

        # lógica de salida
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

    enviar_comando(SUBIR, mm_a_pasos(Y_ESTACION_MM[estacion]))
    enviar_comando(DERECHA, mm_a_pasos(X_ESTACIONES_MM[estacion]))
    pos_actual_x = X_ESTACIONES_MM[estacion]
    pos_actual_y = Y_ESTACION_MM[estacion]

def ir_a_estacion_directo(estacion):
    x = X_ESTACIONES_MM[estacion]
    y = Y_ESTACION_MM[estacion]
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

def coords_estacion(estacion):
    x = X_ESTACIONES_MM[estacion]
    y = Y_ESTACION_MM[estacion]
    return x, y


# ================= CICLOS =================
def ciclo_carga(estacion):
    global pos_actual_x, pos_actual_y, operacion_actual, ciclos_totales, tiempo_total
    
    inicio = time.time()
    operacion_actual = "CARGA"  # o DESCARGA
    lbl_op.config(text=operacion_actual, fg="green")
    
    ir_a_estacion_directo(estacion)
    
    enviar_comando(CARGA_ESTACION[estacion])
    
    color_detectado = enviar_comando(LEER_COLOR_ESTACION[estacion])

    if color_detectado is None:
        log("Color no detectado")
        color_detectado = 4
    
    posicion = elegir_posicion(color_detectado, estacion)

    if posicion is None:
        log("Carga cancelada → zona sin espacio")
        enviar_comando(DESCARGA_ESTACION[estacion])
        enviar_comando(HOME)
        pos_actual_x = 0
        pos_actual_y = 0
        return
    
    enviar_comando(PASAR_CARTESIANO[estacion])
    
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

    ciclos_totales += 1
    tiempo_total += (time.time() - inicio)

    lbl_op.config(text="IDLE", fg="blue")
    actualizar_metricas()

def ciclo_descarga(estacion, color_solicitado):
    global pos_actual_x, pos_actual_y, operacion_actual, ciclos_totales, tiempo_total
    
    inicio = time.time()
    operacion_actual = "DESCARGA"
    lbl_op.config(text=operacion_actual, fg="green")

    x_est, y_est = coords_estacion(estacion)
    
    pos = buscar_caja_mas_cercana(color_solicitado, x_est, y_est)

    if pos is None:
        log("No hay cajas de ese color")
        return
    
    ir_a_storage_directo(pos)

    enviar_comando(BAJAR, mm_a_pasos(20))
    enviar_comando(SACAR_GARRA)
    enviar_comando(SUBIR, mm_a_pasos(20))
    enviar_comando(METER_GARRA)

    presencia[pos-1] = 0
    color[pos-1] = 0
    actualizar_frecuencia(estacion, color_solicitado)
    actualizar_estado_logico()
    actualizar_grid()

    ir_a_estacion_directo(estacion)

    enviar_comando(SUBIR, mm_a_pasos(10))
    enviar_comando(PASAR_ESTACION[estacion])
    enviar_comando(DESCARGA_ESTACION[estacion])

    enviar_comando(HOME)
    pos_actual_x = 0
    pos_actual_y = 0
    
    ciclos_totales += 1
    tiempo_total += (time.time() - inicio)

    lbl_op.config(text="IDLE", fg="blue")
    actualizar_metricas()

# =============== SELECCION DE ALGORITMO ==============
def elegir_posicion(color_detectado, estacion):

    if ALGORITMO_ACTUAL == "zonas":
        return buscar_celda_libre_zona(pos_actual_x, pos_actual_y)

    elif ALGORITMO_ACTUAL == "producto":
        return buscar_por_producto(color_detectado, pos_actual_x, pos_actual_y)

    elif ALGORITMO_ACTUAL == "frecuencia":
        return buscar_por_frecuencia(estacion, color_detectado, pos_actual_x, pos_actual_y)

    else:
        return None

# ================ ALGORITMO POR ZONA ================

def zona_por_pos(pos):
    col = (pos - 1) % ESPACIOS_X
    return (col // 2) + 1


def buscar_celda_libre_zona(x0, y0):

    mejor_pos = None
    mejor_dist = 1e9

    for i in range(TOTAL_CELDAS):

        if estado_logico[i] == 0 and zona_por_pos(i+1) == ZONA_ACTIVA:

            fila = i // ESPACIOS_X
            col  = i % ESPACIOS_X

            x_mm = X_INICIAL_MM + col * DX_MM
            y_mm = Y_INICIAL_MM + sum(ALTURAS_MM[:fila])

            dist = abs(x_mm - x0) + abs(y_mm - y0)

            if dist < mejor_dist:
                mejor_dist = dist
                mejor_pos = i + 1

    if mejor_pos is None:
        log(f"⚠ Zona {ZONA_ACTIVA} llena -> Elija otra zona")
        return None
    else: 
        log(f"Zona {ZONA_ACTIVA} -> pos elegida {mejor_pos}")
    return mejor_pos


# ================ ALGORITMO POR PRODUCTO ================

def distancia(a, b):
    ax, ay = divmod(a, ESPACIOS_X)
    bx, by = divmod(b, ESPACIOS_X)
    return abs(ax - bx) + abs(ay - by)

def columna_de_pos(pos): 
    return (pos - 1) % ESPACIOS_X 

def producto_por_columnas(pos):
    col = columna_de_pos(pos)
    if 0 <= col <= 2:
        return 1   # rojo
    elif 3 <= col <= 5:
        return 2   # verde
    elif 7 <= col <= 9:
        return 3   # azul
    else:
        return 4   # desconocido (columna 3)


def buscar_por_producto(color_objetivo, x0, y0):
    if color_objetivo == 0 or color_objetivo is None:
        color_objetivo = 4

        
    mejor_pos = None
    mejor_dist = 1e9

    for i in range(TOTAL_CELDAS):

        if estado_logico[i] == 0 and producto_por_columnas(i+1) == color_objetivo:

            fila = i // ESPACIOS_X
            col  = i % ESPACIOS_X

            x_mm = X_INICIAL_MM + col * DX_MM
            y_mm = Y_INICIAL_MM + sum(ALTURAS_MM[:fila])

            dist = abs(x_mm - x0) + abs(y_mm - y0)

            if dist < mejor_dist:
                mejor_dist = dist
                mejor_pos = i + 1

    log(f"Producto {color_objetivo} -> pos elegida {mejor_pos}")
    return mejor_pos

# ================ ALGORITMO POR FRECUENCIA ================

# Utilidades internas
def distancia_mm_pos(pos, x0, y0):
    fila = (pos - 1) // ESPACIOS_X
    col  = (pos - 1) % ESPACIOS_X

    x_mm = X_INICIAL_MM + col * DX_MM
    y_mm = Y_INICIAL_MM + sum(ALTURAS_MM[:fila])

    return abs(x_mm - x0) + abs(y_mm - y0)


def contar_color_en_zona(celdas, color_obj):
    c = 0
    for p in celdas:
        if estado_logico[p-1] == color_obj:
            c += 1
    return c


def mejor_libre_en_lista(celdas, x0, y0):
    mejor = None
    mejor_d = 1e9

    for p in celdas:
        if estado_logico[p-1] == 0:
            d = distancia_mm_pos(p, x0, y0)
            if d < mejor_d:
                mejor_d = d
                mejor = p

    return mejor


# Ranking + bootstrap + histéresis
def calcular_ranking_estacion(est):

    hist = historial[est]

    # BOOTSTRAP (almacén vacío o pocas muestras)
    # orden de aparición define prioridad
    if len(hist) < 3:
        orden = []
        for c in hist:
            if c not in orden:
                orden.append(c)

        for c in (1,2,3):
            if c not in orden:
                orden.append(c)

        return orden[:3]

    # conteo normal
    conteo = {1:0, 2:0, 3:0}
    for c in hist:
        conteo[c] += 1

    ranking = sorted(conteo, key=lambda x: conteo[x], reverse=True)
    return ranking


def actualizar_frecuencia(est, color_descargado):

    # guardar historial
    historial[est].append(color_descargado)

    ranking = calcular_ranking_estacion(est)

    lider_actual = indices_estacion[est]
    nuevo_lider  = ranking[0]

    # aplicar histéresis
    if lider_actual is None:
        indices_estacion[est] = nuevo_lider
        log(f"Estación {est} -> líder inicial {nuevo_lider}")
        return

    # ---------- HISTÉRESIS ----------
    conteo = {1:0, 2:0, 3:0}
    for c in historial[est]:
        conteo[c] += 1

    if conteo[nuevo_lider] >= conteo[lider_actual] + HISTERESIS:
        indices_estacion[est] = nuevo_lider
        log(f"Estación {est} -> nueva zona frecuente color {nuevo_lider}")

    ##actualizar_panel_frecuencia()

# Selección principal de celda
def buscar_por_frecuencia(estacion, color_objetivo, x0, y0):

    if color_objetivo not in (1,2,3):
        return None

    # 1) ZONAS FRECUENTES DEL COLOR con menos de MIN_CAUSAS
    for est, celdas in ZONAS_FRECUENTES.items():

        if indices_estacion[est] == color_objetivo:

            if contar_color_en_zona(celdas, color_objetivo) < MIN_CAUSAS:
                pos = mejor_libre_en_lista(celdas, x0, y0)
                if pos:
                    log(f"Frecuencia -> mínimo zona {est} -> {pos}")
                    return pos

    # 2) ZONAS FRECUENTES DEL COLOR normales
    for est, celdas in ZONAS_FRECUENTES.items():

        if indices_estacion[est] == color_objetivo:
            pos = mejor_libre_en_lista(celdas, x0, y0)
            if pos:
                log(f"Frecuencia -> zona frecuente {est} -> {pos}")
                return pos

    # 2.5) si ninguna zona es líder pero hay hueco en cualquier frecuente
    for celdas in ZONAS_FRECUENTES.values():
        pos = mejor_libre_en_lista(celdas, x0, y0)
        if pos:
            log(f"Frecuencia -> fallback frecuente -> {pos}")
            return pos

    # 3) ZONA NEUTRA
    pos = mejor_libre_en_lista(ZONA_NEUTRA, x0, y0)
    if pos:
        log(f"Frecuencia -> neutra -> {pos}")
        return pos

    # 4) ZONA BAJA
    pos = mejor_libre_en_lista(ZONA_MENOS_FRECUENTE, x0, y0)
    if pos:
        log(f"Frecuencia -> baja -> {pos}")
        return pos

    log("Frecuencia -> sin espacio")
    return None


# ================= FUNCIÓN UNIFICADA =================
def movimiento_auto(estacion, accion, color_sel=None):
    global ocupado
    if ocupado:
        return
    ocupado = True

    if accion == "carga":
        ciclo_carga(estacion)

    elif accion == "descarga":

        # buscar la caja MÁS CERCANA del color elegido
        pos = buscar_caja_mas_cercana(  color_sel,
                                        pos_actual_x,
                                        pos_actual_y)

        if pos:
            ciclo_descarga(estacion, color_sel)

        else:
            log("No hay cajas de ese color")
    ocupado = False

# ================= HMI =================

# ====================================================
# ================= SERIAL UI ========================
# ====================================================

def listar_puertos():
    puertos = [p.device for p in list_ports.comports()]
    combo_puertos["values"] = puertos
    if puertos:
        combo_puertos.current(0)
    log("Puertos actualizados")


def conectar_serial():
    global puerto
    global pos_actual_x, pos_actual_y
    
    try:
        puerto_sel = combo_puertos.get()
        puerto = serial.Serial(puerto_sel, 115200, timeout=1)
        time.sleep(2)

        lbl_serial.config(text="ONLINE", bg="green")
        btn_serial.config(text="DESCONECTAR")
        log(f"Conectado a {puerto_sel}")
        pos_actual_x = 0
        pos_actual_y = 0

    except Exception as e:
        puerto = None
        log(f"Error: {e}")


def desconectar_serial():
    global puerto

    if puerto:
        puerto.close()

    puerto = None
    lbl_serial.config(text="OFFLINE", bg="red")
    btn_serial.config(text="CONECTAR")
    log("Serial cerrado")


def toggle_serial():
    if puerto and puerto.is_open:
        desconectar_serial()
    else:
        conectar_serial()


# ====================================================
# =================== UTILIDADES =====================
# ====================================================

def log(msg):
    t = datetime.datetime.now().strftime("%H:%M:%S")
    if 'text_log' in globals():
        text_log.insert(tk.END, f"[{t}] {msg}\n")
        text_log.see(tk.END)


def set_estado(ok):
    if ok:
        lbl_estado.config(text="DISPONIBLE", bg="green", fg="white", width=10)
    else:
        lbl_estado.config(text="OCUPADO", bg="orange", fg="white", width=8)


def cambiar_zona():
    global ZONA_ACTIVA
    ZONA_ACTIVA = zona_var.get()
    log(f"Zona activa -> {ZONA_ACTIVA}")


def cambiar_algoritmo():
    global ALGORITMO_ACTUAL
    ALGORITMO_ACTUAL = algoritmo_var.get()
    log(f"Algoritmo -> {ALGORITMO_ACTUAL}")
    actualizar_panel_dinamico()
    
def actualizar_textbox_instrucciones():

    text_instr.delete("1.0", tk.END)

    for i, (tipo, est, col) in enumerate(lista_instrucciones, start=1):

        if tipo == "carga":
            linea = f"{i}. CARGA   -> Estación {est}"

        else:
            colores = {1:"Rojo",2:"Verde",3:"Azul"}
            linea = f"{i}. DESCARGA -> Estación {est} ({colores[col]})"

        text_instr.insert(tk.END, linea + "\n")

def ejecutar_lista():

    def worker():

        for tipo, est, col in lista_instrucciones:

            if tipo == "carga":
                ciclo_carga(est)

            else:
                ciclo_descarga(est, col)

        log("Lista completada")

    threading.Thread(target=worker, daemon=True).start()

def cerrar_programa():
    guardar_estado()
    root.destroy()
    
def actualizar_reloj():
    ahora = datetime.datetime.now()
    lbl_hora.config(text=ahora.strftime("%H:%M:%S"))
    lbl_fecha.config(text=ahora.strftime("%d/%m/%Y"))
    root.after(1000, actualizar_reloj)
    
def actualizar_metricas():

    ocup = sum(presencia)

    r = color.count(1)
    v = color.count(2)
    a = color.count(3)

    lbl_ocup.config(text=f"Ocupación\n{ocup}/50")
    lbl_colores.config(text=f"Rojas: {r}  Verdes: {v}  Azules: {a}")
    lbl_ciclos.config(text=f"Ciclos\n{ciclos_totales}")

    if ciclos_totales > 0:
        prom = tiempo_total / ciclos_totales
        lbl_tprom.config(text=f"t̄ ciclo\n{prom:.2f} s")
        lbl_rate.config(text=f"{60/prom:.1f} cajas/min")

def pausar():
    global pausado
    pausado = True
    log("⏸ Pausado")




# ====================================================
# =================== STORAGE GRID ===================
# ====================================================

FILAS = 5
COLUMNAS = 10
celdas_ui = []


def color_celda(v):
    colores = {
        0: "gray",
        1: "red",
        2: "green",
        3: "blue",
        4: "yellow"
    }
    return colores.get(v, "black")


def actualizar_grid():
    for i, valor in enumerate(estado_logico):
        celdas_ui[i].config(bg=color_celda(valor))
    actualizar_panel_dinamico() 

def crear_grid(parent):
    for r in range(FILAS):
        for c in range(COLUMNAS):

            lbl = tk.Label(
                parent,
                width=4,
                height=2,
                bg="gray",
                relief="ridge"
            )

            lbl.grid(row=FILAS-1-r, column=c, padx=2, pady=2)
            celdas_ui.append(lbl)

def generar_lista_random():
    try:
        n = int(entry_cantidad.get())
        lista_instrucciones.clear()

        for _ in range(n):
            tipo = random.choice(["carga", "descarga"])
            est = random.randint(1, 3)
            col = random.randint(1, 3)
            
            # Guardar como TUPLA
            lista_instrucciones.append((tipo, est, col))

        actualizar_lista_ui()
        actualizar_textbox_instrucciones()  # Actualizar automáticamente

    except:
        messagebox.showerror("Error", "Cantidad inválida")

def actualizar_lista_ui():
    text_lista.delete("1.0", tk.END)
    
    for i, (tipo, est, col) in enumerate(lista_instrucciones, start=1):
        if tipo == "carga":
            texto = f"{i}. CARGA   -> Estación {est}"
        else:
            colores = {1: "Rojo", 2: "Verde", 3: "Azul"}
            texto = f"{i}. DESCARGA -> Estación {est} ({colores[col]})"
        
        text_lista.insert(tk.END, texto + "\n")


def agregar_instruccion():
    try:
        tipo = tipo_instr_var.get().lower()  # "carga" o "descarga"
        est = int(entry_est_manual.get())
        
        # Mapear color texto a número
        color_texto = color_manual_var.get()
        color_map = {"Rojo": 1, "Verde": 2, "Azul": 3}
        col = color_map.get(color_texto, 1)
        
        # Guardar como TUPLA (igual que ejecutar_lista espera)
        lista_instrucciones.append((tipo, est, col))
        
        actualizar_lista_ui()
        actualizar_textbox_instrucciones()  # Actualizar automáticamente
        
    except:
        messagebox.showerror("Error", "Datos inválidos")

def eliminar_ultima():
    if lista_instrucciones:
        lista_instrucciones.pop()
        actualizar_lista_ui()
        actualizar_textbox_instrucciones()  # Actualizar automáticamente
        
def reset_grid():
    # vaciar estructuras
    for i in range(TOTAL_CELDAS):
        presencia[i] = 0
        color[i] = 0
        estado_logico[i] = 0

    # limpiar frecuencia
    for k in historial:
        historial[k].clear()

    # ✅ Resetear índices
    for est in indices_estacion:
        indices_estacion[est] = {1: None, 2: None, 3: None}

    # limpiar instrucciones pendientes
    lista_instrucciones.clear()

    actualizar_grid()
    actualizar_textbox_instrucciones()
    guardar_estado()

    log("🧹 Grid reseteado → almacén vacío")
    
    
# ===================== funciones extra ===================

def reset_ui_con_confirmacion():
    if messagebox.askyesno("Confirmar", 
                           "¿Estás seguro de resetear todo el almacén?\n"
                           "Se perderán todas las cajas y el historial."):
        reset_ui()

def ejecutar_o_continuar():
    global pausado

    # si estaba pausado → continuar
    if pausado:
        pausado = False
        log("▶ Continuar")
        btn_run.config(text="Ejecutar")
        
    else:
        ejecutar_lista()


def pausar_ui():
    pausar()
    btn_run.config(text="Continuar")


def home_ui():
    global pos_actual_x, pos_actual_y

    enviar_comando(HOME)
    pos_actual_x = 0
    pos_actual_y = 0
    log("🏠 Home manual")


def reset_ui():
    global pausado
    pausado = True
    reset_grid()
    
# ====================================================
# ===================== UI ===========================
# ====================================================

root = tk.Tk()
root.title("HMI TESIS SISTEMA AUTOMATIZADO DE ALMACENAMIENTO")
root.state("zoomed")        # Windows maximizado
root.resizable(True, True)

zona_var = tk.IntVar(value=1)

notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True)

tab_sim   = tk.Frame(notebook)
tab_config = tk.Frame(notebook)
tab_stats  = tk.Frame(notebook)

notebook.add(tab_sim, text="Simulación")
notebook.add(tab_config, text="Configuración")
notebook.add(tab_stats, text="Estadísticas")



# ====================================================
# ========= SIMULACIÓN - BLOQUE SUPERIOR =============
# ====================================================

frame_barra = tk.Frame(tab_sim)
frame_barra.pack(fill="x", pady=10, padx=10)

# Configurar grid con 4 columnas de igual peso
for i in range(4):
    frame_barra.columnconfigure(i, weight=1)

# -------- SERIAL --------
frame_serial = tk.LabelFrame(frame_barra, text="🔌 Serial", padx=10, pady=8, font=("Arial", 10, "bold"))
frame_serial.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

inner_serial = tk.Frame(frame_serial)
inner_serial.pack(expand=True, fill="both", padx=5)

tk.Button(inner_serial, text="↻", width=3, command=listar_puertos).pack(side="left", padx=2)
combo_puertos = ttk.Combobox(inner_serial, width=10)
combo_puertos.pack(side="left", padx=2)
btn_serial = tk.Button(inner_serial, text="Conectar", width=11, command=toggle_serial)
btn_serial.pack(side="left", padx=2)
lbl_serial = tk.Label(inner_serial, text="OFFLINE", bg="red", fg="white", width=7, font=("Arial", 9, "bold"))
lbl_serial.pack(side="left", padx=2)

# -------- ALGORITMO --------
frame_alg = tk.LabelFrame(frame_barra, text="⚙️ Algoritmo", padx=10, pady=8, font=("Arial", 10, "bold"))
frame_alg.grid(row=0, column=1, sticky="nsew", padx=2, pady=2)

inner_alg = tk.Frame(frame_alg)
inner_alg.pack(expand=True, fill="both", padx=5)

algoritmo_var = tk.StringVar(value="zonas")

tk.Radiobutton(inner_alg, text="Zonas", variable=algoritmo_var, value="zonas",
               command=cambiar_algoritmo, font=("Arial", 9)).pack(side="left", padx=5)
tk.Radiobutton(inner_alg, text="Producto", variable=algoritmo_var, value="producto",
               command=cambiar_algoritmo, font=("Arial", 9)).pack(side="left", padx=5)
tk.Radiobutton(inner_alg, text="Frecuencia", variable=algoritmo_var, value="frecuencia",
               command=cambiar_algoritmo, font=("Arial", 9)).pack(side="left", padx=5)

# -------- CONTROL --------
frame_ctrl = tk.LabelFrame(frame_barra, text="🎮 Control", padx=10, pady=8, font=("Arial", 10, "bold"))
frame_ctrl.grid(row=0, column=2, sticky="nsew", padx=2, pady=2)

inner_ctrl = tk.Frame(frame_ctrl)
inner_ctrl.pack(expand=True, fill="both", padx=5)

btn_run = tk.Button(inner_ctrl, text="Ejecutar", width=8, command=ejecutar_o_continuar,
                    bg="#4CAF50", fg="white", font=("Arial", 9, "bold"))
btn_run.pack(side="left", padx=3)

btn_pause = tk.Button(inner_ctrl, text="Pausa", width=7, command=pausar_ui,
                      bg="#FFC107", font=("Arial", 9, "bold"))
btn_pause.pack(side="left", padx=3)

btn_home = tk.Button(inner_ctrl, text="Home", width=7, command=home_ui,
                     bg="#2196F3", fg="white", font=("Arial", 9, "bold"))
btn_home.pack(side="left", padx=3)

btn_reset = tk.Button(inner_ctrl, text="Reset", width=7, command=reset_ui_con_confirmacion,
                      bg="#f44336", fg="white", font=("Arial", 9, "bold"))
btn_reset.pack(side="left", padx=3)

# -------- SISTEMA --------
frame_estado = tk.LabelFrame(frame_barra, text="⏱️ Sistema", padx=10, pady=8, font=("Arial", 10, "bold"))
frame_estado.grid(row=0, column=3, sticky="nsew", padx=2, pady=2)

inner_estado = tk.Frame(frame_estado)
inner_estado.pack(expand=True, fill="both", padx=10)

tk.Label(inner_estado, text="Estado:", font=("Arial", 9, "bold")).pack(side="left")
lbl_estado = tk.Label(
    inner_estado,
    text="DISPONIBLE",
    bg="green",
    fg="white",
    width=10,
    font=("Arial", 9, "bold")
)
lbl_estado.pack(side="left", padx=3)

tk.Label(inner_estado, text="|", font=("Arial", 14), fg="gray").pack(side="left", padx=5)

tk.Label(inner_estado, text="Hora:", font=("Arial", 9, "bold")).pack(side="left")
lbl_hora = tk.Label(
    inner_estado,
    text="00:00:00",
    font=("Consolas", 10, "bold"),
    fg="#2196F3"
)
lbl_hora.pack(side="left", padx=3)

tk.Label(inner_estado, text="|", font=("Arial", 14), fg="gray").pack(side="left", padx=5)

tk.Label(inner_estado, text="Fecha:", font=("Arial", 9, "bold")).pack(side="left")
lbl_fecha = tk.Label(
    inner_estado,
    text="16/02/2026",
    font=("Arial", 9),
    fg="#666"
)
lbl_fecha.pack(side="left", padx=3)


# ====================================================
# ============ ACCIONES (segunda fila) ===============
# ====================================================

frame_controles = tk.Frame(tab_sim)
frame_controles.pack(pady=5)

frame_instr = tk.LabelFrame(tab_sim, text="Instrucciones")
frame_instr.pack(side="left", padx=10, pady=10)

text_instr = tk.Text(frame_instr, width=40, height=25)
text_instr.pack()

tk.Button(frame_instr, text="Actualizar",
          command=actualizar_textbox_instrucciones).pack(pady=3)

tk.Button(frame_instr, text="Ejecutar lista",
          command=ejecutar_lista).pack(pady=3)

tk.Button(frame_instr, text="RESET GRID", command=reset_grid).pack(pady=3)



# ====================================================
# ========= SEGUNDA FILA: PANEL DINÁMICO + RESUMEN ===
# ====================================================

frame_segunda_fila = tk.Frame(tab_sim)
frame_segunda_fila.pack(fill="x", pady=5, padx=10)

# Configurar dos columnas: izquierda (dinámica) y derecha (resumen)
frame_segunda_fila.columnconfigure(0, weight=2)  # Panel dinámico más ancho
frame_segunda_fila.columnconfigure(1, weight=1)  # Resumen más compacto

# Panel dinámico (cambia según algoritmo)
frame_panel_dinamico = tk.LabelFrame(frame_segunda_fila, text="📊 Información del Algoritmo", 
                                      font=("Arial", 10, "bold"), padx=10, pady=10)
frame_panel_dinamico.grid(row=0, column=0, sticky="nsew", padx=(0,5))

# Panel de resumen del sistema
frame_resumen = tk.LabelFrame(frame_segunda_fila, text="📈 Resumen del Sistema", 
                                font=("Arial", 10, "bold"), padx=10, pady=10)
frame_resumen.grid(row=0, column=1, sticky="nsew", padx=(5,0))

# Configurar tamaño fijo para ambos paneles (ancho en píxeles)
frame_panel_dinamico.grid_propagate(False)
frame_panel_dinamico.config(width=550, height=130)

# Frame interno para el contenido dinámico
inner_dinamico = tk.Frame(frame_panel_dinamico)
inner_dinamico.pack(expand=True, fill="both", padx=5, pady=5)

def actualizar_panel_dinamico():
    # Limpiar contenido anterior
    for widget in inner_dinamico.winfo_children():
        widget.destroy()
    
    algoritmo = ALGORITMO_ACTUAL
    if algoritmo == "zonas":
        crear_panel_zonas()
    elif algoritmo == "producto":
        crear_panel_producto()
    elif algoritmo == "frecuencia":
        crear_panel_frecuencia()

def crear_panel_zonas():
    # Mostrar selector de zona activa y ocupación por zona
    # Fila 1: selector de zona
    fila1 = tk.Frame(inner_dinamico)
    fila1.pack(fill="x", pady=2)
    tk.Label(fila1, text="Zona activa:", font=("Arial", 9, "bold")).pack(side="left")
    
    zona_var = tk.IntVar(value=ZONA_ACTIVA)
    for i in range(1, 6):
        rb = tk.Radiobutton(fila1, text=f"Z{i}", variable=zona_var, value=i,
                            command=lambda: cambiar_zona_desde_panel(zona_var.get()),
                            font=("Arial", 8))
        rb.pack(side="left", padx=2)
    
    # Fila 2: ocupación de cada zona (5 zonas, cada una con 10 celdas)
    fila2 = tk.Frame(inner_dinamico)
    fila2.pack(fill="x", pady=2)
    
    # Calcular ocupación por zona (según columnas)
    ocupacion_zona = [0]*5
    total_zona = [0]*5
    for i in range(50):  # índice 0-49
        pos = i+1
        col = (pos-1) % 10
        zona = (col // 2)  # 0 a 4
        if estado_logico[i] != 0:
            ocupacion_zona[zona] += 1
        total_zona[zona] += 1
    
    for z in range(5):
        porcentaje = (ocupacion_zona[z] / total_zona[z]) * 100 if total_zona[z] else 0
        texto = f"Z{z+1}: {ocupacion_zona[z]}/{total_zona[z]} ({porcentaje:.0f}%)"
        tk.Label(fila2, text=texto, font=("Arial", 8), padx=5).pack(side="left")

def crear_panel_producto():
    # Mostrar ocupación por color en sus zonas designadas
    # Colores: 1=rojo, 2=verde, 3=azul
    # Zonas de producto: según columnas
    # Rojo: columnas 0-2 (15 celdas)
    # Verde: columnas 3-5 (15 celdas)
    # Azul: columnas 7-9 (15 celdas)
    # Neutra: columna 6 (5 celdas)
    
    # Contar celdas ocupadas por color en su zona
    ocup_rojo = ocup_verde = ocup_azul = 0
    total_rojo = total_verde = total_azul = 15
    for i in range(50):
        col = i % 10
        if estado_logico[i] != 0:
            if col <= 2:
                ocup_rojo += 1
            elif 3 <= col <= 5:
                ocup_verde += 1
            elif 7 <= col <= 9:
                ocup_azul += 1
    
    fila1 = tk.Frame(inner_dinamico)
    fila1.pack(fill="x", pady=5)
    tk.Label(fila1, text="Producto Rojo:", fg="red", font=("Arial", 9, "bold")).pack(side="left", padx=5)
    tk.Label(fila1, text=f"{ocup_rojo}/{total_rojo} ({ocup_rojo*100//total_rojo}%)", font=("Arial", 9)).pack(side="left", padx=5)
    
    fila2 = tk.Frame(inner_dinamico)
    fila2.pack(fill="x", pady=5)
    tk.Label(fila2, text="Producto Verde:", fg="green", font=("Arial", 9, "bold")).pack(side="left", padx=5)
    tk.Label(fila2, text=f"{ocup_verde}/{total_verde} ({ocup_verde*100//total_verde}%)", font=("Arial", 9)).pack(side="left", padx=5)
    
    fila3 = tk.Frame(inner_dinamico)
    fila3.pack(fill="x", pady=5)
    tk.Label(fila3, text="Producto Azul:", fg="blue", font=("Arial", 9, "bold")).pack(side="left", padx=5)
    tk.Label(fila3, text=f"{ocup_azul}/{total_azul} ({ocup_azul*100//total_azul}%)", font=("Arial", 9)).pack(side="left", padx=5)

def crear_panel_frecuencia():
    # Mostrar para cada estación: color líder, stock mínimo en zona frecuente, ocupación zona frecuente
    # Las zonas frecuentes están definidas en ZONAS_FRECUENTES (6 celdas cada una)
    fila1 = tk.Frame(inner_dinamico)
    fila1.pack(fill="x", pady=2)
    tk.Label(fila1, text="Estación", font=("Arial", 9, "bold"), width=8).pack(side="left")
    tk.Label(fila1, text="Color líder", font=("Arial", 9, "bold"), width=10).pack(side="left")
    tk.Label(fila1, text="Stock mín", font=("Arial", 9, "bold"), width=8).pack(side="left")
    tk.Label(fila1, text="Ocup Zona", font=("Arial", 9, "bold"), width=8).pack(side="left")
    
    for est in [1,2,3]:
        # Color líder
        lider = indices_estacion[est]  # esto es un entero 1,2,3 o None
        color_text = {1:"Rojo",2:"Verde",3:"Azul", None:"---"}.get(lider, "---")
        
        # Calcular stock mínimo del color líder en su zona frecuente
        celdas_zona = ZONAS_FRECUENTES[est]  # lista de posiciones (1-index)
        count_color = 0
        for pos in celdas_zona:
            idx = pos-1
            if estado_logico[idx] == lider:
                count_color += 1
        stock_min = count_color  # Podríamos definir un mínimo deseado, aquí mostramos ocupación actual
        
        # Ocupación de la zona frecuente (total celdas ocupadas en esa zona)
        ocup_zona = sum(1 for pos in celdas_zona if estado_logico[pos-1] != 0)
        
        fila = tk.Frame(inner_dinamico)
        fila.pack(fill="x", pady=1)
        tk.Label(fila, text=f"E{est}", font=("Arial", 8), width=8).pack(side="left")
        tk.Label(fila, text=color_text, font=("Arial", 8), width=10).pack(side="left")
        tk.Label(fila, text=f"{stock_min}/6", font=("Arial", 8), width=8).pack(side="left")
        tk.Label(fila, text=f"{ocup_zona}/6", font=("Arial", 8), width=8).pack(side="left")

def cambiar_zona_desde_panel(zona):
    global ZONA_ACTIVA
    ZONA_ACTIVA = zona
    log(f"Zona activa cambiada a {zona} desde panel")
    # Opcional: actualizar también los radio buttons de la barra superior si existen
    # zona_var.set(zona)  # si tenemos variable compartida

actualizar_panel_dinamico()

frame_resumen.grid_propagate(False)
frame_resumen.config(width=350, height=130)

# ----- Contenido del panel Resumen -----
inner_resumen = tk.Frame(frame_resumen)
inner_resumen.pack(expand=True, fill="both", padx=5, pady=5)

# Configurar grid 2x3
for i in range(3):
    inner_resumen.columnconfigure(i, weight=1)
for i in range(2):
    inner_resumen.rowconfigure(i, weight=1)

# Fila 0
lbl_ocup = tk.Label(inner_resumen, text="Ocupación\n0/50", font=("Arial", 9, "bold"), justify="center")
lbl_ocup.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

lbl_colores = tk.Label(inner_resumen, text="R:0  V:0  A:0", font=("Arial", 9), justify="center")
lbl_colores.grid(row=0, column=1, sticky="nsew", padx=2, pady=2)

lbl_op = tk.Label(inner_resumen, text="IDLE", fg="blue", font=("Arial", 9, "bold"))
lbl_op.grid(row=0, column=2, sticky="nsew", padx=2, pady=2)

# Fila 1
lbl_ciclos = tk.Label(inner_resumen, text="Ciclos\n0", justify="center", font=("Arial", 9))
lbl_ciclos.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)

lbl_tprom = tk.Label(inner_resumen, text="Tiempo prom\n0.0 s", justify="center", font=("Arial", 9))
lbl_tprom.grid(row=1, column=1, sticky="nsew", padx=2, pady=2)

lbl_rate = tk.Label(inner_resumen, text="Rendimiento\n0 cajas/min", justify="center", font=("Arial", 9))
lbl_rate.grid(row=1, column=2, sticky="nsew", padx=2, pady=2)


# ====================================================
# =============== GRID CENTRAL =======================
# ====================================================

frame_grid = tk.Frame(tab_sim)
frame_grid.pack(pady=15)

crear_grid(frame_grid)


# ====================================================
# ================= LOG ==============================
# ====================================================

frame_bottom = tk.Frame(tab_sim)
frame_bottom.pack(fill="both", expand=True, padx=10, pady=10)

text_log = tk.Text(frame_bottom)
text_log.pack(fill="both", expand=True)


# ================= TAB CONFIGURACIÓN =================



tab_config.grid_rowconfigure(1, weight=1)

tab_config.grid_columnconfigure(0, weight=2)
tab_config.grid_columnconfigure(1, weight=2)
tab_config.grid_columnconfigure(2, weight=3)


# ===== FILA 1 → Configuraciones generales (vacío) =====
frame_general = tk.LabelFrame(
    tab_config,
    text="Configuraciones generales",
    height=80,
    font=("TkDefaultFont", 10, "bold")
)
frame_general.grid(row=0, column=0, columnspan=3, sticky="ew", padx=10, pady=10)


# ===== FILA 2 → Generador =====
frame_gen = tk.LabelFrame(
    tab_config,
    text="Generador de instrucciones",
    font=("TkDefaultFont", 10, "bold")
)
frame_gen.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=10, pady=10)

frame_gen.grid_columnconfigure(0, weight=2)
frame_gen.grid_columnconfigure(1, weight=2)
frame_gen.grid_columnconfigure(2, weight=3)


# ====================================================
# ========= COLUMNA 1 → MANUAL =======================
# ====================================================

frame_manual = tk.LabelFrame(
    frame_gen,
    text="Instrucción manual",
    font=("TkDefaultFont", 10, "bold")
)
frame_manual.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

frame_manual.grid_columnconfigure(1, weight=1)

tk.Label(frame_manual, text="Instrucción:", font=("TkDefaultFont", 9, "bold"))\
    .grid(row=0, column=0, sticky="w", pady=4)

tipo_instr_var = tk.StringVar(value="carga")

ttk.Combobox(
    frame_manual,
    textvariable=tipo_instr_var,
    values=["Carga", "Descarga"],
    state="readonly"
).grid(row=0, column=1, sticky="ew")


tk.Label(frame_manual, text="N° Estación:", font=("TkDefaultFont", 9, "bold"))\
    .grid(row=1, column=0, sticky="w", pady=4)

entry_est_manual = tk.Entry(frame_manual)
entry_est_manual.grid(row=1, column=1, sticky="ew")


tk.Label(frame_manual, text="Color de caja:", font=("TkDefaultFont", 9, "bold"))\
    .grid(row=2, column=0, sticky="w", pady=4)

color_manual_var = tk.StringVar(value="Rojo")

ttk.Combobox(
    frame_manual,
    textvariable=color_manual_var,
    values=["Rojo", "Verde", "Azul"],
    state="readonly"
).grid(row=2, column=1, sticky="ew")


tk.Button(frame_manual, text="Agregar instrucción",
          command=agregar_instruccion)\
          .grid(row=3, column=0, columnspan=2, sticky="ew", pady=6)

tk.Button(frame_manual, text="Eliminar última instrucción",
          command=eliminar_ultima)\
          .grid(row=4, column=0, columnspan=2, sticky="ew")


# ====================================================
# ========= COLUMNA 2 → ALEATORIAS ===================
# ====================================================

frame_rand = tk.LabelFrame(
    frame_gen,
    text="Instrucciones aleatorias",
    font=("TkDefaultFont", 10, "bold")
)
frame_rand.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

frame_rand.grid_columnconfigure(1, weight=1)

tk.Label(frame_rand, text="Cantidad:")\
    .grid(row=0, column=0, sticky="w")

entry_cantidad = tk.Entry(frame_rand)
entry_cantidad.grid(row=0, column=1, sticky="ew")

tk.Button(frame_rand, text="Generar lista",
          command=generar_lista_random)\
          .grid(row=1, column=0, columnspan=2, sticky="ew", pady=6)


# ====================================================
# ========= COLUMNA 3 → VISOR ========================
# ====================================================

frame_lista = tk.LabelFrame(
    frame_gen,
    text="Lista de instrucciones",
    font=("TkDefaultFont", 10, "bold"))

frame_lista.grid(row=0, column=2, sticky="nsew", padx=10, pady=10)

frame_lista.grid_rowconfigure(0, weight=1)
frame_lista.grid_columnconfigure(0, weight=1)

text_lista = tk.Text(frame_lista)
text_lista.grid(row=0, column=0, sticky="nsew")
# ====================================================
# ================= MAIN =============================
# ====================================================
cargar_estado()
root.protocol("WM_DELETE_WINDOW", cerrar_programa)
actualizar_reloj()
root.mainloop()