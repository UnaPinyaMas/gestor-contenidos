"""Menu y explorador de carpetas de TerraHub."""
from pathlib import Path
import pygame
from video_player import VideoPlayer
from juegos import ejecutar_juego
from documentos import LectorDocumento
import interfaz_video as iv
import interfaz_inicio

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
        self._inicio = None
        self.botones = []

    @property
    def inicio(self):
        """Recursos de la pantalla de Inicio (SVG rasterizados), creados al usarse."""
        if self._inicio is None:
            self._inicio = interfaz_inicio.PantallaInicio(self.pantalla.get_size())
        return self._inicio

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
            self.cache.blit(self.completo, (0, 0))
            return
        self.cache.fill((0, 0, 0))
        pygame.transform.scale(self.lienzo, self.area.size, self.cache.subsurface(self.area))

    def presentar(self):
        self.pantalla.blit(self.cache, (0, 0))
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

    def girar(self, paso):
        self.carrusel_destino += paso
        self.sucio = True

    def animar_inicio(self):
        """Acerca el carrusel a su destino y caduca el aviso; True si hay que repintar."""
        cambio = False
        if self.carrusel != self.carrusel_destino:
            self.carrusel += (self.carrusel_destino - self.carrusel) * .25
            if abs(self.carrusel - self.carrusel_destino) < .01:
                self.carrusel = self.carrusel_destino
            cambio = True
        if self.aviso_inicio and pygame.time.get_ticks() > self.aviso_inicio_hasta:
            self.aviso_inicio = ""
            cambio = True
        return cambio

    def seccion_central(self):
        n = len(interfaz_inicio.SECCIONES)
        return interfaz_inicio.SECCIONES[round(self.carrusel_destino) % n][1]

    def controles_visibles(self):
        return (self.estado == "audio" or self.pausa or self.arrastre is not None or
                pygame.time.get_ticks() < self.controles_hasta)

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
        self.controles_hasta = pygame.time.get_ticks() + CONTROLES_MS
        self.sucio = True

    def consultar_tiempo(self):
        """Lee posición y duración de mpv como mucho 4 veces por segundo."""
        ahora = pygame.time.get_ticks()
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
        if self.estado in ("video", "audio", "foto", "documento"):
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
        elif accion == "ajustes":
            # El carrusel de ajustes del wireframe todavía no está hecho.
            self.aviso_inicio = "Ajustes: próximamente"
            self.aviso_inicio_hasta = pygame.time.get_ticks() + 2000
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
        v.modo_completo = (self.estado == "menu" or
                           self.estado in ("video", "audio") and self.player is not None)
        if self.estado == "menu":
            # Pantalla de Inicio del wireframe, a la resolución real de la pantalla.
            v.inicio.dibujar(v.completo, self.carrusel, v.zona, self.aviso_inicio)
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
        if evento.type == pygame.QUIT:
            self.accion("salir" if self.estado == "menu" else "volver")
        elif evento.type == pygame.KEYDOWN:
            if evento.key == pygame.K_ESCAPE:
                self.accion("salir" if self.estado == "menu" else "volver")
            elif self.estado == "menu" and evento.key in (pygame.K_LEFT, pygame.K_RIGHT):
                self.girar(-1 if evento.key == pygame.K_LEFT else 1)
            elif self.estado == "menu" and evento.key in (pygame.K_RETURN, pygame.K_KP_ENTER,
                                                          pygame.K_SPACE):
                self.accion(self.seccion_central())
            elif self.documento and evento.key in (pygame.K_LEFT, pygame.K_RIGHT):
                self.accion("doc_anterior" if evento.key == pygame.K_LEFT else "doc_siguiente")
            elif evento.key == pygame.K_SPACE and self.player:
                self.accion("pausa")
            elif self.player and evento.key in (pygame.K_LEFT, pygame.K_RIGHT):
                self.accion("retroceder" if evento.key == pygame.K_LEFT else "adelantar")
            elif self.player and evento.key == pygame.K_m:
                self.accion("silenciar")
        elif self.estado == "menu":
            self.evento_inicio(evento)
        elif self.arrastre:
            if evento.type in MOVER:
                pos = self.vista.posicion(evento, MOVER)
                if pos is not None:
                    self.arrastrar(pos)
            elif evento.type in SOLTAR:
                self.soltar(self.vista.posicion(evento, SOLTAR))
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

    def evento_inicio(self, evento):
        """Inicio: un toque actúa al soltar; deslizar en horizontal gira el carrusel."""
        pos = self.vista.posicion(evento)
        if pos is not None:
            accion = next((a for r, a in self.vista.botones if r.collidepoint(pos)), None)
            self.toque = (pos, accion)
        elif self.toque and evento.type in SOLTAR:
            (x0, _), accion = self.toque
            self.toque = None
            fin = self.vista.posicion(evento, SOLTAR)
            dx = fin[0] - x0 if fin else 0
            if abs(dx) > 50:
                self.girar(1 if dx < 0 else -1)
            elif accion:
                self.accion(accion)

    def run(self):
        reloj = pygame.time.Clock()
        self.dibujar()
        self.vista.presentar()
        try:
            while self.ejecutando:
                presentar = False
                for evento in pygame.event.get():
                    self.evento(evento)
                    if not self.ejecutando:
                        break
                    if self.sucio:
                        self.dibujar()
                        presentar = True
                    if evento.type in (pygame.MOUSEMOTION, pygame.WINDOWEXPOSED):
                        presentar = True
                if not self.ejecutando:
                    break
                if self.estado == "menu" and self.animar_inicio():
                    self.sucio = True
                if self.player:
                    try:
                        nuevo = self.player.update()
                        if self.player.ended:
                            aviso = self.player.error
                            self.volver()
                            self.aviso = aviso
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
