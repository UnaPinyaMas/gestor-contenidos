"""Miniaturas de Vídeos, Libros e Imágenes, hechas en segundo plano y guardadas en disco.

Cargar una foto 4K o sacar un fotograma de un vídeo tarda; si se hiciera al pintar, la
pantalla se quedaría parada. Un hilo las prepara una vez (ffmpeg, pymupdf o pygame) en
.cache/miniaturas; la pantalla pinta un hueco mientras tanto y se avisa al menú para que
repinte cuando están. Si una falla se guarda un archivo vacío para no reintentarla.
"""
import hashlib
import queue
import subprocess
import threading
from pathlib import Path
import pygame

BASE = Path(__file__).resolve().parent
CACHE = BASE / ".cache" / "miniaturas"
# Tamaño máximo de cada tipo (ancho, alto): suficiente para una pantalla de 1280x720.
TAMANOS = {"video": (480, 270), "libro": (320, 600), "imagen": (480, 270), "vista": (1280, 760)}


def _clave(ruta, tipo):
    try:
        marca = Path(ruta).stat().st_mtime_ns
    except OSError:
        marca = 0
    return hashlib.sha1(f"{ruta}:{marca}:{tipo}".encode()).hexdigest()


def _escalar(img, w, h, cubrir):
    f = (max if cubrir else min)(w / img.get_width(), h / img.get_height())
    if not cubrir:
        f = min(1.0, f)
    tam = (max(1, round(img.get_width() * f)), max(1, round(img.get_height() * f)))
    img = pygame.transform.smoothscale(img, tam)
    if cubrir:
        x, y = (tam[0] - w) // 2, (tam[1] - h) // 2
        img = img.subsurface(pygame.Rect(max(0, x), max(0, y), min(w, tam[0]), min(h, tam[1]))).copy()
    return img


def generar(ruta, tipo, destino):
    """Crea la miniatura 'tipo' de 'ruta' en 'destino'. True si ha salido bien."""
    ruta = Path(ruta)
    w, h = TAMANOS[tipo]
    if tipo == "video":
        for segundo in ("3", "0"):                    # un poco adentro (evita negros), o el primero
            try:
                subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", segundo, "-i", str(ruta), "-frames:v", "1",
                                "-vf", f"scale={w}:-2", str(destino)], capture_output=True, timeout=30)
            except (OSError, subprocess.TimeoutExpired):
                return False
            if destino.is_file() and destino.stat().st_size:
                return True
        return False
    if tipo == "libro":
        try:
            import pymupdf as fitz
        except ImportError:
            import fitz
        doc = fitz.open(str(ruta))
        try:
            if doc.needs_pass or not doc.page_count:
                return False
            pagina = doc.load_page(0)
            f = min(w / pagina.rect.width, h / pagina.rect.height)
            pagina.get_pixmap(matrix=fitz.Matrix(f, f), alpha=False).save(str(destino))
        finally:
            doc.close()
        return True
    img = pygame.image.load(str(ruta))
    pygame.image.save(_escalar(img, w, h, cubrir=tipo == "imagen"), str(destino))
    return True


def duracion(ruta):
    """Duración en segundos de un vídeo (ffprobe), o None."""
    try:
        salida = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                 "default=nw=1:nk=1", str(ruta)], capture_output=True, text=True, timeout=15).stdout
        return float(salida.strip())
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


class Miniaturas:
    """Cola de miniaturas pendientes y las ya cargadas (como superficies de pygame).

    'avisar' se llama (desde el hilo) cada vez que termina una, para repintar.
    """
    def __init__(self, avisar=lambda: None, carpeta=CACHE):
        self.avisar = avisar
        self.carpeta = Path(carpeta)
        self.cola = queue.Queue()
        self.pedidas = set()
        self.cargadas = {}           # (ruta, tipo) -> Surface o False (falló)
        self.duraciones = {}         # ruta -> segundos o None
        self._hilo = None

    def _archivo(self, ruta, tipo):
        return self.carpeta / f"{_clave(ruta, tipo)}.{'png' if tipo == 'libro' else 'jpg'}"

    def superficie(self, ruta, tipo):
        """La miniatura ya cargada, None si aún no está (se pide) o False si no se puede."""
        clave = (str(ruta), tipo)
        if clave in self.cargadas:
            return self.cargadas[clave]
        archivo = self._archivo(ruta, tipo)
        if archivo.is_file():
            if not archivo.stat().st_size:
                self.cargadas[clave] = False
                return False
            try:
                self.cargadas[clave] = pygame.image.load(str(archivo)).convert()
            except (pygame.error, OSError):
                self.cargadas[clave] = False
            return self.cargadas[clave]
        self._pedir(ruta, tipo)
        return None

    def duracion(self, ruta):
        """Duración de un vídeo si ya se conoce (se pide si no)."""
        if str(ruta) not in self.duraciones:
            self._pedir(ruta, "duracion")
            return None
        return self.duraciones[str(ruta)]

    def olvidar(self, ruta):
        """Tras borrar un archivo: quita sus miniaturas de memoria."""
        for clave in [c for c in self.cargadas if c[0] == str(ruta)]:
            del self.cargadas[clave]

    def _pedir(self, ruta, tipo):
        clave = (str(ruta), tipo)
        if clave in self.pedidas:
            return
        self.pedidas.add(clave)
        self.cola.put(clave)
        if self._hilo is None or not self._hilo.is_alive():
            self._hilo = threading.Thread(target=self._trabajar, daemon=True)
            self._hilo.start()

    def _trabajar(self):
        while True:                                    # hilo 'daemon': vive con TerraHub
            ruta, tipo = self.cola.get()
            try:
                if tipo == "duracion":
                    self.duraciones[ruta] = duracion(ruta)
                else:
                    self.carpeta.mkdir(parents=True, exist_ok=True)
                    destino = self._archivo(ruta, tipo)
                    temporal = destino.with_name("tmp-" + destino.name)
                    if generar(ruta, tipo, temporal):
                        temporal.replace(destino)
                    else:
                        temporal.unlink(missing_ok=True)
                        destino.write_bytes(b"")
            except Exception as error:               # archivo dañado, formato raro...
                print("Miniatura:", Path(ruta).name, error, flush=True)
                try:
                    self._archivo(ruta, tipo).write_bytes(b"")
                except OSError:
                    pass
            self.avisar()
