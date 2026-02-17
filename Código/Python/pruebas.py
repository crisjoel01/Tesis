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
    3: 50,
    2: 50,
    1: 57
}

X_ESTACIONES_MM = {
    3: 163,
    2: 165 + 465,
    1: 170 + 465 + 610
}

ALTURAS_MM = [160, 155, 157.5, 155, 155]

ALGORITMO_ACTUAL = "zonas"

ocupado = False

lista_instrucciones = []


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

ranking_colores = {
    1: {1: 1, 2: 2, 3: 3},  # Inicial: Rojo=1, Verde=2, Azul=3
    2: {1: 1, 2: 2, 3: 3},
    3: {1: 1, 2: 2, 3: 3}
}

# ====== zonas físicas ======
ZONAS_FRECUENTES = {
    1: [8,9,10,18,19,20],
    2: [4,5,6,14,15,16],
    3: [1,2,3,11,12,13]
}

ZONA_NEUTRA = [7,17] + list(range(21,31))
ZONA_BAJA   = list(range(31,51))


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
    
    if color_detectado in (1, 2, 3):
        # Verificar si el storage está completamente vacío
        storage_vacio = all(p == 0 for p in presencia)
        
        if storage_vacio:
            # Primera carga en storage vacío
            # Este color será índice 1 en su estación
            ranking_colores[estacion][color_detectado] = 1
            
            # Los otros dos colores serán índice 2 y 3 (orden inicial)
            otros_colores = [c for c in [1, 2, 3] if c != color_detectado]
            ranking_colores[estacion][otros_colores[0]] = 2
            ranking_colores[estacion][otros_colores[1]] = 3
            
            # Actualizar zona_frecuente_color para compatibilidad
            zona_frecuente_color[estacion] = color_detectado
            
            log(f"INICIALIZACIÓN: Estación {estacion} - {color_detectado}=índice1")
    
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
        return buscar_por_frecuencia(estacion, color_detectado)

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

# Verificar si una caja puede ir a una zona frecuente
def puede_ir_a_zona_frecuente(zona_estacion, color_caja):
    """
    Verifica si una caja de 'color_caja' puede ir a zona frecuente 'zona_estacion'
    Regla: Cada zona frecuente solo acepta su color índice 1
    """
    # Obtener color líder de esta zona (índice 1)
    color_lider = None
    for color_id, indice in ranking_colores[zona_estacion].items():
        if indice == 1:
            color_lider = color_id
            break
    
    # Si no hay líder asignado, no acepta nada
    if color_lider is None:
        return False
    
    # La caja debe ser del MISMO color que el líder de la zona
    return color_caja == color_lider

# Obtener índice de un color para una estación =====
def obtener_indice_color(estacion, color_caja):
    """Retorna el índice (1,2,3) de un color para una estación"""
    return ranking_colores[estacion].get(color_caja, 3)

def actualizar_frecuencia(estacion, color_descargado):
    """
    Actualiza historial y recalcula índices basado en DESCARGAS
    Mantiene compatibilidad con la función original pero añade ranking completo
    """
    # 1. Guardar en historial (solo descargas)
    historial[estacion].append(color_descargado)
    
    # 2. Recalcular índices basado en historial de DESCARGAS
    actualizar_indices_por_descargas(estacion)
    
    log(f"Frecuencia actualizada - Estación {estacion} descargó {color_descargado}")

def actualizar_indices_por_descargas(estacion):
    """
    Recalcula índices 1,2,3 basado en historial de descargas
    """
    hist = list(historial[estacion])  # Últimas 20 descargas
    
    if len(hist) < 1:
        return  # No hay suficientes datos
    
    # Contar frecuencia de descargas
    conteo = {1: 0, 2: 0, 3: 0}
    for color_desc in hist:
        conteo[color_desc] += 1
    
    # Ordenar colores por frecuencia (más frecuente primero)
    colores_ordenados = sorted(conteo.items(), key=lambda x: x[1], reverse=True)
    
    # Asignar nuevos índices
    # Índice 1 = más frecuente, Índice 3 = menos frecuente
    for idx, (color_id, _) in enumerate(colores_ordenados):
        ranking_colores[estacion][color_id] = idx + 1
    
    # Asignar índices a colores que no aparecieron en historial
    for color_id in [1, 2, 3]:
        if color_id not in [c for c, _ in colores_ordenados]:
            ranking_colores[estacion][color_id] = 3  # Menor prioridad
    
    # Actualizar color líder para zona frecuente (compatibilidad)
    if colores_ordenados:
        nuevo_lider = colores_ordenados[0][0]
        
        # Verificar histéresis si hay líder anterior
        lider_actual = zona_frecuente_color[estacion]
        if lider_actual is None:
            zona_frecuente_color[estacion] = nuevo_lider
        elif lider_actual != nuevo_lider:
            if conteo[nuevo_lider] >= conteo[lider_actual] + HISTERESIS:
                zona_frecuente_color[estacion] = nuevo_lider
                log(f"Estación {estacion}: nuevo líder {nuevo_lider} (histéresis)")
    
    # Log de cambios
    log(f"Estación {estacion} índices: Rojo={ranking_colores[estacion][1]}, Verde={ranking_colores[estacion][2]}, Azul={ranking_colores[estacion][3]}")

def buscar_celda_mas_cercana_en_zonas(zonas_lista, x_ref, y_ref):
    """
    Busca la celda libre más cercana en una lista de zonas
    """
    mejor_pos = None
    mejor_dist = float('inf')
    
    for zona in zonas_lista:
        for pos_celda in zona:
            if estado_logico[pos_celda-1] == 0:  # Celda libre
                dist = distancia_mm_pos(pos_celda, x_ref, y_ref)
                if dist < mejor_dist:
                    mejor_dist = dist
                    mejor_pos = pos_celda
    
    return mejor_pos

# Selección principal de celda
def buscar_por_frecuencia(estacion_origen, color_caja):
    """
    Implementa TODAS las reglas del algoritmo por frecuencia
    """
    if color_caja not in (1, 2, 3):
        log(f"Color {color_caja} no válido para algoritmo frecuencia")
        return None
    
    # Obtener coordenadas de la estación de origen
    x_est, y_est = coords_estacion(estacion_origen)
    
    # Obtener índice de este color para ESTA estación
    indice = obtener_indice_color(estacion_origen, color_caja)
    log(f"Frecuencia: Estación {estacion_origen}, Color {color_caja}, Índice {indice}")
    
    # ===== REGLA 1: MIN_CAUSAS (PRIORIDAD ABSOLUTA) =====
    for zona_id, celdas in ZONAS_FRECUENTES.items():
        # Verificar si en esta zona, el color_caja es índice 1
        if obtener_indice_color(zona_id, color_caja) == 1:
            cajas_en_zona = contar_color_en_zona(celdas, color_caja)
            if cajas_en_zona < MIN_CAUSAS:
                pos = mejor_libre_en_lista(celdas, x_est, y_est)
                if pos:
                    log(f"MIN_CAUSAS -> zona {zona_id} (solo {cajas_en_zona} cajas)")
                    return pos
    
    # ===== PREPARAR LISTAS DE ZONAS PERMITIDAS SEGÚN ÍNDICE =====
    zonas_a_considerar = []
    
    if indice == 1:
        # ÍNDICE 1: puede ir a su zona, otras zonas, neutra, baja
        # Su propia zona frecuente (si puede)
        if puede_ir_a_zona_frecuente(estacion_origen, color_caja):
            zonas_a_considerar.append(ZONAS_FRECUENTES[estacion_origen])
        
        # Otras zonas frecuentes (si mismo color)
        for zona_id, celdas in ZONAS_FRECUENTES.items():
            if zona_id != estacion_origen and puede_ir_a_zona_frecuente(zona_id, color_caja):
                zonas_a_considerar.append(celdas)
        
        # Zona neutra y baja
        zonas_a_considerar.append(ZONA_NEUTRA)
        zonas_a_considerar.append(ZONA_BAJA)
        
    elif indice == 2:
        # ÍNDICE 2: NO puede ir a su zona, sí a otras, sí a neutra, sí a baja
        # Otras zonas frecuentes (si mismo color)
        for zona_id, celdas in ZONAS_FRECUENTES.items():
            if zona_id != estacion_origen and puede_ir_a_zona_frecuente(zona_id, color_caja):
                zonas_a_considerar.append(celdas)
        
        # Zona neutra y baja
        zonas_a_considerar.append(ZONA_NEUTRA)
        zonas_a_considerar.append(ZONA_BAJA)
        
    else:  # indice == 3
        # ÍNDICE 3: NO puede ir a su zona, sí a otras, NO a neutra, sí a baja
        # Otras zonas frecuentes (si mismo color)
        for zona_id, celdas in ZONAS_FRECUENTES.items():
            if zona_id != estacion_origen and puede_ir_a_zona_frecuente(zona_id, color_caja):
                zonas_a_considerar.append(celdas)
        
        # Solo zona baja
        zonas_a_considerar.append(ZONA_BAJA)
    
    # ===== BUSCAR CELDA MÁS CERCANA ENTRE ZONAS PERMITIDAS =====
    mejor_pos = None
    mejor_dist = float('inf')
    
    for zona in zonas_a_considerar:
        for pos_celda in zona:
            if estado_logico[pos_celda-1] == 0:  # Celda libre
                dist = distancia_mm_pos(pos_celda, x_est, y_est)
                if dist < mejor_dist:
                    mejor_dist = dist
                    mejor_pos = pos_celda
    
    if mejor_pos:
        # Identificar en qué zona se encontró
        if mejor_pos in ZONA_BAJA:
            zona_tipo = "BAJA"
        elif mejor_pos in ZONA_NEUTRA:
            zona_tipo = "NEUTRA"
        else:
            # Encontrar en qué zona frecuente
            for zona_id, celdas in ZONAS_FRECUENTES.items():
                if mejor_pos in celdas:
                    zona_tipo = f"FRECUENTE {zona_id}"
                    break
            else:
                zona_tipo = "DESCONOCIDA"
        
        log(f"Frecuencia -> {zona_tipo} -> celda {mejor_pos} (distancia: {mejor_dist:.1f}mm)")
        return mejor_pos
    
    # Si no encontró espacio
    log(f"Frecuencia -> SIN ESPACIO para color {color_caja} (índice {indice})")
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

# ================= HMI ==================
# ========================================
# ========================================

# ====================================================
# ===================== UI ===========================
# ====================================================

root = tk.Tk()
root.title("HMI TESIS SISTEMA AUTOMATIZADO DE ALMACENAMIENTO")
root.state("zoomed")
root.resizable(True, True)

# Variables de control
zona_var = tk.IntVar(value=1)
algoritmo_var = tk.StringVar(value="zonas")
tipo_instr_var = tk.StringVar(value="carga")
color_manual_var = tk.StringVar(value="Rojo")

# Variables de estado del sistema
estado_sistema = {
    "estado": "DESCONECTADO",
    "color": "red",
    "mensaje": "",
    "timestamp": None
}

# ================= NOTEBOOK (PESTAÑAS) =================
notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True)

tab_sim = tk.Frame(notebook)
tab_config = tk.Frame(notebook)
tab_stats = tk.Frame(notebook)

notebook.add(tab_sim, text="Simulación")
notebook.add(tab_config, text="Configuración")
notebook.add(tab_stats, text="Estadísticas")

# ====================================================
# ========= DEFINICIONES DEL GRID ===================
# ====================================================
FILAS = 5
COLUMNAS = 10
celdas_ui = []

def crear_grid(parent):
    """Crea el grid de 5x10 celdas"""
    for r in range(FILAS):
        for c in range(COLUMNAS):
            lbl = tk.Label(
                parent,
                width=4,
                height=2,
                bg="gray",
                relief="ridge",
                font=("Arial", 7)
            )
            lbl.grid(row=FILAS-1-r, column=c, padx=2, pady=2)
            celdas_ui.append(lbl)

def color_celda(v):
    """Retorna color según estado lógico"""
    colores = {
        0: "gray",
        1: "red",
        2: "green",
        3: "blue",
        4: "yellow"
    }
    return colores.get(v, "black")

def zona_por_pos(pos):
    """Calcula zona (1-5) según posición de celda"""
    col = (pos - 1) % ESPACIOS_X
    return (col // 2) + 1

# ====================================================
# ========= FUNCIONES ================================
# ====================================================

def log(msg):
    t = datetime.datetime.now().strftime("%H:%M:%S")
    text_log.insert(tk.END, f"[{t}] {msg}\n")
    text_log.see(tk.END)
    print(f"[{t}] {msg}")

def actualizar_reloj():
    lbl_tiempo.config(text=datetime.datetime.now().strftime("%H:%M:%S"))
    root.after(1000, actualizar_reloj)

def actualizar_variables_tiempo_real():
    celdas_ocupadas = sum(1 for v in estado_logico if v != 0)
    porc_ocupacion = int((celdas_ocupadas / TOTAL_CELDAS) * 100)
    lbl_ocupacion.config(text=f"{porc_ocupacion}% ({celdas_ocupadas}/50 celdas)")
    
    r = sum(1 for v in estado_logico if v == 1)
    v = sum(1 for v in estado_logico if v == 2)
    a = sum(1 for v in estado_logico if v == 3)
    d = sum(1 for v in estado_logico if v == 4)
    lbl_por_color.config(text=f"Rojo:{r} Verde:{v} Azul:{a} Desc:{d}")
    
    # Actualizar tiempo ciclo y distancia (valores de ejemplo)
    lbl_tiempo_ciclo.config(text=f"0.0s")
    lbl_distancia.config(text=f"0.0m")
    
    root.after(1000, actualizar_variables_tiempo_real)

tiempo_inicio_simulacion = datetime.datetime.now()

def actualizar_tiempo_simulacion():
    delta = datetime.datetime.now() - tiempo_inicio_simulacion
    horas = int(delta.total_seconds() // 3600)
    minutos = int((delta.total_seconds() % 3600) // 60)
    segundos = int(delta.total_seconds() % 60)
    lbl_tiempo_simulacion.config(text=f"{horas:02d}:{minutos:02d}:{segundos:02d}")
    root.after(1000, actualizar_tiempo_simulacion)

def actualizar_grid():
    for i, valor in enumerate(estado_logico):
        if i < len(celdas_ui):
            celdas_ui[i].config(bg=color_celda(valor), text=str(i+1))

def cambiar_zona():
    global ZONA_ACTIVA
    ZONA_ACTIVA = zona_var.get()
    log(f"Zona activa cambiada a Zona {ZONA_ACTIVA}")
    actualizar_panel_algoritmo()

def cambiar_algoritmo():
    global ALGORITMO_ACTUAL
    ALGORITMO_ACTUAL = algoritmo_var.get()
    log(f"Algoritmo cambiado a: {ALGORITMO_ACTUAL}")
    actualizar_panel_algoritmo()

def actualizar_textbox_instrucciones():
    text_instr.delete("1.0", tk.END)
    for i, (tipo, est, col) in enumerate(lista_instrucciones, start=1):
        if tipo == "carga":
            linea = f"{i}. CARGA   -> Estación {est}"
        else:
            colores = {1:"Rojo", 2:"Verde", 3:"Azul"}
            linea = f"{i}. DESCARGA -> Estación {est} ({colores[col]})"
        text_instr.insert(tk.END, linea + "\n")

def actualizar_lista_ui():
    text_lista.delete("1.0", tk.END)
    for i, (tipo, est, col) in enumerate(lista_instrucciones, start=1):
        if tipo == "carga":
            texto = f"{i}. CARGA   -> Estación {est}"
        else:
            colores = {1: "Rojo", 2: "Verde", 3: "Azul"}
            texto = f"{i}. DESCARGA -> Estación {est} ({colores[col]})"
        text_lista.insert(tk.END, texto + "\n")

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
        actualizar_textbox_instrucciones()
        log(f"Lista aleatoria generada: {n} instrucciones")
    except:
        messagebox.showerror("Error", "Cantidad inválida")

def agregar_instruccion():
    try:
        tipo = tipo_instr_var.get().lower()
        est = int(entry_est_manual.get())
        color_texto = color_manual_var.get()
        color_map = {"Rojo": 1, "Verde": 2, "Azul": 3}
        col = color_map.get(color_texto, 1)
        lista_instrucciones.append((tipo, est, col))
        actualizar_lista_ui()
        actualizar_textbox_instrucciones()
        log(f"Instrucción agregada: {tipo} Est.{est} Color {color_texto}")
    except:
        messagebox.showerror("Error", "Datos inválidos")

def eliminar_ultima():
    if lista_instrucciones:
        ultima = lista_instrucciones.pop()
        actualizar_lista_ui()
        actualizar_textbox_instrucciones()
        log("Última instrucción eliminada")

def limpiar_log():
    text_log.delete("1.0", tk.END)
    log("Log limpiado")

def copiar_log():
    root.clipboard_append(text_log.get("1.0", tk.END))
    log("Log copiado al portapapeles")

def listar_puertos():
    try:
        puertos = [p.device for p in list_ports.comports()]
        combo_puertos["values"] = puertos
        if puertos:
            combo_puertos.current(0)
            log(f"Puertos actualizados: {len(puertos)} disponible(s)")
        else:
            log("No se encontraron puertos COM")
    except Exception as e:
        log(f"Error al listar puertos: {e}")

def conectar_serial():
    global puerto
    try:
        puerto_sel = combo_puertos.get()
        if not puerto_sel:
            log("Seleccione un puerto")
            return
            
        puerto = serial.Serial(puerto_sel, 115200, timeout=1)
        time.sleep(2)
        
        if puerto.is_open:
            lbl_serial.config(text="CONECTADO", bg="green", fg="white")
            btn_serial.config(text="Desconectar")
            btn_actualizar_puertos.config(state="disabled")
            actualizar_estado_sistema("CONECTADO", "green")
            log(f"Conectado a {puerto_sel}")
            iniciar_monitoreo_estado()
        else:
            log("No se pudo abrir el puerto")
    except Exception as e:
        puerto = None
        lbl_serial.config(text="ERROR", bg="orange", fg="white")
        log(f"Error conexión: {e}")

def desconectar_serial():
    global puerto
    if puerto:
        try:
            puerto.close()
            log("Puerto cerrado correctamente")
        except:
            pass
    puerto = None
    lbl_serial.config(text="DESCONECTADO", bg="red", fg="white")
    btn_serial.config(text="Conectar")
    btn_actualizar_puertos.config(state="normal")
    actualizar_estado_sistema("DESCONECTADO", "red")
    log("Serial cerrado")

def toggle_serial():
    if puerto and puerto.is_open:
        desconectar_serial()
    else:
        conectar_serial()

def actualizar_estado_sistema(estado, color="green", mensaje=""):
    lbl_estado.config(text=estado, bg=color, fg="white")
    estado_sistema["estado"] = estado
    estado_sistema["color"] = color
    estado_sistema["mensaje"] = mensaje
    estado_sistema["timestamp"] = datetime.datetime.now()

def iniciar_monitoreo_estado():
    def monitor():
        while puerto and puerto.is_open:
            try:
                if puerto.in_waiting > 0:
                    linea = puerto.readline().decode().strip()
                    if linea:
                        if "HOME" in linea or "home" in linea:
                            actualizar_estado_sistema("HOMING", "blue")
                        elif "ACK" in linea:
                            actualizar_estado_sistema("EJECUTANDO", "orange")
                        elif "ERROR" in linea or "error" in linea:
                            actualizar_estado_sistema("ERROR", "red", linea)
                
                if estado_sistema["estado"] not in ["DESCONECTADO", "ERROR"]:
                    if estado_sistema["timestamp"]:
                        delta = datetime.datetime.now() - estado_sistema["timestamp"]
                        if delta.seconds > 2:
                            actualizar_estado_sistema("LISTO", "green")
            except:
                pass
            time.sleep(0.5)
    threading.Thread(target=monitor, daemon=True).start()

def set_estado(ok):
    if ok:
        actualizar_estado_sistema("EJECUTADO", "green")
    else:
        actualizar_estado_sistema("EN ESPERA", "red")
        
# ====================================================
# ========= FUNCIÓN DE EJECUTAR LISTA - ORIGINAL =====
# ====================================================

ejecucion_en_curso = False

def ejecutar_lista():
    global ejecucion_en_curso
    
    if not lista_instrucciones:
        log("No hay instrucciones para ejecutar")
        return
    
    if ejecucion_en_curso:
        log("Ya hay una ejecución en curso")
        return
    
    def worker():
        global ejecucion_en_curso
        ejecucion_en_curso = True
        
        for i, (tipo, est, col) in enumerate(lista_instrucciones):
            if not ejecucion_en_curso:
                break
                
            try:
                if tipo == "carga":
                    ciclo_carga(est)
                else:
                    ciclo_descarga(est, col)
                log(f"Instrucción {i+1}/{len(lista_instrucciones)} completada")
            except Exception as e:
                log(f"Error en instrucción {i+1}: {e}")
                break
        
        ejecucion_en_curso = False
        log("Lista completada")
    
    threading.Thread(target=worker, daemon=True).start()
    log(f"Ejecutando lista de {len(lista_instrucciones)} instrucciones...")

# ====================================================
# ========= CREAR WIDGETS - DISTRIBUCIÓN EXACTA =====
# ====================================================

# FRAME PRINCIPAL DE SIMULACIÓN
frame_principal = tk.Frame(tab_sim)
frame_principal.pack(fill="both", expand=True, padx=2, pady=2)

# ========= FILA 1 =========
frame_fila1 = tk.Frame(frame_principal)
frame_fila1.pack(fill="x", pady=1)

# Columna 1: COMUNICACIÓN SERIAL
frame_serial = tk.LabelFrame(frame_fila1, text="COMUNICACIÓN SERIAL", padx=4, pady=2, font=("Arial", 9, "bold"))
frame_serial.pack(side="left", padx=2, fill="y")

combo_puertos = ttk.Combobox(frame_serial, width=12, font=("Arial", 9))
combo_puertos.pack(side="left", padx=2)

btn_actualizar_puertos = tk.Button(frame_serial, text="Actualizar", width=10, font=("Arial", 8))
btn_actualizar_puertos.pack(side="left", padx=2)

btn_serial = tk.Button(frame_serial, text="Conectar", width=10, font=("Arial", 8))
btn_serial.pack(side="left", padx=2)

lbl_serial = tk.Label(frame_serial, text="DESCONECTADO", bg="red", fg="white", width=14, font=("Arial", 8, "bold"))
lbl_serial.pack(side="left", padx=2)

# Columna 2: ALGORITMO
frame_alg = tk.LabelFrame(frame_fila1, text="ALGORITMO", padx=8, pady=5, font=("Arial", 9, "bold"))
frame_alg.pack(side="left", padx=2, fill="y")

btn_zona = tk.Radiobutton(frame_alg, text="ZONAS", variable=algoritmo_var, value="zonas", font=("Arial", 8))
btn_zona.pack(side="left", padx=2)

btn_producto = tk.Radiobutton(frame_alg, text="PRODUCTO", variable=algoritmo_var, value="producto", font=("Arial", 8))
btn_producto.pack(side="left", padx=2)

btn_frecuencia = tk.Radiobutton(frame_alg, text="FRECUENCIA", variable=algoritmo_var, value="frecuencia", font=("Arial", 8))
btn_frecuencia.pack(side="left", padx=2)

# Columna 3: ESTADO
frame_estado = tk.LabelFrame(frame_fila1, text="ESTADO", padx=8, pady=5, font=("Arial", 9, "bold"))
frame_estado.pack(side="left", padx=2, fill="y")

frame_estado_inner = tk.Frame(frame_estado)
frame_estado_inner.pack()

lbl_estado = tk.Label(frame_estado_inner, text="DESCONECTADO", bg="red", fg="white", width=16, font=("Arial", 9, "bold"))
lbl_estado.grid(row=1, column=0, padx=2)

# FILA 2: Label "Hora:"
tk.Label(frame_estado_inner, text="Hora:", font=("Arial", 9, "bold")).grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

# FILA 3: Tiempo (reloj)
lbl_tiempo = tk.Label(frame_estado_inner, text="", font=("Arial", 9, "bold"))
lbl_tiempo.grid(row=0, column=1, sticky="w", padx=2, pady=2)

# Columna 4: VARIABLES DEL SISTEMA - 2x2 CENTRADO
frame_variables_top = tk.LabelFrame(frame_fila1, text="VARIABLES DEL SISTEMA", padx=8, pady=5, font=("Arial", 9, "bold"))
frame_variables_top.pack(side="left", padx=2, fill="both", expand=True)

# Frame contenedor centrado
frame_centrado = tk.Frame(frame_variables_top)
frame_centrado.place(relx=0.5, rely=0.5, anchor="center")  # CENTRADO PERFECTO

# Configurar grid 2x2
frame_centrado.grid_columnconfigure(0, weight=0)  # Label - tamaño fijo
frame_centrado.grid_columnconfigure(1, weight=0)  # Valor - tamaño fijo
frame_centrado.grid_rowconfigure(0, weight=0)
frame_centrado.grid_rowconfigure(1, weight=0)

# FILA 0, COLUMNA 0 - Tiempo
tk.Label(frame_centrado, text="Tiempo encendido:", font=("Arial", 8, "bold")).grid(row=0, column=0, sticky="e", padx=5, pady=2)
lbl_tiempo_simulacion = tk.Label(frame_centrado, text="00:00:00", font=("Arial", 8))
lbl_tiempo_simulacion.grid(row=0, column=1, sticky="w", padx=5, pady=2)

# FILA 0, COLUMNA 2 - Ocupación (usamos column=2 para separar)
tk.Label(frame_centrado, text="Ocupación:", font=("Arial", 8, "bold")).grid(row=0, column=2, sticky="e", padx=15, pady=2)
lbl_ocupacion = tk.Label(frame_centrado, text="0% (0/50)", font=("Arial", 8))
lbl_ocupacion.grid(row=0, column=3, sticky="w", padx=5, pady=2)

# FILA 1, COLUMNA 0 - Cajas
tk.Label(frame_centrado, text="Cajas:", font=("Arial", 8, "bold")).grid(row=1, column=0, sticky="e", padx=5, pady=2)
lbl_por_color = tk.Label(frame_centrado, text="R0 V0 A0 D0", font=("Arial", 8))
lbl_por_color.grid(row=1, column=1, sticky="w", padx=5, pady=2)

# FILA 1, COLUMNA 2 - Tiempo ciclo
tk.Label(frame_centrado, text="Tiempo ciclo:", font=("Arial", 8, "bold")).grid(row=1, column=2, sticky="e", padx=15, pady=2)
lbl_tiempo_ciclo = tk.Label(frame_centrado, text="0.0s", font=("Arial", 8))
lbl_tiempo_ciclo.grid(row=1, column=3, sticky="w", padx=5, pady=2)

# ========= FILA 2 =========
frame_fila2 = tk.Frame(frame_principal)
frame_fila2.pack(fill="x", pady=2)

# Columna 1-3: ALGORITMO ELEGIDO (ocupa 3 columnas)
frame_algoritmo_elegido = tk.LabelFrame(frame_fila2, text="ALGORITMO ELEGIDO", padx=8, pady=5, font=("Arial", 9, "bold"))
frame_algoritmo_elegido.pack(side="left", padx=2, fill="both", expand=True)

# PANEL ALGORITMO DINÁMICO
frame_panel_algoritmo = tk.Frame(frame_algoritmo_elegido)
frame_panel_algoritmo.pack(fill="both", expand=True, padx=5, pady=5)

# Columna 4: ACCIONES + VARIABLES (PARTE INFERIOR)
frame_derecha_fila2 = tk.Frame(frame_fila2)
frame_derecha_fila2.pack(side="left", padx=2, fill="both")

# ACCIONES
frame_acciones = tk.LabelFrame(frame_derecha_fila2, text="ACCIONES", padx=8, pady=5, font=("Arial", 9, "bold"))
frame_acciones.pack(fill="x", pady=(0,2))

btn_ejecutar = tk.Button(frame_acciones, text="EJECUTAR", bg="#4CAF50", fg="white", width=10, font=("Arial", 8, "bold"))
btn_ejecutar.pack(side="left", padx=2)

btn_home = tk.Button(frame_acciones, text="HOME", bg="#2196F3", fg="white", width=10, font=("Arial", 8, "bold"))
btn_home.pack(side="left", padx=2)

# VARIABLES DEL SISTEMA (PARTE INFERIOR)
frame_variables_bottom = tk.LabelFrame(frame_derecha_fila2, text="", padx=8, pady=5, font=("Arial", 9, "bold"))
frame_variables_bottom.pack(fill="x", pady=(2,0))

lbl_distancia = tk.Label(frame_variables_bottom, text="Distancia: 0.0m", font=("Arial", 8))
lbl_distancia.pack(side="left", padx=10)

# ========= FILA 3 =========
frame_fila3 = tk.Frame(frame_principal)
frame_fila3.pack(fill="both", expand=True, pady=2)

# Columna 1-3: GRID + LEYENDAS (en una sola fila abajo)
frame_grid_container = tk.LabelFrame(frame_fila3, text="ALMACÉN - 50 CELDAS", padx=10, pady=10, font=("Arial", 10, "bold"))
frame_grid_container.pack(side="left", padx=2, fill="both", expand=True)

# Grid centrado
frame_grid_centrado = tk.Frame(frame_grid_container)
frame_grid_centrado.pack(expand=True)

frame_grid = tk.Frame(frame_grid_centrado, bg="lightgray")
frame_grid.pack(pady=10)

frame_grid_celdas = tk.Frame(frame_grid, bg="lightgray")
frame_grid_celdas.pack()

crear_grid(frame_grid_celdas)

# LEYENDAS DEL GRID - UNA SOLA FILA EN LA PARTE INFERIOR IZQUIERDA
frame_leyendas_container = tk.Frame(frame_grid_container)
frame_leyendas_container.pack(side="bottom", anchor="sw", pady=10)

frame_leyendas = tk.Frame(frame_leyendas_container, bg="lightgray", relief="groove", bd=1)
frame_leyendas.pack()

leyendas = [
    ("Celda vacía", "gray", "black"),
    ("Caja color rojo", "red", "black"),
    ("Caja color verde", "green", "black"),
    ("Caja color azul", "blue", "black"),
    ("Caja color desconocido", "yellow", "black")
]

for i, (texto, bg_color, fg_color) in enumerate(leyendas):
    lbl = tk.Label(frame_leyendas, text=texto, bg=bg_color, fg=fg_color,
                  width=25, font=("Arial", 8, "bold"), anchor="center", padx=2)
    lbl.grid(row=0, column=i, padx=1, pady=1)

# Columna 4: LISTA INSTRUCCIONES + REGISTRO EVENTOS
frame_derecha_fila3 = tk.Frame(frame_fila3, width=280)
frame_derecha_fila3.pack(side="left", padx=2, fill="both", expand=False)
frame_derecha_fila3.pack_propagate(False)

# LISTA DE INSTRUCCIONES
frame_lista_container = tk.LabelFrame(frame_derecha_fila3, text="LISTA DE INSTRUCCIONES", font=("Arial", 10, "bold"))
frame_lista_container.pack(fill="both", expand=True, pady=(0,2))

btn_limpiar_lista = tk.Button(frame_lista_container, text="Limpiar lista", font=("Arial", 8), width=12)
btn_limpiar_lista.pack(anchor="ne", padx=5, pady=5)

text_instr = tk.Text(frame_lista_container, height=14, font=("Consolas", 9), wrap=tk.WORD)
text_instr.pack(fill="both", expand=True, padx=5, pady=5)

# REGISTRO DE EVENTOS
frame_log_container = tk.LabelFrame(frame_derecha_fila3, text="REGISTRO DE EVENTOS", font=("Arial", 10, "bold"))
frame_log_container.pack(fill="both", expand=True, pady=(2,0))

frame_log_tools = tk.Frame(frame_log_container)
frame_log_tools.pack(fill="x", pady=2)

btn_limpiar_log = tk.Button(frame_log_tools, text="Limpiar log", font=("Arial", 8), width=10)
btn_limpiar_log.pack(side="left", padx=2)

btn_copiar_log = tk.Button(frame_log_tools, text="Copiar log", font=("Arial", 8), width=10)
btn_copiar_log.pack(side="left", padx=2)

lbl_log_timestamp = tk.Label(frame_log_tools, text="", font=("Arial", 7))
lbl_log_timestamp.pack(side="right", padx=5)

text_log = tk.Text(frame_log_container, height=10, font=("Consolas", 8), wrap=tk.WORD)
text_log.pack(fill="both", expand=True, padx=5, pady=5)

scroll_log = tk.Scrollbar(text_log)
scroll_log.pack(side="right", fill="y")
text_log.config(yscrollcommand=scroll_log.set)
scroll_log.config(command=text_log.yview)

# ====================================================
# ========= ACTUALIZAR PANEL ALGORITMO ==============
# ====================================================
frame_algoritmo_info = tk.LabelFrame(tab_sim, text="⚙️ ALGORITMO ELEGIDO", 
                                      font=("Arial", 12, "bold"), padx=10, pady=10)
frame_algoritmo_info.pack(fill="x", padx=10, pady=5)

# Frame interno para contenido dinámico (se actualizará según algoritmo)
inner_algoritmo_info = tk.Frame(frame_algoritmo_info)
inner_algoritmo_info.pack(fill="both", expand=True, padx=5, pady=5)


def actualizar_panel_algoritmo():
    for widget in frame_panel_algoritmo.winfo_children():
        widget.destroy()
    
    algoritmo = algoritmo_var.get()
    
    if algoritmo == "zonas":
        inner_frame = tk.Frame(frame_panel_algoritmo)
        inner_frame.pack(fill="both", expand=True)
        
        tk.Label(inner_frame, text="Zona activa:", font=("Arial", 9, "bold")).pack(side="left", padx=2)
        lbl_zona_actual = tk.Label(inner_frame, text=str(ZONA_ACTIVA),
                                  font=("Arial", 12, "bold"), width=2, 
                                  bg="lightblue", relief="sunken")
        lbl_zona_actual.pack(side="left", padx=2)
        
        tk.Label(inner_frame, text="  ", font=("Arial", 9)).pack(side="left")
        tk.Label(inner_frame, text="Seleccionar zona:", font=("Arial", 9)).pack(side="left", padx=2)
        
        for i in range(1, 6):
            rb = tk.Radiobutton(inner_frame, text=f"{i}",
                               variable=zona_var, value=i,
                               indicatoron=False, width=3,
                               font=("Arial", 8, "bold"))
            rb.pack(side="left", padx=1)
            rb.config(command=cambiar_zona)
        
        tk.Label(inner_frame, text="  ", font=("Arial", 9)).pack(side="left")
        
        celdas_zona = sum(1 for i in range(TOTAL_CELDAS) 
                         if zona_por_pos(i+1) == ZONA_ACTIVA and estado_logico[i] != 0)
        total_zona = sum(1 for i in range(TOTAL_CELDAS) if zona_por_pos(i+1) == ZONA_ACTIVA)
        porcentaje = int((celdas_zona / total_zona) * 100) if total_zona > 0 else 0
        
        tk.Label(inner_frame, 
                text=f"Ocupación: {porcentaje}% ({celdas_zona}/{total_zona} celdas)",
                font=("Arial", 9, "bold")).pack(side="left", padx=5)
        
    elif algoritmo == "producto":
        inner_frame = tk.Frame(frame_panel_algoritmo)
        inner_frame.pack(fill="both", expand=True)
        
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
        
        tk.Label(inner_frame, text="Cajas registradas:", font=("Arial", 9, "bold")).pack(side="left", padx=2)
        
        tk.Label(inner_frame, text="🔴", font=("Arial", 10)).pack(side="left", padx=1)
        tk.Label(inner_frame, text=f"Rojo: {total_rojo}/{total_rojo_max} ({pct_rojo}%)", 
                font=("Arial", 8)).pack(side="left", padx=2)
        
        tk.Label(inner_frame, text="🟢", font=("Arial", 10)).pack(side="left", padx=1)
        tk.Label(inner_frame, text=f"Verde: {total_verde}/{total_verde_max} ({pct_verde}%)", 
                font=("Arial", 8)).pack(side="left", padx=2)
        
        tk.Label(inner_frame, text="🔵", font=("Arial", 10)).pack(side="left", padx=1)
        tk.Label(inner_frame, text=f"Azul: {total_azul}/{total_azul_max} ({pct_azul}%)", 
                font=("Arial", 8)).pack(side="left", padx=2)
        
        tk.Label(inner_frame, text="🟡", font=("Arial", 10)).pack(side="left", padx=1)
        tk.Label(inner_frame, text=f"Desc: {total_desc}/{total_desc_max} ({pct_desc}%)", 
                font=("Arial", 8)).pack(side="left", padx=2)
        
    elif algoritmo == "frecuencia":
        inner_frame = tk.Frame(frame_panel_algoritmo)
        inner_frame.pack(fill="both", expand=True)
        
        tk.Label(inner_frame, text="Estaciones - color más solicitado:", font=("Arial", 9, "bold")).pack(side="left", padx=2)
        
        color_icons = {1: "🔴", 2: "🟢", 3: "🔵"}
        color_names = {1: "Rojo", 2: "Verde", 3: "Azul"}
        
        for est in [1, 2, 3]:
            hist = list(historial[est])
            conteo = {1:0, 2:0, 3:0}
            for c in hist:
                if c in conteo:
                    conteo[c] += 1
            
            sorted_colors = sorted(conteo.items(), key=lambda x: x[1], reverse=True)
            top1 = sorted_colors[0][0] if sorted_colors and sorted_colors[0][1] > 0 else 1
            top1_icon = color_icons.get(top1, "⚪")
            top1_name = color_names.get(top1, "?")
            
            est_frame = tk.Frame(inner_frame)
            est_frame.pack(side="left", padx=5)
            
            tk.Label(est_frame, text=f"E{est}:", font=("Arial", 8, "bold")).pack(side="left")
            tk.Label(est_frame, text=f"{top1_icon} {top1_name}", font=("Arial", 8)).pack(side="left", padx=2)
        
        tk.Label(inner_frame, text=f"  Stock mínimo: {MIN_CAUSAS} cajas", 
                font=("Arial", 8, "bold")).pack(side="left", padx=10)

# ====================================================
# ========= TAB CONFIGURACIÓN =======================
# ====================================================

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

# COLUMNA 1 - MANUAL
frame_manual = tk.LabelFrame(frame_gen, text="Instrucción manual", font=("TkDefaultFont", 10, "bold"))
frame_manual.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
frame_manual.grid_columnconfigure(1, weight=1)

tk.Label(frame_manual, text="Instrucción:", font=("TkDefaultFont", 9, "bold")).grid(row=0, column=0, sticky="w", pady=4)
combo_tipo_instr = ttk.Combobox(frame_manual, textvariable=tipo_instr_var, values=["Carga", "Descarga"], state="readonly")
combo_tipo_instr.grid(row=0, column=1, sticky="ew")

tk.Label(frame_manual, text="N° Estación:", font=("TkDefaultFont", 9, "bold")).grid(row=1, column=0, sticky="w", pady=4)
entry_est_manual = tk.Entry(frame_manual)
entry_est_manual.grid(row=1, column=1, sticky="ew")

tk.Label(frame_manual, text="Color de caja:", font=("TkDefaultFont", 9, "bold")).grid(row=2, column=0, sticky="w", pady=4)
combo_color_manual = ttk.Combobox(frame_manual, textvariable=color_manual_var, values=["Rojo", "Verde", "Azul"], state="readonly")
combo_color_manual.grid(row=2, column=1, sticky="ew")

btn_agregar_instr = tk.Button(frame_manual, text="Agregar instrucción")
btn_agregar_instr.grid(row=3, column=0, columnspan=2, sticky="ew", pady=6)

btn_eliminar_instr = tk.Button(frame_manual, text="Eliminar última instrucción")
btn_eliminar_instr.grid(row=4, column=0, columnspan=2, sticky="ew")

# COLUMNA 2 - ALEATORIAS
frame_rand = tk.LabelFrame(frame_gen, text="Instrucciones aleatorias", font=("TkDefaultFont", 10, "bold"))
frame_rand.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
frame_rand.grid_columnconfigure(1, weight=1)

tk.Label(frame_rand, text="Cantidad:").grid(row=0, column=0, sticky="w")
entry_cantidad = tk.Entry(frame_rand)
entry_cantidad.grid(row=0, column=1, sticky="ew")

btn_generar_lista = tk.Button(frame_rand, text="Generar lista")
btn_generar_lista.grid(row=1, column=0, columnspan=2, sticky="ew", pady=6)

# COLUMNA 3 - VISOR
frame_lista = tk.LabelFrame(frame_gen, text="Lista de instrucciones", font=("TkDefaultFont", 10, "bold"))
frame_lista.grid(row=0, column=2, sticky="nsew", padx=10, pady=10)
frame_lista.grid_rowconfigure(0, weight=1)
frame_lista.grid_columnconfigure(0, weight=1)

text_lista = tk.Text(frame_lista)
text_lista.grid(row=0, column=0, sticky="nsew")

# ====================================================
# ========= TAB ESTADÍSTICAS ========================
# ====================================================

tk.Label(tab_stats, text="ESTADÍSTICAS DEL SISTEMA", font=("Arial", 14, "bold")).pack(pady=20)
tk.Label(tab_stats, text="(Próximamente...)", font=("Arial", 10)).pack()

# ====================================================
# ========= ASIGNACIÓN DE COMANDOS =================
# ====================================================

btn_actualizar_puertos.config(command=listar_puertos)
btn_serial.config(command=toggle_serial)
btn_zona.config(command=cambiar_algoritmo)
btn_producto.config(command=cambiar_algoritmo)
btn_frecuencia.config(command=cambiar_algoritmo)

# ✅ SOLO EJECUTAR - SIN PAUSAR/DETENER
btn_ejecutar.config(command=ejecutar_lista)
btn_home.config(command=lambda: enviar_comando(HOME) if puerto else log("No conectado"))

btn_limpiar_lista.config(command=lambda: [lista_instrucciones.clear(), 
                                         actualizar_lista_ui(),
                                         actualizar_textbox_instrucciones(),
                                         log("Lista de instrucciones limpiada")])

btn_limpiar_log.config(command=limpiar_log)
btn_copiar_log.config(command=copiar_log)

btn_agregar_instr.config(command=agregar_instruccion)
btn_eliminar_instr.config(command=eliminar_ultima)
btn_generar_lista.config(command=generar_lista_random)

algoritmo_var.trace_add("write", lambda *args: actualizar_panel_algoritmo())

# ====================================================
# ========= INICIALIZACIÓN ==========================
# ====================================================

lbl_log_timestamp.config(text=f"Inicio: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
listar_puertos()
actualizar_reloj()
actualizar_tiempo_simulacion()
actualizar_variables_tiempo_real()
actualizar_grid()
actualizar_panel_algoritmo()

log("Sistema HMI iniciado")
log("Esperando conexión serial...")

# ====================================================
# ================= MAIN =============================
# ====================================================
root.mainloop()