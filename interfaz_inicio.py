"""Barra superior, Inicio y Configuración según la entrega de diseño v2 (1280x720).

Barra superior: negra con una línea magenta debajo; Wi-Fi a la izquierda (abre las
redes), hora y un círculo magenta a la derecha que se expande hasta Configuración.
Inicio: logotipo en caja, carrusel de burbujas magenta con el nombre de cada sección,
flechas de vidrio y puntos de página. Configuración: lista en tonos de magenta; la
fila pulsada pasa a violeta.
"""
import io
import math
import re
from pathlib import Path
import pygame
import estilo
from estilo import (BLANCO, NEGRO, MAGENTA, VIOLETA, VIOLETA_CLARO, AZUL_OSCURO, mezcla,
                    sombra, difuminar as _difuminar)

INTERFAZ = Path(__file__).resolve().parent / "recursos" / "interfaz"
DISENO = (1280, 720)                  # tamaño de los frames del diseño
TEXTO = estilo.TEXTO

# Carrusel de Inicio: (etiqueta, sección de CARPETAS, svg del glifo).
SECCIONES = [
    ("Música", "Audio", "burbuja-audio.svg"),
    ("Vídeos", "Vídeos", "burbuja-videos.svg"),
    ("Libros", "Libros", "burbuja-libros.svg"),
    ("Imágenes", "Imágenes", "burbuja-imagenes.svg"),
    ("Juegos", "Juegos", "burbuja-juegos.svg"),
]
# Configuración (se abre con el círculo de la barra): (acción, etiqueta, icono svg).
# La primera fila despliega las opciones de energía.
AJUSTES_FILAS = [
    ("energia", "Opciones de energía", "energia-apagar.svg"),
    ("ajuste_fecha", "Fecha y hora", "icono-reloj.svg"),
    ("ajuste_redes", "Redes", "wifi.svg"),
    ("ajuste_ip", "Dirección IP", "icono-ip.svg"),
    ("ajuste_fondo", "Fondo de pantalla", "icono-fondo.svg"),
    ("salir_terminal", "Salir a la terminal", "icono-salir.svg"),
]
ENERGIA_OPCIONES = [
    ("suspender", "Suspender", "energia-suspender.svg"),
    ("reiniciar", "Reiniciar", "energia-reiniciar.svg"),
    ("apagar", "Apagar", "energia-apagar.svg"),
]
CON_FLECHA = {"ajuste_redes", "ajuste_fondo"}     # filas que abren otra pantalla
FILA_ALTO = 64                         # px del diseño

# Inicio (coordenadas del diseño).
CENTRO_CARRUSEL = (640, 400)
SEPARACION = 390
DIAMETRO_CENTRO, DIAMETRO_LADO = 270, 200
FLECHA_IZQ, FLECHA_DER = (70, 400), (1210, 400)
LADO_FLECHA = 60
LOGO = pygame.Rect(443, 77, 394, 83)   # logotipo en caja
PUNTOS_Y = 673

# Barra superior.
BARRA_ALTO = 45                        # banda negra; debajo, 3 px de línea magenta
LINEA = 3
CIRCULO = ((1228, 22), 70)             # (centro, diámetro)
RELOJ_DER = 1175


class Escala:
    """Convierte coordenadas del frame 1280x720 a la pantalla, sin deformar.

    Centrado en horizontal y pegado arriba: la barra superior va siempre en el borde y
    lo de debajo empieza justo después (en 800x480 sobran 30 px abajo, no en medio).
    """
    def __init__(self, tam):
        w, h = tam
        self.k = min(w / DISENO[0], h / DISENO[1])
        self.dx = (w - DISENO[0] * self.k) / 2
        self.dy = 0.0

    def p(self, punto):
        return (round(self.dx + punto[0] * self.k), round(self.dy + punto[1] * self.k))

    def n(self, valor):
        return max(1, round(valor * self.k))

    def r(self, rect):
        x, y = self.p(rect.topleft)
        return pygame.Rect(x, y, self.n(rect.width), self.n(rect.height))


def cargar_svg(nombre, factor, color=None, original="white"):
    """SVG del diseño a 'factor' veces su tamaño (cambiando 'original' por 'color')."""
    texto = (INTERFAZ / nombre).read_text(encoding="utf-8")
    if color:
        texto = texto.replace(f'"{original}"', f'"{color}"')
    w = float(re.search(r'width="([\d.]+)"', texto).group(1))
    h = float(re.search(r'height="([\d.]+)"', texto).group(1))
    texto = re.sub(r'width="[\d.]+"', f'width="{w * factor:.2f}"', texto, count=1)
    texto = re.sub(r'height="[\d.]+"', f'height="{h * factor:.2f}"', texto, count=1)
    return pygame.image.load(io.BytesIO(texto.encode("utf-8")), "a.svg").convert_alpha()


def cargar_png(nombre, factor):
    """Imagen del diseño escalada a 'factor' veces su tamaño."""
    img = pygame.image.load(str(INTERFAZ / nombre)).convert_alpha()
    tam = (max(1, round(img.get_width() * factor)), max(1, round(img.get_height() * factor)))
    return pygame.transform.smoothscale(img, tam)


def aviso(sup, texto, fuente, y):
    estilo.aviso(sup, texto, fuente, y)


def _mezcla(a, b, t):
    return mezcla(a, b, t)


def _aclarar(c, cantidad):
    return tuple(min(255, round(x + (255 - x) * cantidad)) for x in c)


def _oscurecer(c, f):
    return tuple(round(x * f) for x in c)


def fuente_aviso(e):
    return estilo.fuente(e.n(19), "Medium")


class BotonTornar:
    """Control Tornar: píldora de vidrio con la flecha de volver; violeta al pulsarla."""
    def __init__(self, e, rect):
        self.rect = e.r(rect)
        self.boton = estilo.Boton(self.rect.width, self.rect.height, glifo="volver.svg",
                                  lado_glifo=self.rect.height * .72)

    def dibujar(self, sup, pulsado=False):
        self.boton.dibujar(sup, self.rect.center, pulsado)

    def toca(self, pos):
        return self.rect.inflate(self.rect.height * .5, self.rect.height * .6).collidepoint(pos)


# Posiciones del Tornar (px del diseño): bajo la barra en las pantallas con cabecera
# blanca; en la banda de las listas magenta; arriba del todo a pantalla completa.
TORNAR_CABECERA = pygame.Rect(25, 67, 111, 49)
TORNAR_BANDA = pygame.Rect(28, 60, 84, 41)
TORNAR_COMPLETO = pygame.Rect(25, 25, 111, 49)


TITULO_CENTRO_Y = 88                   # títulos en Zrnic (Games, Music...): centro y alto
TITULO_ALTO = 47
SUBRAYADO_Y = 119


def cabecera_blanca(tam, e, titulo=None):
    """Fondo de las pantallas de contenido (Games, Music, Vídeos...): blanco, barra
    superior y título en Zrnic con la línea magenta debajo. Devuelve (fondo, barra)."""
    barra = BarraSuperior(e, tam[0])
    fondo = pygame.Surface(tam).convert()
    fondo.fill(BLANCO)
    fondo.blit(barra.fondo, (0, 0))
    if titulo:
        img = estilo.imagen(titulo, alto=e.n(TITULO_ALTO))
        fondo.blit(img, img.get_rect(center=e.p((640, TITULO_CENTRO_Y))))
        estilo.subrayado(fondo, e.p((640, 0))[0], e.p((0, SUBRAYADO_Y))[1], e.n(64), e.n(3))
    return fondo, barra


def flechas_pagina(e, izq, der):
    """Flechas de vidrio para cambiar de página (Games, Music)."""
    lado = e.n(LADO_FLECHA)
    return [(estilo.Boton(lado, lado, glifo="flecha-izquierda.svg", lado_glifo=lado * .5), e.p(izq)),
            (estilo.Boton(lado, lado, glifo="flecha-derecha.svg", lado_glifo=lado * .5), e.p(der))]


class BarraSuperior:
    """Barra negra con la línea magenta: red a la izquierda, hora y círculo a la derecha.

    Lo fijo se pinta una vez en 'fondo'; cada fotograma solo se copian la hora (cacheada
    por minuto) y el círculo. Tocar la red abre las redes; el círculo, Configuración.
    """
    def __init__(self, e, ancho, color=None):
        self.e = e
        alto = e.n(BARRA_ALTO)
        linea = max(2, e.n(LINEA))
        self.fondo = pygame.Surface((ancho, alto + linea)).convert()
        self.fondo.fill(NEGRO)
        self.fondo.fill(MAGENTA, (0, alto, ancho, linea))
        # Un poco de sombra magenta oscura bajo el negro (como en el diseño).
        pygame.draw.line(self.fondo, (103, 33, 103), (0, alto - 1), (ancho, alto - 1))
        self.centro_y = alto // 2
        wifi = estilo.icono("wifi.svg", e.n(27), BLANCO)
        self.fondo.blit(wifi, wifi.get_rect(center=(round(e.dx + e.n(33)), self.centro_y)))
        self.zona_red = pygame.Rect(0, 0, round(e.dx + e.n(120)), alto + linea + e.n(10))
        self.fuente = estilo.fuente(e.n(23), "Medium")
        self._hora = ("", None)
        (cx, cy), diam = CIRCULO
        self.circulo, self.ancla = estilo.burbuja(e.n(diam), aro=max(1, e.n(2.5)))
        self.centro = (round(e.dx + cx * e.k), round(cy * e.k))
        self.radio = e.n(diam) // 2
        r = self.radio + e.n(30)
        self.zona_circulo = pygame.Rect(self.centro[0] - r, 0, 2 * r, self.centro[1] + self.radio + e.n(6))

    def dibujar(self, sup, zona, hora, fijo=True):
        """'fijo': el fondo de la barra ya está en la superficie."""
        e = self.e
        if not fijo:
            sup.blit(self.fondo, (0, 0))
        if self._hora[0] != hora:
            self._hora = (hora, self.fuente.render(hora, True, BLANCO))
        texto = self._hora[1]
        sup.blit(texto, texto.get_rect(midright=(round(e.dx + RELOJ_DER * e.k), self.centro_y + 1)))
        sup.blit(self.circulo, (self.centro[0] - self.ancla[0], self.centro[1] - self.ancla[1]))
        self.zonas(zona)

    def zonas(self, zona):
        zona(self.zona_red, "redes")
        zona(self.zona_circulo, "panel")

    def expansion(self, sup, t, captura):
        """El círculo crece desde la esquina mostrando dentro 'captura' (Configuración tal
        cual se verá) hasta cubrirlo todo (t de 0 a 1). Se recorta fila a fila con copias
        opacas (barato en la Pi)."""
        t = t * t * t * (t * (6 * t - 15) + 10)          # 'smootherstep'
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
        if t < .9:
            pygame.draw.circle(sup, BLANCO, (cx, cy), round(r), max(1, self.e.n(2.5)))


class ElementoBurbuja:
    """Burbuja del carrusel con su nombre debajo.

    Cada tamaño entre centro y lado se monta una vez, con su sombra, sobre el fondo
    blanco y sin transparencia: al moverse, cada burbuja es una única copia opaca. Con
    fondo de pantalla se usan los mismos pasos con transparencia ('transparente').
    """
    PASOS = 12

    def __init__(self, svg, etiqueta, e, fondo=BLANCO):
        self.e = e
        centro_img, centro_c = estilo.burbuja(e.n(DIAMETRO_CENTRO), svg)
        self.diametros = (e.n(DIAMETRO_CENTRO), e.n(DIAMETRO_LADO))
        self.transparente = False
        self.pasos, self.pasos_alpha = [], []
        for j in range(self.PASOS + 1):
            f = self.tam(j / self.PASOS)[0] / self.diametros[0]
            if j == 0:
                img, c = centro_img, centro_c
            elif j == self.PASOS:
                img, c = estilo.burbuja(self.diametros[1], svg)
            else:
                img = pygame.transform.smoothscale(
                    centro_img, (max(1, round(centro_img.get_width() * f)), max(1, round(centro_img.get_height() * f))))
                c = (round(centro_c[0] * f), round(centro_c[1] * f))
            opaca = pygame.Surface(img.get_size()).convert()
            opaca.fill(fondo)
            opaca.blit(img, (0, 0))
            self.pasos.append((opaca, c))
            self.pasos_alpha.append((img, c))
        self.pulsada = estilo.burbuja(self.diametros[0], svg, pulsada=True, fondo=fondo)
        self.pulsada_alpha = estilo.burbuja(self.diametros[0], svg, pulsada=True)
        self.nombre_centro = estilo.fuente(e.n(26), "Bold").render(etiqueta, True, TEXTO)
        self.nombre_lado = estilo.fuente(e.n(21), "SemiBold").render(etiqueta, True, (136, 136, 136))

    def tam(self, t):
        d = round(self.diametros[0] + (self.diametros[1] - self.diametros[0]) * t)
        return d, d

    def dibujar(self, sup, centro, t, alpha, pulsada=False):
        if pulsada:
            img, ancla = self.pulsada_alpha if self.transparente else self.pulsada
        else:
            img, ancla = (self.pasos_alpha if self.transparente else self.pasos)[round(t * self.PASOS)]
        if alpha < 255:
            img.set_alpha(alpha)
        sup.blit(img, (centro[0] - ancla[0], centro[1] - ancla[1]))
        if alpha < 255:
            img.set_alpha(None)
        # Nombre debajo: grande y negro en el centro, pequeño y gris a los lados.
        nombre = self.nombre_centro if t < .5 else self.nombre_lado
        y = centro[1] + self.tam(t)[0] // 2 + self.e.n(32 if t < .5 else 30)
        if alpha < 255:
            nombre = nombre.copy()
            nombre.set_alpha(alpha)
        sup.blit(nombre, nombre.get_rect(center=(centro[0], y)))


def dibujar_carrusel(sup, e, elementos, acciones, posicion, zona, pulsada=None):
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
        elementos[i].dibujar(sup, (x, cy), t, alpha, pulsada=estatico and abs(d) < .5 and pulsada == acciones[i])
        if estatico and abs(d) <= 1:
            w, h = elementos[i].tam(t)
            rect = pygame.Rect(0, 0, w, h)
            rect.center = (x, cy)
            zona(rect, acciones[i] if abs(d) < .5 else ("carrusel_izq" if d < 0 else "carrusel_der"))


class PantallaInicio:
    """Recursos ya escalados a la pantalla; se crean una vez por Vista."""
    def __init__(self, tam):
        self.esc = e = Escala(tam)
        self.elementos = [ElementoBurbuja(svg, nombre, e) for nombre, _, svg in SECCIONES]
        self.acciones = [seccion for _, seccion, _ in SECCIONES]
        lado = e.n(LADO_FLECHA)
        self.izq = estilo.Boton(lado, lado, glifo="flecha-izquierda.svg", lado_glifo=lado * .5)
        self.der = estilo.Boton(lado, lado, glifo="flecha-derecha.svg", lado_glifo=lado * .5)
        self.barra = BarraSuperior(e, tam[0])
        self.fuente_aviso = fuente_aviso(e)
        r = e.r(LOGO)
        self.logo = estilo.imagen("logo-caja.png", alto=r.height)
        self.logo_caja = pygame.Surface(self.logo.get_size(), pygame.SRCALPHA)
        pygame.draw.rect(self.logo_caja, BLANCO, self.logo_caja.get_rect(), border_radius=e.n(12))
        self.logo_caja.blit(self.logo, (0, 0))
        self.logo_rect = self.logo.get_rect(center=r.center)
        # Lo que no se mueve (fondo, barra y logo) se pinta una sola vez.
        self.fondo = pygame.Surface(tam).convert()
        self.fondo.fill(BLANCO)
        self.fondo.blit(self.barra.fondo, (0, 0))
        self.fondo.blit(self.logo, self.logo_rect)

    def _puntos(self, sup, actual):
        """Puntos de página: el de la sección del centro es una píldora magenta."""
        e = self.esc
        n = len(self.elementos)
        anchos = [e.n(26) if i == actual else e.n(8) for i in range(n)]
        hueco = e.n(12)
        x = e.p((640, 0))[0] - (sum(anchos) + hueco * (n - 1)) // 2
        y = e.p((0, PUNTOS_Y))[1]
        alto = e.n(8)
        for i, w in enumerate(anchos):
            pygame.draw.rect(sup, MAGENTA if i == actual else estilo.VIDRIO,
                             (x, y - alto // 2, w, alto), border_radius=alto // 2)
            x += w + hueco

    def dibujar(self, sup, posicion, zona, aviso_texto="", hora="", expansion=0.0, captura=None,
                fondo=None, pulsado=None):
        """'posicion' es el índice (decimal) del carrusel en el centro; 'pulsado', la
        acción que se está tocando (la burbuja o la flecha se ven pulsadas)."""
        e = self.esc
        if expansion > 0:
            zona = lambda rect, accion: None
        if fondo is not None:
            sup.blit(fondo, (0, 0))
            sup.blit(self.barra.fondo, (0, 0))
            sup.blit(self.logo_caja, self.logo_rect)
        else:
            sup.blit(self.fondo, (0, 0))
        for elemento in self.elementos:
            elemento.transparente = fondo is not None
        dibujar_carrusel(sup, e, self.elementos, self.acciones, posicion, zona, pulsado)
        for control, centro, accion in ((self.izq, FLECHA_IZQ, "carrusel_izq"),
                                        (self.der, FLECHA_DER, "carrusel_der")):
            r = control.dibujar(sup, e.p(centro), pulsado == accion)
            zona(r.inflate(e.n(40), e.n(40)), accion)
        self._puntos(sup, round(posicion) % len(self.elementos))
        self.barra.dibujar(sup, zona, hora)
        if expansion > 0 and captura is not None:
            self.barra.expansion(sup, expansion, captura)
        if aviso_texto:
            aviso(sup, aviso_texto, self.fuente_aviso, sup.get_height() - e.n(60))


# --- Configuración ------------------------------------------------------------------
FONDO_ARRIBA, FONDO_ABAJO = (156, 46, 156), (206, 66, 206)


def fondo_magenta(tam, e, arriba=None):
    """Fondo de las listas: degradado magenta de arriba abajo y una franja más clara en
    diagonal a la derecha (como un reflejo en el vidrio). 'arriba': y donde empieza."""
    w, h = tam
    sup = pygame.Surface(tam).convert()
    for y in range(h):
        sup.fill(mezcla(FONDO_ARRIBA, FONDO_ABAJO, y / max(1, h - 1)), (0, y, w, 1))
    luz = pygame.Surface(tam, pygame.SRCALPHA)
    x_arriba, x_abajo = e.p((573, 0))[0], e.p((513, 0))[0]
    for y in range(h):
        x0 = round(x_arriba + (x_abajo - x_arriba) * y / max(1, h - 1))
        ancho = w - x0
        for x in range(0, ancho, 8):                 # más clara junto al borde, se apaga a la derecha
            a = round(26 - 12 * x / max(1, ancho))
            luz.fill((255, 255, 255, a), (x0 + x, y, min(8, ancho - x), 1))
    sup.blit(luz, (0, 0))
    return sup


def fila_pulsada(w, alto):
    """Fila pulsada o elegida: violeta con dos líneas blancas y un halo suave."""
    halo = max(2, alto // 10)
    s = pygame.Surface((w, alto + 2 * halo), pygame.SRCALPHA)
    for i in range(halo):
        a = round(80 * (1 - i / halo) ** 2)
        s.fill((150, 130, 255, a), (0, halo - 1 - i, w, 1))
        s.fill((150, 130, 255, a), (0, halo + alto + i, w, 1))
    s.blit(estilo.degradado(w, alto, (132, 117, 255), (112, 93, 252)), (0, halo))
    linea = max(1, alto // 32)
    s.fill(BLANCO, (0, halo, w, linea))
    s.fill(BLANCO, (0, halo + alto - linea, w, linea))
    return s.convert_alpha(), halo


class PantallaAjustes:
    """Configuración: lista sobre el fondo magenta; 'Opciones de energía' (arriba)
    despliega Suspender, Reiniciar y Apagar. Se abre y se cierra con el círculo.

    El fondo es una imagen opaca; de cada fila solo se copian icono y texto (pequeños,
    ya pintados). Desplazamiento en px del diseño.
    """
    def __init__(self, tam):
        self.esc = e = Escala(tam)
        self.tam = w, h = tam
        self.barra = BarraSuperior(e, w)
        self.arriba = self.barra.fondo.get_height()        # la lista empieza bajo la barra
        self.fila = e.n(FILA_ALTO)
        self.fondo = fondo_magenta(tam, e)
        self.fondo.blit(self.barra.fondo, (0, 0))
        fuente = estilo.fuente(e.n(23), "SemiBold")
        fuente_sub = estilo.fuente(e.n(21), "SemiBold")
        self.contenido = {}
        for accion, etiqueta, svg in AJUSTES_FILAS:
            self.contenido[accion] = self._contenido(etiqueta, svg, fuente, e.n(33), e.n(42), e.n(78))
        for accion, etiqueta, svg in ENERGIA_OPCIONES:
            self.contenido[accion] = self._contenido(etiqueta, svg, fuente_sub, e.n(28), e.n(87), e.n(122))
        self.separador = pygame.Surface((w, 1), pygame.SRCALPHA)
        self.separador.fill((255, 255, 255, 46))
        self.sombra_sub = pygame.Surface((w, self.fila), pygame.SRCALPHA)
        self.sombra_sub.fill((60, 0, 70, 34))
        self.pulsada, self.halo = fila_pulsada(w, self.fila)
        self.flecha = estilo.icono("flecha-derecha.svg", e.n(30), BLANCO)
        self.flecha_abajo = estilo.icono("flecha-abajo.svg", e.n(30), BLANCO)
        self.fuente_valor = estilo.fuente(e.n(19), "Medium")
        self.fuente_aviso = fuente_aviso(e)
        self._textos = {}

    def _contenido(self, etiqueta, svg, fuente, lado, x_icono, x_texto):
        """Icono y texto de una fila, en blanco sobre transparente: (imagen, x)."""
        ico = estilo.icono(svg, lado, BLANCO)
        t = fuente.render(etiqueta, True, BLANCO)
        sombra_t = fuente.render(etiqueta, True, (90, 20, 90))
        x0 = x_icono - lado // 2
        ancho = x_texto - x0 + t.get_width() + 2
        alto = self.fila
        s = pygame.Surface((ancho, alto), pygame.SRCALPHA)
        s.blit(ico, ico.get_rect(center=(x_icono - x0, alto // 2)))
        s.blit(sombra_t, sombra_t.get_rect(midleft=(x_texto - x0 + 1, alto // 2 + 2)))
        s.blit(t, t.get_rect(midleft=(x_texto - x0, alto // 2)))
        return s.convert_alpha(), x0

    def maximo(self, energia):
        """Desplazamiento máximo (px del diseño) con la energía desplegada 'energia' (0..1)."""
        contenido = (len(AJUSTES_FILAS) + len(ENERGIA_OPCIONES) * energia) * FILA_ALTO
        return max(0.0, contenido - (self.tam[1] - self.arriba) / self.esc.k)

    def _texto(self, valor):
        if valor not in self._textos:
            if len(self._textos) > 20:
                self._textos.clear()
            self._textos[valor] = self.fuente_valor.render(valor, True, (250, 235, 250))
        return self._textos[valor]

    def _pintar(self, sup, accion, y, area, zona, resaltado, valores, sub=False, energia=0.0):
        if y >= area.bottom or y + self.fila <= area.top:
            return
        e, w = self.esc, self.tam[0]
        if sub:
            sup.blit(self.sombra_sub, (0, y))
        if resaltado == accion:
            sup.blit(self.pulsada, (0, y - self.halo))
        img, x = self.contenido[accion]
        sup.blit(img, (x, y))
        valor = valores.get(accion)
        derecha = w - e.n(29)
        if valor:
            t = self._texto(valor)
            sup.blit(t, t.get_rect(midright=(derecha, y + self.fila // 2)))
        elif accion in CON_FLECHA or accion == "energia":
            flecha = self.flecha_abajo if accion == "energia" and energia > .5 else self.flecha
            sup.blit(flecha, flecha.get_rect(center=(w - e.n(42), y + self.fila // 2)))
        sup.blit(self.separador, (0, y + self.fila - 1))
        if zona:
            rect = area.clip(pygame.Rect(0, y, w, self.fila))
            if rect.height > 0:
                zona(rect, accion)

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
            self._pintar(sup, accion, y, area, zona_filas, resaltado, valores, energia=energia)
            y += self.fila
            if accion == "energia" and energia > 0:
                # Las opciones salen de debajo de la fila; las demás bajan a la vez.
                alto = round(len(ENERGIA_OPCIONES) * self.fila * energia)
                hueco = area.clip(pygame.Rect(0, y, w, alto))
                sup.set_clip(hueco)
                for i, (opcion, _, _) in enumerate(ENERGIA_OPCIONES):
                    self._pintar(sup, opcion, y + i * self.fila - (len(ENERGIA_OPCIONES) * self.fila - alto),
                                 hueco, zona_filas if energia > .999 else None, resaltado, valores, sub=True)
                sup.set_clip(area)
                y += alto
        sup.set_clip(None)
        self.barra.dibujar(sup, lambda rect, accion: None, hora)
        if aviso_texto:
            aviso(sup, aviso_texto, self.fuente_aviso, sup.get_height() - e.n(58))
