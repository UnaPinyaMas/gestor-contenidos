"""Libros (entrega v2, 6.13) y lector EPUB / PDF / cómic (6.14).

Libros: carrusel de portadas; la del centro es más grande, con borde magenta y el
título debajo. Las portadas son la primera página de cada libro (miniaturas.py).
Lector: página sin barra superior, con Tornar, zoom + y -, flechas para pasar de
página y el contador con una barra de progreso magenta.
"""
from pathlib import Path
import pygame
import estilo
from estilo import BLANCO, MAGENTA, TEXTO, AZUL_OSCURO, GRIS
from interfaz_inicio import Escala, aviso, fuente_aviso, cabecera_blanca

CENTRO = (640, 370)
SEPARACION = 305
PORTADA_CENTRO, PORTADA_LADO = (227, 427), (170, 310)
LADO_Y = 382                           # centro vertical de las portadas laterales
FLECHA_IZQ, FLECHA_DER = (127, 387), (1152, 387)
TITULO_Y = 625


def titulo_libro(ruta):
    """Nombre legible del libro a partir del archivo."""
    return Path(ruta).stem.replace("_", " ").strip()


class PantallaLibros:
    PASOS = 6

    def __init__(self, tam):
        self.esc = e = Escala(tam)
        self.tam = tam
        self.fondo, self.barra = cabecera_blanca(tam, e, "titulo-books.png")
        self.flecha_izq = estilo.icono("flecha-izquierda.svg", e.n(58), AZUL_OSCURO)
        self.flecha_der = estilo.icono("flecha-derecha.svg", e.n(58), AZUL_OSCURO)
        self.flecha_pulsada = (estilo.icono("flecha-izquierda.svg", e.n(58), estilo.VIOLETA),
                               estilo.icono("flecha-derecha.svg", e.n(58), estilo.VIOLETA))
        self.fuente_titulo = estilo.fuente(e.n(22), "Bold")
        self.fuente_hueco = estilo.fuente(e.n(18), "SemiBold")
        self.fuente_aviso = fuente_aviso(e)
        self._portadas = {}

    def _tam(self, t):
        e = self.esc
        return (e.n(PORTADA_CENTRO[0] + (PORTADA_LADO[0] - PORTADA_CENTRO[0]) * t),
                e.n(PORTADA_CENTRO[1] + (PORTADA_LADO[1] - PORTADA_CENTRO[1]) * t))

    def _portada(self, ruta, img, paso, central):
        """Portada a un tamaño (paso 0 = centro ... PASOS = lado) con sombra, sobre blanco."""
        clave = (str(ruta), bool(img), paso, central)
        if clave not in self._portadas:
            if len(self._portadas) > 120:
                self._portadas.clear()
            e = self.esc
            w, h = self._tam(paso / self.PASOS)
            radio = e.n(14)
            if img:
                cara = estilo.redondear(estilo.cubrir(img, w, h, arriba=0), radio)
            else:                                       # aún sin portada: tarjeta con el título
                cara = estilo.degradado(w, h, (250, 251, 253), (226, 233, 242), radio)
                pygame.draw.rect(cara, (205, 214, 226), cara.get_rect(), max(1, e.n(1.5)), border_radius=radio)
                y = h // 2 - self.fuente_hueco.get_linesize()
                for linea in _partir(titulo_libro(ruta), self.fuente_hueco, w * .8)[:4]:
                    t = self.fuente_hueco.render(linea, True, GRIS)
                    cara.blit(t, t.get_rect(midtop=(w // 2, y)))
                    y += self.fuente_hueco.get_linesize()
            if central:
                borde = max(2, e.n(4))
                marco = pygame.Surface((w + 2 * borde, h + 2 * borde), pygame.SRCALPHA)
                pygame.draw.rect(marco, MAGENTA, marco.get_rect(), border_radius=radio + borde)
                marco.blit(cara, (borde, borde))
                cara = marco
            img_s, pos = estilo.con_sombra(cara, radio, e.n(8), e.n(16), (13, 31, 64, 60))
            opaca = pygame.Surface(img_s.get_size()).convert()
            opaca.fill(BLANCO)
            opaca.blit(img_s, (0, 0))
            centro = (pos[0] + cara.get_width() // 2, pos[1] + cara.get_height() // 2)
            self._portadas[clave] = (opaca, centro)
        return self._portadas[clave]

    def dibujar(self, sup, libros, posicion, miniaturas, zona, aviso_texto="", hora="", resaltado=None):
        e = self.esc
        sup.blit(self.fondo, (0, 0))
        if not libros:
            t = estilo.fuente(e.n(22), "Medium").render("No hay libros en recursos/epub ni recursos/pdf", True, GRIS)
            sup.blit(t, t.get_rect(center=e.p((640, 400))))
        estatico = abs(posicion - round(posicion)) < 2e-3
        visibles = sorted(((abs(i - posicion), i) for i in range(len(libros)) if abs(i - posicion) < 1.6),
                          reverse=True)
        for d_abs, i in visibles:                       # los lejanos primero
            d = i - posicion
            t = min(1.0, d_abs)
            paso = round(t * self.PASOS)
            img = miniaturas.superficie(libros[i], "libro")
            central = d_abs < .5
            portada, (cx, cy) = self._portada(libros[i], img, paso, central)
            x = e.p((CENTRO[0] + d * SEPARACION, 0))[0]
            y = e.p((0, CENTRO[1] + (LADO_Y - CENTRO[1]) * t))[1]
            if d_abs > 1:
                portada = portada.copy()
                portada.set_alpha(round(255 * max(0, 1.6 - d_abs) / .6))
            sup.blit(portada, (x - cx, y - cy))
            if estatico and d_abs <= 1.01:
                w, h = self._tam(t)
                r = pygame.Rect(0, 0, w, h)
                r.center = (x, y)
                zona(r, ("libro", i) if central else ("libros_izq" if d < 0 else "libros_der"))
        if libros:
            actual = min(len(libros) - 1, max(0, round(posicion)))
            t = self.fuente_titulo.render(estilo.recortar(self.fuente_titulo, titulo_libro(libros[actual]), e.n(900)),
                                          True, TEXTO)
            sup.blit(t, t.get_rect(center=e.p((640, TITULO_Y))))
        for img, pulsada, centro, accion in ((self.flecha_izq, self.flecha_pulsada[0], FLECHA_IZQ, "libros_izq"),
                                             (self.flecha_der, self.flecha_pulsada[1], FLECHA_DER, "libros_der")):
            img = pulsada if resaltado == accion else img
            r = img.get_rect(center=e.p(centro))
            sup.blit(img, r)
            zona(r.inflate(e.n(60), e.n(120)), accion)
        self.barra.dibujar(sup, zona, hora)
        if aviso_texto:
            aviso(sup, aviso_texto, self.fuente_aviso, sup.get_height() - e.n(50))


def _partir(texto, f, ancho):
    lineas, actual = [], ""
    for palabra in texto.split():
        prueba = (actual + " " + palabra).strip()
        if f.size(prueba)[0] <= ancho or not actual:
            actual = prueba
        else:
            lineas.append(actual)
            actual = palabra
    return lineas + ([actual] if actual else [])


# --- Lector ------------------------------------------------------------------------------
PAGINA = pygame.Rect(200, 30, 880, 545)        # zona de la página
MAS, MENOS = (1229, 52), (1229, 117)
ANTERIOR, SIGUIENTE = (137, 327), (1143, 327)
CONTADOR_Y = 614
PROGRESO = pygame.Rect(340, 650, 600, 5)


def tam_pagina(tam):
    """Tamaño en px de pantalla de la zona donde se pinta la página."""
    return Escala(tam).r(PAGINA).size


class PantallaLector:
    def __init__(self, tam):
        self.esc = e = Escala(tam)
        self.tam = tam
        lado = e.n(54)
        self.mas = estilo.Boton(lado, lado, e.n(12), glifo="icono-mas.svg", lado_glifo=lado * .5)
        self.menos = estilo.Boton(lado, lado, e.n(12), glifo="icono-menos.svg", lado_glifo=lado * .5)
        self.flechas = {a: (estilo.icono(svg, e.n(58), AZUL_OSCURO), estilo.icono(svg, e.n(58), estilo.VIOLETA))
                        for a, svg in (("doc_anterior", "flecha-izquierda.svg"), ("doc_siguiente", "flecha-derecha.svg"))}
        self.progreso = estilo.Barra(e.r(PROGRESO))
        self.fuente_contador = estilo.fuente(e.n(26), "Bold")
        self.fuente_aviso = fuente_aviso(e)

    def dibujar(self, sup, pagina, indicador, fraccion, hay_anterior, hay_siguiente, zona,
                aviso_texto="", resaltado=None):
        """'pagina': superficie ya renderizada (cabe en PAGINA); 'fraccion': progreso 0..1."""
        e = self.esc
        sup.fill(BLANCO)
        area = e.r(PAGINA)
        if pagina is not None:
            sup.blit(pagina, pagina.get_rect(center=area.center))
        zona_pagina = area
        for accion, centro, visible in (("doc_anterior", ANTERIOR, hay_anterior),
                                        ("doc_siguiente", SIGUIENTE, hay_siguiente)):
            if visible:
                img = self.flechas[accion][resaltado == accion]
                r = img.get_rect(center=e.p(centro))
                sup.blit(img, r)
                zona(r.inflate(e.n(80), e.n(260)), accion)
        for boton, centro, accion in ((self.mas, MAS, "doc_mas"), (self.menos, MENOS, "doc_menos")):
            r = boton.dibujar(sup, e.p(centro), resaltado == accion)
            zona(r.inflate(e.n(16), e.n(10)), accion)
        zona(zona_pagina, "doc_pagina")                # deslizar: pasar página o mover la ampliada
        t = self.fuente_contador.render(indicador, True, TEXTO)
        sup.blit(t, t.get_rect(center=e.p((640, CONTADOR_Y))))
        self.progreso.dibujar(sup, fraccion, con_tirador=False)
        if aviso_texto:
            aviso(sup, aviso_texto, self.fuente_aviso, sup.get_height() - e.n(30))
