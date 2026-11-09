"""Menu y explorador de carpetas de TerraHub."""
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
import tiempo

ANCHO, ALTO = 800, 600
BASE = Path(__file__).resolve().parent
RECURSOS = BASE / "recursos"
# Secciones del carrusel de Inicio. Libros agrupa dos carpetas, que se muestran
# como subcarpetas al entrar.
CARPETAS = {"Audio": "audio", "Vídeos": "videos", "Libros": ("pdf", "epub"),
            "Imágenes": "imagenes", "Juegos": "juegos"}
VIDEO_EXT = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".mpg", ".mpeg", ".ts"}
AUDIO_EXT = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac", ".opus", ".wma"}
FOTO_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
JUEGO_EXT = {".gb", ".gbc", ".sgb"}
FONDO = (10, 15, 20)
AZUL, VERDE, ROJO = (21, 101, 192), (46, 125, 50), (165, 55, 65)
POR_PAGINA = 5
CONTROLES_MS = 3500        # tiempo que siguen visibles los controles del vídeo
MOVER = (pygame.MOUSEMOTION, pygame.FINGERMOTION)
SOLTAR = (pygame.MOUSEBUTTONUP, pygame.FINGERUP)


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


class Vista:
    """Lienzo de 800x600, adaptado a la pantalla, con imagen en cache."""
    def __init__(self):
        self.pantalla = pygame.display.get_surface()
        self.lienzo = pygame.Surface((ANCHO, ALTO)).convert()
        self.cache = pygame.Surface(self.pantalla.get_size()).convert()
        w, h = self.pantalla.get_size()
        escala = min(w / ANCHO, h / ALTO)
        self.area = pygame.Rect(0, 0, round(ANCHO * escala), round(ALTO * escala))
        self.area.center = self.pantalla.get_rect().center
        self.fuente = pygame.font.Font(None, 30)
        self.fuente_peq = pygame.font.Font(None, 22)
        # El reproductor dibuja a la resolución real de la pantalla, sin escalar,
        # para que el vídeo la ocupe entera (el lienzo 800x600 deja franjas).
        self.completo = pygame.Surface((w, h)).convert()
        self.modo_completo = False
        self.degradado_sup = iv.degradado(w, 110, hacia_abajo=False)
        self.degradado_inf = iv.degradado(w, 170, hacia_abajo=True)
        self._inicio = self._ajustes = self._redes = self._juegos = None
        self._musica = self._audio = None
        self.botones = []

    @property
    def inicio(self):
        """Recursos de la pantalla de Inicio (SVG rasterizados), creados al usarse."""
        if self._inicio is None:
            self._inicio = interfaz_inicio.PantallaInicio(self.pantalla.get_size())
        return self._inicio

    @property
    def ajustes(self):
        """Recursos del carrusel de ajustes, creados al usarse."""
        if self._ajustes is None:
            self._ajustes = interfaz_inicio.PantallaAjustes(self.pantalla.get_size())
        return self._ajustes

    @property
    def redes(self):
        """Recursos de la pantalla 'Redes disponibles', creados al usarse."""
        if self._redes is None:
            self._redes = interfaz_redes.PantallaRedes(self.pantalla.get_size())
        return self._redes

    @property
    def juegos(self):
        """Recursos de la pantalla 'Games', creados al usarse."""
        if self._juegos is None:
            self._juegos = interfaz_juegos.PantallaJuegos(self.pantalla.get_size())
        return self._juegos

    @property
    def musica(self):
        """Recursos de la lista 'Music', creados al usarse."""
        if self._musica is None:
            self._musica = interfaz_musica.PantallaMusica(self.pantalla.get_size())
        return self._musica

    @property
    def audio(self):
        """Recursos del reproductor de audio, creados al usarse."""
        if self._audio is None:
            self._audio = interfaz_musica.PantallaAudio(self.pantalla.get_size())
        return self._audio

    def texto(self, texto, centro, ancho=750, izquierda=False, sup=None):
        while self.fuente.size(texto)[0] > ancho and len(texto) > 4:
            texto = texto[:-4] + "..."
        imagen = self.fuente.render(texto, True, (255, 255, 255))
        rect = imagen.get_rect(midleft=centro) if izquierda else imagen.get_rect(center=centro)
        (sup or self.lienzo).blit(imagen, rect)

    def zona(self, rect, accion):
        """Zona táctil sin dibujo (los iconos del reproductor se dibujan aparte)."""
        self.botones.append((pygame.Rect(rect), accion))

    def boton(self, nombre, rect, accion, color=AZUL):
        rect = pygame.Rect(rect)
        pygame.draw.rect(self.lienzo, color, rect, border_radius=12)
        self.texto(nombre, rect.center, rect.width - 20)
        self.botones.append((rect, accion))

    def posicion(self, evento, tipos=(pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN)):
        """Posición en el lienzo de un toque/clic de los tipos indicados, o None."""
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
        if self.modo_completo:
            return pos
        if not self.area.collidepoint(pos):
            return None
        return ((pos[0] - self.area.x) * ANCHO / self.area.width,
                (pos[1] - self.area.y) * ALTO / self.area.height)

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
        self.foto = None
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
        self.toque = None           # (posición, acción) al pulsar en Inicio
        self.aviso_inicio = ""
        self.aviso_inicio_hasta = 0
        # Círculo de la barra superior: 0 = en la esquina, 1 = cubre la pantalla (ajustes).
        self.panel = self.panel_destino = 0.0
        self.confirmar = (None, 0)    # apagar/reiniciar piden un segundo toque: (acción, hasta)
        self.hora_pintada = ""
        self.origen_redes = "menu"    # Redes se abre desde la barra (Inicio o ajustes)
        self.captura = None           # ajustes que se ven dentro del círculo al crecer/encoger
        # Lista de ajustes: desplazamiento (px del diseño) con inercia, y la fila de energía
        # desplegada (0..1, animado).
        self.ajustes_scroll = self.ajustes_vel = 0.0
        self.energia = self.energia_destino = 0.0
        self.ip = ""
        # Redes disponibles (frame 4): None mientras nmcli busca. La lista se desplaza
        # en px del diseño, con la velocidad que deja el dedo al soltar (inercia).
        self.redes = None
        self.redes_scroll = 0.0
        self.redes_vel = 0.0
        self._ultimo_tick = tiempo.ms()
        # Games (frame 9): juegos encontrados y página visible (decimal al deslizar).
        self.lista_juegos = []
        self.juegos_pos = self.juegos_destino = 0.0
        # Music (frames 12 y 13): pistas, página visible y la que suena.
        self.pistas = []
        self._pistas = {}                    # ruta -> Pista (los metadatos se leen una vez)
        self.musica_pos = self.musica_destino = 0.0
        self.pista_actual = None
        self.indice_pista = None
        self.origen_audio = "carpeta"        # a dónde vuelve 'Volver' desde el reproductor
        self.letra_scroll = 0.0
        self.letra_vel = 0.0
        self.letra_tocada = -10 ** 9         # última vez que se movió la letra a mano (ms)

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

    def abrir_redes(self):
        """Muestra 'Redes disponibles' y busca las redes en segundo plano."""
        if self.estado in ("menu", "ajustes"):
            self.origen_redes = self.estado
        self.estado = "redes"
        self.redes, self.redes_scroll, self.redes_vel = None, 0.0, 0.0

        def buscar():
            self.redes = interfaz_redes.buscar_redes()
            self.sucio = True
        threading.Thread(target=buscar, daemon=True).start()

    def redes_maximo(self):
        return interfaz_redes.desplazamiento_maximo(len(self.redes or []))

    def desplazar_redes(self, filas):
        """Teclado: desliza la lista unas filas (con la misma inercia que el dedo)."""
        self.redes_vel = filas * interfaz_redes.PASO * 5.2
        self.sucio = True

    def k_diseno(self):
        """Píxeles de pantalla por píxel del diseño de Figma."""
        return self.vista.inicio.esc.k

    def avisar_inicio(self, texto, ms=2500):
        self.aviso_inicio = texto
        self.aviso_inicio_hasta = tiempo.ms() + ms
        self.sucio = True

    def energia_sistema(self, accion, verbo, texto):
        """Apagar/reiniciar: el primer toque pide confirmación; el segundo (antes de 4 s)
        muestra el aviso ya (la orden puede tardar) y llama a systemctl."""
        if self.confirmar[0] != accion or tiempo.ms() > self.confirmar[1]:
            self.confirmar = (accion, tiempo.ms() + 4000)
            self.avisar_inicio(f"Toca otra vez para {accion}", 4000)
            return
        self.confirmar = (None, 0)
        self.avisar_inicio(texto, 15000)
        self.dibujar()
        self.vista.presentar()
        if not ejecutar_energia(verbo):
            self.avisar_inicio("No se pudo: falta el permiso de deploy/instalar.sh", 4000)

    def girar(self, paso):
        """Mueve el carrusel de Inicio un elemento, o Games/Music una página."""
        if self.estado in ("juegos", "musica"):
            _, destino = self._carrusel_activo()
            nuevo = max(0, min(self._ultima_pagina(), round(getattr(self, destino)) + paso))
            setattr(self, destino, float(nuevo))
        else:
            self.carrusel_destino += paso
        self.sucio = True

    def animar_inicio(self):
        """Avanza carruseles y lista de redes según el tiempo real; True si hay que repintar.

        Va por tiempo (no por fotogramas), así el movimiento es igual de suave aunque
        la Raspberry dibuje a menos de 60 fps.
        """
        ahora = tiempo.ms()
        dt = min(.05, max(.001, (ahora - self._ultimo_tick) / 1000))
        self._ultimo_tick = ahora
        arrastrando = self.toque is not None and self.toque["arrastre"]
        cambio = False
        acercar = 1 - math.exp(-dt * 14)          # recolocación del carrusel (~0,3 s)
        for actual, destino in (("carrusel", "carrusel_destino"),
                                ("energia", "energia_destino"),
                                ("juegos_pos", "juegos_destino"),
                                ("musica_pos", "musica_destino")):
            a, d = getattr(self, actual), getattr(self, destino)
            if a != d and not arrastrando:
                a += (d - a) * acercar
                setattr(self, actual, d if abs(a - d) < .002 else a)
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
        if self.estado in ("menu", "ajustes") and time.strftime("%H:%M") != self.hora_pintada:
            cambio = True                             # la hora de la barra ha cambiado
        if self.aviso_inicio and tiempo.ms() > self.aviso_inicio_hasta:
            self.aviso_inicio = ""
            cambio = True
        return cambio

    def abrir_panel(self):
        """Círculo de la barra: desde Inicio crece hasta los ajustes; en ajustes, se cierra."""
        if self.estado == "ajustes":
            self.cerrar_panel()
        elif self.estado == "menu" and self.panel == 0:
            self.ajustes_scroll = self.ajustes_vel = 0.0
            self.energia = self.energia_destino = 0.0
            self.confirmar = (None, 0)
            self.ip = direccion_ip()
            self.capturar_ajustes()
            self.panel_destino = 1.0
        self.sucio = True

    def cerrar_panel(self):
        """De los ajustes al Inicio: el círculo encoge hasta la esquina."""
        self.capturar_ajustes()
        self.estado = "menu"
        self.panel, self.panel_destino = 1.0, 0.0
        self.confirmar = (None, 0)
        self.sucio = True

    def valores_ajustes(self):
        return {"ajuste_fecha": time.strftime("%H:%M  ·  %d/%m/%Y"), "ajuste_ip": self.ip}

    def capturar_ajustes(self):
        """Pinta los ajustes, tal cual se verán, para mostrarlos dentro del círculo.

        Se hace antes de empezar la animación (montar los ajustes la primera vez tarda) y
        se reinicia el reloj de la animación para que no dé un salto.
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
        """Elemento central del carrusel de ajustes; sus pantallas aún no están diseñadas."""
        if accion == "ajuste_fecha":
            self.avisar_inicio(time.strftime("%H:%M  ·  %d/%m/%Y"), 4000)
        elif accion == "ajuste_ip":
            self.avisar_inicio("IP: " + direccion_ip(), 5000)
        elif accion == "ajuste_redes":
            self.abrir_redes()
        elif accion == "ajuste_fondo":
            self.avisar_inicio("Fondos de pantalla: próximamente", 3000)

    def controles_visibles(self):
        return (self.estado == "audio" or self.pausa or self.arrastre is not None or
                tiempo.ms() < self.controles_hasta)

    def arrastrar(self, pos):
        """El dedo se mueve sobre una barra: el volumen cambia ya; el vídeo salta al soltar."""
        tipo, barra = self.arrastre
        self.fraccion_arrastre = max(0.0, min(1.0, (pos[0] - barra.x) / barra.width))
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

    def actualizar(self):
        try:
            if self.subcarpetas and self.carpeta == self.raiz:
                # Sección que agrupa carpetas (Libros: pdf y epub): mostrar solo esas.
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
        """Abre una carpeta dentro de su sección, p. ej. al volver del emulador."""
        carpeta = Path(carpeta).resolve()
        for nombre, subs in CARPETAS.items():
            for sub in (subs if isinstance(subs, tuple) else (subs,)):
                raiz = RECURSOS / sub
                if carpeta.is_relative_to(raiz.resolve()) and nombre == "Juegos":
                    self.abrir_juegos(aviso)        # al volver del emulador: pantalla Games
                    return
                if carpeta.is_relative_to(raiz.resolve()):
                    self.accion(nombre)
                    self.carpeta = raiz / carpeta.relative_to(raiz.resolve())
                    self.actualizar()
                    self.aviso = aviso
                    return

    def cerrar_contenido(self):
        self.arrastre = None
        if self.player:
            self.player.close()
            self.player = None
        if self.documento:
            self.documento.close()
            self.documento = None
        self.pagina_documento = None
        self.foto = None

    def volver(self):
        self.cerrar_contenido()
        if self.estado == "redes":
            self.estado = self.origen_redes  # Inicio o ajustes, según desde dónde se abrió
        elif self.estado == "ajustes":
            self.cerrar_panel()
        elif self.estado == "audio":
            self.estado = self.origen_audio  # lista 'Music' o carpeta, según desde dónde se abrió
        elif self.estado in ("video", "foto", "documento"):
            self.estado = "carpeta"
            self.foto = None
        elif self.estado == "carpeta" and self.carpeta != self.raiz:
            self.carpeta = self.carpeta.parent
            self.pagina = 0
            self.actualizar()
        else:
            self.estado = "menu"
        self.aviso = ""
        self.sucio = True

    def abrir(self, path):
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
            elif path.suffix.lower() in {".pdf", ".epub"}:
                self.documento = LectorDocumento(path)
                self.pagina_documento = self.documento.render()
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
                self.estado = "audio" if es_audio else "video"
                self.pausa = False
                self.silencio = False
                self.posicion, self.duracion = 0.0, None
                self.nombre = path.name
                self.mostrar_controles()
            elif path.suffix.lower() in FOTO_EXT:
                foto = pygame.image.load(str(path)).convert()
                w, h = foto.get_size()
                escala = min(760 / w, 450 / h)
                self.foto = pygame.transform.smoothscale(foto, (max(1, round(w * escala)), max(1, round(h * escala))))
                self.nombre = path.name
                self.estado = "foto"
            else:
                self.aviso = f"{path.name}: {path.stat().st_size:,} bytes. Visor pendiente."
        except Exception as error:
            self.cerrar_contenido()
            self.estado = "carpeta"
            self.aviso = "No se ha podido abrir el archivo: " + str(error)
            print("Error al abrir:", error, flush=True)
        self.sucio = True

    def accion(self, accion):
        self.sucio = True
        if isinstance(accion, Path):
            self.abrir(accion)
        elif accion == "Juegos":
            self.abrir_juegos()
        elif accion == "Audio":
            self.abrir_musica()
        elif isinstance(accion, tuple) and accion[0] == "pista":
            self.reproducir_pista(accion[1])
        elif accion in ("musica_izq", "musica_der"):
            self.girar(-1 if accion == "musica_izq" else 1)
        elif accion in ("audio_anterior", "audio_siguiente") and self.player:
            self.pista_contigua(-1 if accion == "audio_anterior" else 1)
        elif isinstance(accion, tuple) and accion[0] == "juego":
            self.lanzar_juego(accion[1])
        elif accion in ("juegos_izq", "juegos_der"):
            self.girar(-1 if accion == "juegos_izq" else 1)
        elif isinstance(accion, tuple) and accion[0] == "red":
            # Conectarse a otra red necesitaría pedir la contraseña: no está en el diseño.
            red = next((r for r in self.redes or [] if r["ssid"] == accion[1]), None)
            if red and red["conectada"]:
                self.avisar_inicio(f"Conectado a {red['ssid']}  ·  IP {direccion_ip()}", 4000)
            else:
                self.avisar_inicio("Conectarse a otra red: próximamente", 2500)
        elif accion in CARPETAS:
            self.categoria = accion
            sub = CARPETAS[accion]
            self.subcarpetas = sub if isinstance(sub, tuple) else None
            self.raiz = self.carpeta = RECURSOS if self.subcarpetas else RECURSOS / sub
            self.pagina = 0
            self.estado = "carpeta"
            self.actualizar()
        elif accion in ("carrusel_izq", "carrusel_der"):
            self.girar(-1 if accion == "carrusel_izq" else 1)
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
            try:
                if accion == "doc_anterior":
                    self.documento.mover_pagina(-1)
                elif accion == "doc_siguiente":
                    self.documento.mover_pagina(1)
                elif accion in ("doc_mas", "doc_menos"):
                    paso = 2 / 22 if self.documento.doc.is_reflowable else .5
                    self.documento.ampliar(paso if accion == "doc_mas" else -paso)
                else:
                    dx, dy = {"doc_izq": (-90, 0), "doc_der": (90, 0),
                              "doc_arriba": (0, -90), "doc_abajo": (0, 90)}[accion]
                    self.documento.desplazar(dx, dy)
                self.pagina_documento = self.documento.render()
            except Exception as error:
                self.volver()
                self.aviso = "No se pudo leer la página: " + str(error)
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
        elif accion == "controles" and self.player:
            # Tocar el vídeo muestra los controles; si ya se ven, los oculta.
            if self.controles_visibles() and self.estado == "video" and not self.pausa:
                self.controles_hasta = 0
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

    def dibujar_reproductor(self):
        """Vídeo/audio a pantalla completa con controles superpuestos (estilo YouTube)."""
        v = self.vista
        sup = v.completo                     # resolución real de la pantalla
        w, h = sup.get_size()
        sup.fill((0, 0, 0))
        if self.estado == "video":
            sup.blit(self.player.surface, self.player.surface.get_rect(center=(w // 2, h // 2)))
        else:
            iv.nota(sup, (w // 2, h // 2 - 50), 70)
            v.texto(self.nombre, (w // 2, h // 2 + 60), w - 100, sup=sup)
        self.controles_dibujados = self.controles_visibles()
        if self.controles_dibujados:
            sup.blit(v.degradado_sup, (0, 0))
            sup.blit(v.degradado_inf, (0, h - v.degradado_inf.get_height()))
            # Arriba: volver, título e inicio.
            iv.atras(sup, (36, 36))
            v.zona((0, 0, 72, 72), "volver")
            v.texto(self.nombre, (76, 36), w - 160, izquierda=True, sup=sup)
            iv.inicio(sup, (w - 36, 36))
            v.zona((w - 72, 0, 72, 72), "inicio")
            if self.estado == "video" and self.pausa:
                iv.boton_central(sup, (w // 2, h // 2), en_pausa=True)
                v.zona((w // 2 - 60, h // 2 - 60, 120, 120), "pausa")
            # Barra de progreso: se toca o se arrastra; zona alta y de todo el ancho.
            progreso = pygame.Rect(20, h - 66, w - 40, 5)
            fraccion = self.posicion / self.duracion if self.duracion else 0
            arrastrando = self.arrastre is not None and self.arrastre[0] == "buscar"
            iv.barra(sup, progreso, fraccion, perilla=11 if arrastrando else 7)
            v.zona((0, h - 98, w, 48), ("buscar", progreso))
            # Fila inferior.
            y = h - 26
            (iv.play if self.pausa else iv.pausa)(sup, (40, y), 13)
            v.zona((8, h - 50, 64, 50), "pausa")
            iv.saltar(sup, (102, y), v.fuente_peq, adelante=False)
            v.zona((72, h - 50, 60, 50), "retroceder")
            iv.saltar(sup, (160, y), v.fuente_peq, adelante=True)
            v.zona((132, h - 50, 58, 50), "adelantar")
            iv.volumen(sup, (222, y), self.volumen, self.silencio)
            v.zona((192, h - 50, 52, 50), "silenciar")
            volumen = pygame.Rect(256, y - 2, 140, 4)
            iv.barra(sup, volumen, 0 if self.silencio else self.volumen / 100,
                     color=iv.BLANCO, perilla=11 if self.arrastre and self.arrastre[0] == "volumen" else 7)
            v.zona((244, h - 50, 168, 50), ("volumen", volumen))
            tiempo = f"{iv.formato_tiempo(self.posicion)} / {iv.formato_tiempo(self.duracion)}"
            v.texto(tiempo, (424, y), 300, izquierda=True, sup=sup)
            # Un toque que falla por poco en la franja de controles no los esconde.
            v.zona((0, h - 98, w, 98), "mostrar")
            v.zona((0, 0, w, 72), "mostrar")
        # Toque en cualquier otro punto: mostrar u ocultar los controles.
        v.zona(sup.get_rect(), "controles")

    def dibujar(self):
        v = self.vista
        v.lienzo.fill(FONDO)
        v.botones = []
        v.modo_completo = (self.estado in ("menu", "ajustes", "redes", "juegos", "musica", "reposo") or
                           self.estado in ("video", "audio") and self.player is not None)
        if self.estado in ("menu", "ajustes"):
            self.hora_pintada = time.strftime("%H:%M")
        if self.estado == "menu":
            # Pantalla de Inicio del wireframe, a la resolución real de la pantalla.
            v.inicio.dibujar(v.completo, self.carrusel, v.zona, self.aviso_inicio,
                             self.hora_pintada, self.panel, self.captura)
        elif self.estado == "ajustes":
            pulsando = self.toque is not None and not self.toque["arrastre"]
            moviendo = (self.ajustes_vel != 0 or
                        self.toque is not None and self.toque["arrastre"])
            v.ajustes.dibujar(v.completo, self.ajustes_scroll, self.energia, v.zona,
                              self.aviso_inicio, self.hora_pintada, self.valores_ajustes(),
                              resaltado=self.toque["accion"] if pulsando else None,
                              tocable=not moviendo)
        elif self.estado == "juegos":
            arrastrando = self.toque is not None and self.toque["arrastre"]
            v.juegos.dibujar(v.completo, self.lista_juegos, self.juegos_pos, v.zona,
                             self.aviso_inicio, tocable=not arrastrando)
        elif self.estado == "redes":
            moviendo = (self.redes_vel != 0 or
                        self.toque is not None and self.toque["arrastre"])
            v.redes.dibujar(v.completo, self.redes, self.redes_scroll, v.zona, self.aviso_inicio,
                            tocable=not moviendo)
        elif self.estado == "musica":
            arrastrando = self.toque is not None and self.toque["arrastre"]
            v.musica.dibujar(v.completo, self.pistas, self.musica_pos, v.zona,
                             self.aviso_inicio, tocable=not arrastrando)
        elif self.estado == "reposo":
            v.completo.fill((0, 0, 0))
        elif self.estado == "audio" and self.player is not None:
            # Reproductor de audio del wireframe (frame 13).
            v.audio.dibujar(v.completo, self.pista_actual, self.posicion, self.duracion,
                            self.pausa, self.letra_scroll, v.zona, self.aviso_inicio)
            self.controles_dibujados = True       # siempre visibles: no hay que ocultarlos
        elif v.modo_completo:
            self.dibujar_reproductor()
        else:
            v.boton("Volver", (16, 16, 120, 56), "volver")
            v.boton("Inicio", (148, 16, 112, 56), "inicio")
            if self.estado == "carpeta":
                v.texto(self.categoria, (440, 44), 280)
                v.boton("Actualizar", (624, 16, 160, 56), "actualizar")
                v.texto(str(self.carpeta.relative_to(BASE)), (400, 96))
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
            else:
                v.texto(self.nombre, (535, 44), 480)
                if self.estado == "documento" and self.documento:
                    v.lienzo.blit(self.pagina_documento, (20, 82))
                    controles = [
                        ("Zoom -", "doc_menos"), ("Zoom +", "doc_mas"),
                        ("Izq.", "doc_izq"), ("Der.", "doc_der"),
                        ("Arriba", "doc_arriba"), ("Abajo", "doc_abajo")]
                    if self.documento.doc.is_reflowable:
                        controles = [("Letra -", "doc_menos"), ("Letra +", "doc_mas")]
                    for i, (label, accion) in enumerate(controles):
                        v.boton(label, (20 + i * 128, 480, 120, 50), accion)
                    if self.documento.pagina > 0 or self.documento.capitulo > 0:
                        v.boton("Anterior", (20, 540, 165, 52), "doc_anterior")
                    indicador = f"{self.documento.pagina + 1} / {self.documento.total}"
                    if self.documento.doc.is_reflowable:
                        indicador = f"Cap. {self.documento.capitulo + 1} · " + indicador
                    v.texto(indicador, (400, 566), 270)
                    if (self.documento.pagina + 1 < self.documento.total or
                            (self.documento.doc.is_reflowable and
                             self.documento.capitulo + 1 < self.documento.doc.chapter_count)):
                        v.boton("Siguiente", (615, 540, 165, 52), "doc_siguiente")
                elif self.foto:
                    v.lienzo.blit(self.foto, self.foto.get_rect(center=(400, 310)))
        v.preparar()
        self.sucio = False

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
        if evento.type == pygame.QUIT:
            self.accion("salir" if self.estado == "menu" else "volver")
        elif evento.type == pygame.KEYDOWN:
            if evento.key == pygame.K_ESCAPE:
                self.accion("salir" if self.estado == "menu" else "volver")
            elif self.estado == "redes" and evento.key in (pygame.K_UP, pygame.K_DOWN):
                self.desplazar_redes(-1 if evento.key == pygame.K_UP else 1)
            elif self.estado in ("menu", "juegos", "musica") and evento.key in (
                    pygame.K_LEFT, pygame.K_RIGHT):
                self.girar(-1 if evento.key == pygame.K_LEFT else 1)
            elif self.estado == "menu" and evento.key in (
                    pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.accion(self.seccion_central())
            elif self.documento and evento.key in (pygame.K_LEFT, pygame.K_RIGHT):
                self.accion("doc_anterior" if evento.key == pygame.K_LEFT else "doc_siguiente")
            elif evento.key == pygame.K_SPACE and self.player:
                self.accion("pausa")
            elif self.player and evento.key in (pygame.K_LEFT, pygame.K_RIGHT):
                self.accion("retroceder" if evento.key == pygame.K_LEFT else "adelantar")
            elif self.player and evento.key == pygame.K_m:
                self.accion("silenciar")
        elif self.arrastre:                  # barra deslizante (progreso, volumen) cogida
            if evento.type in MOVER:
                pos = self.vista.posicion(evento, MOVER)
                if pos is not None:
                    self.arrastrar(pos)
            elif evento.type in SOLTAR:
                self.soltar(self.vista.posicion(evento, SOLTAR))
        elif self.estado in ("menu", "ajustes", "redes", "juegos", "musica", "audio"):
            self.evento_inicio(evento)
        else:
            pos = self.vista.posicion(evento)
            if pos is not None:
                for rect, accion in self.vista.botones:
                    if rect.collidepoint(pos):
                        if isinstance(accion, tuple):
                            # Barra deslizante: sigue al dedo hasta que se suelta.
                            self.arrastre = accion
                            self.arrastrar(pos)
                        else:
                            self.accion(accion)
                        break

    def _carrusel_activo(self):
        if self.estado == "juegos":
            return "juegos_pos", "juegos_destino"
        if self.estado == "musica":
            return "musica_pos", "musica_destino"
        return "carrusel", "carrusel_destino"

    def _ultima_pagina(self):
        """Última página de la pantalla paginada visible (Games o Music)."""
        if self.estado == "musica":
            return max(1, -(-len(self.pistas) // interfaz_musica.PantallaMusica.POR_PAGINA)) - 1
        return interfaz_juegos.paginas(len(self.lista_juegos)) - 1

    def _vertical(self):
        """Lista vertical deslizable visible: (atributo scroll, atributo velocidad, máximo)."""
        if self.estado == "redes":
            return "redes_scroll", "redes_vel", self.redes_maximo()
        if self.estado == "ajustes":
            return "ajustes_scroll", "ajustes_vel", self.vista.ajustes.maximo(self.energia)
        if self.estado == "audio" and self.pista_actual is not None:
            return "letra_scroll", "letra_vel", self.vista.audio.letra_maximo(self.pista_actual)
        return None

    def evento_inicio(self, evento):
        """Pantallas táctiles nuevas. Un toque actúa al soltar; al arrastrar, los carruseles
        y páginas (horizontal) o las listas (vertical: redes, letra) siguen al dedo, y al
        soltar continúan con su velocidad: se recolocan o frenan por inercia."""
        pos = self.vista.posicion(evento)
        if pos is not None:
            accion = next((a for r, a in self.vista.botones if r.collidepoint(pos)), None)
            if isinstance(accion, tuple) and accion[0] in ("buscar", "volumen") and self.player:
                self.arrastre = accion           # barra de progreso: la sigue el dedo
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
            if self.estado == "ajustes":
                self.sucio = True                # la fila tocada se resalta mientras se pulsa
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
        if not t["arrastre"]:
            umbral = 10
            if vertical:
                # En el reproductor solo se arrastra la letra (no el resto de la pantalla).
                t["arrastre"] = abs(dy) > umbral and (self.estado != "audio" or t["accion"] == "letra")
            elif self.estado in ("menu", "juegos", "musica"):
                t["arrastre"] = abs(dx) > umbral
            if not t["arrastre"]:
                return
        if vertical:
            # El contenido sigue al dedo; fuera de los límites se resiste (elástico).
            scroll, _, maximo = vertical
            s = t["base"] - dy / self.k_diseno()
            limite = min(max(s, 0), maximo)
            setattr(self, scroll, limite + (s - limite) * .35)
            if self.estado == "audio":
                self.letra_tocada = tiempo.ms()
        else:
            actual, destino = self._carrusel_activo()
            if self.estado in ("juegos", "musica"):
                # Páginas: una pantalla de ancho; en los extremos, elástico.
                p = t["base"] - dx / self.vista.pantalla.get_width()
                limite = min(max(p, 0), self._ultima_pagina())
                setattr(self, actual, limite + (p - limite) * .35)
            else:
                separacion = interfaz_inicio.SEPARACION * self.k_diseno()
                setattr(self, actual, t["base"] - dx / separacion)
            setattr(self, destino, getattr(self, actual))
        self.sucio = True

    def soltar_toque(self):
        t, self.toque = self.toque, None
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
        vertical = self._vertical()
        if vertical:
            setattr(self, vertical[1], max(-6000, min(6000, -vy / self.k_diseno())))
            if self.estado == "audio":
                self.letra_tocada = tiempo.ms()
        else:
            actual, destino = self._carrusel_activo()
            pos, base = getattr(self, actual), round(t["base"])
            objetivo = round(pos)
            dx = fin_p[0] - t["inicio"][0]
            if objetivo == base and (abs(dx) > 50 or abs(vx) > 400):
                objetivo = base + (1 if dx < 0 else -1)   # un gesto corto basta para pasar
            if self.estado in ("juegos", "musica"):
                objetivo = max(0, min(self._ultima_pagina(), objetivo))
            setattr(self, destino, float(objetivo))
        self.sucio = True

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
                if (self.estado in ("menu", "ajustes", "redes", "juegos", "musica", "audio")
                        and self.animar_inicio()):
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
                            if aviso and self.estado == "musica":
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


def mostrar_menu(carpeta=None, aviso=""):
    m = Menu()
    if carpeta:
        m.abrir_carpeta(carpeta, aviso)
    m.run()
