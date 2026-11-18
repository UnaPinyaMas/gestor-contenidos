"""Menú de TerraHub: estados, toques y dibujo de cada pantalla (entrega de diseño v2)."""
import math
from pathlib import Path
import socket
import subprocess
import threading
import time
import pygame
from video_player import VideoPlayer
from juegos import ejecutar_juego, buscar_juegos, JUEGOS
from documentos import LectorDocumento
import interfaz_video as iv
import interfaz_inicio
import interfaz_redes
import interfaz_juegos
import interfaz_musica
import interfaz_teclado
import interfaz_fondo
import interfaz_videos
import interfaz_libros
import interfaz_imagenes
import fondo as fondos
import miniaturas
import estilo
import tiempo

ANCHO, ALTO = 800, 600
BASE = Path(__file__).resolve().parent
RECURSOS = BASE / "recursos"
# Secciones del carrusel de Inicio. Libros agrupa dos carpetas.
CARPETAS = {"Audio": "audio", "Vídeos": "videos", "Libros": ("pdf", "epub"),
            "Imágenes": "imagenes", "Juegos": "juegos"}
VIDEO_EXT = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".mpg", ".mpeg", ".ts"}
AUDIO_EXT = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac", ".opus", ".wma"}
FOTO_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
LIBRO_EXT = {".pdf", ".epub", ".cbz"}
JUEGO_EXT = {".gb", ".gbc", ".sgb"}
FONDO = (10, 15, 20)
AZUL = (21, 101, 192)
POR_PAGINA = 5
CONTROLES_MS = 3500        # tiempo que siguen visibles los controles del vídeo
MOVER = (pygame.MOUSEMOTION, pygame.FINGERMOTION)
SOLTAR = (pygame.MOUSEBUTTONUP, pygame.FINGERUP)

# Pantallas táctiles nuevas (toques al soltar, deslizar con inercia).
TACTILES = ("menu", "ajustes", "fondo", "redes", "clave", "juegos", "musica", "audio",
            "videos", "video", "libros", "documento", "imagenes", "foto")
CON_BARRA = ("menu", "ajustes", "fondo", "redes", "clave", "juegos", "musica", "audio", "videos", "libros",
             "imagenes")
PAGINADAS = ("juegos", "musica", "videos", "imagenes")


def direccion_ip():
    """IP local por la que sale el tráfico (no envía nada: UDP sin datos)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return "sin red"


def ejecutar_energia(verbo):
    """Apaga ('poweroff') o reinicia ('reboot') la Raspberry; True si se ha pedido bien.

    El servicio no tiene sesión de usuario, así que logind pediría contraseña:
    se usa sudo sin contraseña solo para estas órdenes (deploy/terrahub.sudoers).
    """
    try:
        r = subprocess.run(["sudo", "-n", "/usr/bin/systemctl", verbo],
                           capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired) as error:
        print("Energía:", error, flush=True)
        return False
    if r.returncode:
        print("Energía:", r.stderr.strip(), flush=True)
    return r.returncode == 0


def buscar_archivos(carpetas, extensiones, excluir=()):
    """Archivos con esas extensiones dentro de las carpetas (sin ocultos), por nombre."""
    encontrados = []
    for carpeta in carpetas:
        carpeta.mkdir(parents=True, exist_ok=True)
        for p in carpeta.rglob("*"):
            partes = p.relative_to(carpeta).parts
            if (p.is_file() and p.suffix.lower() in extensiones and p.name not in excluir
                    and not any(parte.startswith(".") for parte in partes)):
                encontrados.append(p)
    return sorted(encontrados, key=lambda p: p.stem.casefold())


class Vista:
    """Pantalla: lienzo de 800x600 escalado (explorador antiguo) o 'completo' a la
    resolución real (todas las pantallas del diseño). Recursos de cada pantalla, al usarse."""
    PANTALLAS = {
        "inicio": interfaz_inicio.PantallaInicio, "ajustes": interfaz_inicio.PantallaAjustes,
        "redes": interfaz_redes.PantallaRedes, "juegos": interfaz_juegos.PantallaJuegos,
        "musica": interfaz_musica.PantallaMusica, "audio": interfaz_musica.PantallaAudio,
        "fondos": interfaz_fondo.PantallaFondo, "clave": interfaz_teclado.PantallaClave,
        "videos": interfaz_videos.PantallaVideos, "video": interfaz_videos.PantallaVideo,
        "libros": interfaz_libros.PantallaLibros, "lector": interfaz_libros.PantallaLector,
        "imagenes": interfaz_imagenes.PantallaImagenes, "visor": interfaz_imagenes.PantallaVisor,
    }

    def __init__(self):
        self.pantalla = pygame.display.get_surface()
        self.lienzo = pygame.Surface((ANCHO, ALTO)).convert()
        self.cache = pygame.Surface(self.pantalla.get_size()).convert()
        w, h = self.pantalla.get_size()
        escala = min(w / ANCHO, h / ALTO)
        self.area = pygame.Rect(0, 0, round(ANCHO * escala), round(ALTO * escala))
        self.area.center = self.pantalla.get_rect().center
        self.fuente = pygame.font.Font(None, 30)
        self.completo = pygame.Surface((w, h)).convert()
        self.modo_completo = False
        self.esc = interfaz_inicio.Escala((w, h))
        self._pantallas = {}
        self._tornar = {}
        self.atras = None            # rectángulo del Tornar visible (o None)
        self.botones = []

    def __getattr__(self, nombre):
        # self.inicio, self.ajustes, self.redes...: cada pantalla se monta la primera vez.
        clase = Vista.PANTALLAS.get(nombre)
        if clase is None:
            raise AttributeError(nombre)
        pantallas = self.__dict__["_pantallas"]
        if nombre not in pantallas:
            pantallas[nombre] = clase(self.__dict__["pantalla"].get_size())
        return pantallas[nombre]

    def tornar(self, rect):
        """Control Tornar en la posición 'rect' (px del diseño), montado una vez."""
        clave = tuple(rect)
        if clave not in self._tornar:
            self._tornar[clave] = interfaz_inicio.BotonTornar(self.esc, rect)
        return self._tornar[clave]

    def texto(self, texto, centro, ancho=750, izquierda=False, sup=None):
        while self.fuente.size(texto)[0] > ancho and len(texto) > 4:
            texto = texto[:-4] + "..."
        imagen = self.fuente.render(texto, True, (255, 255, 255))
        rect = imagen.get_rect(midleft=centro) if izquierda else imagen.get_rect(center=centro)
        (sup or self.lienzo).blit(imagen, rect)

    def zona(self, rect, accion):
        """Zona táctil (lo que se pinta lo hace cada pantalla)."""
        self.botones.append((pygame.Rect(rect), accion))

    def boton(self, nombre, rect, accion, color=AZUL):
        rect = pygame.Rect(rect)
        pygame.draw.rect(self.lienzo, color, rect, border_radius=12)
        self.texto(nombre, rect.center, rect.width - 20)
        self.botones.append((rect, accion))

    def posicion(self, evento, tipos=(pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN)):
        """Posición en el lienzo de un toque/clic de los tipos indicados, o None."""
        pos = self.posicion_pantalla(evento, tipos)
        if pos is None or self.modo_completo:
            return pos
        if not self.area.collidepoint(pos):
            return None
        return ((pos[0] - self.area.x) * ANCHO / self.area.width,
                (pos[1] - self.area.y) * ALTO / self.area.height)

    def posicion_pantalla(self, evento, tipos=(pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN)):
        """Posición en píxeles de la pantalla (también fuera del lienzo), o None."""
        if evento.type not in tipos or getattr(evento, "touch", False):
            return None
        if evento.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            if evento.button != 1:
                return None
            pos = evento.pos
        elif evento.type == pygame.MOUSEMOTION:
            if not evento.buttons[0]:
                return None
            pos = evento.pos
        else:
            w, h = self.pantalla.get_size()
            pos = (evento.x * w, evento.y * h)
        return pos

    def preparar(self):
        if self.modo_completo:
            return                      # 'completo' ya está a la resolución de la pantalla
        self.cache.fill((0, 0, 0))
        pygame.transform.scale(self.lienzo, self.area.size, self.cache.subsurface(self.area))

    def presentar(self):
        self.pantalla.blit(self.completo if self.modo_completo else self.cache, (0, 0))
        pygame.display.flip()


class Menu:
    def __init__(self):
        self.vista = Vista()
        self.estado = "menu"
        self.ejecutando = True
        self.sucio = True
        self.categoria = ""
        self.raiz = self.carpeta = None
        self.archivos = []
        self.pagina = 0
        self.aviso = ""
        self.player = None
        self.pausa = False
        self.nombre = ""
        self.documento = None
        self.pagina_documento = None
        self.volumen = 70
        self.silencio = False
        self.posicion = 0.0
        self.duracion = None
        self.controles_hasta = 0
        self.controles_dibujados = False
        self.proxima_consulta = 0
        self.arrastre = None        # (tipo, barra) mientras se desliza una barra
        self.fraccion_arrastre = 0.0
        self.subcarpetas = None     # carpetas que agrupa la sección (Libros)
        # Carrusel de Inicio: posición animada y destino (índice en SECCIONES).
        self.carrusel = self.carrusel_destino = 1.0     # empieza en Vídeos
        self.toque = None           # el dedo en una pantalla táctil (ver evento_inicio)
        self.aviso_inicio = ""
        self.aviso_inicio_hasta = 0
        # Círculo de la barra superior: 0 = en la esquina, 1 = cubre la pantalla (ajustes).
        self.panel = self.panel_destino = 0.0
        self.confirmar = (None, 0)    # acciones delicadas piden un segundo toque: (acción, hasta)
        self.hora_pintada = ""
        self.origen_redes = "menu"    # a dónde vuelve 'Redes' (la pantalla desde la que se abrió)
        self.captura = None           # ajustes que se ven dentro del círculo al crecer/encoger
        self.ajustes_scroll = self.ajustes_vel = 0.0
        self.energia = self.energia_destino = 0.0
        self.ip = ""
        # Contraseña Wi-Fi (teclado táctil) y conexión en curso.
        self.clave_red = None
        self.clave = ""
        self.clave_ver = self.clave_mayus = self.clave_simbolos = False
        self.conectando = None        # ssid mientras nmcli conecta (en otro hilo)
        self.resultado_red = None     # (ssid, conseguido, mensaje, con_clave) al acabar
        # Fondo de pantalla del Inicio (imagen, GIF o MP4) y su pantalla de ajustes.
        self.fondo = fondos.Fondo(self.vista.pantalla.get_size(),
                                  crear_reproductor=lambda ruta, tam: VideoPlayer(ruta, audio=False, size=tam))
        self.lista_fondos = []
        self.fondo_scroll = self.fondo_vel = 0.0
        # Control Tornar: violeta mientras se pulsa; vuelve al soltar encima.
        self.atras_pulsado = False
        # Redes disponibles: None mientras nmcli busca; lista desplazable con inercia.
        self.redes = None
        self.redes_scroll = 0.0
        self.redes_vel = 0.0
        self._ultimo_tick = tiempo.ms()
        # Juegos, Música, Vídeos e Imágenes: listas y página visible (decimal al deslizar).
        self.lista_juegos = []
        self.juegos_pos = self.juegos_destino = 0.0
        self.pistas = []
        self._pistas = {}                    # ruta -> Pista (los metadatos se leen una vez)
        self.musica_pos = self.musica_destino = 0.0
        self.pista_actual = None
        self.indice_pista = None
        self.origen_audio = "carpeta"        # a dónde vuelve 'Tornar' desde el reproductor
        self.letra_scroll = 0.0
        self.letra_vel = 0.0
        self.letra_tocada = -10 ** 9         # última vez que se movió la letra a mano (ms)
        self.lista_videos = []
        self.videos_pos = self.videos_destino = 0.0
        self.lista_fotos = []
        self.fotos_pos = self.fotos_destino = 0.0
        self.foto_indice = 0
        self.foto_desplazamiento = 0.0       # el dedo arrastra la foto del visor
        self.lista_libros = []
        self.libros_pos = self.libros_destino = 0.0
        self.doc_arrastre = (0.0, 0.0)       # el dedo arrastra la página ampliada
        self.origen_contenido = "carpeta"    # a dónde vuelven el vídeo, el lector y el visor
        self.panel_video = False             # ajustes (volumen) del reproductor de vídeo
        self.miniaturas = miniaturas.Miniaturas(avisar=self._miniatura_lista)

    def _miniatura_lista(self):
        self.sucio = True                    # desde el hilo de miniaturas: repintar

    # --- Música ------------------------------------------------------------------------
    def _pista(self, ruta):
        """Pista de una ruta; sus metadatos (ffprobe/ffmpeg) se leen en segundo plano."""
        ruta = Path(ruta)
        if ruta not in self._pistas:
            pista = self._pistas[ruta] = interfaz_musica.Pista(ruta)

            def leer():
                interfaz_musica.leer_metadatos(pista)
                self.sucio = True
            threading.Thread(target=leer, daemon=True).start()
        return self._pistas[ruta]

    def abrir_musica(self):
        """Pantalla 'Music' con los audios de recursos/audio."""
        self.estado = "musica"
        rutas = interfaz_musica.buscar_audios(RECURSOS / "audio", AUDIO_EXT)
        self.pistas = [self._pista(r) for r in rutas]
        ultima = self._ultima_pagina()
        self.musica_pos = self.musica_destino = float(min(round(self.musica_destino), ultima))
        self.sucio = True

    def pista_contigua(self, paso):
        """⏮ / ⏭. ⏮ vuelve al principio si la pista lleva más de 3 s (como los reproductores
        habituales). Fuera de la lista Music, o en los extremos, solo se reinicia la pista."""
        if paso < 0 and self.posicion > 3:
            self.player.command("seek", "0", "absolute")
            self.posicion = 0.0
            return
        nuevo = None if self.indice_pista is None else self.indice_pista + paso
        if nuevo is not None and 0 <= nuevo < len(self.pistas):
            self.reproducir_pista(nuevo)
        elif paso < 0:
            self.player.command("seek", "0", "absolute")
            self.posicion = 0.0
        else:
            self.avisar_inicio("Es la última pista", 2000)

    def reproducir_pista(self, indice):
        """Abre una pista de la lista en el reproductor (también para anterior/siguiente)."""
        if self.player:
            self.player.close()
            self.player = None
        self.indice_pista = indice
        self.raiz = self.carpeta = RECURSOS / "audio"
        self.subcarpetas = None
        self.origen_audio = "musica"
        self.abrir(self.pistas[indice].ruta)
        if self.estado != "audio":            # no se pudo abrir: aviso en la lista
            self.estado = "musica"
            self.avisar_inicio(self.aviso or "No se pudo reproducir", 4000)

    # --- Juegos, Vídeos, Libros e Imágenes ---------------------------------------------
    def abrir_juegos(self, aviso=""):
        """Pantalla 'Games' con los juegos de recursos/juegos."""
        self.estado = "juegos"
        self.lista_juegos = buscar_juegos()
        ultima = interfaz_juegos.paginas(len(self.lista_juegos)) - 1
        self.juegos_pos = self.juegos_destino = float(min(round(self.juegos_destino), ultima))
        if aviso:
            self.avisar_inicio(aviso, 4000)
        self.sucio = True

    def lanzar_juego(self, indice):
        """Abre el juego con RetroArch; si falla, se queda en 'Games' con el aviso."""
        self.raiz = self.carpeta = JUEGOS
        self.subcarpetas = None
        self.aviso = ""
        self.abrir(self.lista_juegos[indice])   # normalmente no vuelve (relanza TerraHub)
        self.estado = "juegos"
        if self.aviso:
            self.avisar_inicio(self.aviso, 4000)

    def abrir_videos(self):
        self.estado = "videos"
        self.lista_videos = buscar_archivos([RECURSOS / "videos"], VIDEO_EXT, excluir=("intro.mp4",))
        ultima = interfaz_videos.paginas(len(self.lista_videos)) - 1
        self.videos_pos = self.videos_destino = float(min(round(self.videos_destino), ultima))
        self.sucio = True

    def abrir_imagenes(self):
        self.estado = "imagenes"
        self.lista_fotos = buscar_archivos([RECURSOS / "imagenes"], FOTO_EXT)
        ultima = interfaz_videos.paginas(len(self.lista_fotos)) - 1
        self.fotos_pos = self.fotos_destino = float(min(round(self.fotos_destino), ultima))
        self.sucio = True

    def abrir_libros(self):
        self.estado = "libros"
        self.lista_libros = buscar_archivos([RECURSOS / "epub", RECURSOS / "pdf"], LIBRO_EXT)
        ultimo = max(0, len(self.lista_libros) - 1)
        self.libros_pos = self.libros_destino = float(min(round(self.libros_destino), ultimo))
        self.sucio = True

    def abrir_desde(self, origen, ruta):
        """Abre un vídeo, libro o imagen desde su pantalla (Tornar vuelve a ella)."""
        self.raiz = self.carpeta = ruta.parent
        self.subcarpetas = None
        self.abrir(ruta)
        if self.estado in ("video", "documento", "foto"):
            self.origen_contenido = origen
        elif self.aviso:                           # no se pudo abrir: aviso en la lista
            self.estado = origen
            self.avisar_inicio(self.aviso, 4000)
            self.aviso = ""

    def abrir_foto(self, indice):
        self.foto_indice = indice
        self.foto_desplazamiento = 0.0
        self.origen_contenido = "imagenes"
        self.estado = "foto"
        self.sucio = True

    def borrar_foto(self):
        """Borra la imagen del visor (con segundo toque de confirmación)."""
        if not self.lista_fotos or not self.confirmado("foto_borrar", "borrar la imagen"):
            return
        ruta = self.lista_fotos[self.foto_indice]
        try:
            ruta.unlink()
        except OSError as error:
            self.avisar_inicio(f"No se pudo borrar: {error.strerror or error}", 4000)
            return
        self.miniaturas.olvidar(ruta)
        del self.lista_fotos[self.foto_indice]
        self.avisar_inicio(f"{ruta.name} borrada", 3000)
        if not self.lista_fotos:
            self.volver()
            return
        self.foto_indice = min(self.foto_indice, len(self.lista_fotos) - 1)

    # --- Redes ---------------------------------------------------------------------------
    def abrir_redes(self):
        """Muestra 'Redes disponibles' y busca las redes en segundo plano."""
        if self.estado == "audio":
            self.cerrar_contenido()
            self.estado = self.origen_audio
        if self.estado not in ("redes", "clave"):
            self.origen_redes = self.estado
        self.estado = "redes"
        self.redes, self.redes_scroll, self.redes_vel = None, 0.0, 0.0

        def buscar():
            self.redes = interfaz_redes.buscar_redes()
            self.sucio = True
        threading.Thread(target=buscar, daemon=True).start()

    def tocar_red(self, ssid):
        """Fila de 'Redes disponibles': conectarse (con contraseña si hace falta)."""
        red = next((r for r in self.redes or [] if r["ssid"] == ssid), None)
        if red is None:
            return
        if red["conectada"]:
            self.avisar_inicio(f"Conectado a {ssid}  ·  IP {direccion_ip()}", 4000)
        elif red.get("empresa"):
            self.avisar_inicio("Las redes con usuario (802.1X) aún no se pueden configurar aquí", 4000)
        elif not red["segura"] or ssid in interfaz_redes.redes_guardadas():
            self.conectar_red(ssid)
        else:
            self.pedir_clave(red)

    def pedir_clave(self, red, aviso=""):
        """Pantalla de contraseña con teclado táctil."""
        self.clave_red = red
        self.clave = ""
        self.clave_ver = self.clave_mayus = self.clave_simbolos = False
        self.estado = "clave"
        if aviso:
            self.avisar_inicio(aviso, 4000)
        self.sucio = True

    def conectar_red(self, ssid, clave=None):
        """Conecta en otro hilo (nmcli tarda unos segundos); el resultado lo recoge
        fin_conexion desde el bucle principal."""
        if self.conectando:
            return
        if clave is not None and len(clave) < 8:
            self.avisar_inicio("La contraseña tiene al menos 8 caracteres", 3000)
            return
        self.conectando = ssid
        self.avisar_inicio(f"Conectando a {ssid}...", 60000)

        def conectar():
            conseguido, mensaje = interfaz_redes.conectar(ssid, clave)
            self.resultado_red = (ssid, conseguido, mensaje, clave is not None)
        threading.Thread(target=conectar, daemon=True).start()

    def fin_conexion(self):
        ssid, conseguido, mensaje, con_clave = self.resultado_red
        self.resultado_red = self.conectando = None
        if conseguido:
            self.clave = ""
            if self.estado in ("clave", "redes"):
                self.abrir_redes()               # vuelve a la lista, ya con la red nueva
            self.avisar_inicio(f"{mensaje}  ·  IP {direccion_ip()}", 4000)
            return
        red = next((r for r in self.redes or [] if r["ssid"] == ssid), None)
        if (not con_clave and red and red["segura"] and self.estado == "redes"
                and "permiso" not in mensaje):
            # La contraseña guardada ya no vale: pedirla.
            self.pedir_clave(red, "Escribe la contraseña de la red")
        else:
            self.avisar_inicio(mensaje, 4000)

    def tecla(self, valor):
        """Tecla del teclado de contraseña (táctil o física)."""
        if self.conectando:
            return
        if valor == "borrar":
            self.clave = self.clave[:-1]
        elif valor == "mayus":
            self.clave_mayus = not self.clave_mayus
        elif valor == "modo":
            self.clave_simbolos = not self.clave_simbolos
        elif valor == "ver":
            self.clave_ver = not self.clave_ver
        elif valor == "conectar":
            self.conectar_red(self.clave_red["ssid"], self.clave)
        elif len(self.clave) < interfaz_teclado.LARGO_MAXIMO:
            letra = " " if valor == "espacio" else valor
            self.clave += letra.upper() if self.clave_mayus else letra
        self.sucio = True

    # --- Tornar --------------------------------------------------------------------------
    def tornar_visible(self):
        """Posición (px del diseño) del Tornar de la pantalla actual, o None."""
        e = self.estado
        if e in ("redes", "clave", "fondo"):
            return interfaz_inicio.TORNAR_BANDA
        if e in ("juegos", "musica", "videos", "libros", "imagenes") or (e == "audio" and self.player):
            return interfaz_inicio.TORNAR_CABECERA
        if e == "video" and self.player is not None:
            return interfaz_inicio.TORNAR_COMPLETO if self.controles_dibujados else None
        if e in ("documento", "foto", "carpeta"):
            return interfaz_inicio.TORNAR_COMPLETO
        return None

    def evento_atras(self, evento):
        """Toques sobre el Tornar: violeta al pulsar, 'volver' al soltar encima."""
        v = self.vista
        if evento.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN):
            p = v.posicion_pantalla(evento)
            if p is not None and v.atras is not None and v.atras.toca(p):
                self.atras_pulsado = True
                if self.estado == "video":
                    self.mostrar_controles()
                self.sucio = True
                return True
            return False
        if not self.atras_pulsado:
            return False
        if evento.type in SOLTAR:
            p = v.posicion_pantalla(evento, SOLTAR)
            self.atras_pulsado = False
            self.sucio = True
            if p is None or (v.atras is not None and v.atras.toca(p)):
                self.accion("volver")
            return True
        return evento.type in MOVER

    # --- utilidades ----------------------------------------------------------------------
    def redes_maximo(self):
        return interfaz_redes.desplazamiento_maximo(len(self.redes or []))

    def desplazar_redes(self, filas):
        """Teclado: desliza la lista unas filas (con la misma inercia que el dedo)."""
        self.redes_vel = filas * interfaz_redes.PASO * 5.2
        self.sucio = True

    def k_diseno(self):
        """Píxeles de pantalla por píxel del diseño."""
        return self.vista.esc.k

    def avisar_inicio(self, texto, ms=2500):
        self.aviso_inicio = texto
        self.aviso_inicio_hasta = tiempo.ms() + ms
        self.sucio = True

    def confirmado(self, accion, verbo):
        """Acciones delicadas: el primer toque avisa; True si es el segundo (antes de 4 s)."""
        if self.confirmar[0] != accion or tiempo.ms() > self.confirmar[1]:
            self.confirmar = (accion, tiempo.ms() + 4000)
            self.avisar_inicio(f"Toca otra vez para {verbo}", 4000)
            return False
        self.confirmar = (None, 0)
        return True

    def energia_sistema(self, accion, verbo, texto):
        """Apagar/reiniciar, con confirmación: muestra el aviso ya (la orden puede
        tardar) y llama a systemctl."""
        if not self.confirmado(accion, accion):
            return
        self.avisar_inicio(texto, 15000)
        self.dibujar()
        self.vista.presentar()
        if not ejecutar_energia(verbo):
            self.avisar_inicio("No se pudo: falta el permiso de deploy/instalar.sh", 4000)

    def girar(self, paso):
        """Mueve el carrusel de Inicio un elemento, una página (Games, Music, Vídeos,
        Imágenes) o un libro."""
        if self.estado in PAGINADAS + ("libros",):
            _, destino = self._carrusel_activo()
            nuevo = max(0, min(self._ultima_pagina(), round(getattr(self, destino)) + paso))
            setattr(self, destino, float(nuevo))
        else:
            self.carrusel_destino += paso
        self.sucio = True

    def animar_inicio(self):
        """Avanza carruseles, listas y el círculo según el tiempo real; True si hay que repintar.

        Va por tiempo (no por fotogramas), así el movimiento es igual de suave aunque
        la Raspberry dibuje a menos de 60 fps.
        """
        ahora = tiempo.ms()
        dt = min(.05, max(.001, (ahora - self._ultimo_tick) / 1000))
        self._ultimo_tick = ahora
        if self.resultado_red:                    # nmcli ha acabado (en otro hilo)
            self.fin_conexion()
            return True
        arrastrando = self.toque is not None and self.toque["arrastre"]
        cambio = False
        acercar = 1 - math.exp(-dt * 14)          # recolocación (~0,3 s)
        for actual, destino in (("carrusel", "carrusel_destino"), ("energia", "energia_destino"),
                                ("juegos_pos", "juegos_destino"), ("musica_pos", "musica_destino"),
                                ("videos_pos", "videos_destino"), ("fotos_pos", "fotos_destino"),
                                ("libros_pos", "libros_destino")):
            a, d = getattr(self, actual), getattr(self, destino)
            if a != d and not arrastrando:
                a += (d - a) * acercar
                setattr(self, actual, d if abs(a - d) < .002 else a)
                cambio = True
        if self.foto_desplazamiento and not arrastrando:   # la foto vuelve a su sitio
            self.foto_desplazamiento *= math.exp(-dt * 16)
            if abs(self.foto_desplazamiento) < 1:
                self.foto_desplazamiento = 0.0
            cambio = True
        vertical = self._vertical()
        if vertical and not arrastrando:
            scroll, vel, maximo = vertical
            s, v = getattr(self, scroll), getattr(self, vel)
            if v:
                s += v * dt
                v *= math.exp(-dt * 5)                    # frenado de la inercia
                if abs(v) < 15:
                    v = 0.0
            elif self.estado == "audio" and tiempo.ms() - self.letra_tocada > 4000:
                # Letra .lrc: seguir la línea que suena (si no se ha movido a mano hace poco).
                linea = self.vista.audio.linea_actual(self.pista_actual, self.posicion)
                if linea is not None:
                    objetivo = min(max(interfaz_musica.LINEA * linea - 150, 0), maximo)
                    s += (objetivo - s) * (1 - math.exp(-dt * 6))
                    if abs(objetivo - s) < .5:
                        s = objetivo
            fuera = s - min(max(s, 0), maximo)
            if fuera:                                     # rebote suave en los bordes
                v = 0.0
                s -= fuera * (1 - math.exp(-dt * 16))
                if abs(s - min(max(s, 0), maximo)) < .5:
                    s = min(max(s, 0), maximo)
            setattr(self, vel, v)
            if s != getattr(self, scroll):
                setattr(self, scroll, s)
                cambio = True
        if self.panel != self.panel_destino:
            # Círculo de la barra: crece o encoge en ~0,35 s.
            paso = dt / .35
            if self.panel < self.panel_destino:
                self.panel = min(self.panel_destino, self.panel + paso)
            else:
                self.panel = max(self.panel_destino, self.panel - paso)
            if self.panel >= 1:                       # ya cubre la pantalla: ajustes
                self.panel = self.panel_destino = 0.0
                self.estado = "ajustes"
                self.captura = None
            elif self.panel <= 0:
                self.captura = None
            cambio = True
        if self.estado in CON_BARRA and time.strftime("%H:%M") != self.hora_pintada:
            cambio = True                             # la hora de la barra ha cambiado
        if self.aviso_inicio and tiempo.ms() > self.aviso_inicio_hasta:
            self.aviso_inicio = ""
            cambio = True
        return cambio

    def abrir_panel(self):
        """Círculo de la barra: crece hasta Configuración; en Configuración, se cierra.
        Desde otra pantalla se vuelve primero al Inicio y crece desde allí."""
        if self.estado == "ajustes":
            self.cerrar_panel()
            return
        if self.estado != "menu":
            self.cerrar_contenido()
            self.estado = "menu"
        if self.panel == 0:
            self.ajustes_scroll = self.ajustes_vel = 0.0
            self.energia = self.energia_destino = 0.0
            self.confirmar = (None, 0)
            self.ip = direccion_ip()
            self.capturar_ajustes()
            self.panel_destino = 1.0
        self.sucio = True

    def cerrar_panel(self):
        """De Configuración al Inicio: el círculo encoge hasta la esquina."""
        self.capturar_ajustes()
        self.estado = "menu"
        self.panel, self.panel_destino = 1.0, 0.0
        self.confirmar = (None, 0)
        self.sucio = True

    def valores_ajustes(self):
        return {"ajuste_fecha": time.strftime("%H:%M · %d/%m/%Y"), "ajuste_ip": self.ip}

    def capturar_ajustes(self):
        """Pinta Configuración, tal cual se verá, para mostrarla dentro del círculo.

        Se hace antes de empezar la animación (montarla la primera vez tarda) y se
        reinicia el reloj de la animación para que no dé un salto.
        """
        v = self.vista
        if self.captura is None:
            self.captura = pygame.Surface(v.completo.get_size()).convert()
        v.ajustes.dibujar(self.captura, self.ajustes_scroll, self.energia, lambda r, a: None,
                          hora=time.strftime("%H:%M"), valores=self.valores_ajustes())
        self._ultimo_tick = tiempo.ms()

    def seccion_central(self):
        """Acción del elemento central del carrusel de Inicio."""
        n = len(interfaz_inicio.SECCIONES)
        return interfaz_inicio.SECCIONES[round(self.carrusel_destino) % n][1]

    def accion_ajuste(self, accion):
        if accion == "ajuste_fecha":
            self.avisar_inicio(time.strftime("%H:%M · %d/%m/%Y"), 4000)
        elif accion == "ajuste_ip":
            self.avisar_inicio("IP: " + direccion_ip(), 5000)
        elif accion == "ajuste_redes":
            self.abrir_redes()
        elif accion == "ajuste_fondo":
            self.lista_fondos = fondos.buscar_fondos(RECURSOS)
            self.fondo_scroll = self.fondo_vel = 0.0
            self.estado = "fondo"

    # --- reproductor ---------------------------------------------------------------------
    def controles_visibles(self):
        return (self.estado == "audio" or self.pausa or self.panel_video or self.arrastre is not None or
                tiempo.ms() < self.controles_hasta)

    def arrastrar(self, pos):
        """El dedo se mueve sobre una barra: el volumen cambia ya; el vídeo salta al soltar."""
        tipo, barra = self.arrastre
        self.fraccion_arrastre = max(0.0, min(1.0, (pos[0] - barra.x) / barra.width))
        if tipo.startswith("fondo_"):            # deslizables HSV del fondo de pantalla
            nombre = {"fondo_h": "tono", "fondo_s": "saturacion", "fondo_v": "brillo"}[tipo]
            self.fondo.ajustar(**{nombre: interfaz_fondo.valor(tipo, self.fraccion_arrastre)})
            self.sucio = True
            return
        if tipo == "volumen":
            self.accion(("volumen", self.fraccion_arrastre))
        elif self.duracion:
            self.posicion = self.fraccion_arrastre * self.duracion
        self.mostrar_controles()

    def soltar(self, pos):
        if pos is not None:
            self.arrastrar(pos)
        tipo, _ = self.arrastre
        self.arrastre = None
        if tipo.startswith("fondo_"):
            self.fondo.guardar()
            self.sucio = True
            return
        if tipo == "buscar":
            self.accion(("buscar", self.fraccion_arrastre))
        self.mostrar_controles()

    def mostrar_controles(self):
        self.controles_hasta = tiempo.ms() + CONTROLES_MS
        self.sucio = True

    def consultar_tiempo(self):
        """Lee posición y duración de mpv como mucho 4 veces por segundo."""
        ahora = tiempo.ms()
        if ahora < self.proxima_consulta:
            return
        self.proxima_consulta = ahora + 250
        if self.arrastre and self.arrastre[0] == "buscar":
            return  # mientras se arrastra, la barra sigue al dedo y no a mpv
        posicion = self.player.propiedad("time-pos")
        duracion = self.player.propiedad("duration")
        if posicion is not None and int(posicion) != int(self.posicion):
            self.sucio = True
        if duracion != self.duracion:
            self.sucio = True
        self.posicion = posicion if posicion is not None else self.posicion
        self.duracion = duracion

    def deslizar(self, tipo, fraccion):
        """Toque en la barra de progreso (saltar) o en la de volumen."""
        fraccion = max(0.0, min(1.0, fraccion))
        if tipo == "buscar":
            self.player.command("seek", f"{fraccion * 100:.2f}", "absolute-percent")
            if self.duracion:
                self.posicion = fraccion * self.duracion
        elif tipo == "volumen":
            self.volumen = round(fraccion * 20) * 5
            self.silencio = False
            self.player.command("set", "mute", "no")
            self.player.command("set", "volume", str(self.volumen))
        self.mostrar_controles()

    # --- explorador de carpetas (antiguo: solo al volver del emulador a otra carpeta) ---
    def actualizar(self):
        try:
            if self.subcarpetas and self.carpeta == self.raiz:
                self.archivos = [self.raiz / s for s in self.subcarpetas]
                for carpeta in self.archivos:
                    carpeta.mkdir(parents=True, exist_ok=True)
            else:
                self.carpeta.mkdir(parents=True, exist_ok=True)
                self.archivos = sorted(
                    (p for p in self.carpeta.iterdir() if not p.name.startswith(".")),
                    key=lambda p: (not p.is_dir(), p.name.casefold()))
            self.aviso = ""
        except OSError as error:
            self.archivos = []
            self.aviso = "No se puede leer esta carpeta."
            print(error, flush=True)
        self.pagina = min(self.pagina, max(0, (len(self.archivos) - 1) // POR_PAGINA))
        self.sucio = True

    def abrir_carpeta(self, carpeta, aviso=""):
        """Abre la sección de una carpeta, p. ej. al volver del emulador."""
        carpeta = Path(carpeta).resolve()
        for nombre, subs in CARPETAS.items():
            for sub in (subs if isinstance(subs, tuple) else (subs,)):
                raiz = RECURSOS / sub
                if carpeta.is_relative_to(raiz.resolve()):
                    if nombre == "Juegos":
                        self.abrir_juegos(aviso)        # al volver del emulador: pantalla Games
                    else:
                        self.accion(nombre)
                        if aviso:
                            self.avisar_inicio(aviso, 4000)
                    return

    def cerrar_contenido(self):
        self.arrastre = None
        self.panel_video = False
        if self.player:
            self.player.close()
            self.player = None
        if self.documento:
            self.documento.close()
            self.documento = None
        self.pagina_documento = None

    def volver(self):
        self.cerrar_contenido()
        if self.estado == "fondo":
            self.estado = "ajustes"
        elif self.estado == "clave":
            self.estado = "redes"
            self.clave = ""
        elif self.estado == "redes":
            self.estado = self.origen_redes  # la pantalla desde la que se abrió
        elif self.estado == "ajustes":
            self.cerrar_panel()
        elif self.estado == "audio":
            self.estado = self.origen_audio  # lista 'Music' o carpeta, según desde dónde se abrió
        elif self.estado in ("video", "foto", "documento"):
            self.estado = self.origen_contenido
            if self.estado == "carpeta" and self.carpeta is None:
                self.estado = "menu"
        elif self.estado == "carpeta" and self.carpeta != self.raiz:
            self.carpeta = self.carpeta.parent
            self.pagina = 0
            self.actualizar()
        else:
            self.estado = "menu"
        self.aviso = ""
        self.sucio = True

    def abrir(self, path):
        path = Path(path)
        try:
            raices = ([self.raiz / s for s in self.subcarpetas] if self.subcarpetas
                      else [self.raiz])
            if not any(path.resolve().is_relative_to(r.resolve()) for r in raices):
                self.aviso = "Este enlace apunta fuera de la carpeta."
            elif path.is_dir():
                self.carpeta = path
                self.pagina = 0
                self.actualizar()
            elif path.suffix.lower() in JUEGO_EXT:
                try:
                    ejecutar_juego(path)
                finally:
                    self.vista = Vista()
                    self.actualizar()
            elif path.suffix.lower() in LIBRO_EXT:
                tam = interfaz_libros.tam_pagina(self.vista.pantalla.get_size())
                self.documento = LectorDocumento(path, size=tam)
                self.pagina_documento = self.documento.render()
                self.doc_arrastre = (0.0, 0.0)
                self.origen_contenido = "carpeta"
                self.estado = "documento"
                self.nombre = path.name
            elif path.suffix.lower() in VIDEO_EXT | AUDIO_EXT:
                es_audio = path.suffix.lower() in AUDIO_EXT
                self.player = VideoPlayer(path, video=not es_audio,
                                          size=self.vista.pantalla.get_size())
                self.player.command("set", "volume", str(self.volumen))
                if es_audio:
                    if self.estado == "carpeta":     # abierto desde el explorador, no desde Music
                        self.origen_audio, self.indice_pista = "carpeta", None
                    self.pista_actual = self._pista(path)
                    self.letra_scroll, self.letra_vel = 0.0, 0.0
                    self.letra_tocada = -10 ** 9
                else:
                    self.origen_contenido = "carpeta"
                self.estado = "audio" if es_audio else "video"
                self.pausa = False
                self.silencio = False
                self.panel_video = False
                self.posicion, self.duracion = 0.0, None
                self.nombre = path.name
                self.mostrar_controles()
            elif path.suffix.lower() in FOTO_EXT:
                if path not in self.lista_fotos:
                    self.lista_fotos = [path]
                self.abrir_foto(self.lista_fotos.index(path))
                self.origen_contenido = "carpeta"
            else:
                self.aviso = f"{path.name}: {path.stat().st_size:,} bytes. Visor pendiente."
        except Exception as error:
            self.cerrar_contenido()
            self.estado = "carpeta"
            self.aviso = "No se ha podido abrir el archivo: " + str(error)
            print("Error al abrir:", error, flush=True)
        self.sucio = True

    def accion_documento(self, accion):
        try:
            if accion == "doc_anterior":
                self.documento.mover_pagina(-1)
            elif accion == "doc_siguiente":
                self.documento.mover_pagina(1)
            elif accion in ("doc_mas", "doc_menos"):
                paso = 2 / 22 if self.documento.doc.is_reflowable else .5
                self.documento.ampliar(paso if accion == "doc_mas" else -paso)
            elif accion != "doc_pagina":
                dx, dy = {"doc_izq": (-90, 0), "doc_der": (90, 0),
                          "doc_arriba": (0, -90), "doc_abajo": (0, 90)}[accion]
                self.documento.desplazar(dx, dy)
            self.pagina_documento = self.documento.render()
        except Exception as error:
            self.volver()
            self.aviso = "No se pudo leer la página: " + str(error)
            self.avisar_inicio(self.aviso, 4000)

    def accion(self, accion):
        self.sucio = True
        if isinstance(accion, Path):
            self.abrir(accion)
        elif accion == "Juegos":
            self.abrir_juegos()
        elif accion == "Audio":
            self.abrir_musica()
        elif accion == "Vídeos":
            self.abrir_videos()
        elif accion == "Imágenes":
            self.abrir_imagenes()
        elif accion == "Libros":
            self.abrir_libros()
        elif isinstance(accion, tuple) and accion[0] == "pista":
            self.reproducir_pista(accion[1])
        elif isinstance(accion, tuple) and accion[0] == "video":
            self.abrir_desde("videos", self.lista_videos[accion[1]])
        elif isinstance(accion, tuple) and accion[0] == "libro":
            self.abrir_desde("libros", self.lista_libros[accion[1]])
        elif isinstance(accion, tuple) and accion[0] == "foto":
            self.abrir_foto(accion[1])
        elif isinstance(accion, tuple) and accion[0] == "foto_ir":
            self.foto_indice = accion[1]
            self.foto_desplazamiento = 0.0
        elif accion == "foto_borrar":
            self.borrar_foto()
        elif accion in ("musica_izq", "juegos_izq", "libros_izq", "carrusel_izq"):
            self.girar(-1)
        elif accion in ("musica_der", "juegos_der", "libros_der", "carrusel_der"):
            self.girar(1)
        elif accion in ("audio_anterior", "audio_siguiente") and self.player:
            self.pista_contigua(-1 if accion == "audio_anterior" else 1)
        elif isinstance(accion, tuple) and accion[0] == "juego":
            self.lanzar_juego(accion[1])
        elif isinstance(accion, tuple) and accion[0] == "red":
            self.tocar_red(accion[1])
        elif isinstance(accion, tuple) and accion[0] == "tecla":
            self.tecla(accion[1])
        elif isinstance(accion, tuple) and accion[0] == "fondo_elegir":
            i = accion[1]
            self.fondo.elegir(self.lista_fondos[i] if 0 <= i < len(self.lista_fondos) else None)
        elif accion == "fondo_restablecer":
            self.fondo.restablecer()
        elif accion == "salir_terminal":
            # El servicio no se reinicia al salir bien y vuelve a la consola (chvt 1).
            if self.confirmado(accion, "salir a la terminal"):
                self.ejecutando = False
        elif accion in CARPETAS:
            self.categoria = accion
            sub = CARPETAS[accion]
            self.subcarpetas = sub if isinstance(sub, tuple) else None
            self.raiz = self.carpeta = RECURSOS if self.subcarpetas else RECURSOS / sub
            self.pagina = 0
            self.estado = "carpeta"
            self.actualizar()
        elif accion == "panel":
            self.abrir_panel()
        elif accion == "energia":
            # Despliega o pliega Suspender / Reiniciar / Apagar bajo 'Opciones de energía'.
            self.energia_destino = 0.0 if self.energia_destino else 1.0
            self.confirmar = (None, 0)
        elif accion == "redes":
            self.abrir_redes()
        elif accion in ("ajuste_fecha", "ajuste_redes", "ajuste_ip", "ajuste_fondo"):
            self.accion_ajuste(accion)
        elif accion == "apagar":
            self.energia_sistema("apagar", "poweroff", "Apagando...")
        elif accion == "reiniciar":
            self.energia_sistema("reiniciar", "reboot", "Reiniciando...")
        elif accion == "suspender":
            # La Raspberry no admite suspensión (/sys/power/state vacío):
            # reposo de TerraHub con la pantalla en negro hasta el siguiente toque.
            self.panel = self.panel_destino = 0.0
            self.estado = "reposo"
        elif accion == "salir":
            self.ejecutando = False
        elif accion == "inicio":
            self.cerrar_contenido()
            self.estado = "menu"
        elif isinstance(accion, str) and accion.startswith("doc_") and self.documento:
            self.accion_documento(accion)
        elif accion == "volver":
            self.volver()
        elif accion == "actualizar":
            self.actualizar()
        elif accion == "anterior":
            self.pagina = max(0, self.pagina - 1)
        elif accion == "siguiente":
            self.pagina = min(max(0, (len(self.archivos) - 1) // POR_PAGINA), self.pagina + 1)
        elif accion == "mostrar" and self.player:
            self.mostrar_controles()
        elif accion == "ajustes_video" and self.player:
            self.panel_video = not self.panel_video
            self.mostrar_controles()
        elif accion == "controles" and self.player:
            # Tocar el vídeo muestra los controles; si ya se ven, los oculta.
            if self.controles_visibles() and self.estado == "video" and not self.pausa:
                self.controles_hasta = 0
                self.panel_video = False
            else:
                self.mostrar_controles()
        elif (accion in ("pausa", "retroceder", "adelantar", "vol_menos", "vol_mas", "silenciar")
              or isinstance(accion, tuple)) and self.player:
            try:
                self.mostrar_controles()
                if isinstance(accion, tuple):
                    self.deslizar(*accion)
                elif accion == "pausa":
                    self.player.command("cycle", "pause")
                    self.pausa = not self.pausa
                elif accion in ("retroceder", "adelantar"):
                    self.player.command("seek", "-10" if accion == "retroceder" else "10", "relative")
                    if self.duracion:
                        paso = -10 if accion == "retroceder" else 10
                        self.posicion = max(0, min(self.duracion, self.posicion + paso))
                elif accion == "silenciar":
                    self.silencio = not self.silencio
                    self.player.command("set", "mute", "yes" if self.silencio else "no")
                else:
                    self.volumen = max(0, min(100, self.volumen + (-10 if accion == "vol_menos" else 10)))
                    self.player.command("set", "volume", str(self.volumen))
            except RuntimeError as error:
                self.volver()
                self.aviso = "Error de reproducción: " + str(error)

    # --- dibujo ----------------------------------------------------------------------------
    def _pulsado(self):
        """Acción que el dedo está pulsando (sin arrastrar), para pintarla pulsada."""
        if self.toque is not None and not self.toque["arrastre"]:
            return self.toque["accion"]
        return None

    def dibujar(self):
        v = self.vista
        v.lienzo.fill(FONDO)
        v.botones = []
        v.modo_completo = self.estado != "carpeta"
        if self.estado in CON_BARRA:
            self.hora_pintada = time.strftime("%H:%M")
        hora, pulsado, sup = self.hora_pintada, self._pulsado(), v.completo
        arrastrando = self.toque is not None and self.toque["arrastre"]
        aviso = self.aviso_inicio
        e = self.estado
        if e == "menu":
            v.inicio.dibujar(sup, self.carrusel, v.zona, aviso, hora, self.panel, self.captura,
                             fondo=self.fondo.superficie(), pulsado=pulsado)
        elif e == "fondo":
            elegido = (self.lista_fondos.index(self.fondo.ruta)
                       if self.fondo.ruta in self.lista_fondos else -1)
            v.fondos.dibujar(sup, self.fondo, self.lista_fondos, elegido, self.fondo_scroll,
                             v.zona, aviso, resaltado=pulsado,
                             tocable=not arrastrando and self.fondo_vel == 0, hora=hora)
        elif e == "ajustes":
            moviendo = self.ajustes_vel != 0 or arrastrando
            v.ajustes.dibujar(sup, self.ajustes_scroll, self.energia, v.zona, aviso, hora,
                              self.valores_ajustes(), resaltado=pulsado, tocable=not moviendo)
        elif e == "juegos":
            v.juegos.dibujar(sup, self.lista_juegos, self.juegos_pos, v.zona, aviso,
                             tocable=not arrastrando, hora=hora, resaltado=pulsado)
        elif e == "redes":
            moviendo = self.redes_vel != 0 or arrastrando
            v.redes.dibujar(sup, self.redes, self.redes_scroll, v.zona, aviso,
                            tocable=not moviendo, hora=hora, resaltado=pulsado)
        elif e == "musica":
            v.musica.dibujar(sup, self.pistas, self.musica_pos, v.zona, aviso,
                             tocable=not arrastrando, hora=hora, resaltado=pulsado)
        elif e == "clave":
            v.clave.dibujar(sup, self.clave_red["ssid"], self.clave, self.clave_ver,
                            self.clave_mayus, self.clave_simbolos, v.zona, aviso,
                            resaltado=pulsado, ocupado=self.conectando is not None, hora=hora)
        elif e == "videos":
            duracion = lambda ruta: (iv.formato_tiempo(d) if (d := self.miniaturas.duracion(ruta)) else None)
            v.videos.dibujar(sup, self.lista_videos, self.videos_pos, self.miniaturas, v.zona, "video",
                             aviso, tocable=not arrastrando, hora=hora, resaltado=pulsado,
                             subtitulo=duracion, vacio="No hay vídeos en recursos/videos")
        elif e == "imagenes":
            v.imagenes.dibujar(sup, self.lista_fotos, self.fotos_pos, self.miniaturas, v.zona, "foto",
                               aviso, tocable=not arrastrando, hora=hora, resaltado=pulsado,
                               vacio="No hay imágenes en recursos/imagenes")
        elif e == "libros":
            v.libros.dibujar(sup, self.lista_libros, self.libros_pos, self.miniaturas, v.zona, aviso,
                             hora=hora, resaltado=pulsado)
        elif e == "foto":
            v.visor.dibujar(sup, self.lista_fotos, self.foto_indice, self.miniaturas, v.zona, aviso,
                            resaltado=pulsado, desplazamiento=self.foto_desplazamiento)
        elif e == "documento" and self.documento:
            d = self.documento
            indicador = f"{d.pagina + 1} / {d.total}"
            if d.doc.is_reflowable:
                indicador = f"Cap. {d.capitulo + 1} · " + indicador
            hay_anterior = d.pagina > 0 or d.capitulo > 0
            hay_siguiente = (d.pagina + 1 < d.total or
                             (d.doc.is_reflowable and d.capitulo + 1 < d.doc.chapter_count))
            pagina = self.pagina_documento
            if self.doc_arrastre != (0.0, 0.0) and pagina is not None:
                movida = pygame.Surface(pagina.get_size()).convert()
                movida.fill((255, 255, 255))
                movida.blit(pagina, (round(self.doc_arrastre[0]), round(self.doc_arrastre[1])))
                pagina = movida
            v.lector.dibujar(sup, pagina, indicador, (d.pagina + 1) / max(1, d.total), hay_anterior,
                             hay_siguiente, v.zona, aviso, resaltado=pulsado)
        elif e == "reposo":
            sup.fill((0, 0, 0))
        elif e == "audio" and self.player is not None:
            v.audio.dibujar(sup, self.pista_actual, self.posicion, self.duracion, self.pausa,
                            self.letra_scroll, v.zona, aviso, hora=hora, resaltado=pulsado)
            self.controles_dibujados = True       # siempre visibles: no hay que ocultarlos
        elif e == "video" and self.player is not None:
            self.controles_dibujados = self.controles_visibles()
            v.video.dibujar(sup, self.player.surface, self.posicion, self.duracion, self.pausa,
                            self.controles_dibujados, self.panel_video, self.volumen, self.silencio,
                            v.zona, aviso, resaltado=pulsado)
        elif e == "carpeta":
            self.dibujar_carpeta()
        else:
            v.modo_completo = True
            sup.fill((0, 0, 0))
        v.preparar()
        # Tornar, en la esquina de la pantalla real (también sobre el explorador antiguo).
        rect = self.tornar_visible()
        if rect is not None:
            boton = v.tornar(rect)
            boton.dibujar(v.completo if v.modo_completo else v.cache, self.atras_pulsado)
            v.atras = boton
        else:
            v.atras = None
        self.sucio = False

    def dibujar_carpeta(self):
        """Explorador antiguo (lienzo 800x600); solo se llega desde pruebas o enlaces raros."""
        v = self.vista
        v.texto(self.categoria, (440, 44), 280)
        v.boton("Actualizar", (624, 16, 160, 56), "actualizar")
        try:
            ruta = str(self.carpeta.relative_to(BASE))
        except (ValueError, AttributeError):
            ruta = str(self.carpeta or "")
        v.texto(ruta, (400, 96))
        inicio = self.pagina * POR_PAGINA
        for i, path in enumerate(self.archivos[inicio:inicio + POR_PAGINA]):
            etiqueta = ("[Carpeta] " if path.is_dir() else "") + path.name
            v.boton(etiqueta, (24, 122 + i * 72, 752, 62), path)
        if not self.archivos:
            v.texto("Esta carpeta esta vacia", (400, 285))
        v.texto(self.aviso, (400, 500))
        paginas = max(1, (len(self.archivos) + POR_PAGINA - 1) // POR_PAGINA)
        v.texto(f"{self.pagina + 1} / {paginas}", (400, 555))
        if self.pagina:
            v.boton("Anterior", (24, 526, 170, 56), "anterior")
        if self.pagina + 1 < paginas:
            v.boton("Siguiente", (606, 526, 170, 56), "siguiente")

    # --- eventos ---------------------------------------------------------------------------
    def evento(self, evento):
        if self.estado == "reposo":
            # Cualquier toque o tecla despierta, sin activar nada debajo.
            if evento.type == pygame.QUIT:
                self.accion("salir")
            elif evento.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN):
                self.estado = "menu"
                self.toque = None
                self.sucio = True
            return
        if self.panel and evento.type != pygame.QUIT:
            return       # el círculo de la barra está creciendo o encogiendo
        if self.evento_atras(evento):
            return
        if evento.type == pygame.QUIT:
            self.accion("salir" if self.estado == "menu" else "volver")
        elif evento.type == pygame.KEYDOWN:
            self.tecla_fisica(evento)
        elif self.arrastre:                  # barra deslizante (progreso, volumen) cogida
            if evento.type in MOVER:
                pos = self.vista.posicion(evento, MOVER)
                if pos is not None:
                    self.arrastrar(pos)
            elif evento.type in SOLTAR:
                self.soltar(self.vista.posicion(evento, SOLTAR))
        elif self.estado in TACTILES:
            self.evento_inicio(evento)
        else:
            pos = self.vista.posicion(evento)
            if pos is not None:
                for rect, accion in self.vista.botones:
                    if rect.collidepoint(pos):
                        self.accion(accion)
                        break

    def tecla_fisica(self, evento):
        k, e = evento.key, self.estado
        izq_der = k in (pygame.K_LEFT, pygame.K_RIGHT)
        paso = -1 if k == pygame.K_LEFT else 1
        if k == pygame.K_ESCAPE:
            self.accion("salir" if e == "menu" else "volver")
        elif e == "clave":                   # teclado físico en la contraseña
            if k == pygame.K_BACKSPACE:
                self.tecla("borrar")
            elif k in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.tecla("conectar")
            elif evento.unicode and evento.unicode.isprintable():
                if not self.conectando and len(self.clave) < interfaz_teclado.LARGO_MAXIMO:
                    self.clave += evento.unicode
                    self.sucio = True
        elif e == "redes" and k in (pygame.K_UP, pygame.K_DOWN):
            self.desplazar_redes(-1 if k == pygame.K_UP else 1)
        elif e in ("menu", "libros") + PAGINADAS and izq_der:
            self.girar(paso)
        elif e == "menu" and k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self.accion(self.seccion_central())
        elif e == "libros" and k in (pygame.K_RETURN, pygame.K_KP_ENTER) and self.lista_libros:
            self.accion(("libro", round(self.libros_destino)))
        elif e == "foto" and izq_der:
            self.pasar_foto(paso)
        elif self.documento and izq_der:
            self.accion("doc_anterior" if k == pygame.K_LEFT else "doc_siguiente")
        elif k == pygame.K_SPACE and self.player:
            self.accion("pausa")
        elif self.player and izq_der:
            self.accion("retroceder" if k == pygame.K_LEFT else "adelantar")
        elif self.player and k == pygame.K_m:
            self.accion("silenciar")

    def pasar_foto(self, paso):
        nuevo = self.foto_indice + paso
        if 0 <= nuevo < len(self.lista_fotos):
            self.foto_indice = nuevo
            self.foto_desplazamiento = -paso * self.vista.pantalla.get_width() * .25
        self.sucio = True

    def _carrusel_activo(self):
        return {"juegos": ("juegos_pos", "juegos_destino"), "musica": ("musica_pos", "musica_destino"),
                "videos": ("videos_pos", "videos_destino"), "imagenes": ("fotos_pos", "fotos_destino"),
                "libros": ("libros_pos", "libros_destino")}.get(self.estado, ("carrusel", "carrusel_destino"))

    def _ultima_pagina(self):
        """Última página (o último libro) de la pantalla visible."""
        if self.estado == "musica":
            return max(1, -(-len(self.pistas) // interfaz_musica.PantallaMusica.POR_PAGINA)) - 1
        if self.estado == "videos":
            return interfaz_videos.paginas(len(self.lista_videos)) - 1
        if self.estado == "imagenes":
            return interfaz_videos.paginas(len(self.lista_fotos)) - 1
        if self.estado == "libros":
            return max(0, len(self.lista_libros) - 1)
        return interfaz_juegos.paginas(len(self.lista_juegos)) - 1

    def _vertical(self):
        """Lista vertical deslizable visible: (atributo scroll, atributo velocidad, máximo)."""
        if self.estado == "redes":
            return "redes_scroll", "redes_vel", self.redes_maximo()
        if self.estado == "ajustes":
            return "ajustes_scroll", "ajustes_vel", self.vista.ajustes.maximo(self.energia)
        if self.estado == "fondo":
            return "fondo_scroll", "fondo_vel", self.vista.fondos.maximo(len(self.lista_fondos))
        if self.estado == "audio" and self.pista_actual is not None:
            return "letra_scroll", "letra_vel", self.vista.audio.letra_maximo(self.pista_actual)
        return None

    def evento_inicio(self, evento):
        """Pantallas táctiles. Un toque actúa al soltar (mientras, se ve pulsado); al
        arrastrar, carruseles y páginas (horizontal) o listas (vertical) siguen al dedo
        y al soltar continúan con su velocidad: se recolocan o frenan por inercia."""
        pos = self.vista.posicion(evento)
        if pos is not None:
            accion = next((a for r, a in self.vista.botones if r.collidepoint(pos)), None)
            if isinstance(accion, tuple) and (accion[0] in ("buscar", "volumen") and self.player
                                              or accion[0] in ("fondo_h", "fondo_s", "fondo_v")):
                self.arrastre = accion           # barra: la sigue el dedo
                self.arrastrar(pos)
                return
            vertical = self._vertical()
            if vertical:
                base = getattr(self, vertical[0])
                setattr(self, vertical[1], 0.0)              # tocar la lista la detiene
            else:
                base = getattr(self, self._carrusel_activo()[0])
            self.toque = {"inicio": pos, "accion": accion, "arrastre": False, "base": base,
                          "muestras": [(tiempo.ms(), pos)]}
            self.sucio = True                    # lo tocado se ve pulsado mientras dura
        elif self.toque and evento.type in MOVER:
            p = self.vista.posicion(evento, MOVER)
            if p is not None:
                self.mover_toque(p)
        elif self.toque and evento.type in SOLTAR:
            p = self.vista.posicion(evento, SOLTAR)
            if p is not None:
                self.mover_toque(p)
            self.soltar_toque()

    def mover_toque(self, p):
        t = self.toque
        dx, dy = p[0] - t["inicio"][0], p[1] - t["inicio"][1]
        t["muestras"] = (t["muestras"] + [(tiempo.ms(), p)])[-6:]
        vertical = self._vertical()
        e = self.estado
        if not t["arrastre"]:
            umbral = 10
            if vertical:
                # En el reproductor solo se arrastra la letra; en el fondo, solo la lista.
                t["arrastre"] = abs(dy) > umbral and (
                    e == "audio" and t["accion"] == "letra" or
                    e == "fondo" and t["inicio"][0] >= self.vista.fondos.esc.p((interfaz_fondo.LISTA_X, 0))[0] or
                    e not in ("audio", "fondo"))
            elif e in ("menu", "libros", "foto") + PAGINADAS:
                t["arrastre"] = abs(dx) > umbral
            elif e == "documento" and t["accion"] == "doc_pagina":
                t["arrastre"] = math.hypot(dx, dy) > umbral
            if not t["arrastre"]:
                return
            self.sucio = True                    # deja de verse pulsado
        if vertical:
            # El contenido sigue al dedo; fuera de los límites se resiste (elástico).
            scroll, _, maximo = vertical
            s = t["base"] - dy / self.k_diseno()
            limite = min(max(s, 0), maximo)
            setattr(self, scroll, limite + (s - limite) * .35)
            if e == "audio":
                self.letra_tocada = tiempo.ms()
        elif e == "foto":
            fuera = ((self.foto_indice == 0 and dx > 0) or
                     (self.foto_indice == len(self.lista_fotos) - 1 and dx < 0))
            self.foto_desplazamiento = dx * (.35 if fuera else 1)
        elif e == "documento":
            if self.documento and self.documento.ampliado:
                self.doc_arrastre = (dx, dy)           # la página ampliada se mueve
            else:
                self.doc_arrastre = (dx * .5, 0.0)     # un poco, para notar el gesto
        else:
            actual, destino = self._carrusel_activo()
            if e in PAGINADAS:
                # Páginas: una pantalla de ancho; en los extremos, elástico.
                pos = t["base"] - dx / self.vista.pantalla.get_width()
            elif e == "libros":
                pos = t["base"] - dx / (interfaz_libros.SEPARACION * self.k_diseno())
            else:
                pos = t["base"] - dx / (interfaz_inicio.SEPARACION * self.k_diseno())
            if e != "menu":
                limite = min(max(pos, 0), self._ultima_pagina())
                pos = limite + (pos - limite) * .35
            setattr(self, actual, pos)
            setattr(self, destino, pos)
        self.sucio = True

    def soltar_toque(self):
        t, self.toque = self.toque, None
        self.sucio = True
        if not t["arrastre"]:
            if t["accion"]:
                self.accion(t["accion"])
            return
        # Velocidad del dedo en los últimos ~100 ms (px de pantalla por segundo).
        fin_t, fin_p = t["muestras"][-1]
        ini_t, ini_p = next(((mt, mp) for mt, mp in t["muestras"] if fin_t - mt <= 100),
                            t["muestras"][0])
        dt = max(16, fin_t - ini_t) / 1000
        vx, vy = (fin_p[0] - ini_p[0]) / dt, (fin_p[1] - ini_p[1]) / dt
        dx = fin_p[0] - t["inicio"][0]
        dy = fin_p[1] - t["inicio"][1]
        rapido = abs(dx) > 50 or abs(vx) > 400
        vertical = self._vertical()
        e = self.estado
        if vertical:
            setattr(self, vertical[1], max(-6000, min(6000, -vy / self.k_diseno())))
            if e == "audio":
                self.letra_tocada = tiempo.ms()
        elif e == "foto":
            if rapido and abs(dx) > abs(dy):
                paso = 1 if dx < 0 else -1
                if 0 <= self.foto_indice + paso < len(self.lista_fotos):
                    self.foto_indice += paso
                    self.foto_desplazamiento = dx + paso * self.vista.pantalla.get_width() * .5
        elif e == "documento" and self.documento:
            arrastre, self.doc_arrastre = self.doc_arrastre, (0.0, 0.0)
            if self.documento.ampliado:
                self.documento.arrastrar(*arrastre)
                self.accion_documento("doc_pagina")
            elif rapido and abs(dx) > abs(dy):
                self.accion_documento("doc_siguiente" if dx < 0 else "doc_anterior")
        else:
            actual, destino = self._carrusel_activo()
            pos, base = getattr(self, actual), round(t["base"])
            objetivo = round(pos)
            if objetivo == base and rapido:
                objetivo = base + (1 if dx < 0 else -1)   # un gesto corto basta para pasar
            if e != "menu":
                objetivo = max(0, min(self._ultima_pagina(), objetivo))
            setattr(self, destino, float(objetivo))

    # --- bucle -----------------------------------------------------------------------------
    def run(self):
        reloj = tiempo.Reloj()
        self.dibujar()
        self.vista.presentar()
        try:
            while self.ejecutando:
                presentar = False
                for evento in pygame.event.get():
                    self.evento(evento)
                    if not self.ejecutando:
                        break
                    # Al arrastrar llegan muchos eventos de movimiento por fotograma:
                    # esos se pintan una sola vez, al final del bucle.
                    if self.sucio and evento.type not in MOVER:
                        self.dibujar()
                        presentar = True
                    if evento.type in (pygame.MOUSEMOTION, pygame.WINDOWEXPOSED):
                        presentar = True
                if not self.ejecutando:
                    break
                if self.estado in TACTILES and self.animar_inicio():
                    self.sucio = True
                if self.animar_fondo():                  # GIF/MP4 de fondo o imagen ya cargada
                    self.sucio = True
                if self.player:
                    try:
                        nuevo = self.player.update()
                        siguiente = (self.indice_pista + 1 if self.estado == "audio"
                                     and self.origen_audio == "musica" and self.indice_pista is not None
                                     else None)
                        if self.player.ended and not self.player.error and \
                                siguiente is not None and siguiente < len(self.pistas):
                            self.reproducir_pista(siguiente)   # en Music, sigue con la próxima
                        elif self.player.ended:
                            aviso = self.player.error
                            self.volver()
                            self.aviso = aviso
                            if aviso:
                                self.avisar_inicio(aviso, 4000)
                        else:
                            self.consultar_tiempo()
                            # Cada fotograma nuevo se pinta con los controles encima,
                            # y al caducar el tiempo de los controles se ocultan.
                            if (nuevo and self.estado == "video" or
                                    self.controles_visibles() != self.controles_dibujados):
                                self.sucio = True
                    except RuntimeError as error:
                        print("Error de reproduccion:", error, flush=True)
                        self.volver()
                        self.aviso = "No se pudo reproducir este contenido."
                if self.sucio:
                    self.dibujar()
                    presentar = True
                if presentar:
                    self.vista.presentar()
                reloj.tick(60)
        finally:
            self.cerrar_contenido()
            self.fondo.cerrar()

    def animar_fondo(self):
        """Fondo de pantalla: solo corre (GIF/MP4) mientras se ve; True si hay que repintar."""
        visible = self.estado in ("menu", "fondo")
        self.fondo.pausar(not visible)
        cambio = False
        if self.fondo.cambiado:                  # imagen terminada de cargar en otro hilo
            self.fondo.cambiado = False
            cambio = visible
        if visible and self.fondo.update():
            cambio = True
        return cambio


def mostrar_menu(carpeta=None, aviso=""):
    m = Menu()
    if carpeta:
        m.abrir_carpeta(carpeta, aviso)
    m.run()
