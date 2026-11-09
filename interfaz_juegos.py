"""Frame '9 Juegos' ("Games"): portadas en burbujas de cristal, por páginas deslizables.

Cada juego es su portada recortada en círculo con la capa de cristal del diseño
(Burbuja/Default) encima. La portada es una imagen junto a la ROM con el mismo
nombre (.png, .jpg, .jpeg o .webp); si no hay, se muestra el nombre del juego.
"""
from pathlib import Path
import pygame
from interfaz_inicio import Escala, Control, cargar_svg, cargar_png, sombra, aviso
from interfaz_redes import cabecera, LINEA_Y

VOLVER = pygame.Rect(19, 13, 128, 72)
FLECHA_IZQ, FLECHA_DER = (60, 382), (1210, 382)
# Esquinas (x, y) de las burbujas de 128 px: filas de 4, 5 y 4 separadas 212 px.
HUECOS = ([(x, 162) for x in (258, 470, 682, 894)] +
          [(x, 318) for x in (152, 364, 576, 788, 1000)] +
          [(x, 474) for x in (258, 470, 682, 894)])
LADO = 128
PORTADA_EXT = (".png", ".jpg", ".jpeg", ".webp")
GLIFO = (43, 52, 66)


def portada(juego):
    """Imagen de portada junto a la ROM con el mismo nombre, o None."""
    juego = Path(juego)
    return next((juego.with_suffix(ext) for ext in PORTADA_EXT if juego.with_suffix(ext).is_file()), None)


def paginas(n):
    return max(1, -(-n // len(HUECOS)))


class BurbujaJuego:
    """Portada en círculo + cristal + sombra, en una sola imagen."""
    def __init__(self, juego, e, cristal, fuente):
        k, lado = e.k, e.n(LADO)
        # La capa de cristal es un SVG de 164x164 con el círculo (128 px) en (82, 74);
        # su filtro de sombra (dy 8, desenfoque 9) está en esas mismas unidades.
        s, d = sombra(lado, lado, lado // 2, round(8 * k), max(2, 9 * k), (13, 31, 64, 77))
        # Rectángulos respecto al centro del círculo; la imagen los contiene a todos.
        r_sombra = pygame.Rect(d, s.get_size())
        r_cristal = pygame.Rect((-round(82 * k), -round(74 * k)), cristal.get_size())
        caja = r_sombra.union(r_cristal)
        # Con transparencia: las burbujas vecinas se solapan un poco en diagonal. Solo
        # se usa al montar la página (una vez); la página sí es opaca.
        img = pygame.Surface(caja.size, pygame.SRCALPHA)
        cx, cy = -caja.x, -caja.y                        # centro del círculo dentro de img
        self.desp = (cx - lado // 2, cy - lado // 2)     # esquina del círculo dentro de img
        img.blit(s, (cx + d[0], cy + d[1]))
        circulo = pygame.Surface((lado, lado), pygame.SRCALPHA)
        ruta = portada(juego)
        try:
            foto = pygame.image.load(str(ruta)).convert() if ruta else None
        except pygame.error:
            foto = None
        if foto:
            # Recorte tipo 'cover': llena el círculo sin deformar la portada. En vertical
            # se muestra la parte de arriba (donde suele ir el título), como en el diseño.
            f = max(lado / foto.get_width(), lado / foto.get_height())
            foto = pygame.transform.smoothscale(foto, (round(foto.get_width() * f), round(foto.get_height() * f)))
            circulo.blit(foto, ((lado - foto.get_width()) // 2, round((lado - foto.get_height()) * .2)))
        else:
            circulo.fill((240, 244, 248))
            self._nombre(circulo, Path(juego).stem, fuente)
        mascara = pygame.Surface((lado, lado), pygame.SRCALPHA)
        pygame.draw.circle(mascara, (255, 255, 255, 255), (lado // 2, lado // 2), lado // 2)
        circulo.blit(mascara, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        img.blit(circulo, self.desp)
        img.blit(cristal, (cx + r_cristal.x, cy + r_cristal.y))
        self.img = img

    @staticmethod
    def _nombre(sup, nombre, fuente):
        """Nombre del juego en varias líneas dentro de la burbuja (sin portada)."""
        nombre = nombre.split("[")[0].strip() or nombre      # sin etiquetas tipo [GBC]
        lineas, actual = [], ""
        for palabra in nombre.split():
            prueba = (actual + " " + palabra).strip()
            if fuente.size(prueba)[0] <= sup.get_width() * .78:
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


class PantallaJuegos:
    def __init__(self, tam):
        self.esc = e = Escala(tam)
        self.tam = tam
        self.volver = Control("volver.svg", e.k, ancho=128, alto=72, radio=36,
                              brillo=(6, 4, 116, 33.12), pos_glifo=(44, 16))
        self.izq = Control("flecha-izquierda.svg", e.k)
        self.der = Control("flecha-derecha.svg", e.k)
        self.cristal = cargar_svg("burbuja-default.svg", e.k)
        self.titulo = cargar_png("titulo-games.png", e.k)    # "Games" en Zrnic, de Figma
        self.fuente_nombre = pygame.font.Font(None, e.n(26))
        self.fuente_aviso = pygame.font.Font(None, e.n(34))
        self._paginas = (None, [])

    def paginas(self, juegos):
        """Cada página montada una vez en una superficie opaca (fondo blanco)."""
        clave = [str(j) for j in juegos]
        if self._paginas[0] != clave:
            e = self.esc
            arriba = e.p((0, LINEA_Y + 3))[1]
            hojas = []
            for p in range(paginas(len(juegos))):
                hoja = pygame.Surface((self.tam[0], self.tam[1] - arriba)).convert()
                hoja.fill((255, 255, 255))
                for juego, (x, y) in zip(juegos[p * len(HUECOS):(p + 1) * len(HUECOS)], HUECOS):
                    b = BurbujaJuego(juego, e, self.cristal, self.fuente_nombre)
                    px, py = e.p((x, y))
                    hoja.blit(b.img, (px - b.desp[0], py - b.desp[1] - arriba))
                hojas.append(hoja)
            self._paginas = (clave, hojas)
        return self._paginas[1]

    def dibujar(self, sup, juegos, posicion, zona, aviso_texto="", tocable=True):
        """'posicion' es la página (decimal mientras se desliza)."""
        e = self.esc
        sup.fill((255, 255, 255))
        arriba = e.p((0, LINEA_Y + 3))[1]
        w = sup.get_width()
        if not juegos:
            t = self.fuente_aviso.render("No hay juegos en recursos/juegos", True, GLIFO)
            sup.blit(t, t.get_rect(center=e.p((640, 360))))
        for p, hoja in enumerate(self.paginas(juegos)):
            x = round((p - posicion) * w)
            if -w < x < w:
                sup.blit(hoja, (x, arriba))
        cabecera(sup, e, self.titulo, self.volver, VOLVER, zona)
        for control, centro, accion in ((self.izq, FLECHA_IZQ, "juegos_izq"),
                                        (self.der, FLECHA_DER, "juegos_der")):
            control.dibujar(sup, e.p(centro))
            rect = pygame.Rect(0, 0, e.n(110), e.n(110))
            rect.center = e.p(centro)
            zona(rect, accion)
        if tocable and abs(posicion - round(posicion)) < 2e-3:
            p = round(posicion)
            for i, (x, y) in enumerate(HUECOS):
                indice = p * len(HUECOS) + i
                if indice < len(juegos):
                    zona(pygame.Rect(e.p((x, y)), (e.n(LADO), e.n(LADO))), ("juego", indice))
        if aviso_texto:
            aviso(sup, aviso_texto, self.fuente_aviso, sup.get_height() - e.n(70))
