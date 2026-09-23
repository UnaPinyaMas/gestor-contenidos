"""Menu y explorador de carpetas de TerraHub."""
from pathlib import Path
import pygame
from video_player import VideoPlayer

ANCHO, ALTO = 800, 600
BASE = Path(__file__).resolve().parent
RECURSOS = BASE / "recursos"
CARPETAS = {"Videos": "videos", "Juegos": "juegos", "EPUB": "epub",
            "Fotos": "imagenes", "Archivos": "archivos"}
VIDEO_EXT = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".mpg", ".mpeg", ".ts"}
FOTO_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
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

    def volver(self):
        if self.player:
            self.player.close()
            self.player = None
        if self.estado in ("video", "foto"):
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
            elif path.suffix.lower() in VIDEO_EXT:
                self.player = VideoPlayer(path)
                self.estado = "video"
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
        except (OSError, RuntimeError, pygame.error) as error:
            self.aviso = "No se ha podido abrir el archivo."
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
        elif accion == "volver":
            self.volver()
        elif accion == "actualizar":
            self.actualizar()
        elif accion == "anterior":
            self.pagina = max(0, self.pagina - 1)
        elif accion == "siguiente":
            self.pagina = min(max(0, (len(self.archivos) - 1) // POR_PAGINA), self.pagina + 1)
        elif accion == "pausa" and self.player:
            self.player.command("cycle", "pause")
            self.pausa = not self.pausa

    def dibujar(self):
        v = self.vista
        v.lienzo.fill(FONDO)
        v.botones = []
        v.boton("Salir", (16, 16, 112, 56), "salir", ROJO)
        if self.estado == "menu":
            v.texto("TerraHub", (400, 48))
            for nombre, rect, color in [
                ("Videos", (40, 150, 220, 120), VERDE),
                ("Juegos", (290, 150, 220, 120), AZUL),
                ("EPUB", (540, 150, 220, 120), (150, 105, 0)),
                ("Fotos", (165, 310, 220, 120), VERDE),
                ("Archivos", (415, 310, 220, 120), AZUL)]:
                v.boton(nombre, rect, nombre, color)
        else:
            v.boton("Volver", (144, 16, 120, 56), "volver")
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
                    v.boton("Continuar" if self.pausa else "Pausar", (300, 536, 200, 56), "pausa")
                elif self.foto:
                    v.lienzo.blit(self.foto, self.foto.get_rect(center=(400, 310)))
        v.preparar()
        self.sucio = False

    def evento(self, evento):
        if evento.type == pygame.QUIT:
            self.ejecutando = False
        elif evento.type == pygame.KEYDOWN:
            if evento.key == pygame.K_ESCAPE:
                self.accion("salir" if self.estado == "menu" else "volver")
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
                        elif nuevo:
                            self.vista.lienzo.blit(self.player.surface, (0, 80))
                            self.vista.preparar()
                            presentar = True
                    except RuntimeError as error:
                        print("Error de reproduccion:", error, flush=True)
                        self.volver()
                        self.aviso = "No se pudo reproducir este video."
                if self.sucio:
                    self.dibujar()
                    presentar = True
                if presentar:
                    self.vista.presentar()
                reloj.tick(60)
        finally:
            if self.player:
                self.player.close()
                self.player = None


def mostrar_menu():
    Menu().run()
