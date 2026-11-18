"""Fondo de pantalla del Inicio: imagen (PNG, JPG, JPEG) o animado (GIF, MP4).

Tono, saturación y brillo (HSV) se aplican igual a todo: a los GIF/MP4 dentro de
mpv con los filtros 'hue' y 'lutyuv' de ffmpeg (en Y/Cb/Cr, rápidos), y a las
imágenes con numpy como una sola matriz de color 3x3 con la misma cuenta.
La elección se guarda en ~/.config/terrahub/fondo.json.
"""
import json
import math
import os
import threading
from pathlib import Path
import numpy
import pygame
import tiempo

BASE = Path(__file__).resolve().parent
RECURSOS = BASE / "recursos"
# Carpetas donde se buscan fondos: la propia de fondos y las de Imágenes y Vídeos.
CARPETAS = ("fondos", "imagenes", "videos")
IMAGENES = (".png", ".jpg", ".jpeg")
ANIMADOS = (".gif", ".mp4")
# TERRAHUB_CONFIG permite a las pruebas usar otra carpeta y no tocar la elección real.
CONFIG = Path(os.environ.get("TERRAHUB_CONFIG", Path.home() / ".config" / "terrahub")) / "fondo.json"
TIPO = {".png": "Imagen", ".jpg": "Imagen", ".jpeg": "Imagen", ".gif": "GIF", ".mp4": "Vídeo"}


def buscar_fondos(recursos=None):
    """Fondos disponibles (rutas), primero los de recursos/fondos."""
    raiz = Path(recursos or RECURSOS)
    salida = []
    for carpeta in CARPETAS:
        d = raiz / carpeta
        if d.is_dir():
            salida += sorted((p for p in d.iterdir()
                              if p.is_file() and p.suffix.lower() in IMAGENES + ANIMADOS
                              and p.name != "logo.png"), key=lambda p: p.name.casefold())
    return salida


# RGB -> (Y, Cb, Cr) de BT.601 y su inversa. El vídeo se ajusta en Y/Cb/Cr con los
# filtros de ffmpeg 'hue' (gira Cb/Cr y escala la saturación) y 'lutyuv' (escala Y);
# para las imágenes se hace la misma cuenta como una matriz RGB.
_A_YCC = numpy.array([[.299, .587, .114],
                      [-.299 / 1.772, -.587 / 1.772, .886 / 1.772],
                      [.701 / 1.402, -.587 / 1.402, -.114 / 1.402]])
_DE_YCC = numpy.linalg.inv(_A_YCC)


def matriz(tono, saturacion, brillo):
    """Matriz RGB 3x3: girar el tono 'tono' grados y multiplicar la saturación y el
    brillo, igual que hacen 'hue' + 'lutyuv' con el vídeo."""
    c, s = math.cos(math.radians(tono)), math.sin(math.radians(tono))
    k = saturacion * brillo
    ajuste = numpy.array([[brillo, 0, 0],
                          [0, c * k, -s * k],              # mismas fórmulas que vf_hue.c
                          [0, s * k, c * k]])
    return (_DE_YCC @ ajuste @ _A_YCC).astype(numpy.float32)


def neutro(tono, saturacion, brillo):
    return abs(tono) < .5 and abs(saturacion - 1) < .005 and abs(brillo - 1) < .005


def aplicar(sup, m):
    """Copia de 'sup' con la matriz de color aplicada."""
    rgb = pygame.surfarray.array3d(sup).astype(numpy.float32)
    salida = numpy.clip(rgb @ m.T, 0, 255).astype(numpy.uint8)
    return pygame.surfarray.make_surface(salida)


def filtro_mpv(tono, saturacion, brillo, tam):
    """Cadena de filtros de mpv: reducir el vídeo al tamaño de la pantalla (así el
    color se calcula sobre menos píxeles) y ajustar el color en Y/Cb/Cr, sin pasar
    a RGB (colorchannelmixer lo hacía y bajaba el vídeo de 28 a 17 fps en la Pi)."""
    # Llenar la pantalla recortando lo que sobre; así mpv ya no tiene que reescalar.
    filtros = [f"scale=w={tam[0]}:h={tam[1]}:force_original_aspect_ratio=increase",
               f"crop=w={tam[0]}:h={tam[1]}"]
    if abs(tono) >= .5 or abs(saturacion * brillo - 1) >= .005:
        filtros.append(f"hue=h={tono:.1f}:s={saturacion * brillo:.3f}")
    if abs(brillo - 1) >= .005:
        filtros.append(f"lutyuv=y=16+(val-16)*{brillo:.3f}")
    return "lavfi=[" + ",".join(filtros) + "]"


def cubrir(img, tam):
    """Escala 'img' para llenar 'tam' sin deformar, recortando lo que sobre (centrado)."""
    f = max(tam[0] / img.get_width(), tam[1] / img.get_height())
    escalada = pygame.transform.smoothscale(img, (max(tam[0], round(img.get_width() * f)),
                                                  max(tam[1], round(img.get_height() * f))))
    x, y = (escalada.get_width() - tam[0]) // 2, (escalada.get_height() - tam[1]) // 2
    return escalada.subsurface((x, y, *tam)).copy()


class Fondo:
    """Fondo elegido y su imagen ya preparada a cada tamaño que se pida."""

    def __init__(self, tam, crear_reproductor=None):
        self.tam = tam
        self.crear_reproductor = crear_reproductor
        self.ruta = None
        self.tono, self.saturacion, self.brillo = 0.0, 1.0, 1.0
        self.player = None
        self.pausado = False
        self._original = None            # imagen cargada (en otro hilo) a tamaño de pantalla
        self._cargando = None
        self._cache = {}                 # tamaño -> (clave de color, superficie)
        self._filtro_enviado = None
        self._proximo_filtro = 0
        self.error = ""
        self.cambiado = False
        self.leer()

    # --- configuración ---
    def leer(self):
        try:
            datos = json.loads(CONFIG.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        ruta = Path(datos["ruta"]) if datos.get("ruta") else None
        self.ruta = ruta if ruta and ruta.is_file() else None
        self.tono = float(datos.get("tono", 0))
        self.saturacion = float(datos.get("saturacion", 1))
        self.brillo = float(datos.get("brillo", 1))

    def guardar(self):
        try:
            CONFIG.parent.mkdir(parents=True, exist_ok=True)
            CONFIG.write_text(json.dumps({"ruta": str(self.ruta) if self.ruta else None, "tono": self.tono,
                                          "saturacion": self.saturacion, "brillo": self.brillo}),
                              encoding="utf-8")
        except OSError as error:
            print("Fondo:", error, flush=True)

    @property
    def animado(self):
        return self.ruta is not None and self.ruta.suffix.lower() in ANIMADOS

    def elegir(self, ruta):
        self.cerrar()
        self.ruta = Path(ruta) if ruta else None
        self._original = None
        self._cache.clear()
        self.error = ""
        self.guardar()

    def ajustar(self, tono=None, saturacion=None, brillo=None):
        if tono is not None:
            self.tono = tono
        if saturacion is not None:
            self.saturacion = saturacion
        if brillo is not None:
            self.brillo = brillo

    def restablecer(self):
        self.tono, self.saturacion, self.brillo = 0.0, 1.0, 1.0
        self.guardar()

    def matriz(self):
        return matriz(self.tono, self.saturacion, self.brillo)

    # --- imagen ---
    def _cargar(self, ruta):
        """En otro hilo: leer la imagen (las de 4K tardan) y escalarla a la pantalla."""
        try:
            img = pygame.image.load(str(ruta))
            if img.get_bitsize() < 24:                   # PNG con paleta: smoothscale no lo admite
                color = pygame.Surface(img.get_size(), 0, 32)
                color.blit(img, (0, 0))
                img = color
            img = cubrir(img, self.tam)
        except (pygame.error, OSError, ValueError) as error:
            print("Fondo:", error, flush=True)
            img, self.error = None, "No se pudo abrir el fondo"
        if self.ruta == ruta:
            self._original = img
        self._cargando = None
        self.cambiado = True                             # el bucle principal repinta

    def superficie(self, tam=None):
        """Fondo con su color a 'tam' (por defecto, la pantalla), o None si no hay
        (o aún se está cargando)."""
        tam = tuple(tam or self.tam)
        if self.ruta is None or self.error:
            return None
        if self.animado:
            return self._video(tam)
        if self._original is None:
            if self._cargando is None:
                self._cargando = threading.Thread(target=self._cargar, args=(self.ruta,), daemon=True)
                self._cargando.start()
            return None
        clave = (self.tono, self.saturacion, self.brillo)
        hecho = self._cache.get(tam)
        if hecho is None or hecho[0] != clave:
            base = self._original if tam == self.tam else pygame.transform.smoothscale(self._original, tam)
            sup = base if neutro(*clave) else aplicar(base, self.matriz())
            self._cache[tam] = (clave, sup.convert())
        return self._cache[tam][1]

    # --- GIF y vídeo ---
    def _video(self, tam):
        if self.player is None and self.crear_reproductor:
            try:
                self.player = self.crear_reproductor(self.ruta, self.tam)
                self.player.command("set", "loop-file", "inf")
                self._filtro_enviado = None              # reproductor nuevo: enviar el filtro ya
                self._proximo_filtro = 0
            except (OSError, RuntimeError) as error:
                print("Fondo:", error, flush=True)
                self.error = "No se pudo reproducir el fondo"
                return None
        if self.player is None:
            return None
        self._enviar_filtro()
        if tam == self.tam:
            return self.player.surface
        return pygame.transform.smoothscale(self.player.surface, tam)

    def _enviar_filtro(self, forzar=False):
        """Color del vídeo: como mucho ~6 veces por segundo mientras se desliza."""
        clave = (self.tono, self.saturacion, self.brillo)
        ahora = tiempo.ms()
        if clave == self._filtro_enviado or (not forzar and ahora < self._proximo_filtro):
            return
        self._filtro_enviado = clave
        self._proximo_filtro = ahora + 160
        self.player.command("vf", "set", filtro_mpv(self.tono, self.saturacion, self.brillo, self.tam))

    def update(self):
        """True si hay un fotograma nuevo del fondo animado."""
        if self.player is None or self.pausado:
            return False
        nuevo = self.player.update()
        if self.player.ended:                            # por si el bucle falla
            self.player.ended = False
            self.player.command("seek", "0", "absolute")
        return nuevo

    def pausar(self, pausado):
        if self.player is not None and pausado != self.pausado:
            self.player.command("set", "pause", "yes" if pausado else "no")
        self.pausado = pausado

    def cerrar(self):
        if self.player is not None:
            self.player.close()
            self.player = None
        self.pausado = False
