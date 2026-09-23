"""Interfaz tactil del media center, disenada para 800x600."""
import os
from pathlib import Path

if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
    os.environ.setdefault("SDL_VIDEODRIVER", "kmsdrm")
# Tratamos los eventos tactiles directamente para evitar clics duplicados.
os.environ.setdefault("SDL_TOUCH_MOUSE_EVENTS", "0")

import pygame
from video_player import VideoPlayer

BASE = Path(__file__).resolve().parent
VIDEOS = BASE / "videos"
EXTENSIONES = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".mpg", ".mpeg", ".ts"}
FONDO = (24, 27, 34)
AZUL = (55, 115, 210)
BLANCO = (245, 247, 250)
POR_PAGINA = 5


def listar_videos(carpeta=VIDEOS):
    carpeta.mkdir(parents=True, exist_ok=True)
    return sorted((p for p in carpeta.iterdir()
                   if p.is_file() and p.suffix.lower() in EXTENSIONES),
                  key=lambda p: p.name.casefold())


class App:
    def __init__(self):
        pygame.display.init()
        pygame.font.init()
        self.pantalla = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        pygame.display.set_caption("Gestor de contenidos")
        # Coordenadas fijas y escalado proporcional para otras pantallas.
        self.lienzo = pygame.Surface((800, 600)).convert()
        self.fondo_pantalla = pygame.Surface(self.pantalla.get_size()).convert()
        self.sucio = True
        ancho, alto = self.pantalla.get_size()
        escala = min(ancho / 800, alto / 600)
        self.area = pygame.Rect(0, 0, round(800 * escala), round(600 * escala))
        self.area.center = self.pantalla.get_rect().center
        self.fuente = pygame.font.Font(None, 32)
        self.pequena = pygame.font.Font(None, 25)
        self.estado = "inicio"
        self.ejecutando = True
        self.archivos = []
        self.pagina = 0
        self.botones = []
        self.player = None
        self.pausa = False
        self.aviso = ""
        self.nombre = ""

    def texto(self, texto, centro, fuente=None, ancho=750):
        fuente = fuente or self.fuente
        while fuente.size(texto)[0] > ancho and len(texto) > 4:
            texto = texto[:-4] + "..."
        imagen = fuente.render(texto, True, BLANCO)
        self.lienzo.blit(imagen, imagen.get_rect(center=centro))

    def boton(self, etiqueta, rect, accion, color=AZUL):
        rect = pygame.Rect(rect)
        pygame.draw.rect(self.lienzo, color, rect, border_radius=10)
        self.texto(etiqueta, rect.center, ancho=rect.width - 24)
        self.botones.append((rect, accion))

    def actualizar_lista(self):
        try:
            self.archivos = listar_videos()
            self.aviso = ""
        except OSError:
            self.archivos = []
            self.aviso = "No se puede leer la carpeta videos."
        self.pagina = min(self.pagina, max(0, (len(self.archivos) - 1) // POR_PAGINA))

    def parar_video(self):
        if self.player:
            self.player.close()
            self.player = None
        self.estado = "videos"
        self.actualizar_lista()

    def accion(self, accion):
        self.sucio = True
        if isinstance(accion, Path):
            self.aviso = ""
            try:
                self.player = VideoPlayer(accion)
                self.nombre = accion.name
                self.pausa = False
                self.estado = "reproduciendo"
            except (OSError, RuntimeError) as error:
                self.aviso = "No se pudo abrir el video. Revisa el archivo."
                print("Error de reproduccion:", error, flush=True)
            return
        if accion == "salir":
            self.ejecutando = False
        elif accion == "videos":
            self.estado = "videos"
            self.pagina = 0
            self.actualizar_lista()
        elif accion == "volver":
            if self.player:
                self.parar_video()
            else:
                self.estado = "inicio"
        elif accion == "actualizar":
            self.actualizar_lista()
        elif accion == "anterior":
            self.pagina = max(0, self.pagina - 1)
        elif accion == "siguiente":
            self.pagina = min((len(self.archivos) - 1) // POR_PAGINA, self.pagina + 1)
        elif accion == "pausa" and self.player:
            self.player.command("cycle", "pause")
            self.pausa = not self.pausa

    def evento(self, evento):
        if evento.type == pygame.QUIT:
            self.ejecutando = False
        elif evento.type == pygame.KEYDOWN:
            if evento.key == pygame.K_ESCAPE:
                self.accion("salir" if self.estado == "inicio" else "volver")
            elif evento.key == pygame.K_SPACE and self.player:
                self.accion("pausa")
        else:
            posicion = None
            if evento.type == pygame.MOUSEBUTTONDOWN and evento.button == 1:
                if not getattr(evento, "touch", False):
                    posicion = evento.pos
            elif evento.type == pygame.FINGERDOWN:
                w, h = self.pantalla.get_size()
                posicion = (evento.x * w, evento.y * h)
            if posicion is not None and self.area.collidepoint(posicion):
                x = (posicion[0] - self.area.x) * 800 / self.area.width
                y = (posicion[1] - self.area.y) * 600 / self.area.height
                for rect, accion in self.botones:
                    if rect.collidepoint(x, y):
                        self.accion(accion)
                        break

    def dibujar(self, presentar=True):
        self.lienzo.fill(FONDO)
        self.botones = []
        self.boton("Salir", (16, 16, 112, 56), "salir", (165, 55, 65))
        if self.estado == "inicio":
            self.boton("Videos", (250, 255, 300, 90), "videos")
        else:
            self.boton("Volver", (144, 16, 120, 56), "volver")
            if self.estado == "videos":
                self.texto("Mis videos", (450, 44))
                self.boton("Actualizar", (624, 16, 160, 56), "actualizar")
                inicio = self.pagina * POR_PAGINA
                for i, archivo in enumerate(self.archivos[inicio:inicio + POR_PAGINA]):
                    self.boton(archivo.name, (24, 100 + i * 76, 752, 64), archivo)
                if not self.archivos:
                    self.texto("Todavia no hay videos", (400, 260))
                    self.texto("Copia tus archivos en gestor-contenidos/videos",
                               (400, 305), self.pequena)
                paginas = max(1, (len(self.archivos) + POR_PAGINA - 1) // POR_PAGINA)
                if self.pagina > 0:
                    self.boton("Anterior", (24, 526, 170, 56), "anterior")
                if self.pagina + 1 < paginas:
                    self.boton("Siguiente", (606, 526, 170, 56), "siguiente")
                self.texto(f"{self.pagina + 1} / {paginas}", (400, 555), self.pequena)
                if self.aviso:
                    self.texto(self.aviso, (400, 500), self.pequena)
            elif self.player:
                self.lienzo.blit(self.player.surface, (0, 80))
                self.texto(self.nombre, (520, 44), self.pequena, ancho=480)
                self.boton("Continuar" if self.pausa else "Pausar",
                           (300, 536, 200, 56), "pausa")
        self.fondo_pantalla.fill((0, 0, 0))
        pygame.transform.scale(self.lienzo, self.area.size,
                               self.fondo_pantalla.subsurface(self.area))
        self.sucio = False
        if presentar:
            self.presentar()

    def presentar(self):
        # Copia la imagen ya preparada; no recalcula textos, botones ni escala.
        self.pantalla.blit(self.fondo_pantalla, (0, 0))
        pygame.display.flip()

    def procesar_eventos(self, eventos):
        presentar = False
        for evento in eventos:
            self.evento(evento)
            if not self.ejecutando:
                break
            if self.sucio:
                # Actualiza las zonas pulsables si cambia el menu, sin esperar
                # a la pantalla por cada evento de la cola.
                self.dibujar(presentar=False)
                presentar = True
            elif evento.type in (pygame.MOUSEMOTION, pygame.WINDOWEXPOSED):
                presentar = True
        return presentar

    def run(self):
        reloj = pygame.time.Clock()
        self.dibujar()
        while self.ejecutando:
            presentar = self.procesar_eventos(pygame.event.get())
            if not self.ejecutando:
                break
            if self.player:
                try:
                    nuevo_frame = self.player.update()
                    if self.player.ended:
                        aviso = self.player.error
                        self.parar_video()
                        self.aviso = aviso
                        self.sucio = True
                    elif nuevo_frame:
                        # Los controles no cambian con cada fotograma.
                        self.lienzo.blit(self.player.surface, (0, 80))
                        pygame.transform.scale(self.lienzo, self.area.size,
                                               self.fondo_pantalla.subsurface(self.area))
                        presentar = True
                except RuntimeError as error:
                    print("Error de video:", error, flush=True)
                    self.parar_video()
                    self.aviso = "Se ha interrumpido la reproduccion."
                    self.sucio = True
            if self.sucio:
                self.dibujar(presentar=False)
                presentar = True
            # Como maximo una presentacion por ciclo, aunque lleguen cientos
            # de eventos del raton. En reposo no redibujamos.
            if presentar:
                self.presentar()
            reloj.tick(60)

    def close(self):
        if self.player:
            self.player.close()
            self.player = None
        pygame.quit()


def main():
    app = None
    try:
        app = App()
        app.run()
    finally:
        if app:
            app.close()
        else:
            pygame.quit()


if __name__ == "__main__":
    main()
