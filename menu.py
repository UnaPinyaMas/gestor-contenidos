"""Menu y explorador de carpetas de TerraHub."""
from pathlib import Path
import pygame
from video_player import VideoPlayer
from juegos import ejecutar_juego
from documentos import LectorDocumento

ANCHO, ALTO = 800, 600
BASE = Path(__file__).resolve().parent
RECURSOS = BASE / "recursos"
CARPETAS = {"Videos": "videos", "Audio": "audio", "PDF": "pdf",
            "EPUB": "epub", "Juegos": "juegos", "Fotos": "imagenes", "Archivos": "archivos"}
VIDEO_EXT = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".mpg", ".mpeg", ".ts"}
AUDIO_EXT = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac", ".opus", ".wma"}
FOTO_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
JUEGO_EXT = {".gb", ".gbc", ".sgb"}
FONDO = (10, 15, 20)
AZUL, VERDE, ROJO = (21, 101, 192), (46, 125, 50), (165, 55, 65)
POR_PAGINA = 5


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
        self.botones = []

    def texto(self, texto, centro, ancho=750):
        while self.fuente.size(texto)[0] > ancho and len(texto) > 4:
            texto = texto[:-4] + "..."
        imagen = self.fuente.render(texto, True, (255, 255, 255))
        self.lienzo.blit(imagen, imagen.get_rect(center=centro))

    def boton(self, nombre, rect, accion, color=AZUL):
        rect = pygame.Rect(rect)
        pygame.draw.rect(self.lienzo, color, rect, border_radius=12)
        self.texto(nombre, rect.center, rect.width - 20)
        self.botones.append((rect, accion))

    def posicion(self, evento):
        if evento.type == pygame.MOUSEBUTTONDOWN and evento.button == 1:
            if getattr(evento, "touch", False):
                return None
            pos = evento.pos
        elif evento.type == pygame.FINGERDOWN:
            w, h = self.pantalla.get_size()
            pos = (evento.x * w, evento.y * h)
        else:
            return None
        if not self.area.collidepoint(pos):
            return None
        return ((pos[0] - self.area.x) * ANCHO / self.area.width,
                (pos[1] - self.area.y) * ALTO / self.area.height)

    def preparar(self):
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

    def actualizar(self):
        try:
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

    def cerrar_contenido(self):
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
            if not path.resolve().is_relative_to(self.raiz.resolve()):
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
                self.player = VideoPlayer(path, video=not es_audio)
                self.player.command("set", "volume", str(self.volumen))
                self.estado = "audio" if es_audio else "video"
                self.pausa = False
                self.nombre = path.name
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
            self.raiz = self.carpeta = RECURSOS / CARPETAS[accion]
            self.pagina = 0
            self.estado = "carpeta"
            self.actualizar()
        elif accion == "salir":
            self.ejecutando = False
        elif accion == "inicio":
            self.cerrar_contenido()
            self.estado = "menu"
        elif accion.startswith("doc_") and self.documento:
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
        elif accion in ("pausa", "retroceder", "adelantar", "vol_menos", "vol_mas") and self.player:
            try:
                if accion == "pausa":
                    self.player.command("cycle", "pause")
                    self.pausa = not self.pausa
                elif accion in ("retroceder", "adelantar"):
                    self.player.command("seek", "-10" if accion == "retroceder" else "10", "relative")
                else:
                    self.volumen = max(0, min(100, self.volumen + (-10 if accion == "vol_menos" else 10)))
                    self.player.command("set", "volume", str(self.volumen))
            except RuntimeError as error:
                self.volver()
                self.aviso = "Error de reproducción: " + str(error)

    def dibujar(self):
        v = self.vista
        v.lienzo.fill(FONDO)
        v.botones = []
        if self.estado == "menu":
            v.boton("Salir", (16, 16, 112, 56), "salir", ROJO)
            v.texto("TerraHub", (400, 48))
            for i, nombre in enumerate(CARPETAS):
                fila, columna = divmod(i, 3)
                v.boton(nombre, (35 + columna * 255, 125 + fila * 145, 220, 115),
                        nombre, VERDE if i % 2 == 0 else AZUL)
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
                if self.estado == "video" and self.player:
                    v.lienzo.blit(self.player.surface, (0, 80))
                elif self.estado == "audio":
                    v.texto("Reproducción de audio", (400, 230))
                    v.texto("En pausa" if self.pausa else "Reproduciendo", (400, 300))
                if self.estado in ("video", "audio") and self.player:
                    v.boton("-10 s", (16, 536, 110, 56), "retroceder")
                    v.boton("Continuar" if self.pausa else "Pausar", (138, 536, 170, 56), "pausa")
                    v.boton("+10 s", (320, 536, 110, 56), "adelantar")
                    v.boton("Vol -", (450, 536, 100, 56), "vol_menos")
                    v.texto(str(self.volumen) + "%", (605, 564), 90)
                    v.boton("Vol +", (660, 536, 120, 56), "vol_mas")
                elif self.estado == "documento" and self.documento:
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
            elif self.documento and evento.key in (pygame.K_LEFT, pygame.K_RIGHT):
                self.accion("doc_anterior" if evento.key == pygame.K_LEFT else "doc_siguiente")
            elif evento.key == pygame.K_SPACE and self.player:
                self.accion("pausa")
        else:
            pos = self.vista.posicion(evento)
            if pos is not None:
                for rect, accion in self.vista.botones:
                    if rect.collidepoint(pos):
                        self.accion(accion)
                        break

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
                if self.player:
                    try:
                        nuevo = self.player.update()
                        if self.player.ended:
                            aviso = self.player.error
                            self.volver()
                            self.aviso = aviso
                        elif nuevo and self.estado == "video":
                            self.vista.lienzo.blit(self.player.surface, (0, 80))
                            self.vista.preparar()
                            presentar = True
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


def mostrar_menu():
    Menu().run()
