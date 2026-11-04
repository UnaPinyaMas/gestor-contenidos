"""Pantalla de Inicio según el wireframe de Figma '1 Inicio' (1280x720).

Las burbujas y los glifos son los SVG exportados del diseño (recursos/interfaz).
Pygame los rasteriza con nanosvg, que no aplica los filtros de sombra, así que
la sombra (feOffset dy=8, feGaussianBlur 9, rgba(13,31,64,.3)) se añade aquí.
"""
import io
import re
from pathlib import Path
import pygame

INTERFAZ = Path(__file__).resolve().parent / "recursos" / "interfaz"
DISENO = (1280, 720)                  # tamaño del frame en Figma
TEXTO = (33, 33, 33)                  # #212121

# Carrusel: (etiqueta, sección de CARPETAS, svg). Orden de la nota del diseño.
SECCIONES = [
    ("Audio", "Audio", "burbuja-audio.svg"),
    ("Vídeos", "Vídeos", "burbuja-videos.svg"),
    ("Libros", "Libros", "burbuja-libros.svg"),
    ("Imágenes", "Imágenes", "burbuja-imagenes.svg"),
    ("Juegos", "Juegos", "burbuja-juegos.svg"),
]

# Geometría del frame (coordenadas de Figma, centros de los círculos base).
CENTRO_CARRUSEL = (640, 345)
SEPARACION = 340                      # de Vídeos (640) a Audio/Libros (300/980)
DIAMETRO_CENTRO, DIAMETRO_LADO = 294, 221
ENERGIA = ((61, 62), 84)              # (centro, diámetro)
AJUSTES = ((1216, 62), 84)
FLECHA_IZQ, FLECHA_DER = (112, 364), (1166, 364)
LADO_FLECHA = 80
LOGO = pygame.Rect(440, 36, 400, 84)


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


def cargar_svg(nombre, factor):
    """Rasteriza un SVG del diseño a 'factor' veces su tamaño (desde el vector)."""
    texto = (INTERFAZ / nombre).read_text(encoding="utf-8")
    w = float(re.search(r'width="([\d.]+)"', texto).group(1))
    h = float(re.search(r'height="([\d.]+)"', texto).group(1))
    texto = re.sub(r'width="[\d.]+"', f'width="{w * factor:.2f}"', texto, count=1)
    texto = re.sub(r'height="[\d.]+"', f'height="{h * factor:.2f}"', texto, count=1)
    return pygame.image.load(io.BytesIO(texto.encode("utf-8")), "a.svg").convert_alpha()


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


def sombra(diametro, dy, desenfoque, color):
    """Sombra de un círculo como la de los filtros del diseño."""
    margen = round(desenfoque * 2.5)
    tam = diametro + margen * 2
    s = pygame.Surface((tam, tam), pygame.SRCALPHA)
    pygame.draw.circle(s, color, (tam // 2, tam // 2), diametro // 2)
    return _difuminar(s, desenfoque), (-tam // 2, -tam // 2 + dy)


class Burbuja:
    """Burbuja del diseño escalada a un diámetro de círculo base dado, con sombra."""
    def __init__(self, nombre, diametro):
        cx, cy, r = _base(nombre)
        f = diametro / (2 * r)
        self.img = cargar_svg(nombre, f)
        self.ancla = (round(cx * f), round(cy * f))     # centro del círculo dentro de img
        self.diametro = diametro
        k = diametro / 294                              # el filtro está definido a escala Vídeos
        self.sombra, self.desp = sombra(diametro, round(8 * k), max(2, 9 * k), (13, 31, 64, 77))

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
    """Control/Izquierda y Control/Derecha del diseño: botón de cristal con glifo SVG."""
    def __init__(self, glifo, lado):
        k = lado / 80
        self.lado = lado
        # Sombra: 0 4px 10px rgba(13,31,64,.22); la superficie la contiene entera.
        s, d = sombra(lado, round(4 * k), 10 * k, (13, 31, 64, 56))
        tam = s.get_width() + 2 * round(4 * k)
        sup = pygame.Surface((tam, tam), pygame.SRCALPHA)
        o = (tam - lado) // 2
        sup.blit(s, (tam // 2 + d[0], tam // 2 + d[1]))
        # Base: degradado blanco -> #d3deea, borde 1.5px #afc0d2, totalmente redondeada.
        base = pygame.Surface((lado, lado), pygame.SRCALPHA)
        for y in range(lado):
            t = y / (lado - 1)
            color = tuple(round(255 + (c - 255) * t) for c in (211, 222, 234))
            pygame.draw.line(base, color, (0, y), (lado - 1, y))
        mascara = pygame.Surface((lado, lado), pygame.SRCALPHA)
        pygame.draw.circle(mascara, (255, 255, 255, 255), (lado // 2, lado // 2), lado // 2)
        base.blit(mascara, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        pygame.draw.circle(base, (175, 192, 210), (lado // 2, lado // 2), lado // 2, max(1, round(1.5 * k)))
        sup.blit(base, (o, o))
        # Brillo: 68x36.8 en (6,4), degradado blanco .9 -> 0, esquinas de 40px.
        bw, bh = round(68 * k), round(36.8 * k)
        brillo = pygame.Surface((bw, bh), pygame.SRCALPHA)
        for y in range(bh):
            pygame.draw.line(brillo, (255, 255, 255, round(230 * (1 - y / max(1, bh - 1)))), (0, y), (bw, y))
        forma = pygame.Surface((bw, bh), pygame.SRCALPHA)
        pygame.draw.rect(forma, (255, 255, 255, 255), forma.get_rect(), border_radius=round(40 * k))
        brillo.blit(forma, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        sup.blit(brillo, (o + round(6 * k), o + round(4 * k)))
        # Glifo 40x40 en (20,20).
        g = cargar_svg(glifo, k)
        sup.blit(g, (o + round(20 * k), o + round(20 * k)))
        self.img = sup

    def dibujar(self, sup, centro):
        sup.blit(self.img, self.img.get_rect(center=centro))


def caja_logo(sup, rect, logo, fuente, grosor):
    """Rectángulo 'logo' del diseño (borde #212121, radio 8) con el logo de TerraHub."""
    pygame.draw.rect(sup, (255, 255, 255), rect, border_radius=max(2, rect.height // 10))
    pygame.draw.rect(sup, TEXTO, rect, grosor, border_radius=max(2, rect.height // 10))
    texto = fuente.render("TerraHub", True, TEXTO)
    ancho = texto.get_width()
    if logo:
        alto = rect.height - 12
        logo = pygame.transform.smoothscale(
            logo, (max(1, round(logo.get_width() * alto / logo.get_height())), alto))
        ancho += logo.get_width() + 10
    x = rect.centerx - ancho // 2
    if logo:
        sup.blit(logo, (x, rect.y + 6))
        x += logo.get_width() + 10
    sup.blit(texto, texto.get_rect(midleft=(x, rect.centery)))


def aviso(sup, texto, fuente, y):
    """Mensaje breve sobre la parte baja de la pantalla."""
    t = fuente.render(texto, True, (255, 255, 255))
    caja = t.get_rect(center=(sup.get_width() // 2, y)).inflate(32, 18)
    pygame.draw.rect(sup, (43, 52, 66), caja, border_radius=caja.height // 2)
    sup.blit(t, t.get_rect(center=caja.center))


# Frame '2 Menú de energía': tarjeta sobre el carrusel con tres botones.
TARJETA_ENERGIA = pygame.Rect(330, 170, 620, 360)
BOTONES_ENERGIA = [   # (acción, etiqueta, svg, x del botón); botones de 170x280 en y=210
    ("apagar", "Apagar", "energia-apagar.svg", 365),
    ("reiniciar", "Reiniciar", "energia-reiniciar.svg", 555),
    ("suspender", "Suspender", "energia-suspender.svg", 745),
]
GRIS_BOTON = (240, 240, 240)          # #f0f0f0


class PanelEnergia:
    """Tarjeta del menú de energía, escalada a la pantalla."""
    def __init__(self, esc):
        self.esc = esc
        self.iconos = [cargar_svg(svg, esc.k) for _, _, svg, _ in BOTONES_ENERGIA]
        self.fuente = pygame.font.Font(None, esc.n(32))

    def dibujar(self, sup, zona):
        e = self.esc
        radio = max(2, e.n(8))
        tarjeta = e.r(TARJETA_ENERGIA)
        pygame.draw.rect(sup, (255, 255, 255), tarjeta, border_radius=radio)
        pygame.draw.rect(sup, TEXTO, tarjeta, e.n(4), border_radius=radio)
        for (accion, etiqueta, _, x), icono in zip(BOTONES_ENERGIA, self.iconos):
            boton = e.r(pygame.Rect(x, 210, 170, 280))
            pygame.draw.rect(sup, GRIS_BOTON, boton, border_radius=radio)
            pygame.draw.rect(sup, TEXTO, boton, e.n(2), border_radius=radio)
            sup.blit(icono, e.p((x + 45, 260)))
            texto = self.fuente.render(etiqueta, True, TEXTO)
            sup.blit(texto, texto.get_rect(center=e.p((x + 85, 405))))
            zona(boton, accion)
        # Tocar fuera de la tarjeta (o el botón de energía otra vez) la cierra.
        zona(sup.get_rect(), "cerrar_energia")


class PantallaInicio:
    """Recursos ya escalados a la pantalla; se crean una vez por Vista."""
    def __init__(self, tam):
        self.esc = e = Escala(tam)
        self.centro = [Burbuja(svg, e.n(DIAMETRO_CENTRO)) for _, _, svg in SECCIONES]
        self.lado = [Burbuja(svg, e.n(DIAMETRO_LADO)) for _, _, svg in SECCIONES]
        self.energia = Burbuja("burbuja-energia.svg", e.n(ENERGIA[1]))
        self.ajustes = Burbuja("burbuja-ajustes.svg", e.n(AJUSTES[1]))
        self.izq = Control("flecha-izquierda.svg", e.n(LADO_FLECHA))
        self.der = Control("flecha-derecha.svg", e.n(LADO_FLECHA))
        self.energia_panel = PanelEnergia(e)
        self.fuente = pygame.font.Font(None, e.n(44))
        self.fuente_aviso = pygame.font.Font(None, e.n(34))
        try:
            self.logo = pygame.image.load(str(INTERFAZ.parent / "imagenes" / "logo.png")).convert_alpha()
        except (OSError, pygame.error):
            self.logo = None

    def dibujar(self, sup, posicion, zona, aviso_texto="", energia=False):
        """Pinta la pantalla. 'posicion' es el índice (decimal) del carrusel en el centro.

        'zona(rect, accion)' registra las zonas táctiles. Con 'energia' se muestra
        encima la tarjeta del menú de energía y solo ella responde a los toques.
        """
        zona_carrusel = (lambda rect, accion: None) if energia else zona
        self._dibujar_inicio(sup, posicion, zona_carrusel, zona, energia)
        if energia:
            self.energia_panel.dibujar(sup, zona)
        if aviso_texto:
            aviso(sup, aviso_texto, self.fuente_aviso, sup.get_height() - self.esc.n(70))

    def _dibujar_inicio(self, sup, posicion, zona, zona_energia, energia):
        e = self.esc
        sup.fill((255, 255, 255))
        n = len(SECCIONES)
        cx, cy = e.p(CENTRO_CARRUSEL)
        separacion = SEPARACION * e.k
        estatico = abs(posicion - round(posicion)) < 1e-3
        dibujo = []
        for i in range(n):
            d = (i - posicion + n / 2) % n - n / 2          # distancia circular al centro
            if abs(d) >= 1.5:
                continue
            dibujo.append((abs(d), i, d))
        for _, i, d in sorted(dibujo, reverse=True):     # los lejanos primero
            x = round(cx + d * separacion)
            alpha = 255 if abs(d) <= 1 else round(255 * (1.5 - abs(d)) / .5)
            if estatico:
                (self.centro if abs(d) < .5 else self.lado)[i].dibujar(sup, (x, cy), alpha)
            else:
                # Durante la animación se escala la burbuja grande (más rápido).
                t = min(1, abs(d))
                diam = round(e.n(DIAMETRO_CENTRO) + (e.n(DIAMETRO_LADO) - e.n(DIAMETRO_CENTRO)) * t)
                b = self.centro[i]
                f = diam / b.diametro
                img = pygame.transform.smoothscale(
                    b.img, (round(b.img.get_width() * f), round(b.img.get_height() * f)))
                if alpha < 255:
                    img.set_alpha(alpha)
                sup.blit(img, (x - round(b.ancla[0] * f), cy - round(b.ancla[1] * f)))
            if estatico and abs(d) < .5:
                r = e.n(DIAMETRO_CENTRO) // 2
                zona(pygame.Rect(x - r, cy - r, 2 * r, 2 * r), SECCIONES[i][1])
            elif estatico and abs(d) <= 1:
                r = e.n(DIAMETRO_LADO) // 2
                zona(pygame.Rect(x - r, cy - r, 2 * r, 2 * r),
                     "carrusel_izq" if d < 0 else "carrusel_der")
        # Controles laterales.
        self.izq.dibujar(sup, e.p(FLECHA_IZQ))
        self.der.dibujar(sup, e.p(FLECHA_DER))
        lado = e.n(LADO_FLECHA) + e.n(20)
        zona(pygame.Rect(0, 0, lado, lado).move(e.p(FLECHA_IZQ)[0] - lado // 2, e.p(FLECHA_IZQ)[1] - lado // 2),
             "carrusel_izq")
        zona(pygame.Rect(0, 0, lado, lado).move(e.p(FLECHA_DER)[0] - lado // 2, e.p(FLECHA_DER)[1] - lado // 2),
             "carrusel_der")
        # Energía (abre/cierra el menú de energía), ajustes y logo.
        for burbuja, (centro, diam), accion, registrar in (
                (self.energia, ENERGIA, "cerrar_energia" if energia else "energia", zona_energia),
                (self.ajustes, AJUSTES, "ajustes", zona)):
            p = e.p(centro)
            burbuja.dibujar(sup, p)
            r = e.n(diam) // 2 + e.n(16)
            registrar(pygame.Rect(p[0] - r, p[1] - r, 2 * r, 2 * r), accion)
        caja_logo(sup, e.r(LOGO), self.logo, self.fuente, max(1, e.n(2)))
