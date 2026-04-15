# Pérez Hernández Ricardo — Práctica 5: Servicios Web
# ─────────────────────────────────────────────────────────────────────────────
# chat_cliente.py  —  Cliente de Chat que consume la API REST
#
# Uso:  python chat_cliente.py
#       (abrir varias terminales para simular múltiples usuarios)
#
# ─── Patrones de servicio web demostrados ────────────────────────────────────
#  1. POLLING  — el cliente pregunta periódicamente si hay mensajes nuevos
#                GET /mensajes?desde=<ultimo_id>
#                Simula "tiempo real" sin conexión persistente.
#
#  2. HEARTBEAT — el cliente avisa cada 5s que sigue activo
#                 POST /heartbeat
#                 El servidor descarta usuarios sin heartbeat (> 15s).
#
#  3. RECURSOS  — los endpoints son sustantivos, los verbos son HTTP:
#                 POST   /mensajes  → crear mensaje
#                 GET    /mensajes  → leer mensajes
#                 DELETE /salir     → eliminar sesión
#
# ─────────────────────────────────────────────────────────────────────────────
import requests
import threading
import time
import tkinter as tk
from tkinter import scrolledtext, simpledialog, messagebox
import queue

# ── Configuración ─────────────────────────────────────────────────────────────
HOST = 'localhost'
PORT = 9000
URL  = f"http://{HOST}:{PORT}"

POLL_INTERVAL      = 1.0   # segundos entre GETs de mensajes nuevos
HEARTBEAT_INTERVAL = 5.0   # segundos entre heartbeats


# ─────────────────────────────────────────────────────────────────────────────
# CLASE CLIENTE  (encapsula todas las llamadas HTTP)
# ─────────────────────────────────────────────────────────────────────────────

class ChatCliente:
    """
    Encapsula las llamadas HTTP al servidor de chat.
    Cada método corresponde a un endpoint REST.
    """

    def __init__(self, usuario: str):
        self.usuario    = usuario
        self.ultimo_id  = 0      # id del último mensaje recibido
        self._activo    = False

    # ── Llamadas a la API ──────────────────────────────────────────────────────

    def unirse(self) -> bool:
        """POST /unirse"""
        try:
            r = requests.post(f"{URL}/unirse",
                              json={'usuario': self.usuario}, timeout=5)
            return r.ok
        except Exception as e:
            print(f"[ERROR] unirse: {e}")
            return False

    def salir(self):
        """DELETE /salir"""
        try:
            requests.delete(f"{URL}/salir",
                            json={'usuario': self.usuario}, timeout=3)
        except Exception:
            pass

    def enviar(self, texto: str) -> bool:
        """POST /mensajes"""
        try:
            r = requests.post(f"{URL}/mensajes",
                              json={'usuario': self.usuario, 'texto': texto},
                              timeout=5)
            return r.ok
        except Exception as e:
            print(f"[ERROR] enviar: {e}")
            return False

    def obtener_nuevos(self) -> list:
        """
        GET /mensajes?desde=<ultimo_id>
        Solo pide mensajes más nuevos que el último recibido.
        Esto es POLLING INCREMENTAL — eficiente porque evita
        retransmitir todo el historial en cada petición.
        """
        try:
            r = requests.get(f"{URL}/mensajes",
                             params={'desde': self.ultimo_id}, timeout=5)
            if not r.ok:
                return []
            nuevos = r.json().get('mensajes', [])
            if nuevos:
                self.ultimo_id = nuevos[-1]['id']
            return nuevos
        except Exception:
            return []

    def obtener_usuarios(self) -> list:
        """GET /usuarios"""
        try:
            r = requests.get(f"{URL}/usuarios", timeout=5)
            return r.json().get('usuarios', []) if r.ok else []
        except Exception:
            return []

    def heartbeat(self):
        """POST /heartbeat — avisar al servidor que seguimos activos."""
        try:
            requests.post(f"{URL}/heartbeat",
                          json={'usuario': self.usuario}, timeout=3)
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# GUI TKINTER
# ─────────────────────────────────────────────────────────────────────────────

class ChatGUI:
    def __init__(self, root: tk.Tk, cliente: ChatCliente):
        self.root    = root
        self.cliente = cliente
        self.cola    = queue.Queue()   # mensajes del hilo de polling → GUI

        self._construir_ui()
        self._iniciar_hilos()
        self.root.after(200, self._procesar_cola)

    # ── Construcción de la interfaz ───────────────────────────────────────────

    def _construir_ui(self):
        self.root.title(f"Chat REST  —  {self.cliente.usuario}")
        self.root.configure(bg='#1a1a2e')
        self.root.resizable(False, False)

        # ── Barra superior ────────────────────────────────────────────────────
        barra = tk.Frame(self.root, bg='#16213e', pady=6)
        barra.pack(fill='x')

        tk.Label(barra, text="💬  CHAT DISTRIBUIDO  —  REST API",
                 font=("Consolas", 11, "bold"),
                 bg='#16213e', fg='#00d4ff').pack(side='left', padx=12)

        self.lbl_usuario = tk.Label(
            barra,
            text=f"● {self.cliente.usuario}",
            font=("Consolas", 9),
            bg='#16213e', fg='#00ff88'
        )
        self.lbl_usuario.pack(side='right', padx=12)

        # ── Panel principal (mensajes + usuarios) ─────────────────────────────
        contenido = tk.Frame(self.root, bg='#1a1a2e')
        contenido.pack(fill='both', expand=True, padx=8, pady=(6, 0))

        # Área de mensajes
        frame_msgs = tk.Frame(contenido, bg='#1a1a2e')
        frame_msgs.pack(side='left', fill='both', expand=True)

        tk.Label(frame_msgs, text="MENSAJES",
                 font=("Consolas", 8), bg='#1a1a2e', fg='#555577').pack(anchor='w')

        self.txt_mensajes = scrolledtext.ScrolledText(
            frame_msgs,
            width=62, height=22,
            font=("Consolas", 9),
            bg='#0d1117', fg='#c9d1d9',
            insertbackground='white',
            relief='flat', bd=0,
            state='disabled'
        )
        self.txt_mensajes.pack(fill='both', expand=True)
        self.txt_mensajes.tag_config('sistema',  foreground='#555577')
        self.txt_mensajes.tag_config('propio',   foreground='#79c0ff')
        self.txt_mensajes.tag_config('otro',     foreground='#56d364')
        self.txt_mensajes.tag_config('hora',     foreground='#444466')

        # Panel lateral: usuarios conectados
        frame_lat = tk.Frame(contenido, bg='#16213e', width=160, padx=8)
        frame_lat.pack(side='right', fill='y', padx=(8, 0))
        frame_lat.pack_propagate(False)

        tk.Label(frame_lat, text="CONECTADOS",
                 font=("Consolas", 8, "bold"),
                 bg='#16213e', fg='#00d4ff').pack(anchor='w', pady=(6, 2))

        self.lst_usuarios = tk.Listbox(
            frame_lat,
            font=("Consolas", 9),
            bg='#0d1117', fg='#00ff88',
            selectbackground='#21262d',
            relief='flat', bd=0,
            activestyle='none'
        )
        self.lst_usuarios.pack(fill='both', expand=True)

        # ── Barra de peticiones HTTP (log en vivo) ────────────────────────────
        tk.Label(self.root, text="PETICIONES HTTP",
                 font=("Consolas", 7), bg='#1a1a2e', fg='#555577').pack(
            anchor='w', padx=8)

        self.txt_http = tk.Text(
            self.root,
            height=4, width=80,
            font=("Consolas", 7),
            bg='#0d1117', fg='#6e7681',
            relief='flat', bd=0,
            state='disabled'
        )
        self.txt_http.pack(fill='x', padx=8, pady=(0, 4))

        # ── Entrada de mensaje ────────────────────────────────────────────────
        frame_entrada = tk.Frame(self.root, bg='#21262d', pady=6)
        frame_entrada.pack(fill='x', padx=8, pady=(0, 8))

        self.entrada = tk.Entry(
            frame_entrada,
            font=("Consolas", 10),
            bg='#21262d', fg='white',
            insertbackground='white',
            relief='flat', bd=4
        )
        self.entrada.pack(side='left', fill='x', expand=True, ipady=4)
        self.entrada.bind('<Return>', self._enviar)
        self.entrada.focus()

        btn = tk.Button(
            frame_entrada,
            text="Enviar",
            font=("Consolas", 9, "bold"),
            bg='#238636', fg='white',
            activebackground='#2ea043',
            relief='flat', bd=0,
            padx=14, pady=4,
            command=self._enviar
        )
        btn.pack(side='right', padx=(6, 0))

    # ── Hilos de background ───────────────────────────────────────────────────

    def _iniciar_hilos(self):
        threading.Thread(target=self._hilo_polling,   daemon=True).start()
        threading.Thread(target=self._hilo_heartbeat, daemon=True).start()

    def _hilo_polling(self):
        """
        Consulta GET /mensajes?desde=N cada POLL_INTERVAL segundos.
        También refresca la lista de usuarios activos.

        Este patrón se llama POLLING:
          - Simple de implementar con REST puro
          - Latencia = hasta POLL_INTERVAL segundos
          - Alternativa más sofisticada: WebSockets (no REST puro)
        """
        while True:
            # Obtener mensajes nuevos
            nuevos = self.cliente.obtener_nuevos()
            for msg in nuevos:
                self.cola.put(('mensaje', msg))
            if nuevos:
                self._log_http(f"GET  /mensajes?desde={self.cliente.ultimo_id - len(nuevos)}"
                               f"  →  {len(nuevos)} nuevo(s)")

            # Refrescar lista de usuarios cada 3 ciclos (~3s)
            if int(time.time()) % 3 == 0:
                usuarios = self.cliente.obtener_usuarios()
                self.cola.put(('usuarios', usuarios))

            time.sleep(POLL_INTERVAL)

    def _hilo_heartbeat(self):
        """POST /heartbeat cada HEARTBEAT_INTERVAL segundos."""
        while True:
            time.sleep(HEARTBEAT_INTERVAL)
            self.cliente.heartbeat()
            self._log_http(f"POST /heartbeat  →  {self.cliente.usuario} activo")

    # ── Procesamiento de la cola en el hilo GUI ───────────────────────────────

    def _procesar_cola(self):
        try:
            while not self.cola.empty():
                tipo, datos = self.cola.get_nowait()
                if tipo == 'mensaje':
                    self._mostrar_mensaje(datos)
                elif tipo == 'usuarios':
                    self._actualizar_usuarios(datos)
        except queue.Empty:
            pass
        self.root.after(200, self._procesar_cola)

    def _mostrar_mensaje(self, msg: dict):
        self.txt_mensajes.config(state='normal')
        hora = msg.get('timestamp', '')
        usr  = msg.get('usuario', '')
        txt  = msg.get('texto', '')

        if usr == 'SISTEMA':
            self.txt_mensajes.insert('end', f"  {txt}\n", 'sistema')
        elif usr == self.cliente.usuario:
            self.txt_mensajes.insert('end', f"[{hora}] ", 'hora')
            self.txt_mensajes.insert('end', f"Tú: {txt}\n", 'propio')
        else:
            self.txt_mensajes.insert('end', f"[{hora}] ", 'hora')
            self.txt_mensajes.insert('end', f"{usr}: {txt}\n", 'otro')

        self.txt_mensajes.config(state='disabled')
        self.txt_mensajes.see('end')

    def _actualizar_usuarios(self, usuarios: list):
        self.lst_usuarios.delete(0, 'end')
        for u in usuarios:
            prefijo = "► " if u == self.cliente.usuario else "  "
            self.lst_usuarios.insert('end', f"{prefijo}{u}")

    def _log_http(self, texto: str):
        """Registra la petición HTTP en el panel inferior."""
        self.txt_http.config(state='normal')
        self.txt_http.insert('end', f"{time.strftime('%H:%M:%S')}  {texto}\n")
        # Mantener solo las últimas 6 líneas
        lineas = int(self.txt_http.index('end-1c').split('.')[0])
        if lineas > 6:
            self.txt_http.delete('1.0', '2.0')
        self.txt_http.config(state='disabled')
        self.txt_http.see('end')

    # ── Enviar mensaje ────────────────────────────────────────────────────────

    def _enviar(self, event=None):
        texto = self.entrada.get().strip()
        if not texto:
            return
        self.entrada.delete(0, 'end')
        ok = self.cliente.enviar(texto)
        self._log_http(f"POST /mensajes  →  {'200 OK' if ok else 'ERROR'}")


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    # Ventana temporal para pedir el nombre de usuario
    root_login = tk.Tk()
    root_login.withdraw()
    usuario = simpledialog.askstring(
        "Chat REST",
        "Ingresa tu nombre de usuario:",
        parent=root_login
    )
    root_login.destroy()

    if not usuario or not usuario.strip():
        print("[INFO] Sin nombre de usuario. Saliendo.")
        return

    usuario = usuario.strip()

    # Conectar al servidor
    cliente = ChatCliente(usuario)
    print(f"[INFO] Conectando como '{usuario}' a {URL} ...")
    if not cliente.unirse():
        messagebox.showerror("Error",
                             f"No se pudo conectar a {URL}\n"
                             "¿Está corriendo chat_servidor.py?")
        return

    print(f"[INFO] Conectado. Iniciando interfaz.")

    # Ventana principal del chat
    root = tk.Tk()
    app  = ChatGUI(root, cliente)

    def al_cerrar():
        cliente.salir()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", al_cerrar)
    root.mainloop()
    print(f"[INFO] {usuario} desconectado.")


if __name__ == '__main__':
    main()
