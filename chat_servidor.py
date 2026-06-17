# Pérez Hernández Ricardo — Práctica 5: Servicios Web
# ─────────────────────────────────────────────────────────────────────────────
# chat_servidor.py  —  Servidor de Chat como SERVICIO WEB (REST / HTTP)
#
# Uso:  python chat_servidor.py
#
# ─── Idea del ejemplo ─────────────────────────────────────────────────────────
#  Demuestra los patrones clásicos de un servicio web REST aplicados a un
#  chat distribuido:
#    • Recursos claramente nombrados  (/mensajes, /usuarios)
#    • Verbos HTTP semánticos         (GET leer, POST escribir, DELETE salir)
#    • Comunicación sin estado        (cada petición es independiente)
#    • Polling como mecanismo de      "tiempo real" sin WebSockets
#
# ─── Endpoints ────────────────────────────────────────────────────────────────
#  POST /unirse            { "usuario": "Ricardo" }
#  DELETE /salir           { "usuario": "Ricardo" }
#  POST /mensajes          { "usuario": "...", "texto": "..." }
#  GET  /mensajes?desde=N  → lista de mensajes con id > N
#  GET  /usuarios          → lista de usuarios conectados
#
# ─────────────────────────────────────────────────────────────────────────────
from flask import Flask, request, jsonify
from flask_cors import CORS # <--- AÑADE ESTO
import threading
import time
import cv2
import numpy as np

# ── Configuración ─────────────────────────────────────────────────────────
HOST = 'localhost'
PORT = 9000

app = Flask(__name__)
CORS(app) # <--- AÑADE ESTO (Permite que el navegador confíe en las peticiones)

# ── Estado del chat ───────────────────────────────────────────────────────────
_lock       = threading.Lock()
_mensajes   = []          # lista de dicts: {id, usuario, texto, timestamp}
_usuarios   = {}          # { nombre: last_seen (float) }
_contador   = 0           # ID autoincremental de mensajes


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/unirse', methods=['POST'])
def unirse():
    datos   = request.get_json()
    usuario = datos.get('usuario', '').strip()
    if not usuario:
        return jsonify({'ok': False, 'error': 'Nombre vacío'}), 400

    with _lock:
        ya_existe = usuario in _usuarios
        _usuarios[usuario] = time.time()
        if not ya_existe:
            _agregar_mensaje('SISTEMA', f'*** {usuario} se unió al chat ***')

    print(f"[+] {usuario} se unió")
    return jsonify({'ok': True})


@app.route('/salir', methods=['DELETE'])
def salir():
    """
    DELETE /salir  { "usuario": "Ricardo" }
    Verbo DELETE: semánticamente correcto para "eliminar" un recurso (la sesión).
    """
    datos   = request.get_json()
    usuario = datos.get('usuario', '').strip()
    with _lock:
        if usuario in _usuarios:
            _usuarios.pop(usuario)
            _agregar_mensaje('SISTEMA', f'*** {usuario} salió del chat ***')
    print(f"[-] {usuario} salió")
    return jsonify({'ok': True})


@app.route('/mensajes', methods=['POST'])
def enviar_mensaje():
    """
    POST /mensajes  { "usuario": "Ricardo", "texto": "Hola a todos" }
    Crea un nuevo recurso 'mensaje' — POST es el verbo correcto para creación.
    """
    datos   = request.get_json()
    usuario = datos.get('usuario', '').strip()
    texto   = datos.get('texto', '').strip()

    if not usuario or not texto:
        return jsonify({'ok': False, 'error': 'Campos incompletos'}), 400

    with _lock:
        # Actualizar presencia del usuario
        _usuarios[usuario] = time.time()
        nuevo_id = _agregar_mensaje(usuario, texto)

    return jsonify({'ok': True, 'id': nuevo_id})


@app.route('/mensajes', methods=['GET'])
def obtener_mensajes():
    desde = int(request.args.get('desde', 0))
    with _lock:
        nuevos = [m for m in _mensajes if m['id'] > desde]
    return jsonify({'mensajes': nuevos})


@app.route('/usuarios', methods=['GET'])
def obtener_usuarios():
    """
    GET /usuarios → lista de usuarios activos (vivos en últimos 15s)
    """
    ahora = time.time()
    with _lock:
        # Limpiar usuarios inactivos (sin heartbeat > 15s)
        caidos = [u for u, t in _usuarios.items() if ahora - t > 15]
        for u in caidos:
            _usuarios.pop(u)
            _agregar_mensaje('SISTEMA', f'*** {u} se desconectó (timeout) ***')
        activos = list(_usuarios.keys())
    return jsonify({'usuarios': activos})


@app.route('/heartbeat', methods=['POST'])
def heartbeat():
    """
    POST /heartbeat  { "usuario": "Ricardo" }
    Los clientes llaman esto cada ~5s para indicar que siguen conectados.
    Sin heartbeat el servidor los marca como desconectados en /usuarios.
    """
    usuario = request.get_json().get('usuario', '')
    with _lock:
        if usuario in _usuarios:
            _usuarios[usuario] = time.time()
    return jsonify({'ok': True})


# ─── Función interna ──────────────────────────────────────────────────────────

def _agregar_mensaje(usuario: str, texto: str) -> int:
    """Inserta mensaje en la lista. Debe llamarse con _lock adquirido."""
    global _contador
    _contador += 1
    _mensajes.append({
        'id'       : _contador,
        'usuario'  : usuario,
        'texto'    : texto,
        'timestamp': time.strftime('%H:%M:%S')
    })
    # Mantener solo los últimos 200 mensajes en memoria
    if len(_mensajes) > 200:
        _mensajes.pop(0)
    return _contador


# ─── Panel visual OpenCV ──────────────────────────────────────────────────────

ANCHO, ALTO = 800, 600
COLOR_FONDO    = (18, 18, 18)
COLOR_TITULO   = (0, 215, 255)
COLOR_SISTEMA  = (100, 100, 100)
COLOR_USUARIO  = (80, 200, 120)
COLOR_MENSAJE  = (210, 210, 210)
COLOR_SEPARADOR= (50, 50, 50)
COLOR_ONLINE   = (0, 255, 120)
COLOR_ENDPOINT = (100, 160, 255)
FUENTE         = cv2.FONT_HERSHEY_SIMPLEX


def _texto_cortado(texto: str, max_chars: int) -> str:
    return texto if len(texto) <= max_chars else texto[:max_chars - 1] + '…'


def dibujar_panel():
    panel = np.full((ALTO, ANCHO, 3), COLOR_FONDO, dtype=np.uint8)

    # ── Encabezado ────────────────────────────────────────────────────────────
    cv2.putText(panel, "CHAT DISTRIBUIDO  —  Servicio Web REST (Flask)",
                (15, 32), FUENTE, 0.65, COLOR_TITULO, 2)
    cv2.putText(panel, f"http://{HOST}:{PORT}",
                (15, 55), FUENTE, 0.45, (140, 140, 140), 1)
    cv2.line(panel, (15, 65), (ANCHO - 15, 65), COLOR_SEPARADOR, 1)

    # ── Endpoints (columna derecha) ───────────────────────────────────────────
    eps = [
        "POST   /unirse",
        "DELETE /salir",
        "POST   /mensajes",
        "GET    /mensajes?desde=N",
        "GET    /usuarios",
        "POST   /heartbeat",
    ]
    cv2.putText(panel, "ENDPOINTS", (590, 85), FUENTE, 0.42, COLOR_ENDPOINT, 1)
    for i, ep in enumerate(eps):
        cv2.putText(panel, ep, (590, 103 + i * 17),
                    FUENTE, 0.36, (90, 130, 200), 1)
    cv2.line(panel, (580, 68), (580, ALTO - 15), COLOR_SEPARADOR, 1)

    # ── Usuarios conectados ───────────────────────────────────────────────────
    with _lock:
        snap_usuarios  = list(_usuarios.keys())
        snap_mensajes  = list(_mensajes[-20:])   # últimos 20

    cv2.putText(panel, f"USUARIOS CONECTADOS  ({len(snap_usuarios)})",
                (15, 88), FUENTE, 0.45, COLOR_ONLINE, 1)
    if snap_usuarios:
        linea_u = "  ".join(snap_usuarios)
        cv2.putText(panel, _texto_cortado(linea_u, 65),
                    (15, 108), FUENTE, 0.4, COLOR_ONLINE, 1)
    else:
        cv2.putText(panel, "  (ninguno)", (15, 108), FUENTE, 0.4,
                    COLOR_SISTEMA, 1)
    cv2.line(panel, (15, 118), (570, 118), COLOR_SEPARADOR, 1)

    # ── Mensajes ──────────────────────────────────────────────────────────────
    cv2.putText(panel, "MENSAJES RECIENTES", (15, 135),
                FUENTE, 0.45, (180, 180, 100), 1)

    y = 158
    for msg in snap_mensajes:
        if y > ALTO - 25:
            break
        if msg['usuario'] == 'SISTEMA':
            cv2.putText(panel,
                        f"  {msg['timestamp']}  {_texto_cortado(msg['texto'], 62)}",
                        (15, y), FUENTE, 0.37, COLOR_SISTEMA, 1)
        else:
            # Nombre de usuario en color
            cv2.putText(panel, f"  {msg['timestamp']}  {msg['usuario']}:",
                        (15, y), FUENTE, 0.38, COLOR_USUARIO, 1)
            texto_x = 15 + int(len(f"  {msg['timestamp']}  {msg['usuario']}:") * 7.5)
            cv2.putText(panel, f" {_texto_cortado(msg['texto'], 48)}",
                        (texto_x, y), FUENTE, 0.38, COLOR_MENSAJE, 1)
        y += 19

    # ── Pie ───────────────────────────────────────────────────────────────────
    cv2.line(panel, (15, ALTO - 22), (ANCHO - 15, ALTO - 22), COLOR_SEPARADOR, 1)
    cv2.putText(panel, f"Mensajes totales: {_contador}   ESC = apagar",
                (15, ALTO - 8), FUENTE, 0.38, (70, 70, 70), 1)
    return panel


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    hilo_flask = threading.Thread(
        target=lambda: app.run(host=HOST, port=PORT,
                               debug=False, use_reloader=False),
        daemon=True
    )
    hilo_flask.start()
    print(f"[CHAT-SERVIDOR] Escuchando en http://{HOST}:{PORT}")
    print("[CHAT-SERVIDOR] ESC para apagar.")

    try:
        while True:
            panel = dibujar_panel()
            cv2.imshow("Chat Distribuido  [Servicio Web REST]", panel)
            if cv2.waitKey(300) & 0xFF == 27:
                break
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        print("[CHAT-SERVIDOR] Apagado.")


if __name__ == '__main__':
    main()
