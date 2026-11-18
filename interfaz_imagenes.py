"""Imágenes (entrega v2, 6.15) y visor de imagen (6.16).

Imágenes: la misma cuadrícula que Vídeos (sin textos). Visor: imagen grande sobre
negro, sin barra superior, con Tornar, el botón de borrar, las miniaturas de las
anteriores (izquierda) y de la actual y siguientes (derecha) y el nombre debajo.
"""
from pathlib import Path
import pygame
import estilo
from estilo import BLANCO, NEGRO_SUAVE, AZUL_OSCURO
from interfaz_inicio import Escala, aviso, fuente_aviso
from interfaz_videos import Rejilla


class PantallaImagenes(Rejilla):
    def __init__(self, tam):
        super().__init__(tam, "titulo-photos.png", "imagen", con_textos=False)


# --- Visor --------------------------------------------------------------------------
IMAGEN = pygame.Rect(280, 130, 720, 460)
MINIATURA = (120, 90)
COLUMNA_IZQ, COLUMNA_DER = 40, 1120
MINIATURAS_Y = (170, 300, 430)
BORRAR = (1226, 52)
PIE_Y = 660


class PantallaVisor:
    def __init__(self, tam):
        self.esc = e = Escala(tam)
        self.tam = tam
        self.borrar = estilo.Boton(e.n(60), e.n(54), e.n(12), glifo="icono-papelera.svg", lado_glifo=e.n(28))
        self.fuente = estilo.fuente(e.n(19), "SemiBold")
        self.fuente_aviso = fuente_aviso(e)
        w, h = e.n(MINIATURA[0]), e.n(MINIATURA[1])
        self.radio = e.n(10)
        hueco = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(hueco, NEGRO_SUAVE, hueco.get_rect(), border_radius=self.radio)
        pygame.draw.rect(hueco, AZUL_OSCURO, hueco.get_rect(), max(1, e.n(1.5)), border_radius=self.radio)
        self.hueco = hueco
        self._mini = {}
        self._grande = (None, None)

    def _miniatura(self, ruta, img, actual):
        clave = (str(ruta), bool(img), actual)
        if clave not in self._mini:
            if len(self._mini) > 40:
                self._mini.clear()
            e = self.esc
            w, h = e.n(MINIATURA[0]), e.n(MINIATURA[1])
            if img:
                m = estilo.redondear(estilo.cubrir(img, w, h), self.radio)
            else:
                m = self.hueco.copy()
            if actual:                                  # la que se ve: con borde blanco
                pygame.draw.rect(m, BLANCO, m.get_rect(), max(2, e.n(3)), border_radius=self.radio)
            self._mini[clave] = m
        return self._mini[clave]

    def _imagen_grande(self, ruta, img):
        """La imagen escalada para caber en la zona central, con esquinas redondeadas."""
        clave = (str(ruta), id(img))
        if self._grande[0] != clave:
            area = self.esc.r(IMAGEN)
            self._grande = (clave, estilo.redondear(estilo.caber(img, area.width, area.height), self.esc.n(16)))
        return self._grande[1]

    def dibujar(self, sup, fotos, indice, miniaturas, zona, aviso_texto="", resaltado=None, desplazamiento=0):
        """'desplazamiento': px de pantalla que el dedo arrastra la imagen al deslizar."""
        e = self.esc
        sup.fill((0, 0, 0))
        if not fotos:
            return
        ruta = fotos[indice]
        area = e.r(IMAGEN)
        grande = miniaturas.superficie(ruta, "vista")
        if grande:
            img = self._imagen_grande(ruta, grande)
            sup.blit(img, img.get_rect(center=(area.centerx + round(desplazamiento), area.centery)))
        else:
            t = self.fuente.render("Cargando..." if grande is None else "No se puede abrir esta imagen",
                                   True, (180, 186, 196))
            sup.blit(t, t.get_rect(center=area.center))
        zona(area, "foto_pasar")
        # Miniaturas: tres anteriores a la izquierda; la actual y dos más a la derecha.
        for columna, desde in ((COLUMNA_IZQ, indice - 3), (COLUMNA_DER, indice)):
            for j, y in enumerate(MINIATURAS_Y):
                n = desde + j
                r = e.r(pygame.Rect(columna, y, *MINIATURA))
                if 0 <= n < len(fotos):
                    img = miniaturas.superficie(fotos[n], "imagen")
                    sup.blit(self._miniatura(fotos[n], img, n == indice), r)
                    if n != indice:
                        zona(r.inflate(e.n(10), e.n(10)), ("foto_ir", n))
                else:
                    sup.blit(self.hueco, r)
        r = self.borrar.dibujar(sup, e.p(BORRAR), resaltado == "foto_borrar")
        zona(r.inflate(e.n(20), e.n(20)), "foto_borrar")
        nombre = estilo.recortar(self.fuente, Path(ruta).name, e.n(700))
        t = self.fuente.render(f"{nombre} · {indice + 1} / {len(fotos)}", True, BLANCO)
        sup.blit(t, t.get_rect(center=e.p((640, PIE_Y))))
        if aviso_texto:
            aviso(sup, aviso_texto, self.fuente_aviso, e.p((0, 610))[1])
