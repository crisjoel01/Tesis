import sys
import serial
import time
import threading
import datetime
from serial.tools import list_ports
from collections import deque
import tkinter as tk
from tkinter import ttk
combo_puertos = ttk.Combobox
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
    1: 52,
    2: 52,
    3: 57
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
zona_frecuente_color = {
    1: None,
    2: None,
    3: None
}


# ====== zonas físicas ======
ZONAS_FRECUENTES = {
    3: [8,9,10,18,19,20],
    2: [4,5,6,14,15,16],
    1: [1,2,3,11,12,13]
}

ZONA_NEUTRA = [7,17] + list(range(21,31))
ZONA_MENOS_FRECUENTE   = list(range(31,51))

# ====== guardar estado ======
def guardar_estado():

    data = {
        "presencia": presencia,
        "color": color,
        "estado_logico": estado_logico,
        "lista_instrucciones": lista_instrucciones,
        "zona_frecuente_color": zona_frecuente_color,
        "historial": {k: list(v) for k, v in historial.items()}
    }

    with open(ARCHIVO_ESTADO, "w") as f:
        json.dump(data, f)

    log("💾 Estado guardado")

def cargar_estado():

    global lista_instrucciones
    global zona_frecuente_color, historial

    if not os.path.exists(ARCHIVO_ESTADO):
        return

    with open(ARCHIVO_ESTADO, "r") as f:
        data = json.load(f)

    presencia[:] = data["presencia"]
    color[:] = data["color"]
    estado_logico[:] = data["estado_logico"]

    lista_instrucciones[:] = [tuple(x) for x in data["lista_instrucciones"]]

    zona_frecuente_color.update(data["zona_frecuente_color"])

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
    global pos_actual_x, pos_actual_y

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



def ciclo_descarga(estacion, color_solicitado):
    global pos_actual_x, pos_actual_y

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

    lider_actual = zona_frecuente_color[est]
    nuevo_lider  = ranking[0]

    # aplicar histéresis
    if lider_actual is None:
        zona_frecuente_color[est] = nuevo_lider
        log(f"Estación {est} -> líder inicial {nuevo_lider}")
        return

    # ---------- HISTÉRESIS ----------
    conteo = {1:0, 2:0, 3:0}
    for c in historial[est]:
        conteo[c] += 1

    if conteo[nuevo_lider] >= conteo[lider_actual] + HISTERESIS:
        zona_frecuente_color[est] = nuevo_lider
        log(f"Estación {est} -> nueva zona frecuente color {nuevo_lider}")

    ##actualizar_panel_frecuencia()

# Selección principal de celda
def buscar_por_frecuencia(estacion, color_objetivo, x0, y0):

    if color_objetivo not in (1,2,3):
        return None

    # 1) ZONAS FRECUENTES DEL COLOR con menos de MIN_CAUSAS
    for est, celdas in ZONAS_FRECUENTES.items():

        if zona_frecuente_color[est] == color_objetivo:

            if contar_color_en_zona(celdas, color_objetivo) < MIN_CAUSAS:
                pos = mejor_libre_en_lista(celdas, x0, y0)
                if pos:
                    log(f"Frecuencia -> mínimo zona {est} -> {pos}")
                    return pos

    # 2) ZONAS FRECUENTES DEL COLOR normales
    for est, celdas in ZONAS_FRECUENTES.items():

        if zona_frecuente_color[est] == color_objetivo:
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

        lbl_serial.config(text="CONECTADO", bg="green")
        btn_serial.config(text="Desconectar")
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
    lbl_serial.config(text="DESCONECTADO", bg="red")
    btn_serial.config(text="Conectar")
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
        lbl_estado.config(text="EJECUTADO", bg="green")
    else:
        lbl_estado.config(text="EN ESPERA", bg="red")


def cambiar_zona():
    global ZONA_ACTIVA
    ZONA_ACTIVA = zona_var.get()
    log(f"Zona activa -> {ZONA_ACTIVA}")


def cambiar_algoritmo():
    global ALGORITMO_ACTUAL
    ALGORITMO_ACTUAL = algoritmo_var.get()
    log(f"Algoritmo -> {ALGORITMO_ACTUAL}")
    
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

    for k in zona_frecuente_color:
        zona_frecuente_color[k] = None

    # limpiar instrucciones pendientes
    lista_instrucciones.clear()

    actualizar_grid()
    actualizar_textbox_instrucciones()
    guardar_estado()

    log("🧹 Grid reseteado → almacén vacío")

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
frame_barra.pack(fill="x", pady=10)


# -------- SERIAL --------
frame_serial = tk.LabelFrame(frame_barra, text="Serial", padx=10, pady=5)
frame_serial.pack(side="left", padx=10)

combo_puertos = ttk.Combobox(frame_serial, width=8)
combo_puertos.pack(side="left", padx=5)

btn_serial = tk.Button(frame_serial, text="Conectar", command=toggle_serial)
btn_serial.pack(side="left", padx=5)

tk.Button(frame_serial, text="↻", width=3, command=listar_puertos).pack(side="left", padx=3)


lbl_serial = tk.Label(frame_serial, text="DESCONECTADO",
                      bg="red", fg="white", width=12)
lbl_serial.pack(side="left", padx=5)

listar_puertos()


# -------- ALGORITMO --------
frame_alg = tk.LabelFrame(frame_barra, text="Algoritmo", padx=10, pady=5)
frame_alg.pack(side="left", padx=20)

algoritmo_var = tk.StringVar(value="zonas")

tk.Radiobutton(frame_alg, text="Zonas",
               variable=algoritmo_var, value="zonas",
               command=cambiar_algoritmo).pack(side="left")

tk.Radiobutton(frame_alg, text="Producto",
               variable=algoritmo_var, value="producto",
               command=cambiar_algoritmo).pack(side="left")

tk.Radiobutton(frame_alg, text="Frecuencia",
               variable=algoritmo_var, value="frecuencia",
               command=cambiar_algoritmo).pack(side="left")


# -------- ESTADO --------
frame_estado = tk.Frame(frame_barra)
frame_estado.pack(side="right", padx=20)

tk.Label(frame_estado, text="Estado:", font=("Arial", 10)).pack(side="left", padx=(0,5))

lbl_estado = tk.Label(frame_estado,
                      text="EN ESPERA",
                      bg="red",
                      fg="white",
                      width=12,
                      font=("Arial", 10, "bold"))
lbl_estado.pack(side="left")



# ====================================================
# ============ ACCIONES (segunda fila) ===============
# ====================================================

frame_controles = tk.Frame(tab_sim)
frame_controles.pack(pady=5)

frame_instr = tk.LabelFrame(tab_sim, text="Instrucciones")
frame_instr.pack(side="right", fill="y", padx=10, pady=10)

text_instr = tk.Text(frame_instr, width=40, height=25)
text_instr.pack()

tk.Button(frame_instr, text="Actualizar",
          command=actualizar_textbox_instrucciones).pack(pady=3)

tk.Button(frame_instr, text="Ejecutar lista",
          command=ejecutar_lista).pack(pady=3)

tk.Button(frame_instr, text="RESET GRID", command=reset_grid).pack(pady=3)



# -------- ZONAS (YA NO EN PRIMERA FILA) --------
frame_zona = tk.LabelFrame(frame_controles, text="Zona activa", padx=10, pady=5)
frame_zona.pack(side="left", padx=10)

for i in range(1, 6):
    tk.Radiobutton(
        frame_zona,
        text=f"Zona {i}",
        indicatoron=False,
        width=7,
        variable=zona_var,
        value=i,
        command=cambiar_zona
    ).pack(side="left", padx=2)


# -------- ACCIÓN --------
accion_var = tk.StringVar(value="carga")

frame_accion = tk.LabelFrame(frame_controles, text="Acción", padx=10, pady=5)
frame_accion.pack(side="left", padx=10)

tk.Radiobutton(frame_accion, text="Carga",
               variable=accion_var, value="carga").pack(side="left")

tk.Radiobutton(frame_accion, text="Descarga",
               variable=accion_var, value="descarga").pack(side="left")


# -------- ESTACIÓN --------
frame_est = tk.LabelFrame(frame_controles, text="Estación", padx=10, pady=5)
frame_est.pack(side="left", padx=10)

entry_est = tk.Entry(frame_est, width=5)
entry_est.pack()


# -------- COLOR --------
color_var = tk.IntVar(value=1)

frame_color = tk.LabelFrame(frame_controles, text="Color", padx=10, pady=5)
frame_color.pack(side="left", padx=10)

tk.Radiobutton(frame_color, text="Rojo", bg="red",
               variable=color_var, value=1).pack(side="left")

tk.Radiobutton(frame_color, text="Verde", bg="green",
               variable=color_var, value=2).pack(side="left")

tk.Radiobutton(frame_color, text="Azul", bg="blue",
               variable=color_var, value=3).pack(side="left")


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
root.mainloop()




