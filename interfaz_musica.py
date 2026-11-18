"""Música (entrega v2, 6.9) y reproductor de audio (6.10).

Datos de cada pista:
- título y artista: etiquetas del archivo (ffprobe); si no hay, el nombre del archivo;
- carátula: imagen con el mismo nombre, cover/folder/front.* de la carpeta, o la
  incrustada en el audio (extraída con ffmpeg a .cache/caratulas);
- letra: .lrc (sincronizada) o .txt con el mismo nombre, o la etiqueta 'lyrics'.
"""
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re
import subprocess
import pygame
import interfaz_video as iv
import estilo
from estilo import BLANCO, MAGENTA, AZUL_OSCURO, GRIS, TEXTO
from interfaz_inicio import Escala, aviso, fuente_aviso, cabecera_blanca, flechas_pagina

BASE = Path(__file__).resolve().parent
CACHE = BASE / ".cache" / "caratulas"
IMAGEN_EXT = (".png", ".jpg", ".jpeg", ".webp")
GLIFO = AZUL_OSCURO

# --- Lista "Music" (coordenadas del diseño: centros de las carátulas) ------------------
HUECOS = ([(x, 232) for x in (390, 640, 890)] +
          [(x, 412) for x in (265, 515, 765, 1015)] +
          [(x, 592) for x in (390, 640, 890)])
LADO_LISTA = 105
TITULO_DY = 66                        # del centro de la carátula al centro del título
FLECHA_IZQ, FLECHA_DER = (60, 420), (1220, 420)
ARRIBA = 135

# --- Reproductor ---------------------------------------------------------------------
CARATULA = (330, 310)                 # centro
LADO_GRANDE = 363
TITULO_POS, ARTISTA_POS = (150, 530), (150, 557)
BARRA = pygame.Rect(100, 600, 460, 6)
TIEMPOS_Y = 624
ANTERIOR, REPRODUCIR, SIGUIENTE = (242, 667), (330, 667), (418, 667)
PANEL = pygame.Rect(651, 121, 558, 558)
LETRA = pygame.Rect(687, 205, 486, 450)
LINEA = 32                            # separación de líneas
LETRA_ARRIBA = 6


@dataclass
class Pista:
    ruta: Path
    titulo: str = ""
    artista: str = ""
    caratula: Path = None
    letra: list = field(default_factory=list)      # [(segundos o None, texto)]
    leida: bool = False

    def __post_init__(self):
        self.titulo = self.titulo or self.ruta.stem

    @property
    def sincronizada(self):
        return any(t is not None for t, _ in self.letra)


def buscar_audios(carpeta, extensiones):
    carpeta.mkdir(parents=True, exist_ok=True)
    return sorted((p for p in carpeta.rglob("*") if p.is_file() and p.suffix.lower() in extensiones
                   and not any(parte.startswith(".") for parte in p.relative_to(carpeta).parts)),
                  key=lambda p: str(p.relative_to(carpeta)).casefold())


def leer_lrc(texto):
    """Letra .lrc: [mm:ss.xx] texto. Las líneas sin tiempo se conservan sin tiempo."""
    lineas = []
    for linea in texto.splitlines():
        tiempos = re.findall(r"\[(\d+):(\d+(?:\.\d+)?)\]", linea)
        contenido = re.sub(r"\[[^\]]*\]", "", linea).strip()
        if tiempos:
            lineas += [(int(m) * 60 + float(s), contenido) for m, s in tiempos]
        elif contenido and not re.match(r"^\[\w+:", linea):
            lineas.append((None, contenido))
    sincronizadas = sorted(l for l in lineas if l[0] is not None)
    return sincronizadas or lineas


def leer_metadatos(pista):
    """Rellena título, artista, carátula y letra (llamadas a ffprobe/ffmpeg: usar en un hilo).

    Si el archivo desaparece a mitad (p. ej. se borra), la pista se queda con lo básico.
    """
    try:
        _leer_metadatos(pista)
    except OSError as error:
        print("Metadatos:", pista.ruta.name, error, flush=True)
    pista.leida = True
    return pista


def _leer_metadatos(pista):
    ruta = pista.ruta
    etiquetas = {}
    try:
        salida = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format_tags", "-of", "json",
                                 str(ruta)], capture_output=True, text=True, timeout=15).stdout
        etiquetas = {k.lower(): v for k, v in json.loads(salida or "{}").get("format", {}).get("tags", {}).items()}
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        print("Metadatos:", ruta.name, error, flush=True)
    pista.titulo = etiquetas.get("title", "").strip() or ruta.stem
    pista.artista = etiquetas.get("artist", "").strip()
    # Carátula: imagen junto al audio, de la carpeta, o la incrustada.
    candidatas = [ruta.with_suffix(e) for e in IMAGEN_EXT]
    candidatas += [ruta.parent / f"{n}{e}" for n in ("cover", "folder", "front") for e in IMAGEN_EXT]
    pista.caratula = next((c for c in candidatas if c.is_file()), None)
    if pista.caratula is None:
        pista.caratula = extraer_caratula(ruta)
    # Letra: .lrc, .txt o etiqueta.
    for ext in (".lrc", ".txt"):
        archivo = ruta.with_suffix(ext)
        if archivo.is_file():
            pista.letra = leer_lrc(archivo.read_text(encoding="utf-8", errors="replace"))
            break
    else:
        etiqueta = next((v for k, v in etiquetas.items() if k.startswith("lyrics") or k == "unsyncedlyrics"), "")
        pista.letra = leer_lrc(etiqueta) if etiqueta else []


def extraer_caratula(ruta):
    """Carátula incrustada en el audio, extraída una vez a .cache/caratulas."""
    clave = hashlib.sha1(f"{ruta}:{ruta.stat().st_mtime_ns}".encode()).hexdigest()
    destino = CACHE / f"{clave}.jpg"
    if destino.is_file():
        return destino if destino.stat().st_size else None
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(ruta), "-an", "-frames:v", "1", str(destino)],
                       capture_output=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        pass
    if not destino.is_file():
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(b"")             # recordar que no tiene carátula
    return destino if destino.stat().st_size else None


def cargar_imagen(ruta):
    try:
        return pygame.image.load(str(ruta)).convert() if ruta else None
    except (pygame.error, OSError):
        return None


def recortar(fuente, texto, ancho):
    return estilo.recortar(fuente, texto, ancho)


def caratula(imagen, lado, aro_magenta=False):
    """Carátula en círculo con aro blanco (y otro magenta en el reproductor) y sombra:
    (imagen, centro del círculo dentro de ella)."""
    disco = pygame.Surface((lado, lado), pygame.SRCALPHA)
    c = lado // 2
    exterior = max(2, round(lado * (.012 if aro_magenta else .028)))
    if aro_magenta:
        pygame.draw.circle(disco, MAGENTA, (c, c), c)
        pygame.draw.circle(disco, BLANCO, (c, c), c - exterior)
        interior = lado - 2 * (exterior + max(2, round(lado * .016)))
    else:
        pygame.draw.circle(disco, BLANCO, (c, c), c)
        pygame.draw.circle(disco, (214, 222, 232), (c, c), c, 1)
        interior = lado - 2 * exterior
    if imagen is not None:
        disco.blit(estilo.circular(imagen, interior), ((lado - interior) // 2, (lado - interior) // 2))
    else:
        hueco = pygame.Surface((interior, interior), pygame.SRCALPHA)
        pygame.draw.circle(hueco, (238, 242, 247), (interior // 2, interior // 2), interior // 2)
        iv.nota(hueco, (interior // 2, interior // 2), max(10, round(interior * .35)), GLIFO)
        disco.blit(hueco, ((lado - interior) // 2, (lado - interior) // 2))
    img, pos = estilo.con_sombra(disco, c, lado * .05, lado * .08, (13, 31, 64, 70))
    return img, (pos[0] + c, pos[1] + c)


class PantallaMusica:
    """Lista 'Music': carátulas en filas de 3-4-3 por páginas deslizables."""
    POR_PAGINA = len(HUECOS)

    def __init__(self, tam):
        self.esc = e = Escala(tam)
        self.tam = tam
        self.fondo, self.barra = cabecera_blanca(tam, e, "titulo-music.png")
        self.flechas = flechas_pagina(e, FLECHA_IZQ, FLECHA_DER)
        self.fuente = estilo.fuente(e.n(15), "Medium")
        self.fuente_aviso = fuente_aviso(e)
        self._paginas = (None, [])

    def paginas(self, pistas):
        """Cada página montada una vez en una superficie opaca."""
        clave = [(str(p.ruta), p.titulo, str(p.caratula), p.leida) for p in pistas]
        if self._paginas[0] != clave:
            e = self.esc
            arriba = e.p((0, ARRIBA))[1]
            hojas = []
            for n in range(max(1, -(-len(pistas) // self.POR_PAGINA))):
                hoja = pygame.Surface((self.tam[0], self.tam[1] - arriba)).convert()
                hoja.fill(BLANCO)
                for pista, centro in zip(pistas[n * self.POR_PAGINA:(n + 1) * self.POR_PAGINA], HUECOS):
                    img, c = caratula(cargar_imagen(pista.caratula), e.n(LADO_LISTA))
                    px, py = e.p(centro)
                    hoja.blit(img, (px - c[0], py - c[1] - arriba))
                    t = self.fuente.render(recortar(self.fuente, pista.titulo, e.n(190)), True, GRIS)
                    hoja.blit(t, t.get_rect(center=(px, py + e.n(TITULO_DY) - arriba)))
                hojas.append(hoja)
            self._paginas = (clave, hojas)
        return self._paginas[1]

    def dibujar(self, sup, pistas, posicion, zona, aviso_texto="", tocable=True, hora="", resaltado=None):
        e = self.esc
        sup.blit(self.fondo, (0, 0))
        arriba = e.p((0, ARRIBA))[1]
        w = sup.get_width()
        if not pistas:
            t = estilo.fuente(e.n(22), "Medium").render("No hay audios en recursos/audio", True, GRIS)
            sup.blit(t, t.get_rect(center=e.p((640, 400))))
        for n, hoja in enumerate(self.paginas(pistas)):
            x = round((n - posicion) * w)
            if -w < x < w:
                sup.blit(hoja, (x, arriba))
        if abs(posicion - round(posicion)) < 2e-3:
            for i, centro in enumerate(HUECOS):
                indice = round(posicion) * self.POR_PAGINA + i
                if indice >= len(pistas):
                    break
                if resaltado == ("pista", indice):
                    pygame.draw.circle(sup, MAGENTA, e.p(centro), e.n(LADO_LISTA / 2 + 6), max(2, e.n(4)))
                if tocable:
                    r = pygame.Rect(0, 0, e.n(LADO_LISTA + 20), e.n(LADO_LISTA + 30))
                    r.center = e.p((centro[0], centro[1] + 10))
                    zona(r, ("pista", indice))
        for (control, centro), accion in zip(self.flechas, ("musica_izq", "musica_der")):
            r = control.dibujar(sup, centro, resaltado == accion)
            zona(r.inflate(e.n(40), e.n(40)), accion)
        self.barra.dibujar(sup, zona, hora)
        if aviso_texto:
            aviso(sup, aviso_texto, self.fuente_aviso, sup.get_height() - e.n(50))


class PantallaAudio:
    """Reproductor de audio: carátula con aro magenta, título, barra de progreso,
    anterior / reproducir / siguiente y el panel de la letra (Lyrics)."""
    def __init__(self, tam):
        self.esc = e = Escala(tam)
        self.tam = tam
        self.fondo_base, self.barra_sup = cabecera_blanca(tam, e)
        lado = e.n(56)
        self.anterior = estilo.Boton(lado, lado, glifo="anterior.svg", lado_glifo=lado * .62)
        self.siguiente = estilo.Boton(lado, lado, glifo="siguiente.svg", lado_glifo=lado * .62)
        grande = e.n(80)
        self.reproducir = estilo.Boton(grande, grande, glifo="reproducir-35.svg", lado_glifo=grande * .42, tipo="oscuro")
        self.pausar = estilo.Boton(grande, grande, glifo="pausa.svg", lado_glifo=grande * .58, tipo="oscuro")
        self.barra = estilo.Barra(e.r(BARRA), alto_tirador=e.n(23))
        self.fuente_titulo = estilo.fuente(e.n(24), "Bold")
        self.fuente_artista = estilo.fuente(e.n(19), "Regular")
        self.fuente_tiempo = estilo.fuente(e.n(14), "Medium")
        self.fuente_letra = estilo.fuente(e.n(19), "Medium")
        self.fuente_aviso = fuente_aviso(e)
        self._fondo = (None, None)
        self._letra = (None, None)
        self._tiempos = {}

    def _panel(self, sup):
        """Tarjeta blanca de la letra con borde suave, sombra y el título 'Lyrics'."""
        e = self.esc
        r = e.r(PANEL)
        tarjeta = pygame.Surface(r.size, pygame.SRCALPHA)
        pygame.draw.rect(tarjeta, BLANCO, tarjeta.get_rect(), border_radius=e.n(20))
        pygame.draw.rect(tarjeta, (226, 232, 240), tarjeta.get_rect(), max(1, e.n(1.5)), border_radius=e.n(20))
        img, pos = estilo.con_sombra(tarjeta, e.n(20), e.n(6), e.n(14), (13, 31, 64, 30))
        sup.blit(img, (r.x - pos[0], r.y - pos[1]))
        t = estilo.fuente(e.n(26), "Bold").render("Lyrics", True, TEXTO)
        rt = t.get_rect(midleft=e.p((687, 167)))
        sup.blit(t, rt)
        pygame.draw.rect(sup, MAGENTA, (rt.right + e.n(10), rt.centery - e.n(2), e.n(36), max(2, e.n(4))),
                         border_radius=e.n(2))

    def fondo(self, pista):
        """Lo que no cambia mientras suena una pista, pintado una vez."""
        clave = (str(pista.ruta), pista.titulo, pista.artista, str(pista.caratula))
        if self._fondo[0] != clave:
            e = self.esc
            sup = self.fondo_base.copy()
            img, c = caratula(cargar_imagen(pista.caratula), e.n(LADO_GRANDE), aro_magenta=True)
            px, py = e.p(CARATULA)
            sup.blit(img, (px - c[0], py - c[1]))
            t = self.fuente_titulo.render(recortar(self.fuente_titulo, pista.titulo, e.n(440)), True, TEXTO)
            sup.blit(t, t.get_rect(midleft=e.p(TITULO_POS)))
            if pista.artista:
                a = self.fuente_artista.render(recortar(self.fuente_artista, pista.artista, e.n(440)), True,
                                               (51, 51, 51))
                sup.blit(a, a.get_rect(midleft=e.p(ARTISTA_POS)))
            self._panel(sup)
            self._fondo = (clave, sup)
        return self._fondo[1]

    def letra(self, pista):
        """Letra pintada una vez sobre blanco: (superficie, posiciones y de cada línea, líneas)."""
        clave = (str(pista.ruta), tuple(pista.letra))
        if self._letra[0] != clave:
            e = self.esc
            ancho = e.n(LETRA.width)
            lineas = []
            for tiempo, texto in pista.letra or [(None, "Sin letra")]:
                actual = ""
                for palabra in (texto or " ").split(" "):
                    prueba = (actual + " " + palabra).strip()
                    if self.fuente_letra.size(prueba)[0] > ancho and actual:
                        lineas.append((tiempo, actual))
                        tiempo, actual = None, palabra
                    else:
                        actual = prueba
                lineas.append((tiempo, actual))
            sup = pygame.Surface((ancho, max(1, e.n(LETRA_ARRIBA + LINEA * len(lineas))))).convert()
            sup.fill(BLANCO)
            ys = []
            for i, (_, texto) in enumerate(lineas):
                y = e.n(LETRA_ARRIBA + LINEA * i)
                color = GRIS if pista.letra else (160, 166, 176)
                sup.blit(self.fuente_letra.render(texto, True, color), (0, y))
                ys.append(y)
            self._letra = (clave, (sup, ys, lineas))
        return self._letra[1]

    def letra_maximo(self, pista):
        """Desplazamiento máximo de la letra (px del diseño)."""
        _, _, lineas = self.letra(pista)
        alto = LETRA_ARRIBA + LINEA * len(lineas) + 20
        return max(0, alto - LETRA.height)

    def linea_actual(self, pista, segundos):
        """Índice (en la letra ya partida) de la línea que suena, o None si no es .lrc."""
        if not pista.sincronizada or segundos is None:
            return None
        _, _, lineas = self.letra(pista)
        actual = None
        for i, (t, _) in enumerate(lineas):
            if t is not None and t <= segundos:
                actual = i
        return actual

    def _tiempo(self, segundos):
        texto = iv.formato_tiempo(segundos)
        if texto not in self._tiempos:
            if len(self._tiempos) > 8:
                self._tiempos.clear()
            self._tiempos[texto] = self.fuente_tiempo.render(texto, True, (51, 51, 51))
        return self._tiempos[texto]

    def dibujar(self, sup, pista, posicion, duracion, pausa, scroll, zona, aviso_texto="", hora="",
                resaltado=None):
        e = self.esc
        sup.blit(self.fondo(pista), (0, 0))
        # Letra: franja visible de la superficie ya pintada, y la línea actual en magenta.
        letra, ys, lineas = self.letra(pista)
        area = e.r(LETRA)
        desp = round(scroll * e.k)
        origen, destino = max(0, desp), area.y + max(0, -desp)
        sup.blit(letra, (area.x, destino), pygame.Rect(0, origen, area.width, area.bottom - destino))
        actual = self.linea_actual(pista, posicion)
        if actual is not None:
            y = area.y + ys[actual] - desp
            if area.y <= y < area.bottom - e.n(20):
                sup.blit(self.fuente_letra.render(lineas[actual][1], True, MAGENTA), (area.x, y))
        zona(area, "letra")
        # Barra de progreso y tiempos.
        fraccion = posicion / duracion if duracion else 0
        self.barra.dibujar(sup, fraccion)
        zona(self.barra.rect.inflate(e.n(40), e.n(40)), ("buscar", self.barra.rect))
        t = self._tiempo(posicion)
        sup.blit(t, t.get_rect(midleft=e.p((BARRA.x, TIEMPOS_Y))))
        t = self._tiempo(duracion)
        sup.blit(t, t.get_rect(midright=e.p((BARRA.right, TIEMPOS_Y))))
        for control, centro, accion in ((self.anterior, ANTERIOR, "audio_anterior"),
                                        (self.reproducir if pausa else self.pausar, REPRODUCIR, "pausa"),
                                        (self.siguiente, SIGUIENTE, "audio_siguiente")):
            r = control.dibujar(sup, e.p(centro), resaltado == accion)
            zona(r.inflate(e.n(16), e.n(16)), accion)
        self.barra_sup.dibujar(sup, zona, hora)
        if aviso_texto:
            aviso(sup, aviso_texto, self.fuente_aviso, sup.get_height() - e.n(40))
