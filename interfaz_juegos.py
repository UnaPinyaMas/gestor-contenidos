"""Juegos (entrega v2, 6.8): portadas circulares por páginas deslizables.

Cada juego es su portada recortada en círculo con un aro blanco y sombra; la que se
toca lleva un aro magenta. La portada es una imagen junto a la ROM con el mismo
nombre (.png, .jpg, .jpeg o .webp); si no hay, se muestra el nombre del juego.
"""
from pathlib import Path
import pygame
import estilo
from estilo import BLANCO, MAGENTA, AZUL_OSCURO
from interfaz_inicio import Escala, aviso, fuente_aviso, cabecera_blanca, flechas_pagina

FLECHA_IZQ, FLECHA_DER = (60, 420), (1220, 420)
# Centros de las portadas (px del diseño): filas de 4, 5 y 4.
HUECOS = ([(x, 250) for x in (330, 530, 750, 950)] +
          [(x, 420) for x in (230, 430, 650, 850, 1050)] +
          [(x, 590) for x in (330, 530, 750, 950)])
LADO = 121
ARRIBA = 135                           # las páginas se deslizan por debajo de aquí
PORTADA_EXT = (".png", ".jpg", ".jpeg", ".webp")
GLIFO = AZUL_OSCURO


def portada(juego):
    """Imagen de portada junto a la ROM con el mismo nombre, o None."""
    juego = Path(juego)
    return next((juego.with_suffix(ext) for ext in PORTADA_EXT if juego.with_suffix(ext).is_file()), None)


def paginas(n):
    return max(1, -(-n // len(HUECOS)))


def nombre_en_circulo(sup, nombre, fuente):
    """Nombre en varias líneas centrado en 'sup' (cuando no hay portada)."""
    nombre = nombre.split("[")[0].strip() or nombre      # sin etiquetas tipo [GBC]
    lineas, actual = [], ""
    for palabra in nombre.split():
        prueba = (actual + " " + palabra).strip()
        if fuente.size(prueba)[0] <= sup.get_width() * .74:
            actual = prueba
        else:
            lineas.append(actual or palabra)
            actual = "" if not actual else palabra
    lineas.append(actual)
    lineas = [l for l in lineas if l][:4]
    alto = fuente.get_linesize()
    y = sup.get_height() // 2 - alto * len(lineas) // 2
    for linea in lineas:
        t = fuente.render(linea, True, GLIFO)
        sup.blit(t, t.get_rect(midtop=(sup.get_width() // 2, y)))
        y += alto


def portada_circular(ruta, lado, nombre, fuente):
    """Círculo de 'lado' px con aro blanco, borde fino y sombra: (imagen, centro)."""
    aro = max(2, round(lado * .03))
    disco = pygame.Surface((lado, lado), pygame.SRCALPHA)
    pygame.draw.circle(disco, BLANCO, (lado // 2, lado // 2), lado // 2)
    pygame.draw.circle(disco, (205, 214, 226), (lado // 2, lado // 2), lado // 2, max(1, aro // 2))
    interior = lado - 2 * aro
    foto = None
    try:
        foto = pygame.image.load(str(ruta)).convert() if ruta else None
    except (pygame.error, OSError):
        foto = None
    if foto is not None:
        disco.blit(estilo.circular(foto, interior), (aro, aro))
    else:
        fondo = pygame.Surface((interior, interior), pygame.SRCALPHA)
        pygame.draw.circle(fondo, (238, 242, 247), (interior // 2, interior // 2), interior // 2)
        nombre_en_circulo(fondo, nombre, fuente)
        disco.blit(fondo, (aro, aro))
    img, pos = estilo.con_sombra(disco, lado // 2, lado * .05, lado * .08, (13, 31, 64, 70))
    return img, (pos[0] + lado // 2, pos[1] + lado // 2)


class PantallaJuegos:
    def __init__(self, tam):
        self.esc = e = Escala(tam)
        self.tam = tam
        self.fondo, self.barra = cabecera_blanca(tam, e, "titulo-games.png")
        self.flechas = flechas_pagina(e, FLECHA_IZQ, FLECHA_DER)
        self.fuente_nombre = estilo.fuente(e.n(15), "SemiBold")
        self.fuente_aviso = fuente_aviso(e)
        self._paginas = (None, [])

    def paginas(self, juegos):
        """Cada página montada una vez en una superficie opaca (fondo blanco)."""
        clave = [str(j) for j in juegos]
        if self._paginas[0] != clave:
            e = self.esc
            arriba = e.p((0, ARRIBA))[1]
            hojas = []
            for p in range(paginas(len(juegos))):
                hoja = pygame.Surface((self.tam[0], self.tam[1] - arriba)).convert()
                hoja.fill(BLANCO)
                for juego, centro in zip(juegos[p * len(HUECOS):(p + 1) * len(HUECOS)], HUECOS):
                    img, c = portada_circular(portada(juego), e.n(LADO), Path(juego).stem, self.fuente_nombre)
                    px, py = e.p(centro)
                    hoja.blit(img, (px - c[0], py - c[1] - arriba))
                hojas.append(hoja)
            self._paginas = (clave, hojas)
        return self._paginas[1]

    def dibujar(self, sup, juegos, posicion, zona, aviso_texto="", tocable=True, hora="", resaltado=None):
        """'posicion' es la página (decimal mientras se desliza); 'resaltado', lo que se toca."""
        e = self.esc
        sup.blit(self.fondo, (0, 0))
        arriba = e.p((0, ARRIBA))[1]
        w = sup.get_width()
        if not juegos:
            t = estilo.fuente(e.n(22), "Medium").render("No hay juegos en recursos/juegos", True, estilo.GRIS)
            sup.blit(t, t.get_rect(center=e.p((640, 400))))
        for p, hoja in enumerate(self.paginas(juegos)):
            x = round((p - posicion) * w)
            if -w < x < w:
                sup.blit(hoja, (x, arriba))
        estatico = abs(posicion - round(posicion)) < 2e-3
        if estatico:
            p = round(posicion)
            for i, centro in enumerate(HUECOS):
                indice = p * len(HUECOS) + i
                if indice >= len(juegos):
                    break
                if resaltado == ("juego", indice):        # aro magenta en la que se toca
                    pygame.draw.circle(sup, MAGENTA, e.p(centro), e.n(LADO / 2 + 6), max(2, e.n(4)))
                if tocable:
                    r = pygame.Rect(0, 0, e.n(LADO), e.n(LADO))
                    r.center = e.p(centro)
                    zona(r, ("juego", indice))
        for (control, centro), accion in zip(self.flechas, ("juegos_izq", "juegos_der")):
            r = control.dibujar(sup, centro, resaltado == accion)
            zona(r.inflate(e.n(40), e.n(40)), accion)
        self.barra.dibujar(sup, zona, hora)
        if aviso_texto:
            aviso(sup, aviso_texto, self.fuente_aviso, sup.get_height() - e.n(50))
