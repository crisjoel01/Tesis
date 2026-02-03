import tkinter as tk
from tkinter import messagebox
import threading


class HMI:

    def __init__(self, movimientos, serial_mgr):
        self.mov = movimientos
        self.serial_mgr = serial_mgr

        self.root = tk.Tk()
        self.root.title("HMI Storage Cartesiano")
        self.root.geometry("460x400")
        self.root.resizable(False, False)

        self.crear_ui()

        serial_mgr.set_callbacks(self.log, self.set_estado)

    # ================= UI =================
    def crear_ui(self):

        tk.Label(self.root, text="Posición (1-50):").place(x=20, y=20)
        self.entry_pos = tk.Entry(self.root, width=10)
        self.entry_pos.place(x=160, y=20)

        tk.Label(self.root, text="Estación (1-3):").place(x=20, y=60)
        self.entry_est = tk.Entry(self.root, width=10)
        self.entry_est.place(x=160, y=60)

        self.accion = tk.StringVar(value="carga")

        tk.Radiobutton(self.root, text="Carga", variable=self.accion, value="carga").place(x=20, y=100)
        tk.Radiobutton(self.root, text="Descarga", variable=self.accion, value="descarga").place(x=120, y=100)

        tk.Button(self.root, text="Ejecutar ciclo", width=20, command=self.ejecutar).place(x=160, y=130)
        tk.Button(self.root, text="Ir a Storage", width=20, command=self.ir_storage).place(x=160, y=165)
        tk.Button(self.root, text="Ir a Estación", width=20, command=self.ir_estacion).place(x=160, y=200)

        self.lbl_estado = tk.Label(self.root, text="WAIT", width=8, bg="red", fg="white")
        self.lbl_estado.place(x=320, y=50)

        self.text_log = tk.Text(self.root, width=54, height=9)
        self.text_log.place(x=20, y=240)

        self.root.protocol("WM_DELETE_WINDOW", self.cerrar)

    # ================= helpers =================
    def log(self, txt):
        self.text_log.insert(tk.END, txt + "\n")
        self.text_log.see(tk.END)

    def set_estado(self, ok):
        if ok:
            self.lbl_estado.config(bg="green", text="ACK")
        else:
            self.lbl_estado.config(bg="red", text="WAIT")

    # ================= botones =================
    def ejecutar(self):
        try:
            pos = int(self.entry_pos.get())
            est = int(self.entry_est.get())
            acc = self.accion.get()
        except:
            messagebox.showerror("Error", "Datos inválidos")
            return

        threading.Thread(target=self.mov.movimiento, args=(pos, est, acc), daemon=True).start()

    def ir_storage(self):
        pos = int(self.entry_pos.get())
        threading.Thread(target=self.mov.ir_a_storage, args=(pos,), daemon=True).start()

    def ir_estacion(self):
        est = int(self.entry_est.get())
        threading.Thread(target=self.mov.ir_a_estacion, args=(est,), daemon=True).start()

    def cerrar(self):
        self.serial_mgr.close()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
