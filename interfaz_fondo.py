"""Fondo de pantalla (Configuración): vista previa, deslizables de tono, saturación y
brillo, y la lista de fondos.

Mismo estilo que Configuración y Redes (entrega v2): fondo magenta, banda con Tornar y
título, filas en blanco y la elegida (o pulsada) en violeta; 'Restablecer' es el botón
principal magenta.
"""
import colorsys
import pygame
import estilo
from estilo import BLANCO, VIOLETA_CLARO, mezcla
from interfaz_inicio import (Escala, BarraSuperior, aviso, fuente_aviso, fondo_magenta, fila_pulsada,
                             _difuminar, _mezcla, _aclarar, _oscurecer)
from interfaz_redes import banda, BANDA
import fondo as fondos

LISTA_X = 720                                             # px del diseño
FILA = 64
LISTA_ARRIBA = BANDA.bottom + 1
VISTA = pygame.Rect(60, 134, 480, 270)                    # vista previa 16:9
DESLIZABLES = [                                           # (tipo, etiqueta, y de la pista)
    ("fondo_h", "Tono", 462),
    ("fondo_s", "Saturación", 532),
    ("fondo_v", "Brillo", 602),
]
PISTA_X, PISTA_ANCHO, PISTA_ALTO = 60, 480, 12
RESTABLECER = pygame.Rect(380, 640, 160, 46)


def fraccion(tipo, f):
    """Valor del fondo (tono en grados, saturación y brillo como factor) <-> 0..1."""
    return {"fondo_h": f.tono / 360 + .5, "fondo_s": f.saturacion / 2, "fondo_v": f.brillo / 2}[tipo]


def valor(tipo, x):
    return {"fondo_h": x * 360 - 180, "fondo_s": x * 2, "fondo_v": x * 2}[tipo]


def texto_valor(tipo, f):
    if tipo == "fondo_h":
        return f"{f.tono:+.0f}°"
    return f"{(f.saturacion if tipo == 'fondo_s' else f.brillo) * 100:.0f} %"


class PantallaFondo:
    def __init__(self, tam):
        self.esc = e = Escala(tam)
        self.tam = w, h = tam
        self.barra = BarraSuperior(e, w)
        self.fondo = fondo_magenta(tam, e)
        self.fondo.blit(self.barra.fondo, (0, 0))
        banda(self.fondo, e, estilo.fuente(e.n(25), "SemiBold").render("Fondo de pantalla", True, BLANCO))
        # Separación entre la columna de ajustes y la lista.
        x0 = e.p((LISTA_X, 0))[0]
        arriba = e.p((0, LISTA_ARRIBA))[1]
        linea = pygame.Surface((1, h - arriba), pygame.SRCALPHA)
        linea.fill((255, 255, 255, 70))
        self.fondo.blit(linea, (x0 - 1, arriba))
        self.fuente = estilo.fuente(e.n(21), "SemiBold")
        self.fuente_peq = estilo.fuente(e.n(18), "SemiBold")
        self.fuente_tipo = estilo.fuente(e.n(16), "Medium")
        self.fuente_aviso = fuente_aviso(e)
        # Pistas de los deslizables: el color de cada una explica lo que hace.
        self.pistas = {}
        for tipo, _, y in DESLIZABLES:
            r = e.r(pygame.Rect(PISTA_X, y - PISTA_ALTO // 2, PISTA_ANCHO, PISTA_ALTO))
            pista = pygame.Surface(r.size, pygame.SRCALPHA)
            for x in range(r.width):
                t = x / max(1, r.width - 1)
                if tipo == "fondo_h":
                    color = tuple(round(v * 255) for v in colorsys.hsv_to_rgb((t + .5) % 1, .75, 1))
                elif tipo == "fondo_s":
                    color = mezcla((170, 170, 176), (206, 66, 206), t)
                else:
                    color = mezcla((20, 10, 24), (255, 255, 255), t)
                pygame.draw.line(pista, color, (x, 0), (x, r.height))
            forma = pygame.Surface(r.size, pygame.SRCALPHA)
            pygame.draw.rect(forma, (255, 255, 255, 255), forma.get_rect(), border_radius=r.height // 2)
            pista.blit(forma, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
            pygame.draw.rect(pista, (255, 255, 255, 160), pista.get_rect(), max(1, e.n(1.5)), border_radius=r.height // 2)
            self.pistas[tipo] = (pista, r)
        self.tirador = estilo.tirador(e.n(30), e.n(3.5))
        self.lado_tirador = e.n(30)
        b = e.r(RESTABLECER)
        self.restablecer = estilo.Boton(b.width, b.height, e.n(12), texto="Restablecer",
                                        fuente_texto=self.fuente_peq, tipo="principal")
        self.iconos = {k: estilo.icono(svg, e.n(30), BLANCO) for k, svg in
                       (("Imagen", "icono-fondo.svg"), ("GIF", "icono-video.svg"),
                        ("Vídeo", "icono-video.svg"), (None, "icono-sin.svg"))}
        self.fila_alto = e.n(FILA)
        self.pulsada, self.halo = fila_pulsada(w - x0, self.fila_alto)
        self.separador = pygame.Surface((w - x0, 1), pygame.SRCALPHA)
        self.separador.fill((255, 255, 255, 46))
        self._filas = {}

    def _contenido(self, nombre, tipo):
        """Icono, nombre y tipo de una fila, en blanco (transparente)."""
        clave = (nombre, tipo)
        if clave not in self._filas:
            if len(self._filas) > 200:
                self._filas.clear()
            e = self.esc
            w = self.tam[0] - e.p((LISTA_X, 0))[0]
            s = pygame.Surface((w, self.fila_alto), pygame.SRCALPHA)
            icono = self.iconos[tipo]
            s.blit(icono, icono.get_rect(center=(e.n(40), self.fila_alto // 2)))
            t_tipo = self.fuente_tipo.render(tipo or "", True, (250, 235, 250))
            s.blit(t_tipo, t_tipo.get_rect(midright=(w - e.n(28), self.fila_alto // 2)))
            texto = estilo.recortar(self.fuente, nombre, w - e.n(76) - t_tipo.get_width() - e.n(46))
            sombra_t = self.fuente.render(texto, True, (90, 20, 90))
            t = self.fuente.render(texto, True, BLANCO)
            s.blit(sombra_t, sombra_t.get_rect(midleft=(e.n(76) + 1, self.fila_alto // 2 + 2)))
            s.blit(t, t.get_rect(midleft=(e.n(76), self.fila_alto // 2)))
            self._filas[clave] = s.convert_alpha()
        return self._filas[clave]

    def _elementos(self, fondos_lista):
        return [(-1, "Sin fondo", None)] + [(i, p.name, fondos.TIPO[p.suffix.lower()])
                                            for i, p in enumerate(fondos_lista)]

    def maximo(self, n):
        return max(0.0, (n + 1) * FILA + 20 - (720 - LISTA_ARRIBA))

    def dibujar(self, sup, f, fondos_lista, elegido, desplazamiento, zona, aviso_texto="",
                resaltado=None, tocable=True, hora=""):
        """'f': el Fondo; 'elegido': índice del fondo actual en la lista (-1: sin fondo)."""
        e = self.esc
        sup.blit(self.fondo, (0, 0))
        # Lista a la derecha (desplazable).
        x0 = e.p((LISTA_X, 0))[0]
        arriba = e.p((0, LISTA_ARRIBA))[1]
        sup.set_clip(pygame.Rect(x0, arriba, self.tam[0] - x0, self.tam[1] - arriba))
        for n, (i, nombre, tipo) in enumerate(self._elementos(fondos_lista)):
            y = arriba + round((n * FILA - desplazamiento) * e.k)
            if y + self.fila_alto <= arriba or y >= self.tam[1]:
                continue
            if i == elegido or resaltado == ("fondo_elegir", i):
                sup.blit(self.pulsada, (x0, y - self.halo))
            else:
                sup.blit(self.separador, (x0, y + self.fila_alto - 1))
            sup.blit(self._contenido(nombre, tipo), (x0, y))
            if tocable and y >= arriba - 1:
                zona(pygame.Rect(x0, y, self.tam[0] - x0, self.fila_alto).clip(sup.get_rect()), ("fondo_elegir", i))
        sup.set_clip(None)
        # Vista previa con marco blanco.
        r = e.r(VISTA)
        pygame.draw.rect(sup, BLANCO, r.inflate(e.n(8), e.n(8)), border_radius=e.n(12))
        imagen = f.superficie(r.size)
        if imagen is not None:
            sup.blit(imagen, r)
        else:
            pygame.draw.rect(sup, (244, 236, 246), r)
            texto = ("Cargando..." if f.ruta and not f.error else (f.error or "Sin fondo"))
            t = self.fuente.render(texto, True, (150, 110, 160))
            sup.blit(t, t.get_rect(center=r.center))
        # Deslizables.
        for tipo, etiqueta, y in DESLIZABLES:
            pista, pr = self.pistas[tipo]
            sup.blit(pista, pr)
            et = self.fuente_peq.render(etiqueta, True, BLANCO)
            sup.blit(et, et.get_rect(bottomleft=(pr.x, pr.y - e.n(10))))
            va = self.fuente_peq.render(texto_valor(tipo, f), True, (255, 228, 255))
            sup.blit(va, va.get_rect(bottomright=(pr.right, pr.y - e.n(10))))
            img, d = self.tirador
            x = pr.x + round(max(0, min(1, fraccion(tipo, f))) * pr.width)
            sup.blit(img, (x - d[0] - self.lado_tirador // 2, pr.centery - d[1] - self.lado_tirador // 2))
            zona(pr.inflate(e.n(40), e.n(44)), (tipo, pr))
        b = e.r(RESTABLECER)
        self.restablecer.dibujar(sup, b.center, resaltado == "fondo_restablecer")
        zona(b.inflate(e.n(16), e.n(16)), "fondo_restablecer")
        self.barra.dibujar(sup, zona, hora)
        if aviso_texto:
            aviso(sup, aviso_texto, self.fuente_aviso, sup.get_height() - e.n(40))
