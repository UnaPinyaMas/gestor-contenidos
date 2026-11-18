"""Vídeos (entrega v2, 6.11) y reproductor de vídeo a pantalla completa (6.12).

Vídeos: cuadrícula de miniaturas de 3x2 por página (deslizable), con el botón de
reproducir de vidrio, el título y la duración debajo. La rejilla es la misma que la de
Imágenes (sin textos ni botón). El reproductor no lleva barra superior: Tornar, ajustes
(volumen), pausa en el centro y la barra de progreso magenta, que se ocultan solos.
"""
from pathlib import Path
import pygame
import interfaz_video as iv
import estilo
from estilo import BLANCO, MAGENTA, TEXTO, GRIS
from interfaz_inicio import Escala, aviso, fuente_aviso, cabecera_blanca

# Tarjetas (px del diseño).
COLUMNAS = (111, 481, 851)
FILAS_Y = (161, 431)
TARJETA = (319, 179)
POR_PAGINA = len(COLUMNAS) * len(FILAS_Y)
ARRIBA = 135


def paginas(n):
    return max(1, -(-n // POR_PAGINA))


def huecos(e):
    """Rectángulos de pantalla de las tarjetas de una página, en orden."""
    return [e.r(pygame.Rect(x, y, *TARJETA)) for y in FILAS_Y for x in COLUMNAS]


def titulo_bonito(ruta):
    """Nombre de archivo legible: sin extensión ni guiones bajos."""
    return Path(ruta).stem.replace("_", " ").strip()


class Rejilla:
    """Cuadrícula paginada de miniaturas (Vídeos e Imágenes).

    Cada página se monta una vez en una superficie opaca y se vuelve a montar solo cuando
    llega una miniatura nueva. 'tipo' es el de miniaturas.Miniaturas ('video' o 'imagen').
    """
    def __init__(self, tam, titulo, tipo, con_textos):
        self.esc = e = Escala(tam)
        self.tam = tam
        self.tipo = tipo
        self.con_textos = con_textos
        self.fondo, self.barra = cabecera_blanca(tam, e, titulo)
        w, h = huecos(e)[0].size
        self.radio = e.n(14)
        self.play = estilo.Boton(e.n(63), e.n(63), glifo="reproducir-35.svg", lado_glifo=e.n(24)) if con_textos else None
        hueco = estilo.degradado(w, h, (248, 250, 252), (214, 223, 234), self.radio)
        pygame.draw.rect(hueco, (200, 210, 222), hueco.get_rect(), max(1, e.n(1.5)), border_radius=self.radio)
        if not con_textos:                             # Imágenes: icono de foto en el hueco
            ico = estilo.icono("icono-fondo.svg", e.n(30), (150, 160, 175))
            hueco.blit(ico, ico.get_rect(center=(w // 2, h // 2)))
        self.hueco = estilo.con_sombra(hueco, self.radio, e.n(4), e.n(10), (13, 31, 64, 40))
        self.fuente_titulo = estilo.fuente(e.n(17), "SemiBold")
        self.fuente_sub = estilo.fuente(e.n(14), "Regular")
        self.fuente_aviso = fuente_aviso(e)
        self._paginas = {}

    def _tarjeta(self, img):
        """Miniatura en tarjeta redondeada con sombra: (imagen, posición de la tarjeta)."""
        e = self.esc
        w, h = huecos(e)[0].size
        foto = estilo.redondear(estilo.cubrir(img, w, h), self.radio)
        return estilo.con_sombra(foto, self.radio, e.n(4), e.n(10), (13, 31, 64, 50))

    def pagina(self, elementos, n, miniaturas, subtitulo=None):
        """Página n montada (opaca): se rehace si cambia algo de lo que muestra."""
        e = self.esc
        trozo = elementos[n * POR_PAGINA:(n + 1) * POR_PAGINA]
        estado = [(str(p), miniaturas.superficie(p, self.tipo) is not None,
                   subtitulo(p) if subtitulo else None) for p in trozo]
        guardada = self._paginas.get(n)
        if guardada and guardada[0] == estado:
            return guardada[1]
        arriba = e.p((0, ARRIBA))[1]
        hoja = pygame.Surface((self.tam[0], self.tam[1] - arriba)).convert()
        hoja.fill(BLANCO)
        for ruta, rect in zip(trozo, huecos(e)):
            rect = rect.move(0, -arriba)
            img = miniaturas.superficie(ruta, self.tipo)
            if img:
                tarjeta, pos = self._tarjeta(img)
            else:
                tarjeta, pos = self.hueco
            hoja.blit(tarjeta, (rect.x - pos[0], rect.y - pos[1]))
            if self.play:
                self.play.dibujar(hoja, rect.center)
            if self.con_textos:
                t = self.fuente_titulo.render(estilo.recortar(self.fuente_titulo, titulo_bonito(ruta), rect.width),
                                              True, TEXTO)
                hoja.blit(t, (rect.x, rect.bottom + e.n(12)))
                sub = subtitulo(ruta) if subtitulo else None
                if sub:
                    s = self.fuente_sub.render(sub, True, GRIS)
                    hoja.blit(s, (rect.x, rect.bottom + e.n(36)))
        if len(self._paginas) > 12:
            self._paginas.clear()
        self._paginas[n] = (estado, hoja)
        return hoja

    def dibujar(self, sup, elementos, posicion, miniaturas, zona, accion, aviso_texto="", tocable=True,
                hora="", resaltado=None, subtitulo=None, vacio=""):
        """'accion': nombre de la acción de cada tarjeta, p. ej. 'video' -> ('video', i)."""
        e = self.esc
        sup.blit(self.fondo, (0, 0))
        arriba = e.p((0, ARRIBA))[1]
        w = sup.get_width()
        if not elementos:
            t = estilo.fuente(e.n(22), "Medium").render(vacio, True, GRIS)
            sup.blit(t, t.get_rect(center=e.p((640, 400))))
        for n in range(paginas(len(elementos))):
            x = round((n - posicion) * w)
            if -w < x < w:
                sup.blit(self.pagina(elementos, n, miniaturas, subtitulo), (x, arriba))
        if abs(posicion - round(posicion)) < 2e-3:
            p = round(posicion)
            for i, rect in enumerate(huecos(e)):
                indice = p * POR_PAGINA + i
                if indice >= len(elementos):
                    break
                if resaltado == (accion, indice):
                    pygame.draw.rect(sup, MAGENTA, rect.inflate(e.n(8), e.n(8)), max(2, e.n(4)),
                                     border_radius=self.radio + e.n(4))
                    if self.play:
                        self.play.dibujar(sup, rect.center, True)
                if tocable:
                    zona(rect, (accion, indice))
        self.barra.dibujar(sup, zona, hora)
        if aviso_texto:
            aviso(sup, aviso_texto, self.fuente_aviso, sup.get_height() - e.n(50))


class PantallaVideos(Rejilla):
    def __init__(self, tam):
        super().__init__(tam, "titulo-videos.png", "video", con_textos=True)


# --- Reproductor -----------------------------------------------------------------------
BARRA = pygame.Rect(40, 672, 1200, 5)
TIEMPOS_Y = 650
AJUSTES = (1228, 49)
PANEL = pygame.Rect(930, 92, 310, 128)            # panel de ajustes (volumen)
BARRA_VOLUMEN = pygame.Rect(956, 182, 258, 5)


class PantallaVideo:
    """Vídeo a pantalla completa con los controles encima (sin barra superior)."""
    def __init__(self, tam):
        self.esc = e = Escala(tam)
        self.tam = w, h = tam
        self.ajustes = estilo.Boton(e.n(55), e.n(55), glifo="icono-ajustes.svg", lado_glifo=e.n(26))
        self.pausar = estilo.Boton(e.n(80), e.n(80), glifo="pausa.svg", lado_glifo=e.n(46))
        self.reproducir = estilo.Boton(e.n(80), e.n(80), glifo="reproducir-35.svg", lado_glifo=e.n(34))
        self.barra = estilo.Barra(e.r(BARRA), pista=(85, 85, 90), alto_tirador=e.n(24))
        self.volumen = estilo.Barra(e.r(BARRA_VOLUMEN), alto_tirador=e.n(22))
        self.fuente_tiempo = estilo.fuente(e.n(17), "SemiBold")
        self.fuente_panel = estilo.fuente(e.n(17), "SemiBold")
        self.fuente_aviso = fuente_aviso(e)
        self.sombra_arriba = iv.degradado(w, e.n(130), hacia_abajo=False, opacidad=150)
        self.sombra_abajo = iv.degradado(w, e.n(170), hacia_abajo=True, opacidad=190)
        # Sin imagen (cargando o solo audio): negro con un brillo azulado en el centro.
        self.vacio = pygame.Surface(tam).convert()
        self.vacio.fill((0, 0, 0))
        luz = pygame.Surface(tam, pygame.SRCALPHA)
        for i in range(24, 0, -1):
            r = round(min(w, h) * .62 * i / 24)
            pygame.draw.circle(luz, (40, 46, 62, 10), (w // 2, h // 2), r)
        self.vacio.blit(luz, (0, 0))
        r = e.r(PANEL)
        panel = estilo.degradado(r.width, r.height, (255, 255, 255, 240), (225, 233, 242, 240), e.n(16))
        pygame.draw.rect(panel, estilo.BORDE_VIDRIO, panel.get_rect(), max(1, e.n(1.5)), border_radius=e.n(16))
        self.panel = estilo.con_sombra(panel, e.n(16), e.n(5), e.n(12), (0, 0, 0, 90))
        self._textos = {}

    def _texto(self, texto, color=BLANCO, f=None):
        clave = (texto, color, id(f))
        if clave not in self._textos:
            if len(self._textos) > 16:
                self._textos.clear()
            self._textos[clave] = (f or self.fuente_tiempo).render(texto, True, color)
        return self._textos[clave]

    def dibujar(self, sup, imagen, posicion, duracion, pausa, controles, panel, volumen, silencio,
                zona, aviso_texto="", resaltado=None, arrastrando=None):
        """'imagen': el fotograma (o None); 'controles': si se ven; 'panel': ajustes abiertos."""
        e = self.esc
        w, h = self.tam
        if imagen is not None:
            sup.fill((0, 0, 0))
            sup.blit(imagen, imagen.get_rect(center=(w // 2, h // 2)))
        else:
            sup.blit(self.vacio, (0, 0))
        if controles:
            sup.blit(self.sombra_arriba, (0, 0))
            sup.blit(self.sombra_abajo, (0, h - self.sombra_abajo.get_height()))
            r = self.ajustes.dibujar(sup, e.p(AJUSTES), panel or resaltado == "ajustes_video")
            zona(r.inflate(e.n(30), e.n(30)), "ajustes_video")
            boton = self.reproducir if pausa else self.pausar
            r = boton.dibujar(sup, (w // 2, h // 2), resaltado == "pausa")
            zona(r.inflate(e.n(30), e.n(30)), "pausa")
            fraccion = posicion / duracion if duracion else 0
            self.barra.dibujar(sup, fraccion)
            zona(pygame.Rect(0, self.barra.rect.y - e.n(30), w, e.n(60)), ("buscar", self.barra.rect))
            t = self._texto(iv.formato_tiempo(posicion))
            sup.blit(t, t.get_rect(midleft=e.p((BARRA.x, TIEMPOS_Y))))
            t = self._texto(iv.formato_tiempo(duracion))
            sup.blit(t, t.get_rect(midright=e.p((BARRA.right, TIEMPOS_Y))))
            if panel:
                img, pos = self.panel
                rp = e.r(PANEL)
                sup.blit(img, (rp.x - pos[0], rp.y - pos[1]))
                t = self._texto("Volumen", estilo.AZUL_OSCURO, self.fuente_panel)
                sup.blit(t, e.p((956, 116)))
                valor = "Silencio" if silencio else f"{volumen} %"
                t = self._texto(valor, estilo.VIOLETA if not silencio else GRIS, self.fuente_panel)
                rv = t.get_rect(topright=e.p((1214, 116)))
                sup.blit(t, rv)
                zona(rv.inflate(e.n(30), e.n(20)), "silenciar")
                self.volumen.dibujar(sup, 0 if silencio else volumen / 100)
                zona(self.volumen.rect.inflate(e.n(30), e.n(44)), ("volumen", self.volumen.rect))
                zona(rp, "mostrar")                     # dentro del panel: nada más
            # Un toque que falla por poco en las franjas de controles no los esconde.
            zona(pygame.Rect(0, h - e.n(110), w, e.n(110)), "mostrar")
            zona(pygame.Rect(0, 0, w, e.n(100)), "mostrar")
        zona(sup.get_rect(), "controles")
        if aviso_texto:
            aviso(sup, aviso_texto, self.fuente_aviso, h // 2 + e.n(90))
