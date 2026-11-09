"""Frames '12 Audio' (lista "Music") y '13 Reproductor de audio'.

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
from interfaz_inicio import Escala, Control, cargar_svg, cargar_png, sombra, aviso, TEXTO
from interfaz_redes import cabecera, relleno, con_sombra, LINEA_Y

BASE = Path(__file__).resolve().parent
CACHE = BASE / ".cache" / "caratulas"
IMAGEN_EXT = (".png", ".jpg", ".jpeg", ".webp")
GLIFO = (43, 52, 66)
GRIS = (128, 128, 128)
AZUL = (23, 100, 214)

# --- Lista "Music" (frame 12), coordenadas del diseño --------------------------------
HUECOS = ([(x, 124) for x in (269, 559, 849)] +
          [(x, 309) for x in (124, 414, 704, 994)] +
          [(x, 500) for x in (269, 559, 849)])
LADO_LISTA = 142
TITULO_DY = 156                       # del borde superior de la burbuja al título
VOLVER_LISTA = pygame.Rect(14, 14, 128, 72)
FLECHA_IZQ, FLECHA_DER = (66, 387), (1215, 376)

# --- Reproductor (frame 13) -----------------------------------------------------------
VOLVER_AUDIO = pygame.Rect(12, 24, 128, 72)
CARATULA = (160, 130)
LADO_GRANDE = 380
TITULO_POS, ARTISTA_POS = (160, 536), (160, 561)
BARRA = pygame.Rect(101, 593, 480, 10)            # pista de la barra de progreso
ANTERIOR = pygame.Rect(191, 631, 56, 56)
REPRODUCIR = pygame.Rect(302, 621, 75, 75)
SIGUIENTE = pygame.Rect(438, 630, 56, 56)
PANEL = pygame.Rect(640, 130, 560, 540)            # "Burbuja cuadrada" de la letra
LETRA = pygame.Rect(664, 200, 520, 455)            # zona de texto dentro del panel
LINEA = 40                                         # separación de líneas del diseño
LETRA_ARRIBA = 15                                  # primera línea en y = 215


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


class Caratula:
    """Burbuja/Caratula del diseño: portada en círculo, anillo de cristal, brillos y sombra.

    lado: diámetro en px del diseño; svg: prefijo de los SVG (caratula142 / caratula380);
    brillos: posiciones (x, y) del brillo inferior y superior dentro del círculo.
    """
    def __init__(self, e, lado, svg, brillo_inf, brillo_sup):
        self.k, self.lado = e.k, e.n(lado)
        self.base = cargar_svg(f"{svg}-base.svg", e.k)
        self.brillos = [(cargar_svg(f"{svg}-brillo-inf.svg", e.k), e.n(brillo_inf[0]), e.n(brillo_inf[1])),
                        (cargar_svg(f"{svg}-brillo-sup.svg", e.k), e.n(brillo_sup[0]), e.n(brillo_sup[1]))]
        self.nota = max(10, round(self.lado * .35))

    def montar(self, imagen):
        """Imagen (con transparencia) y posición del borde superior izquierdo del círculo."""
        k, lado = self.k, self.lado
        s, d = sombra(lado, lado, lado // 2, round(8 * k), max(2, 9 * k), (13, 31, 64, 77))
        r_sombra = pygame.Rect((lado // 2 + d[0], lado // 2 + d[1]), s.get_size())
        r_base = pygame.Rect((-round(18 * k), -round(10 * k)), self.base.get_size())
        caja = r_sombra.union(r_base).union(pygame.Rect(0, 0, lado, lado))
        sup = pygame.Surface(caja.size, pygame.SRCALPHA)
        ox, oy = -caja.x, -caja.y                  # círculo dentro de la imagen
        sup.blit(s, (ox + r_sombra.x, oy + r_sombra.y))
        circulo = pygame.Surface((lado, lado), pygame.SRCALPHA)
        if imagen:
            f = max(lado / imagen.get_width(), lado / imagen.get_height())
            imagen = pygame.transform.smoothscale(imagen, (round(imagen.get_width() * f), round(imagen.get_height() * f)))
            circulo.blit(imagen, ((lado - imagen.get_width()) // 2, (lado - imagen.get_height()) // 2))
        else:
            circulo.fill((240, 244, 248))
            iv.nota(circulo, (lado // 2, lado // 2), self.nota, GLIFO)
        mascara = pygame.Surface((lado, lado), pygame.SRCALPHA)
        pygame.draw.circle(mascara, (255, 255, 255, 255), (lado // 2, lado // 2), lado // 2)
        circulo.blit(mascara, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        sup.blit(circulo, (ox, oy))
        sup.blit(self.base, (ox + r_base.x, oy + r_base.y))
        for brillo, x, y in self.brillos:
            sup.blit(brillo, (ox + x, oy + y))
        return sup, (ox, oy)


def cargar_imagen(ruta):
    try:
        return pygame.image.load(str(ruta)).convert() if ruta else None
    except (pygame.error, OSError):
        return None


def recortar(fuente, texto, ancho):
    while fuente.size(texto)[0] > ancho and len(texto) > 4:
        texto = texto[:-4] + "..."
    return texto


class PantallaMusica:
    """Lista 'Music': carátulas en filas de 3-4-3 por páginas deslizables."""
    POR_PAGINA = len(HUECOS)

    def __init__(self, tam):
        self.esc = e = Escala(tam)
        self.tam = tam
        self.volver = Control("volver.svg", e.k, ancho=128, alto=72, radio=36,
                              brillo=(6, 4, 116, 33.12), pos_glifo=(44, 16))
        self.izq = Control("flecha-izquierda.svg", e.k)
        self.der = Control("flecha-derecha.svg", e.k)
        self.caratula = Caratula(e, LADO_LISTA, "caratula142", (25, 107), (15, 8))
        self.titulo = cargar_png("titulo-music.png", e.k)    # "Music" en Zrnic, de Figma
        self.fuente = pygame.font.Font(None, e.n(28))
        self.fuente_aviso = pygame.font.Font(None, e.n(34))
        self._paginas = (None, [])

    def paginas(self, pistas):
        """Cada página montada una vez en una superficie opaca."""
        clave = [(str(p.ruta), p.titulo, str(p.caratula), p.leida) for p in pistas]
        if self._paginas[0] != clave:
            e = self.esc
            arriba = e.p((0, LINEA_Y + 3))[1]
            hojas = []
            for n in range(max(1, -(-len(pistas) // self.POR_PAGINA))):
                hoja = pygame.Surface((self.tam[0], self.tam[1] - arriba)).convert()
                hoja.fill((255, 255, 255))
                for pista, (x, y) in zip(pistas[n * self.POR_PAGINA:(n + 1) * self.POR_PAGINA], HUECOS):
                    img, (ox, oy) = self.caratula.montar(cargar_imagen(pista.caratula))
                    px, py = e.p((x, y))
                    hoja.blit(img, (px - ox, py - oy - arriba))
                    t = self.fuente.render(recortar(self.fuente, pista.titulo, e.n(250)), True, GLIFO)
                    hoja.blit(t, t.get_rect(center=(px + e.n(LADO_LISTA) // 2, e.p((0, y + TITULO_DY))[1] - arriba)))
                hojas.append(hoja)
            self._paginas = (clave, hojas)
        return self._paginas[1]

    def dibujar(self, sup, pistas, posicion, zona, aviso_texto="", tocable=True):
        e = self.esc
        sup.fill((255, 255, 255))
        arriba = e.p((0, LINEA_Y + 3))[1]
        w = sup.get_width()
        if not pistas:
            t = self.fuente_aviso.render("No hay audios en recursos/audio", True, GLIFO)
            sup.blit(t, t.get_rect(center=e.p((640, 360))))
        for n, hoja in enumerate(self.paginas(pistas)):
            x = round((n - posicion) * w)
            if -w < x < w:
                sup.blit(hoja, (x, arriba))
        cabecera(sup, e, self.titulo, self.volver, VOLVER_LISTA, zona)
        for control, centro, accion in ((self.izq, FLECHA_IZQ, "musica_izq"), (self.der, FLECHA_DER, "musica_der")):
            control.dibujar(sup, e.p(centro))
            rect = pygame.Rect(0, 0, e.n(110), e.n(110))
            rect.center = e.p(centro)
            zona(rect, accion)
        if tocable and abs(posicion - round(posicion)) < 2e-3:
            for i, (x, y) in enumerate(HUECOS):
                indice = round(posicion) * self.POR_PAGINA + i
                if indice < len(pistas):
                    zona(pygame.Rect(e.p((x, y)), (e.n(LADO_LISTA), e.n(LADO_LISTA))), ("pista", indice))
        if aviso_texto:
            aviso(sup, aviso_texto, self.fuente_aviso, sup.get_height() - e.n(70))


class BarraProgreso:
    """Control/Barra de progreso: pista #C3D0DE, relleno #6FB8FF->#2A303B y tirador de cristal."""
    def __init__(self, e):
        n = e.n
        self.esc = e
        self.rect = e.r(BARRA)
        w, h, r = self.rect.width, self.rect.height, n(5)
        self.pista = relleno(w, h, r, (195, 208, 222, 255), (195, 208, 222, 255))
        # Sombra interior arriba (feOffset 1.5, desenfoque 1.5, 30 %): unas líneas más oscuras.
        alto_sombra = max(1, round(3 * e.k))
        for y in range(alto_sombra):
            linea = pygame.Surface((w, 1), pygame.SRCALPHA)
            linea.fill((26, 38, 64, round(77 * (1 - y / alto_sombra))))
            self.pista.blit(linea, (0, y))
        forma = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(forma, (255, 255, 255, 255), forma.get_rect(), border_radius=r)
        self.pista.blit(forma, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        self.relleno = relleno(w, h, r, (111, 184, 255, 255), (42, 48, 59, 255))
        # Tirador: círculo de 32 px con degradado blanco -> #D3DEEA, borde #AFC0D2 y sombra.
        tirador = relleno(n(32), n(32), n(16), (255, 255, 255, 255), (211, 222, 234, 255))
        pygame.draw.circle(tirador, (175, 192, 210), (n(16), n(16)), n(16), max(1, round(1.5 * e.k)))
        self.tirador, self.desp_tirador = con_sombra(tirador, n(16), 3, 3, 77, e.k)

    def dibujar(self, sup, fraccion):
        fraccion = max(0.0, min(1.0, fraccion))
        sup.blit(self.pista, self.rect)
        lleno = round(self.rect.width * fraccion)
        if lleno:
            sup.blit(self.relleno, self.rect, pygame.Rect(0, 0, lleno, self.rect.height))
        # El tirador se centra en el final de la parte llena.
        cx, cy = self.rect.x + lleno, self.rect.centery
        radio = self.esc.n(16)
        sup.blit(self.tirador, (cx - radio - self.desp_tirador[0], cy - radio - self.desp_tirador[1]))


class PantallaAudio:
    """Reproductor de audio: carátula, título, barra, controles y panel de letra."""
    def __init__(self, tam):
        self.esc = e = Escala(tam)
        self.tam = tam
        self.volver = Control("volver.svg", e.k, ancho=128, alto=72, radio=36,
                              brillo=(6, 4, 116, 33.12), pos_glifo=(44, 16))
        self.anterior = Control("anterior.svg", e.k, ancho=56, alto=56, radio=28,
                                brillo=(4, 3, 48, 26), pos_glifo=(14, 14))
        self.siguiente = Control("siguiente.svg", e.k, ancho=56, alto=56, radio=28,
                                 brillo=(4, 3, 48, 26), pos_glifo=(14, 14))
        claves = dict(ancho=75, alto=75, radio=37.5, brillo=(4, 3, 67, 34), pos_glifo=(20, 20),
                      colores=Control.OSCURO)
        self.reproducir = Control("reproducir-35.svg", e.k, **claves)
        self.pausar = Control("pausa.svg", e.k, escala_glifo=35 / 48, **claves)
        self.caratula = Caratula(e, LADO_GRANDE, "caratula380", (65, 285), (42, 21))
        self.barra = BarraProgreso(e)
        self.fuente_titulo = pygame.font.Font(None, e.n(40))
        self.fuente_artista = pygame.font.Font(None, e.n(30))
        self.fuente_letra = pygame.font.Font(None, e.n(32))
        self.fuente_aviso = pygame.font.Font(None, e.n(34))
        self.titulo_letra = cargar_png("titulo-lyrics.png", e.k)   # "Lyrics" en Zrnic, de Figma
        self.panel = self._panel()
        self._fondo = (None, None)
        self._letra = (None, None)

    def _panel(self):
        """'Burbuja cuadrada': borde de cristal de 2.5 px, radio 34, sombra y brillos."""
        e, n = self.esc, self.esc.n
        w, h, r = n(PANEL.width), n(PANEL.height), n(34)
        forma = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(forma, (255, 255, 255, 255), forma.get_rect(), border_radius=r)
        forma.blit(relleno(n(508), n(245), n(28), (255, 255, 255, 179), (255, 255, 255, 0)), (n(26), n(21)))
        forma.blit(relleno(n(420), n(93), n(12), (255, 255, 255, 0), (255, 255, 255, 71)), (n(70), n(422)))
        pygame.draw.rect(forma, (232, 238, 245), forma.get_rect(), max(1, round(2.5 * e.k)), border_radius=r)
        return con_sombra(forma, r, 8, 9, 50, e.k)

    def fondo(self, pista):
        """Lo que no cambia mientras suena una pista, pintado una vez."""
        clave = (str(pista.ruta), pista.titulo, pista.artista, str(pista.caratula))
        if self._fondo[0] != clave:
            e = self.esc
            sup = pygame.Surface(self.tam).convert()
            sup.fill((255, 255, 255))
            img, (ox, oy) = self.caratula.montar(cargar_imagen(pista.caratula))
            px, py = e.p(CARATULA)
            sup.blit(img, (px - ox, py - oy))
            t = self.fuente_titulo.render(recortar(self.fuente_titulo, pista.titulo, e.n(460)), True, TEXTO)
            sup.blit(t, t.get_rect(midleft=e.p(TITULO_POS)))
            if pista.artista:
                a = self.fuente_artista.render(recortar(self.fuente_artista, pista.artista, e.n(460)), True, GRIS)
                sup.blit(a, a.get_rect(midleft=e.p(ARTISTA_POS)))
            panel, desp = self.panel
            x, y = e.p(PANEL.topleft)
            sup.blit(panel, (x - desp[0], y - desp[1]))
            sup.blit(self.titulo_letra, self.titulo_letra.get_rect(midleft=e.p((664, 165))))
            self._fondo = (clave, sup)
        return self._fondo[1]

    def letra(self, pista):
        """Letra pintada una vez sobre blanco: (superficie, posiciones y de cada línea)."""
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
            sup.fill((255, 255, 255))
            ys = []
            for i, (_, texto) in enumerate(lineas):
                y = e.n(LETRA_ARRIBA + LINEA * i)
                color = GRIS if pista.letra else (170, 170, 170)
                sup.blit(self.fuente_letra.render(texto, True, color), (0, y))
                ys.append(y)
            self._letra = (clave, (sup, ys, lineas))
        return self._letra[1]

    def letra_maximo(self, pista):
        """Desplazamiento máximo de la letra (px del diseño)."""
        _, ys, lineas = self.letra(pista)
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

    def dibujar(self, sup, pista, posicion, duracion, pausa, scroll, zona, aviso_texto=""):
        e = self.esc
        sup.blit(self.fondo(pista), (0, 0))
        # Letra: franja visible de la superficie ya pintada, y la línea actual resaltada.
        letra, ys, lineas = self.letra(pista)
        area = e.r(LETRA)
        desp = round(scroll * e.k)
        origen, destino = max(0, desp), area.y + max(0, -desp)
        sup.blit(letra, (area.x, destino), pygame.Rect(0, origen, area.width, area.bottom - destino))
        actual = self.linea_actual(pista, posicion)
        if actual is not None:
            y = area.y + ys[actual] - desp
            if area.y <= y < area.bottom - e.n(20):
                t = self.fuente_letra.render(lineas[actual][1], True, AZUL)
                sup.blit(t, (area.x, y))
        zona(area, "letra")
        # Controles.
        self.volver.dibujar(sup, e.p(VOLVER_AUDIO.center))
        zona(e.r(VOLVER_AUDIO).inflate(e.n(24), e.n(24)), "volver")
        fraccion = posicion / duracion if duracion else 0
        self.barra.dibujar(sup, fraccion)
        zona(self.barra.rect.inflate(e.n(40), e.n(44)), ("buscar", self.barra.rect))
        for control, rect, accion in ((self.anterior, ANTERIOR, "audio_anterior"),
                                      (self.reproducir if pausa else self.pausar, REPRODUCIR, "pausa"),
                                      (self.siguiente, SIGUIENTE, "audio_siguiente")):
            control.dibujar(sup, e.p(rect.center))
            zona(e.r(rect).inflate(e.n(20), e.n(20)), accion)
        if aviso_texto:
            aviso(sup, aviso_texto, self.fuente_aviso, sup.get_height() - e.n(70))
