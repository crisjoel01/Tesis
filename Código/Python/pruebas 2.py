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
Y_ESTACION_MM = {3: 54, 2: 54, 1: 57}
X_ESTACIONES_MM = {1: 163, 2: 165 + 465, 3: 170 + 465 + 610}
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
presencia = [0] * TOTAL_CELDAS
color = [0] * TOTAL_CELDAS
estado_logico = [0] * TOTAL_CELDAS
ZONA_ACTIVA = 1

# Variables de frecuencia
HIST_N = 20
HISTERESIS = 3
MIN_CAUSAS = 2
historial = {1: deque(maxlen=HIST_N), 2: deque(maxlen=HIST_N), 3: deque(maxlen=HIST_N)}
indices_estacion = {1: {1: None, 2: None, 3: None}, 2: {1: None, 2: None, 3: None}, 3: {1: None, 2: None, 3: None}}

# ====== zonas físicas ======
ZONAS_FRECUENTES = {3: [8,9,10,18,19,20], 2: [4,5,6,14,15,16], 1: [1,2,3,11,12,13]}
ZONA_NEUTRA = [7,17] + list(range(21,31))
ZONA_MENOS_FRECUENTE = list(range(31,51))

# ========= variables HMI ===============
ciclos_totales = 0
tiempo_total = 0
operacion_actual = "IDLE"
pausado = False

# ========= Estados de estaciones ===============
estado_estaciones = {1: "rojo", 2: "rojo", 3: "rojo"}
lbl_estaciones = {}

def actualizar_estado_estacion(num_estacion, estado):
    """Actualiza el color de la estación (rojo=parado, verde=moviendo)"""
    if num_estacion in lbl_estaciones:
        estado_estaciones[num_estacion] = estado
        if estado == "verde":
            lbl_estaciones[num_estacion].config(bg="green", fg="white")
        else:
            lbl_estaciones[num_estacion].config(bg="red", fg="white")

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
    global lista_instrucciones, indices_estacion, historial
    if not os.path.exists(ARCHIVO_ESTADO):
        return
    with open(ARCHIVO_ESTADO, "r") as f:
        data = json.load(f)
    presencia[:] = data["presencia"]
    color[:] = data["color"]
    estado_logico[:] = data["estado_logico"]
    lista_instrucciones[:] = [tuple(x) for x in data["lista_instrucciones"]]
    if "indices_estacion" in data:
        for k, v in data["indices_estacion"].items():
            indices_estacion[int(k)] = v
    for k, v in data["historial"].items():
        historial[int(k)] = deque(v, maxlen=HIST_N)
    actualizar_grid()
    actualizar_lista_ui()
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
    
    # Actualizar estados de estaciones según comando
    if op in [7, 10, 13, 16]:  # Estación 1
        actualizar_estado_estacion(1, "verde")
    elif op in [8, 11, 14, 17]:  # Estación 2
        actualizar_estado_estacion(2, "verde")
    elif op in [9, 12, 15, 18]:  # Estación 3
        actualizar_estado_estacion(3, "verde")
    
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
    requiere_color = op in (19, 20, 21)

    while True:
        if puerto.in_waiting:
            resp = puerto.readline().decode().strip()
            log(f"Arduino → {resp}")
            if resp.startswith("C:"):
                color_detectado = int(resp.split(":")[1])
                color_recibido = True
            elif resp == "ACK:1":
                ack_recibido = True
                if op == HOME:
                    global pos_actual_x, pos_actual_y
                    pos_actual_x = 0
                    pos_actual_y = 0
        if requiere_color:
            if ack_recibido and color_recibido:
                break
        else:
            if ack_recibido:
                break
        time.sleep(0.01)

    # Volver estaciones a rojo al terminar comando
    if op in [7, 10, 13, 16]:
        actualizar_estado_estacion(1, "rojo")
    elif op in [8, 11, 14, 17]:
        actualizar_estado_estacion(2, "rojo")
    elif op in [9, 12, 15, 18]:
        actualizar_estado_estacion(3, "rojo")
    
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
        if estado_logico[i] == color_objetivo:
            fila = i // ESPACIOS_X
            col = i % ESPACIOS_X
            x_mm = X_INICIAL_MM + col * DX_MM
            y_mm = Y_INICIAL_MM + sum(ALTURAS_MM[:fila])
            dist = abs(x_mm - x0) + abs(y_mm - y0)
            if dist < mejor_dist:
                mejor_dist = dist
                mejor_pos = i + 1
    return mejor_pos

def coords_estacion(estacion):
    return X_ESTACIONES_MM[estacion], Y_ESTACION_MM[estacion]

# ================= CICLOS =================
def ciclo_carga(estacion):
    global pos_actual_x, pos_actual_y, operacion_actual, ciclos_totales, tiempo_total
    inicio = time.time()
    operacion_actual = "CARGA"
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
    operacion_actual = "HOME"
    enviar_comando(HOME)
    pos_actual_x = 0
    pos_actual_y = 0
    ciclos_totales += 1
    tiempo_total += (time.time() - inicio)
    operacion_actual = "IDLE"
    actualizar_metricas()

def ciclo_descarga(estacion, color_solicitado):
    global pos_actual_x, pos_actual_y, operacion_actual, ciclos_totales, tiempo_total
    inicio = time.time()
    operacion_actual = "DESCARGA"
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
    operacion_actual = "HOME"
    enviar_comando(HOME)
    pos_actual_x = 0
    pos_actual_y = 0
    ciclos_totales += 1
    tiempo_total += (time.time() - inicio)
    operacion_actual = "IDLE"
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
            col = i % ESPACIOS_X
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
def columna_de_pos(pos):
    return (pos - 1) % ESPACIOS_X

def producto_por_columnas(pos):
    col = columna_de_pos(pos)
    if 0 <= col <= 2:
        return 1
    elif 3 <= col <= 5:
        return 2
    elif 7 <= col <= 9:
        return 3
    else:
        return 4

def buscar_por_producto(color_objetivo, x0, y0):
    if color_objetivo == 0 or color_objetivo is None:
        color_objetivo = 4
    mejor_pos = None
    mejor_dist = 1e9
    for i in range(TOTAL_CELDAS):
        if estado_logico[i] == 0 and producto_por_columnas(i+1) == color_objetivo:
            fila = i // ESPACIOS_X
            col = i % ESPACIOS_X
            x_mm = X_INICIAL_MM + col * DX_MM
            y_mm = Y_INICIAL_MM + sum(ALTURAS_MM[:fila])
            dist = abs(x_mm - x0) + abs(y_mm - y0)
            if dist < mejor_dist:
                mejor_dist = dist
                mejor_pos = i + 1
    log(f"Producto {color_objetivo} -> pos elegida {mejor_pos}")
    return mejor_pos

# ================ ALGORITMO POR FRECUENCIA ================
def distancia_mm_pos(pos, x0, y0):
    fila = (pos - 1) // ESPACIOS_X
    col = (pos - 1) % ESPACIOS_X
    x_mm = X_INICIAL_MM + col * DX_MM
    y_mm = Y_INICIAL_MM + sum(ALTURAS_MM[:fila])
    return abs(x_mm - x0) + abs(y_mm - y0)

def contar_color_en_zona(celdas, color_obj):
    return sum(1 for p in celdas if estado_logico[p-1] == color_obj)

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

def calcular_ranking_estacion(est):
    hist = historial[est]
    if len(hist) < 3:
        orden = []
        for c in hist:
            if c not in orden:
                orden.append(c)
        for c in (1,2,3):
            if c not in orden:
                orden.append(c)
        return orden[:3]
    conteo = {1:0, 2:0, 3:0}
    for c in hist:
        conteo[c] += 1
    return sorted(conteo, key=lambda x: conteo[x], reverse=True)

def actualizar_frecuencia(est, color_descargado):
    historial[est].append(color_descargado)
    ranking = calcular_ranking_estacion(est)
    lider_actual = indices_estacion[est][1]
    nuevo_lider = ranking[0]
    if lider_actual is None:
        indices_estacion[est][1] = nuevo_lider
        log(f"Estación {est} -> líder inicial {nuevo_lider}")
        return
    conteo = {1:0, 2:0, 3:0}
    for c in historial[est]:
        conteo[c] += 1
    if conteo[nuevo_lider] >= conteo[lider_actual] + HISTERESIS:
        indices_estacion[est][1] = nuevo_lider
        log(f"Estación {est} -> nueva zona frecuente color {nuevo_lider}")

def buscar_por_frecuencia(estacion, color_objetivo, x0, y0):
    if color_objetivo not in (1,2,3):
        return None
    for est, celdas in ZONAS_FRECUENTES.items():
        if indices_estacion[est][1] == color_objetivo:
            if contar_color_en_zona(celdas, color_objetivo) < MIN_CAUSAS:
                pos = mejor_libre_en_lista(celdas, x0, y0)
                if pos:
                    log(f"Frecuencia -> mínimo zona {est} -> {pos}")
                    return pos
    for est, celdas in ZONAS_FRECUENTES.items():
        if indices_estacion[est][1] == color_objetivo:
            pos = mejor_libre_en_lista(celdas, x0, y0)
            if pos:
                log(f"Frecuencia -> zona frecuente {est} -> {pos}")
                return pos
    for celdas in ZONAS_FRECUENTES.values():
        pos = mejor_libre_en_lista(celdas, x0, y0)
        if pos:
            log(f"Frecuencia -> fallback frecuente -> {pos}")
            return pos
    pos = mejor_libre_en_lista(ZONA_NEUTRA, x0, y0)
    if pos:
        log(f"Frecuencia -> neutra -> {pos}")
        return pos
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
        pos = buscar_caja_mas_cercana(color_sel, pos_actual_x, pos_actual_y)
        if pos:
            ciclo_descarga(estacion, color_sel)
        else:
            log("No hay cajas de ese color")
    ocupado = False

# ================= HMI =================
def listar_puertos():
    puertos = [p.device for p in list_ports.comports()]
    combo_puertos["values"] = puertos
    if puertos:
        combo_puertos.current(0)
    log("Puertos actualizados")

def conectar_serial():
    global puerto, pos_actual_x, pos_actual_y
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
    
    porcentaje = (ocup / 50) * 100
    lbl_ocup.config(text=f"Ocupación: {ocup}/50 ({porcentaje:.0f}%)")
    
    lbl_colores.config(text=f"Cajas -> Rojo:{r}  Verde:{v}  Azul:{a}")
    lbl_ciclos.config(text=f"Ciclos: {ciclos_totales}")
    
    if ciclos_totales > 0:
        prom = tiempo_total / ciclos_totales
        lbl_tprom.config(text=f"T ciclo promedio: {prom:.2f} s")
        lbl_rate.config(text=f"Throughput: {60/prom:.1f}/min")
    else:
        lbl_tprom.config(text="T ciclo promedio: 0.0 s")
        lbl_rate.config(text="Throughput: 0/min")
    
    lbl_op.config(text=f"Operación: {operacion_actual}")
    if operacion_actual == "IDLE":
        lbl_op.config(fg="blue")
    else:
        lbl_op.config(fg="green")
        
def pausar():
    global pausado
    pausado = True
    log("⏸ Pausado")

def continuar():
    global pausado
    pausado = False
    log("▶ Continuar")

# =================== STORAGE GRID ===================
FILAS = 5
COLUMNAS = 10
celdas_ui = []

def color_celda(v):
    colores = {0: "gray", 1: "red", 2: "green", 3: "blue", 4: "yellow"}
    return colores.get(v, "black")

def texto_contraste(bg_color):
    """Retorna blanco o negro según el fondo para mejor contraste"""
    if bg_color in ["red", "blue", "green"]:
        return "white"
    else:
        return "black"

def actualizar_grid():
    for i, valor in enumerate(estado_logico):
        bg = color_celda(valor)
        fg = texto_contraste(bg)
        celdas_ui[i].config(bg=bg, fg=fg)
    actualizar_panel_dinamico()

def crear_grid(parent):
    for r in range(FILAS):
        for c in range(COLUMNAS):
            num_celda = (FILAS - 1 - r) * COLUMNAS + c + 1
            lbl = tk.Label(
                parent,
                text=str(num_celda),
                width=6,
                height=3,
                bg="gray",
                fg="black",
                relief="ridge",
                font=("Arial", 10, "bold")
            )
            lbl.grid(row=r, column=c, padx=1, pady=1)
            celdas_ui.append(lbl)

def generar_lista_random():
    try:
        n = int(entry_cantidad.get())
        lista_instrucciones.clear()
        for _ in range(n):
            tipo = random.choice(["carga", "descarga"])
            est = random.randint(1, 3)
            col = random.randint(1, 3)
            lista_instrucciones.append((tipo, est, col))
        actualizar_lista_ui()
    except:
        messagebox.showerror("Error", "Cantidad inválida")

def actualizar_lista_ui():
    text_instr.delete("1.0", tk.END)
    for i, (tipo, est, col) in enumerate(lista_instrucciones, start=1):
        if tipo == "carga":
            texto = f"{i}. CARGA   -> Estación {est}"
        else:
            colores = {1: "Rojo", 2: "Verde", 3: "Azul"}
            texto = f"{i}. DESCARGA -> Estación {est} ({colores[col]})"
        text_instr.insert(tk.END, texto + "\n")
        
    if 'text_lista_config' in globals() and text_lista_config.winfo_exists():
        text_lista_config.delete("1.0", tk.END)
        text_lista_config.insert(tk.END, text_instr.get("1.0", tk.END))

def agregar_instruccion():
    try:
        tipo = tipo_instr_var.get().lower()
        est = int(entry_est_manual.get())
        color_texto = color_manual_var.get()
        color_map = {"Rojo": 1, "Verde": 2, "Azul": 3}
        col = color_map.get(color_texto, 1)
        lista_instrucciones.append((tipo, est, col))
        actualizar_lista_ui()
    except:
        messagebox.showerror("Error", "Datos inválidos")

def eliminar_ultima():
    if lista_instrucciones:
        lista_instrucciones.pop()
        actualizar_lista_ui()

def limpiar_lista():
    lista_instrucciones.clear()
    actualizar_lista_ui()
    log("📋 Lista de instrucciones limpiada")

def limpiar_log():
    text_log.delete("1.0", tk.END)
    log("🗑️ Log limpiado")

def copiar_log():
    contenido = text_log.get("1.0", tk.END)
    root.clipboard_clear()
    root.clipboard_append(contenido)
    log("📋 Log copiado al portapapeles")

def reset_grid():
    for i in range(TOTAL_CELDAS):
        presencia[i] = 0
        color[i] = 0
        estado_logico[i] = 0
    for k in historial:
        historial[k].clear()
    for est in indices_estacion:
        indices_estacion[est] = {1: None, 2: None, 3: None}
    lista_instrucciones.clear()
    actualizar_grid()
    actualizar_lista_ui()
    guardar_estado()
    log("🧹 Grid reseteado → almacén vacío")

# ===================== funciones extra ===================
def reset_ui_con_confirmacion():
    if messagebox.askyesno("Confirmar", "¿Estás seguro de resetear todo el almacén?\nSe perderán todas las cajas y el historial."):
        reset_ui()

def ejecutar_o_continuar():
    global pausado
    if pausado:
        continuar()
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
root.state("zoomed")
root.resizable(True, True)

zona_var = tk.IntVar(value=1)

notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True)

tab_sim = tk.Frame(notebook)
tab_config = tk.Frame(notebook)
tab_stats = tk.Frame(notebook)
notebook.add(tab_sim, text="Simulación")
notebook.add(tab_config, text="Configuración")
notebook.add(tab_stats, text="Estadísticas")

# ========= BLOQUE SUPERIOR (4 secciones) =========
frame_barra = tk.Frame(tab_sim)
frame_barra.pack(fill="x", pady=10, padx=10)

for i in range(4):
    frame_barra.columnconfigure(i, weight=1)

# ----- SERIAL -----
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
listar_puertos()

# ----- ALGORITMO -----
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

# ----- CONTROL -----
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

# ----- SISTEMA -----
frame_estado = tk.LabelFrame(frame_barra, text="⏱️ Sistema", padx=10, pady=8, font=("Arial", 10, "bold"))
frame_estado.grid(row=0, column=3, sticky="nsew", padx=2, pady=2)
inner_estado = tk.Frame(frame_estado)
inner_estado.pack(expand=True, fill="both", padx=10)
tk.Label(inner_estado, text="Estado:", font=("Arial", 9, "bold")).pack(side="left")
lbl_estado = tk.Label(inner_estado, text="DISPONIBLE", bg="green", fg="white", width=10, font=("Arial", 9, "bold"))
lbl_estado.pack(side="left", padx=3)
tk.Label(inner_estado, text="|", font=("Arial", 14), fg="gray").pack(side="left", padx=5)
tk.Label(inner_estado, text="Hora:", font=("Arial", 9, "bold")).pack(side="left")
lbl_hora = tk.Label(inner_estado, text="00:00:00", font=("Consolas", 10))
lbl_hora.pack(side="left", padx=3)
tk.Label(inner_estado, text="|", font=("Arial", 14), fg="gray").pack(side="left", padx=5)
tk.Label(inner_estado, text="Fecha:", font=("Arial", 9, "bold")).pack(side="left")
lbl_fecha = tk.Label(inner_estado, text="16/02/2026", font=("Arial", 9))
lbl_fecha.pack(side="left", padx=3)

# ========= SEGUNDA FILA: PANEL DINÁMICO + RESUMEN =========
frame_segunda_fila = tk.Frame(tab_sim)
frame_segunda_fila.pack(fill="x", pady=5, padx=10)
frame_segunda_fila.columnconfigure(0, weight=2)
frame_segunda_fila.columnconfigure(1, weight=1)

# Panel dinámico (información del algoritmo)
frame_panel_dinamico = tk.LabelFrame(frame_segunda_fila, text="📊 Información del Algoritmo", 
                                      font=("Arial", 10, "bold"), padx=10, pady=10)
frame_panel_dinamico.grid(row=0, column=0, sticky="nsew", padx=(0,5))
frame_panel_dinamico.grid_propagate(False)
frame_panel_dinamico.config(width=550, height=130)

inner_algoritmo = tk.Frame(frame_panel_dinamico)
inner_algoritmo.pack(expand=True, fill="both", padx=5, pady=5)

def actualizar_panel_dinamico():
    for widget in inner_algoritmo.winfo_children():
        widget.destroy()
    
    algoritmo = algoritmo_var.get()
    
    inner_algoritmo.grid_rowconfigure(0, weight=1)
    inner_algoritmo.grid_rowconfigure(1, weight=1)
    
    if algoritmo == "zonas":
        tk.Label(inner_algoritmo, text="Zona activa:", font=("Arial", 9, "bold")).grid(row=0, column=0, sticky="w", padx=2, pady=2)
        for i in range(1, 6):
            rb = tk.Radiobutton(inner_algoritmo, text=f"Zona {i}",
                                variable=zona_var, value=i,
                                indicatoron=False, width=6,
                                font=("Arial", 8, "bold"),
                                command=cambiar_zona)
            rb.grid(row=0, column=i, padx=1, pady=2)
        
        ocupacion_zona = [0]*5
        total_zona = [0]*5
        for i in range(50):
            pos = i+1
            col = (pos-1) % 10
            zona = col // 2
            if estado_logico[i] != 0:
                ocupacion_zona[zona] += 1
            total_zona[zona] += 1
        
        texto_ocupacion = "Ocupación:                      "
        for z in range(5):
            porcentaje = (ocupacion_zona[z] / total_zona[z]) * 100 if total_zona[z] else 0
            texto_ocupacion += f"Zona {z+1}: {ocupacion_zona[z]}/{total_zona[z]} ({porcentaje:.0f}%)    "
        
        tk.Label(inner_algoritmo, text=texto_ocupacion.strip(), 
                font=("Arial", 9)).grid(row=1, column=0, columnspan=6, sticky="w", padx=2, pady=2)
    
    elif algoritmo == "producto":
        total_rojo = sum(1 for i in range(TOTAL_CELDAS) 
                        if 0 <= (i % ESPACIOS_X) <= 2 and estado_logico[i] != 0)
        total_rojo_max = 15
        pct_rojo = int((total_rojo / total_rojo_max) * 100)
        
        total_verde = sum(1 for i in range(TOTAL_CELDAS) 
                         if 3 <= (i % ESPACIOS_X) <= 5 and estado_logico[i] != 0)
        total_verde_max = 15
        pct_verde = int((total_verde / total_verde_max) * 100)
        
        total_azul = sum(1 for i in range(TOTAL_CELDAS) 
                        if 7 <= (i % ESPACIOS_X) <= 9 and estado_logico[i] != 0)
        total_azul_max = 15
        pct_azul = int((total_azul / total_azul_max) * 100)
        
        total_desc = sum(1 for i in range(TOTAL_CELDAS) 
                        if (i % ESPACIOS_X) == 6 and estado_logico[i] != 0)
        total_desc_max = 5
        pct_desc = int((total_desc / total_desc_max) * 100)
        
        tk.Label(inner_algoritmo, text="Cajas tipo de producto:   ", font=("Arial", 11, "bold")).grid(row=0, column=0, sticky="e", padx=2)
        tk.Label(inner_algoritmo, text="   ", font=("Arial", 12, "bold")).grid(row=0, column=1, sticky="e", padx=2)
        
        tk.Label(inner_algoritmo, text="●", fg="red", font=("Arial", 12)).grid(row=0, column=2, sticky="nsew", padx=2)
        tk.Label(inner_algoritmo, text=f"Rojo: {total_rojo}/{total_rojo_max} ({pct_rojo}%)", 
                font=("Arial", 8)).grid(row=0, column=3, sticky="w", padx=2)
        
        tk.Label(inner_algoritmo, text="              ", font=("Arial", 12, "bold")).grid(row=0, column=4, sticky="e", padx=2)
        
        tk.Label(inner_algoritmo, text="●", fg="green", font=("Arial", 12)).grid(row=0, column=5, sticky="nsew", padx=2)
        tk.Label(inner_algoritmo, text=f"Verde: {total_verde}/{total_verde_max} ({pct_verde}%)", 
                font=("Arial", 8)).grid(row=0, column=6, sticky="w", padx=2)
        
        tk.Label(inner_algoritmo, text="●", fg="blue",  font=("Arial", 12)).grid(row=1, column=2, sticky="nsew", padx=2)
        tk.Label(inner_algoritmo, text=f"Azul: {total_azul}/{total_azul_max} ({pct_azul}%)", 
                font=("Arial", 8)).grid(row=1, column=3, sticky="w", padx=2)
        
        tk.Label(inner_algoritmo, text="●", fg="yellow", font=("Arial", 12)).grid(row=1, column=5, sticky="nsew", padx=2)
        tk.Label(inner_algoritmo, text=f"Desconocido: {total_desc}/{total_desc_max} ({pct_desc}%)", 
                font=("Arial", 8)).grid(row=1, column=6, sticky="w", padx=2)
    
    elif algoritmo == "frecuencia":
        color_icons = {1: ("●", "red"), 2: ("●", "green"), 3: ("●", "blue")}
        color_names = {1: "Rojo", 2: "Verde", 3: "Azul"}
        
        tk.Label(inner_algoritmo, text="Color más requerido:     ", font=("Arial", 9, "bold")).grid(row=0, column=0, columnspan=6, sticky="w", padx=2, pady=2)
        
        col_start = 8
        for est in [1, 2, 3]:
            hist = list(historial[est])
            conteo = {1:0, 2:0, 3:0}
            for c in hist:
                if c in conteo:
                    conteo[c] += 1
            sorted_colors = sorted(conteo.items(), key=lambda x: x[1], reverse=True)
            if sorted_colors and sorted_colors[0][1] > 0:
                top1 = sorted_colors[0][0]
                icono, color = color_icons.get(top1, ("●", "black"))
                nombre = color_names.get(top1, "?")
            else:
                icono, color = ("●", "black")
                nombre = "?"
            
            tk.Label(inner_algoritmo, text=f"Estación {est}:", font=("Arial", 8, "bold")).grid(row=0, column=col_start+1, sticky="e", padx=2)
            tk.Label(inner_algoritmo, text="        ", font=("Arial", 12, "bold")).grid(row=0, column=col_start, sticky="e", padx=2)
            
            frame_icono = tk.Frame(inner_algoritmo)
            frame_icono.grid(row=0, column=col_start+2, sticky="w", padx=2)
            tk.Label(frame_icono, text=icono, fg=color, font=("Arial", 10)).pack(side="left")
            tk.Label(frame_icono, text=f" {nombre}", font=("Arial", 8)).pack(side="left")
            
            col_start += 3
        
        inner_algoritmo.grid_rowconfigure(2, weight=1)
        tk.Label(inner_algoritmo, text=f"Stock mínimo:                    {MIN_CAUSAS} cajas", 
                font=("Arial", 8, "bold")).grid(row=2, column=0, columnspan=6, sticky="w", padx=2, pady=2)

# Panel resumen del sistema
frame_resumen = tk.LabelFrame(frame_segunda_fila, text="📈 Resumen del Sistema", 
                                font=("Arial", 10, "bold"), padx=10, pady=10)
frame_resumen.grid(row=0, column=1, sticky="nsew", padx=(5,0))
frame_resumen.grid_propagate(False)
frame_resumen.config(width=350, height=130)

inner_resumen = tk.Frame(frame_resumen)
inner_resumen.pack(expand=True, fill="both", padx=5, pady=5)

for i in range(3):
    inner_resumen.columnconfigure(i, weight=1)
for i in range(2):
    inner_resumen.rowconfigure(i, weight=1)

lbl_ocup = tk.Label(inner_resumen, text="Ocupación: 0/50 (0%)", font=("Arial", 9), justify="center")
lbl_ocup.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

lbl_colores = tk.Label(inner_resumen, text="Cajas -> Rojo:0  Verde:0  Azul:0", font=("Arial", 9), justify="center")
lbl_colores.grid(row=0, column=1, sticky="nsew", padx=2, pady=2)

lbl_op = tk.Label(inner_resumen, text="Operación: IDLE", fg="blue", font=("Arial", 9, "bold"))
lbl_op.grid(row=0, column=2, sticky="nsew", padx=2, pady=2)

lbl_ciclos = tk.Label(inner_resumen, text="Ciclos: 0", justify="center", font=("Arial", 9))
lbl_ciclos.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)

lbl_tprom = tk.Label(inner_resumen, text="T ciclo promedio: 0.0 s", justify="center", font=("Arial", 9))
lbl_tprom.grid(row=1, column=1, sticky="nsew", padx=2, pady=2)

lbl_rate = tk.Label(inner_resumen, text="Throughput: 0/min", justify="center", font=("Arial", 9))
lbl_rate.grid(row=1, column=2, sticky="nsew", padx=2, pady=2)

# ===================== GRID =================
frame_fila3 = tk.Frame(tab_sim)
frame_fila3.pack(fill="both", expand=True, pady=2)

frame_grid_container = tk.LabelFrame(frame_fila3, text="📦 ALMACÉN - 50 CELDAS", padx=10, pady=10, font=("Arial", 10, "bold"))
frame_grid_container.pack(side="left", padx=2, fill="both", expand=True)

frame_grid_centrado = tk.Frame(frame_grid_container)
frame_grid_centrado.pack(expand=True)

# Grid de celdas
frame_grid = tk.Frame(frame_grid_centrado, bg="lightgray")
frame_grid.pack(pady=5)

crear_grid(frame_grid)

# ========= FILA ADICIONAL PARA ESTACIONES =========
# Crear una fila extra (fila 5+1 = 6) debajo del grid para las estaciones
for c in range(COLUMNAS):
    
    # Estación 1 debajo de celda 2 (columna 1)
    if c == 1:  # Celda 2
        lbl_est = tk.Label(
            frame_grid,
            text="E1",
            width=6,
            height=3,
            bg="red",
            fg="white",
            relief="ridge",
            font=("Arial", 10, "bold")
        )
        lbl_est.grid(row=FILAS, column=c, padx=1, pady=1)
        lbl_estaciones[1] = lbl_est
    
    # Estación 2 debajo de celda 5 (columna 4)
    elif c == 4:  # Celda 5
        lbl_est = tk.Label(
            frame_grid,
            text="E2",
            width=6,
            height=3,
            bg="red",
            fg="white",
            relief="ridge",
            font=("Arial", 10, "bold")
        )
        lbl_est.grid(row=FILAS, column=c, padx=1, pady=1)
        lbl_estaciones[2] = lbl_est
    
    # Estación 3 debajo de celda 9 (columna 8)
    elif c == 8:  # Celda 9
        lbl_est = tk.Label(
            frame_grid,
            text="E3",
            width=6,
            height=3,
            bg="red",
            fg="white",
            relief="ridge",
            font=("Arial", 10, "bold")
        )
        lbl_est.grid(row=FILAS, column=c, padx=1, pady=1)
        lbl_estaciones[3] = lbl_est
    
    # Celdas vacías en las otras posiciones (para mantener alineación)
    else:
        tk.Label(frame_grid, text="", width=6, height=3, bg="lightgray", relief="flat").grid(row=FILAS, column=c, padx=1, pady=1)

# ========= LEYENDAS DEL GRID =========
frame_leyendas_container = tk.Frame(frame_grid_container)
frame_leyendas_container.pack(side="bottom", anchor="sw", pady=10, fill="x")

# Marco principal para las leyendas (una sola fila)
frame_leyendas = tk.Frame(frame_leyendas_container, bg="lightgray", relief="groove", bd=1)
frame_leyendas.pack(fill="x")

# Crear dos columnas: izquierda para celdas, derecha para estaciones
frame_leyendas.columnconfigure(0, weight=1)  # Columna izquierda (celdas)
frame_leyendas.columnconfigure(1, weight=1)  # Columna derecha (estaciones)

# ----- COLUMNA IZQUIERDA: LEYENDAS DE CELDAS -----
frame_celdas = tk.Frame(frame_leyendas, bg="lightgray")
frame_celdas.grid(row=0, column=0, sticky="w", padx=10, pady=5)

tk.Label(frame_celdas, text="Celdas:", font=("Arial", 9, "bold"), bg="lightgray").pack(anchor="w")

frame_muestras_celdas = tk.Frame(frame_celdas, bg="lightgray")
frame_muestras_celdas.pack(fill="x", pady=2)

celdas_leyendas = [
    ("Vacía", "gray", "black"),
    ("Caja Rojo ", "red", "white"),
    ("Caja Verde", "green", "white"),
    ("Caja Azul ", "blue", "white"),
    ("Caja Desc.", "yellow", "black")
]

for texto, bg_color, fg_color in celdas_leyendas:
    lbl = tk.Label(frame_muestras_celdas, text=texto, bg=bg_color, fg=fg_color,
                   width=10, font=("Arial", 8, "bold"), relief="ridge", padx=2)
    lbl.pack(side="left", padx=2, pady=2)

# ----- COLUMNA DERECHA: LEYENDAS DE ESTACIONES -----
frame_estaciones_leyenda = tk.Frame(frame_leyendas, bg="lightgray")
frame_estaciones_leyenda.grid(row=0, column=1, sticky="e", padx=10, pady=5)

tk.Label(frame_estaciones_leyenda, text="Estaciones:", font=("Arial", 9, "bold"), bg="lightgray").pack(anchor="w")

frame_muestras_estaciones = tk.Frame(frame_estaciones_leyenda, bg="lightgray")
frame_muestras_estaciones.pack(fill="x", pady=2)

estados_leyendas = [
    ("Movimiento", "green", "white"),
    ("Espera", "red", "white")
]

for texto, bg_color, fg_color in estados_leyendas:
    lbl = tk.Label(frame_muestras_estaciones, text=texto, bg=bg_color, fg=fg_color,
                   width=10, font=("Arial", 8, "bold"), relief="ridge", padx=2)
    lbl.pack(side="left", padx=2, pady=2)

# Columna derecha: LISTA INSTRUCCIONES + LOG
frame_derecha_fila3 = tk.Frame(frame_fila3, width=280)
frame_derecha_fila3.pack(side="left", padx=2, fill="both", expand=False)
frame_derecha_fila3.pack_propagate(False)

# LISTA DE INSTRUCCIONES
frame_lista_container = tk.LabelFrame(frame_derecha_fila3, text="📋 LISTA DE INSTRUCCIONES", font=("Arial", 10, "bold"))
frame_lista_container.pack(fill="both", expand=True, pady=(0,2))

btn_limpiar_lista = tk.Button(frame_lista_container, text="Limpiar lista", font=("Arial", 8), width=12, command=limpiar_lista)
btn_limpiar_lista.pack(anchor="ne", padx=5, pady=5)

frame_progreso = tk.Frame(frame_lista_container)
frame_progreso.pack(fill="x", padx=5, pady=2)
frame_progreso.pack_forget()  # Ocultar inicialmente

progress_bar = ttk.Progressbar(frame_progreso, length=200, mode='determinate')
progress_bar.pack(side="left", padx=5)

progress_label = tk.Label(frame_progreso, text="0%", font=("Arial", 8))
progress_label.pack(side="left", padx=5)

text_instr = tk.Text(frame_lista_container, height=14, font=("Consolas", 9), wrap=tk.WORD)
text_instr.pack(fill="both", expand=True, padx=5, pady=5)

# REGISTRO DE EVENTOS
frame_log_container = tk.LabelFrame(frame_derecha_fila3, text="📜 REGISTRO DE EVENTOS", font=("Arial", 10, "bold"))
frame_log_container.pack(fill="both", expand=True, pady=(2,0))

frame_log_tools = tk.Frame(frame_log_container)
frame_log_tools.pack(fill="x", pady=2)

btn_limpiar_log = tk.Button(frame_log_tools, text="Limpiar log", font=("Arial", 8), width=10, command=limpiar_log)
btn_limpiar_log.pack(side="left", padx=2)

btn_copiar_log = tk.Button(frame_log_tools, text="Copiar log", font=("Arial", 8), width=10, command=copiar_log)
btn_copiar_log.pack(side="left", padx=2)

text_log = tk.Text(frame_log_container, height=10, font=("Consolas", 8), wrap=tk.WORD)
text_log.pack(fill="both", expand=True, padx=5, pady=5)

scroll_log = tk.Scrollbar(text_log)
scroll_log.pack(side="right", fill="y")
text_log.config(yscrollcommand=scroll_log.set)
scroll_log.config(command=text_log.yview)

# ================= TAB CONFIGURACIÓN =================
tab_config.grid_rowconfigure(1, weight=1)
tab_config.grid_columnconfigure(0, weight=2)
tab_config.grid_columnconfigure(1, weight=2)
tab_config.grid_columnconfigure(2, weight=3)

frame_general = tk.LabelFrame(tab_config, text="Configuraciones generales", height=80, font=("TkDefaultFont", 10, "bold"))
frame_general.grid(row=0, column=0, columnspan=3, sticky="ew", padx=10, pady=10)

frame_gen = tk.LabelFrame(tab_config, text="Generador de instrucciones", font=("TkDefaultFont", 10, "bold"))
frame_gen.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=10, pady=10)

frame_gen.grid_columnconfigure(0, weight=2)
frame_gen.grid_columnconfigure(1, weight=2)
frame_gen.grid_columnconfigure(2, weight=3)

# COLUMNA 1 → MANUAL
frame_manual = tk.LabelFrame(frame_gen, text="Instrucción manual", font=("TkDefaultFont", 10, "bold"))
frame_manual.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
frame_manual.grid_columnconfigure(1, weight=1)

tk.Label(frame_manual, text="Instrucción:", font=("TkDefaultFont", 9, "bold")).grid(row=0, column=0, sticky="w", pady=4)
tipo_instr_var = tk.StringVar(value="carga")
ttk.Combobox(frame_manual, textvariable=tipo_instr_var, values=["Carga", "Descarga"], state="readonly").grid(row=0, column=1, sticky="ew")

tk.Label(frame_manual, text="N° Estación:", font=("TkDefaultFont", 9, "bold")).grid(row=1, column=0, sticky="w", pady=4)
entry_est_manual = tk.Entry(frame_manual)
entry_est_manual.grid(row=1, column=1, sticky="ew")

tk.Label(frame_manual, text="Color de caja:", font=("TkDefaultFont", 9, "bold")).grid(row=2, column=0, sticky="w", pady=4)
color_manual_var = tk.StringVar(value="Rojo")
ttk.Combobox(frame_manual, textvariable=color_manual_var, values=["Rojo", "Verde", "Azul"], state="readonly").grid(row=2, column=1, sticky="ew")

tk.Button(frame_manual, text="Agregar instrucción", command=agregar_instruccion).grid(row=3, column=0, columnspan=2, sticky="ew", pady=6)
tk.Button(frame_manual, text="Eliminar última instrucción", command=eliminar_ultima).grid(row=4, column=0, columnspan=2, sticky="ew")

# COLUMNA 2 → ALEATORIAS
frame_rand = tk.LabelFrame(frame_gen, text="Instrucciones aleatorias", font=("TkDefaultFont", 10, "bold"))
frame_rand.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
frame_rand.grid_columnconfigure(1, weight=1)

tk.Label(frame_rand, text="Cantidad:").grid(row=0, column=0, sticky="w")
entry_cantidad = tk.Entry(frame_rand)
entry_cantidad.grid(row=0, column=1, sticky="ew")
tk.Button(frame_rand, text="Generar lista", command=generar_lista_random).grid(row=1, column=0, columnspan=2, sticky="ew", pady=6)

# COLUMNA 3 → VISOR
frame_lista = tk.LabelFrame(frame_gen, text="Lista de instrucciones", font=("TkDefaultFont", 10, "bold"))
frame_lista.grid(row=0, column=2, sticky="nsew", padx=10, pady=10)
frame_lista.grid_rowconfigure(0, weight=1)
frame_lista.grid_columnconfigure(0, weight=1)

text_lista_config = tk.Text(frame_lista)
text_lista_config.grid(row=0, column=0, sticky="nsew")

# ================= MAIN =================
cargar_estado()
root.protocol("WM_DELETE_WINDOW", cerrar_programa)
actualizar_reloj()
actualizar_panel_dinamico()
root.mainloop()