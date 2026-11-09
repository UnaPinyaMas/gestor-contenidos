"""Pantallas de Inicio, menú de energía y ajustes según el wireframe de Figma (1280x720).

Las burbujas y los glifos son los SVG exportados del diseño (recursos/interfaz).
Pygame los rasteriza con nanosvg, que no aplica los filtros de sombra, así que
la sombra (feOffset dy=8, feGaussianBlur 9, rgba(13,31,64,.3)) se añade aquí.
"""
import io
import math
import re
from pathlib import Path
import pygame

INTERFAZ = Path(__file__).resolve().parent / "recursos" / "interfaz"
DISENO = (1280, 720)                  # tamaño del frame en Figma
TEXTO = (33, 33, 33)                  # #212121

# Carrusel de Inicio: (etiqueta, sección de CARPETAS, svg). Orden de la nota del diseño.
SECCIONES = [
    ("Audio", "Audio", "burbuja-audio.svg"),
    ("Vídeos", "Vídeos", "burbuja-videos.svg"),
    ("Libros", "Libros", "burbuja-libros.svg"),
    ("Imágenes", "Imágenes", "burbuja-imagenes.svg"),
    ("Juegos", "Juegos", "burbuja-juegos.svg"),
]
# Menú de ajustes (se abre desde el círculo de la barra superior), lista estilo PS Vita:
# (acción, etiqueta, icono svg). La primera fila despliega las opciones de energía.
AJUSTES_FILAS = [
    ("energia", "Opciones de energía", "energia-apagar.svg"),
    ("ajuste_fecha", "Fecha y hora", "icono-reloj.svg"),
    ("ajuste_redes", "Redes", "wifi.svg"),
    ("ajuste_ip", "Dirección IP", "icono-ip.svg"),
    ("ajuste_fondo", "Fondo de pantalla", "icono-fondo.svg"),
]
ENERGIA_OPCIONES = [
    ("suspender", "Suspender", "energia-suspender.svg"),
    ("reiniciar", "Reiniciar", "energia-reiniciar.svg"),
    ("apagar", "Apagar", "energia-apagar.svg"),
]
FILA_ALTO = 92                         # px del diseño

# Geometría de los frames (coordenadas de Figma, centros de los círculos base).
CENTRO_CARRUSEL = (640, 345)
SEPARACION = 340                      # de Vídeos (640) a Audio/Libros (300/980)
DIAMETRO_CENTRO, DIAMETRO_LADO = 294, 221
FLECHA_IZQ, FLECHA_DER = (112, 364), (1166, 364)
LOGO = pygame.Rect(440, 62, 400, 84)  # bajado 26 px para dejar sitio a la barra superior

# Barra superior (no está en el Figma: estilo de la referencia del equipo). Medidas en
# px del diseño; va pegada al borde de arriba de la pantalla.
BARRA_ALTO = 44
BARRA_CORTE = 880                     # x de la franja blanca en diagonal
CIRCULO = ((1232, 20), 100)           # (centro, diámetro) del círculo de la esquina
RELOJ_DER = 1160                      # borde derecho de la hora


class Escala:
    """Convierte coordenadas del frame 1280x720 a la pantalla, sin deformar."""
    def __init__(self, tam):
        w, h = tam
        self.k = min(w / DISENO[0], h / DISENO[1])
        self.dx = (w - DISENO[0] * self.k) / 2
        self.dy = (h - DISENO[1] * self.k) / 2

    def p(self, punto):
        return (round(self.dx + punto[0] * self.k), round(self.dy + punto[1] * self.k))

    def n(self, valor):
        return max(1, round(valor * self.k))

    def r(self, rect):
        x, y = self.p(rect.topleft)
        return pygame.Rect(x, y, self.n(rect.width), self.n(rect.height))


def cargar_svg(nombre, factor, color=None, original="white"):
    """Rasteriza un SVG del diseño a 'factor' veces su tamaño (desde el vector).

    'color' sustituye el color 'original' de los glifos (por defecto el blanco; p. ej.
    un icono blanco sobre fondo claro, o uno oscuro en blanco sobre fondo oscuro).
    """
    texto = (INTERFAZ / nombre).read_text(encoding="utf-8")
    if color:
        texto = texto.replace(f'"{original}"', f'"{color}"')
    w = float(re.search(r'width="([\d.]+)"', texto).group(1))
    h = float(re.search(r'height="([\d.]+)"', texto).group(1))
    texto = re.sub(r'width="[\d.]+"', f'width="{w * factor:.2f}"', texto, count=1)
    texto = re.sub(r'height="[\d.]+"', f'height="{h * factor:.2f}"', texto, count=1)
    return pygame.image.load(io.BytesIO(texto.encode("utf-8")), "a.svg").convert_alpha()


def cargar_png(nombre, factor):
    """Imagen exportada del diseño, escalada a 'factor' veces su tamaño.

    Los títulos en Zrnic ("Games", "Music", "Lyrics") se usan así, ya renderizados por
    Figma: la licencia gratuita de Zrnic no permite incrustar la fuente en software.
    """
    img = pygame.image.load(str(INTERFAZ / nombre)).convert_alpha()
    tam = (max(1, round(img.get_width() * factor)), max(1, round(img.get_height() * factor)))
    return pygame.transform.smoothscale(img, tam)


def _base(nombre):
    texto = (INTERFAZ / nombre).read_text(encoding="utf-8")
    m = re.search(r'<circle cx="([\d.]+)" cy="([\d.]+)" r="([\d.]+)"', texto)
    return float(m.group(1)), float(m.group(2)), float(m.group(3))


def _difuminar(sup, radio):
    """Desenfoque aproximado (reducir y ampliar) para las sombras."""
    w, h = sup.get_size()
    f = max(2, round(radio))
    peq = pygame.transform.smoothscale(sup, (max(1, w // f), max(1, h // f)))
    return pygame.transform.smoothscale(peq, (w, h))


def sombra(ancho, alto, radio, dy, desenfoque, color):
    """Sombra de un rectángulo redondeado (o círculo) como las del diseño.

    Devuelve la superficie y su desplazamiento respecto al centro de la forma.
    """
    margen = round(desenfoque * 2.5)
    s = pygame.Surface((ancho + margen * 2, alto + margen * 2), pygame.SRCALPHA)
    pygame.draw.rect(s, color, (margen, margen, ancho, alto), border_radius=radio)
    # convert_alpha: mismo formato de píxel que la pantalla, copias más rápidas.
    return _difuminar(s, desenfoque).convert_alpha(), (-s.get_width() // 2, -s.get_height() // 2 + dy)


class Burbuja:
    """Burbuja del diseño escalada a un diámetro de círculo base dado, con sombra."""
    def __init__(self, nombre, diametro):
        cx, cy, r = _base(nombre)
        f = diametro / (2 * r)
        self.img = cargar_svg(nombre, f)
        self.ancla = (round(cx * f), round(cy * f))     # centro del círculo dentro de img
        self.diametro = diametro
        k = diametro / 294                              # el filtro está definido a escala Vídeos
        self.sombra, self.desp = sombra(diametro, diametro, diametro // 2, round(8 * k),
                                        max(2, 9 * k), (13, 31, 64, 77))

    def dibujar(self, sup, centro, alpha=255):
        x, y = centro
        s, img = self.sombra, self.img
        if alpha < 255:
            s, img = s.copy(), img.copy()
            s.set_alpha(alpha)
            img.set_alpha(alpha)
        sup.blit(s, (x + self.desp[0], y + self.desp[1]))
        sup.blit(img, (x - self.ancla[0], y - self.ancla[1]))


class Control:
    """Controles de cristal del diseño (Control/Izquierda, /Derecha, /Volver).

    Base con degradado blanco -> #d3deea, borde 1.5px #afc0d2, sombra 0 4px 10px
    rgba(13,31,64,.22), brillo superior y glifo SVG. Medidas en px del diseño.
    """
    CLARO = ((255, 255, 255), (211, 222, 234), (175, 192, 210), 230)   # arriba, abajo, borde, brillo
    OSCURO = ((90, 100, 117), (42, 48, 59), (28, 33, 41), 89)          # Control/Pausa y /Reproducir

    def __init__(self, glifo, k, ancho=80, alto=80, radio=40, brillo=(6, 4, 68, 36.8),
                 pos_glifo=(20, 20), colores=CLARO, escala_glifo=1.0):
        arriba, abajo, borde, alpha_brillo = colores
        w, h, rad = round(ancho * k), round(alto * k), round(radio * k)
        s, d = sombra(w, h, rad, round(4 * k), 10 * k, (13, 31, 64, 56))
        margen = round(4 * k)
        sup = pygame.Surface((s.get_width() + 2 * margen, s.get_height() + 2 * margen), pygame.SRCALPHA)
        cx, cy = sup.get_width() // 2, sup.get_height() // 2
        sup.blit(s, (cx + d[0], cy + d[1]))
        base = pygame.Surface((w, h), pygame.SRCALPHA)
        for y in range(h):
            t = y / max(1, h - 1)
            color = tuple(round(a + (b - a) * t) for a, b in zip(arriba, abajo))
            pygame.draw.line(base, color, (0, y), (w - 1, y))
        forma = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(forma, (255, 255, 255, 255), forma.get_rect(), border_radius=rad)
        base.blit(forma, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        pygame.draw.rect(base, borde, base.get_rect(), max(1, round(1.5 * k)), border_radius=rad)
        x0, y0 = cx - w // 2, cy - h // 2
        sup.blit(base, (x0, y0))
        bx, by, bw, bh = (round(v * k) for v in brillo)
        luz = pygame.Surface((bw, bh), pygame.SRCALPHA)
        for y in range(bh):
            pygame.draw.line(luz, (255, 255, 255, round(alpha_brillo * (1 - y / max(1, bh - 1)))), (0, y), (bw, y))
        forma = pygame.Surface((bw, bh), pygame.SRCALPHA)
        pygame.draw.rect(forma, (255, 255, 255, 255), forma.get_rect(), border_radius=rad)
        luz.blit(forma, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        sup.blit(luz, (x0 + bx, y0 + by))
        # escala_glifo: para reutilizar un glifo de otro tamaño (p. ej. pausa de 48 en un hueco de 35).
        sup.blit(cargar_svg(glifo, k * escala_glifo), (x0 + round(pos_glifo[0] * k), y0 + round(pos_glifo[1] * k)))
        self.img = sup.convert_alpha()
        self.tam = (w, h)

    def dibujar(self, sup, centro):
        sup.blit(self.img, self.img.get_rect(center=centro))


class ElementoBurbuja:
    """Elemento de carrusel con burbuja SVG.

    Cada tamaño entre centro y lado se monta una sola vez, con su sombra, sobre el
    fondo blanco de la pantalla y sin transparencia: al moverse, cada burbuja es una
    única copia opaca (el pygame de la Raspberry no usa NEON y mezclar transparencias
    en cada fotograma era lo más lento). Las vecinas nunca se solapan: están a 340 px
    del diseño y cada imagen mide como mucho ~320.
    """
    PASOS = 12

    def __init__(self, svg, e, fondo=(255, 255, 255)):
        centro = Burbuja(svg, e.n(DIAMETRO_CENTRO))
        lado = Burbuja(svg, e.n(DIAMETRO_LADO))
        self.diametros = (centro.diametro, lado.diametro)
        self.pasos = []                  # (imagen opaca, posición del centro dentro) de centro a lado
        for j in range(self.PASOS + 1):
            if j in (0, self.PASOS):
                b = centro if j == 0 else lado
                img, ancla, sombra_img, desp = b.img, b.ancla, b.sombra, b.desp
            else:
                f = self.tam(j / self.PASOS)[0] / centro.diametro
                escalar = lambda s: pygame.transform.smoothscale(
                    s, (max(1, round(s.get_width() * f)), max(1, round(s.get_height() * f))))
                img, sombra_img = escalar(centro.img), escalar(centro.sombra)
                ancla = (round(centro.ancla[0] * f), round(centro.ancla[1] * f))
                desp = (round(centro.desp[0] * f), round(centro.desp[1] * f))
            # Rectángulos de sombra e imagen respecto al centro de la burbuja.
            r_sombra = pygame.Rect(desp, sombra_img.get_size())
            r_img = pygame.Rect((-ancla[0], -ancla[1]), img.get_size())
            caja = r_sombra.union(r_img)
            opaca = pygame.Surface(caja.size).convert()
            opaca.fill(fondo)
            opaca.blit(sombra_img, (r_sombra.x - caja.x, r_sombra.y - caja.y))
            opaca.blit(img, (r_img.x - caja.x, r_img.y - caja.y))
            self.pasos.append((opaca, (-caja.x, -caja.y)))

    def tam(self, t):
        d = round(self.diametros[0] + (self.diametros[1] - self.diametros[0]) * t)
        return d, d

    def dibujar(self, sup, centro, t, alpha, estatico):
        img, ancla = self.pasos[round(t * self.PASOS)]
        if alpha < 255:
            img.set_alpha(alpha)
        sup.blit(img, (centro[0] - ancla[0], centro[1] - ancla[1]))
        if alpha < 255:
            img.set_alpha(None)


def dibujar_carrusel(sup, e, elementos, acciones, posicion, zona):
    """Carrusel circular: el elemento 'posicion' en el centro y los vecinos a los lados.

    Registra zonas (solo en reposo): el del centro -> su acción; los laterales -> girar.
    """
    n = len(elementos)
    cx, cy = e.p(CENTRO_CARRUSEL)
    separacion = SEPARACION * e.k
    estatico = abs(posicion - round(posicion)) < 2e-3
    visibles = []
    for i in range(n):
        d = (i - posicion + n / 2) % n - n / 2          # distancia circular al centro
        if abs(d) < 1.5:
            visibles.append((abs(d), i, d))
    for _, i, d in sorted(visibles, reverse=True):     # los lejanos primero
        x = round(cx + d * separacion)
        alpha = 255 if abs(d) <= 1 else round(255 * (1.5 - abs(d)) / .5)
        t = min(1, abs(d))
        elementos[i].dibujar(sup, (x, cy), t, alpha, estatico)
        if estatico and abs(d) <= 1:
            w, h = elementos[i].tam(t)
            rect = pygame.Rect(0, 0, w, h)
            rect.center = (x, cy)
            if abs(d) < .5:
                zona(rect, acciones[i])
            else:
                zona(rect, "carrusel_izq" if d < 0 else "carrusel_der")


def caja_logo(rect, logo, fuente, grosor):
    """Rectángulo 'logo' del diseño (borde #212121, radio 8) con el logo de TerraHub.

    Devuelve la caja ya pintada, para no reescalar el logo en cada fotograma.
    """
    caja = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(caja, (255, 255, 255), caja.get_rect(), border_radius=max(2, rect.height // 10))
    pygame.draw.rect(caja, TEXTO, caja.get_rect(), grosor, border_radius=max(2, rect.height // 10))
    texto = fuente.render("TerraHub", True, TEXTO)
    ancho = texto.get_width()
    if logo:
        alto = rect.height - 12
        logo = pygame.transform.smoothscale(
            logo, (max(1, round(logo.get_width() * alto / logo.get_height())), alto))
        ancho += logo.get_width() + 10
    x = rect.width // 2 - ancho // 2
    if logo:
        caja.blit(logo, (x, 6))
        x += logo.get_width() + 10
    caja.blit(texto, texto.get_rect(midleft=(x, rect.height // 2)))
    return caja


def aviso(sup, texto, fuente, y):
    """Mensaje breve sobre la parte baja de la pantalla."""
    t = fuente.render(texto, True, (255, 255, 255))
    caja = t.get_rect(center=(sup.get_width() // 2, y)).inflate(32, 18)
    pygame.draw.rect(sup, (43, 52, 66), caja, border_radius=caja.height // 2)
    sup.blit(t, t.get_rect(center=caja.center))


class BarraSuperior:
    """Barra de estado de arriba: red a la izquierda; hora y círculo a la derecha.

    Banda gris clara con brillo arriba, sombra debajo y un corte blanco en diagonal
    (referencia del equipo). Lo fijo se pinta una vez en 'fondo' (opaco); cada
    fotograma solo se copian la hora (cacheada por minuto) y el círculo.
    Tocar la red abre 'Redes disponibles'; tocar el círculo abre los ajustes.
    """
    def __init__(self, e, ancho, color=(255, 255, 255)):
        """'color': el de la pantalla justo debajo (la sombra se funde con él)."""
        self.e = e
        k = e.k
        alto = e.n(BARRA_ALTO)
        sombra_alto = max(2, e.n(7))
        self.fondo = pygame.Surface((ancho, alto + sombra_alto)).convert()
        self.fondo.fill(color)
        arriba, abajo = e.n(3), alto
        for y in range(arriba, abajo):                  # banda: #dedede -> #cacaca
            t = (y - arriba) / max(1, abajo - arriba - 1)
            g = round(222 - 20 * t)
            pygame.draw.line(self.fondo, (g, g, g), (0, y), (ancho, y))
        pygame.draw.line(self.fondo, (244, 244, 244), (0, arriba), (ancho, arriba))
        pygame.draw.line(self.fondo, (246, 246, 246), (0, arriba + 1), (ancho, arriba + 1))
        pygame.draw.line(self.fondo, (178, 182, 188), (0, abajo - 1), (ancho, abajo - 1))
        for i in range(sombra_alto):                    # sombra suave bajo la barra
            t = (i + 1) / sombra_alto
            tono = tuple(round(c * (.84 + .16 * t)) for c in color)
            pygame.draw.line(self.fondo, tono, (0, abajo + i), (ancho, abajo + i))
        # Corte blanco en diagonal ('/').
        x = e.dx + BARRA_CORTE * k
        inclinacion, grueso = (abajo - arriba) * .55, max(3, 13 * k)
        pygame.draw.polygon(self.fondo, (255, 255, 255), [
            (x + inclinacion, arriba), (x + inclinacion + grueso, arriba),
            (x + grueso, abajo - 1), (x, abajo - 1)])
        self.centro_y = (arriba + abajo) // 2
        # Red: glifo wifi del diseño, oscuro sobre la barra clara.
        wifi = cargar_svg("wifi.svg", k * .8, color="#2B3442")
        self.zona_red = pygame.Rect(0, 0, round(e.dx + e.n(130)), alto + sombra_alto)
        self.fondo.blit(wifi, wifi.get_rect(midleft=(round(e.dx + e.n(26)), self.centro_y)))
        self.fuente = pygame.font.Font(None, e.n(38))
        self._hora = ("", None)
        self._circulo()

    def _circulo(self):
        """Burbuja de cristal de la esquina, con base azulada como los controles."""
        e = self.e
        (cx, cy), diam = CIRCULO
        d = e.n(diam)
        base = pygame.Surface((d, d), pygame.SRCALPHA)
        for y in range(d):
            t = y / max(1, d - 1)
            color = tuple(round(a + (b - a) * t) for a, b in zip((250, 252, 255), (190, 204, 221)))
            pygame.draw.line(base, color, (0, y), (d, y))
        forma = pygame.Surface((d, d), pygame.SRCALPHA)
        pygame.draw.circle(forma, (255, 255, 255, 255), (d // 2, d // 2), d // 2)
        base.blit(forma, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        pygame.draw.circle(base, (175, 192, 210), (d // 2, d // 2), d // 2, max(1, e.n(2)))
        f = d / (2 * 62.75)                              # círculo de burbuja-default.svg
        cristal = cargar_svg("burbuja-default.svg", f)
        s, desp = sombra(d, d, d // 2, e.n(5), max(2, 8 * e.k), (13, 31, 64, 70))
        r_sombra = pygame.Rect(desp, s.get_size())
        r_cristal = pygame.Rect((-round(82 * f), -round(74 * f)), cristal.get_size())
        caja = r_sombra.union(r_cristal).union(pygame.Rect(-d // 2, -d // 2, d, d))
        img = pygame.Surface(caja.size, pygame.SRCALPHA)
        c = (-caja.x, -caja.y)
        img.blit(s, (c[0] + r_sombra.x, c[1] + r_sombra.y))
        img.blit(base, (c[0] - d // 2, c[1] - d // 2))
        img.blit(cristal, (c[0] + r_cristal.x, c[1] + r_cristal.y))
        self.circulo = img.convert_alpha()
        # Pegado al borde de arriba (no al marco centrado del diseño).
        self.centro = (round(e.dx + cx * e.k), round(cy * e.k))
        self.radio = d // 2
        self.ancla = c
        # Zona táctil: más ancha que el círculo, pero sin bajar de su borde (debajo
        # empiezan las filas de los ajustes).
        r = self.radio + e.n(30)
        self.zona_circulo = pygame.Rect(self.centro[0] - r, 0, 2 * r, self.centro[1] + self.radio)

    def dibujar(self, sup, zona, hora, fijo=True):
        """'fijo': el fondo de la barra ya está en la superficie (p. ej. en el fondo de Inicio)."""
        e = self.e
        if not fijo:
            sup.blit(self.fondo, (0, 0))
        if self._hora[0] != hora:
            self._hora = (hora, self.fuente.render(hora, True, TEXTO))
        texto = self._hora[1]
        sup.blit(texto, texto.get_rect(midright=(round(e.dx + RELOJ_DER * e.k), self.centro_y + 1)))
        sup.blit(self.circulo, (self.centro[0] - self.ancla[0], self.centro[1] - self.ancla[1]))
        self.zonas(zona)

    def zonas(self, zona):
        zona(self.zona_red, "redes")
        zona(self.zona_circulo, "panel")

    def expansion(self, sup, t, captura):
        """El círculo crece desde la esquina mostrando dentro 'captura' (la pantalla de
        ajustes tal cual se verá), hasta cubrirlo todo (t de 0 a 1).

        Al llegar a 1 la pantalla ya es exactamente la de ajustes: el cambio de estado no
        se nota. El círculo se recorta fila a fila con copias opacas (barato en la Pi).
        """
        t = t * t * t * (t * (6 * t - 15) + 10)          # 'smootherstep': sin tirones al empezar ni al acabar
        w, h = sup.get_size()
        cx, cy = self.centro
        lejos = math.hypot(max(cx, w - cx), max(cy, h - cy)) + 2
        r = self.radio + (lejos - self.radio) * t
        if r >= lejos - 1:
            sup.blit(captura, (0, 0))
            return
        for y in range(max(0, math.floor(cy - r)), min(h, math.ceil(cy + r) + 1)):
            dy = y + .5 - cy
            if abs(dy) >= r:
                continue
            dx = math.sqrt(r * r - dy * dy)
            x0, x1 = max(0, round(cx - dx)), min(w, round(cx + dx))
            if x1 > x0:
                sup.blit(captura, (x0, y), (x0, y, x1 - x0, 1))
        # Borde fino del círculo, que se desvanece al final.
        if t < .9:
            pygame.draw.circle(sup, (175, 192, 210), (cx, cy), round(r), max(1, self.e.n(2)))


class PantallaInicio:
    """Recursos ya escalados a la pantalla; se crean una vez por Vista."""
    def __init__(self, tam):
        self.esc = e = Escala(tam)
        self.elementos = [ElementoBurbuja(svg, e) for _, _, svg in SECCIONES]
        self.acciones = [seccion for _, seccion, _ in SECCIONES]
        self.izq = Control("flecha-izquierda.svg", e.k)
        self.der = Control("flecha-derecha.svg", e.k)
        self.barra = BarraSuperior(e, tam[0])
        self.fuente = pygame.font.Font(None, e.n(44))
        self.fuente_aviso = pygame.font.Font(None, e.n(34))
        try:
            logo = pygame.image.load(str(INTERFAZ.parent / "imagenes" / "logo.png")).convert_alpha()
        except (OSError, pygame.error):
            logo = None
        # Lo que no se mueve (fondo, barra y logo) se pinta una sola vez.
        self.fondo = pygame.Surface(tam).convert()
        self.fondo.fill((255, 255, 255))
        self.fondo.blit(self.barra.fondo, (0, 0))
        self.fondo.blit(caja_logo(e.r(LOGO), logo, self.fuente, max(1, e.n(2))), e.r(LOGO))

    def dibujar(self, sup, posicion, zona, aviso_texto="", hora="", expansion=0.0, captura=None):
        """Pinta la pantalla. 'posicion' es el índice (decimal) del carrusel en el centro.

        'zona(rect, accion)' registra las zonas táctiles. Con 'expansion' > 0 el círculo
        de la barra está creciendo (o encogiendo) con los ajustes ('captura') dentro y
        nada responde debajo.
        """
        e = self.esc
        if expansion > 0:
            zona = lambda rect, accion: None
        sup.blit(self.fondo, (0, 0))
        dibujar_carrusel(sup, e, self.elementos, self.acciones, posicion, zona)
        # Controles laterales.
        for control, centro, accion in ((self.izq, FLECHA_IZQ, "carrusel_izq"),
                                        (self.der, FLECHA_DER, "carrusel_der")):
            control.dibujar(sup, e.p(centro))
            rect = pygame.Rect(0, 0, e.n(100), e.n(100))
            rect.center = e.p(centro)
            zona(rect, accion)
        self.barra.dibujar(sup, zona, hora)
        if expansion > 0 and captura is not None:
            self.barra.expansion(sup, expansion, captura)
        if aviso_texto:
            aviso(sup, aviso_texto, self.fuente_aviso, sup.get_height() - e.n(70))


def _mezcla(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def _aclarar(c, cantidad):
    return tuple(min(255, round(x + (255 - x) * cantidad)) for x in c)


def _oscurecer(c, f):
    return tuple(round(x * f) for x in c)


class PantallaAjustes:
    """Ajustes en lista, con el estilo de los menús de la PS Vita (referencia del equipo).

    Fondo morado con luces suaves, filas en bandas de color con icono y texto blancos, y
    la fila tocada resaltada en cian. 'Opciones de energía' (arriba del todo) despliega
    Suspender, Reiniciar y Apagar. Se abre y se cierra con el círculo de la barra.

    Cada fila (normal y resaltada) se monta una vez como imagen opaca: al deslizar o
    desplegar solo se copian. Desplazamiento en px del diseño, como 'Redes'.
    """
    ARRIBA, ABAJO = (92, 16, 146), (206, 66, 206)          # degradado del fondo
    FILA_ARRIBA, FILA_ABAJO = (112, 24, 170), (196, 58, 196)
    CIAN, VIOLETA = (70, 228, 255), (108, 88, 252)

    def __init__(self, tam):
        self.esc = e = Escala(tam)
        self.tam = w, h = tam
        self.barra = BarraSuperior(e, w, self.ARRIBA)
        self.arriba = self.barra.fondo.get_height()        # la lista empieza bajo la barra
        self.fila = e.n(FILA_ALTO)
        self.fondo = pygame.Surface(tam).convert()
        for y in range(h):
            pygame.draw.line(self.fondo, _mezcla(self.ARRIBA, self.ABAJO, y / max(1, h - 1)), (0, y), (w, y))
        luz = pygame.Surface(tam, pygame.SRCALPHA)       # luces difuminadas, como en la Vita
        for cx, cy, rx, ry, a in ((.78, .42, .55, .10, 46), (.30, .78, .65, .09, 38), (.62, .97, .80, .07, 60)):
            pygame.draw.ellipse(luz, (255, 255, 255, a), (round((cx - rx) * w), round((cy - ry) * h),
                                                           round(2 * rx * w), round(2 * ry * h)))
        self.fondo.blit(_difuminar(luz, e.n(40)), (0, 0))
        self.fondo.blit(self.barra.fondo, (0, 0))
        fuente = pygame.font.Font(None, e.n(46))
        orden = AJUSTES_FILAS[:1] + ENERGIA_OPCIONES + AJUSTES_FILAS[1:]
        subopciones = {a for a, _, _ in ENERGIA_OPCIONES}
        self.filas = {}
        for i, (accion, etiqueta, svg) in enumerate(orden):
            base = _mezcla(self.FILA_ARRIBA, self.FILA_ABAJO, i / (len(orden) - 1))
            sub = accion in subopciones
            if sub:
                base = _oscurecer(base, .86)
            self.filas[accion] = tuple(self._fila(etiqueta, svg, base, sub, resaltada, fuente)
                                       for resaltada in (False, True))
        self.fuente_valor = pygame.font.Font(None, e.n(36))
        self.fuente_aviso = pygame.font.Font(None, e.n(34))
        self._textos = {}

    def _fila(self, etiqueta, svg, base, sub, resaltada, fuente):
        e, (w, _), alto = self.esc, self.tam, self.fila
        s = pygame.Surface((w, alto)).convert()
        if resaltada:
            # Banda cian brillante en los bordes y violeta en el centro.
            for y in range(alto):
                d = min(y, alto - 1 - y) / (alto / 2)
                t = min(1, d * 2.2)
                pygame.draw.line(s, _mezcla(self.CIAN, self.VIOLETA, t * t * (3 - 2 * t)), (0, y), (w, y))
            for y in (0, 1, alto - 2, alto - 1):
                pygame.draw.line(s, (205, 250, 255), (0, y), (w, y))
        else:
            claro = _aclarar(base, .14)
            for y in range(alto):
                pygame.draw.line(s, _mezcla(claro, base, y / max(1, alto - 1)), (0, y), (w, y))
            brillo = pygame.Surface((w, alto), pygame.SRCALPHA)   # reflejo en diagonal
            pygame.draw.polygon(brillo, (255, 255, 255, 16), [
                (w * .52, 0), (w, 0), (w, alto), (w * .52 - alto * .8, alto)])
            s.blit(brillo, (0, 0))
            pygame.draw.line(s, _aclarar(base, .38), (0, 0), (w, 0))
            pygame.draw.line(s, _oscurecer(base, .72), (0, alto - 1), (w, alto - 1))
        sangria = e.n(56) if sub else 0
        texto_svg = (INTERFAZ / svg).read_text(encoding="utf-8")
        ancho_svg = float(re.search(r'width="([\d.]+)"', texto_svg).group(1))
        lado = e.n(34 if sub else 42)
        if '"#222222"' in texto_svg:                     # iconos de energía: oscuros en el diseño
            icono = cargar_svg(svg, lado / ancho_svg, "white", "#222222")
        else:
            icono = cargar_svg(svg, lado / ancho_svg)
        s.blit(icono, icono.get_rect(center=(e.n(84) + sangria, alto // 2)))
        sombra_txt = fuente.render(etiqueta, True, _oscurecer(base if not resaltada else self.VIOLETA, .5))
        texto = fuente.render(etiqueta, True, (255, 255, 255))
        x = e.n(140) + sangria
        s.blit(sombra_txt, sombra_txt.get_rect(midleft=(x + 1, alto // 2 + 2)))
        s.blit(texto, texto.get_rect(midleft=(x, alto // 2)))
        return s

    def maximo(self, energia):
        """Desplazamiento máximo (px del diseño) con la energía desplegada 'energia' (0..1)."""
        contenido = (len(AJUSTES_FILAS) + len(ENERGIA_OPCIONES) * energia) * FILA_ALTO
        return max(0.0, contenido - (self.tam[1] - self.arriba) / self.esc.k)

    def _texto(self, valor):
        if valor not in self._textos:
            if len(self._textos) > 20:
                self._textos.clear()
            self._textos[valor] = self.fuente_valor.render(valor, True, (240, 225, 255))
        return self._textos[valor]

    def _pintar(self, sup, accion, y, area, zona, resaltado, valores):
        if y >= area.bottom or y + self.fila <= area.top:
            return
        sup.blit(self.filas[accion][resaltado == accion], (0, y))
        valor = valores.get(accion)
        if valor:
            t = self._texto(valor)
            sup.blit(t, t.get_rect(midright=(self.tam[0] - self.esc.n(56), y + self.fila // 2)))
        if zona:
            rect = area.clip(pygame.Rect(0, y, self.tam[0], self.fila))
            if rect.height > 0:
                zona(rect, accion)

    def _flecha(self, sup, y, energia):
        """Flecha de la fila de energía: '>' plegada, 'v' desplegada."""
        e = self.esc
        cx, cy, s = self.tam[0] - e.n(64), y + self.fila // 2, e.n(13)
        a = math.pi / 2 * energia
        puntos = []
        for px, py in ((-s / 2, -s), (s / 2, 0), (-s / 2, s)):
            puntos.append((cx + px * math.cos(a) - py * math.sin(a), cy + px * math.sin(a) + py * math.cos(a)))
        pygame.draw.lines(sup, (255, 255, 255), False, puntos, max(2, e.n(5)))

    def dibujar(self, sup, desplazamiento, energia, zona, aviso_texto="", hora="",
                valores=None, resaltado=None, tocable=True):
        """'energia': cuánto está desplegada la fila de energía (0..1, animado)."""
        e, (w, h) = self.esc, self.tam
        valores = valores or {}
        sup.blit(self.fondo, (0, 0))
        self.barra.zonas(zona)                           # el círculo y la red, antes que las filas
        area = pygame.Rect(0, self.arriba, w, h - self.arriba)
        zona_filas = zona if tocable else None
        sup.set_clip(area)
        y = self.arriba - round(desplazamiento * e.k)
        for accion, _, _ in AJUSTES_FILAS:
            self._pintar(sup, accion, y, area, zona_filas, resaltado, valores)
            if accion == "energia":
                self._flecha(sup, y, energia)
            y += self.fila
            if accion == "energia" and energia > 0:
                # Las opciones salen de debajo de la fila; las demás bajan a la vez.
                alto = round(len(ENERGIA_OPCIONES) * self.fila * energia)
                hueco = area.clip(pygame.Rect(0, y, w, alto))
                sup.set_clip(hueco)
                for i, (opcion, _, _) in enumerate(ENERGIA_OPCIONES):
                    self._pintar(sup, opcion, y + i * self.fila - (len(ENERGIA_OPCIONES) * self.fila - alto),
                                 hueco, zona_filas if energia > .999 else None, resaltado, valores)
                sup.set_clip(area)
                y += alto
        sup.set_clip(None)
        self.barra.dibujar(sup, lambda rect, accion: None, hora)
        if aviso_texto:
            aviso(sup, aviso_texto, self.fuente_aviso, sup.get_height() - e.n(70))
