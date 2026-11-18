"""Contraseña Wi-Fi (entrega v2, 6.7): campo de contraseña y teclado táctil de vidrio.

Cabecera magenta con Tornar y el nombre de la red, campo blanco redondeado con
'Mostrar' y, debajo, las teclas de vidrio; la pulsada pasa a violeta y 'Conectar'
es el botón principal magenta. Cada distribución (minúsculas, mayúsculas, símbolos)
se pinta una vez en una superficie opaca; al pulsar solo se copia la tecla violeta.
"""
import pygame
import estilo
from estilo import BLANCO, AZUL_OSCURO, MAGENTA, VIOLETA
from interfaz_inicio import Escala, BarraSuperior, aviso, fuente_aviso, fondo_magenta
from interfaz_redes import banda

LARGO_MAXIMO = 63                         # WPA: de 8 a 63 caracteres
ZONA_CAMPO = pygame.Rect(0, 112, 1280, 86)   # franja magenta del campo (px del diseño)
CAMPO = pygame.Rect(28, 124, 1224, 54)
HUECO = 13
FILAS = [  # (y, x inicial, x final) de cada fila de teclas
    (212, 147, 1133), (290, 147, 1133), (368, 147, 1133), (446, 95, 1185), (524, 79, 1201)]
ALTO_TECLA = 63

# (valor, peso). Valores especiales: mayus, borrar, modo, espacio, conectar.
LETRAS = [
    [(c, 1) for c in "1234567890"],
    [(c, 1) for c in "qwertyuiop"],
    [(c, 1) for c in "asdfghjklñ"],
    [("mayus", 1.6)] + [(c, 1) for c in "zxcvbnm-"] + [("borrar", 1.6)],
    [("modo", 1.6), ("@", 1), (".", 1), ("espacio", 4.82), ("_", 1), ("conectar", 2.75)],
]
SIMBOLOS = [
    [(c, 1) for c in "1234567890"],
    [(c, 1) for c in "!@#$%^&*()"],
    [(c, 1) for c in "-_=+[]{};:"],
    [("'", 1.6)] + [(c, 1) for c in "\",./|~`?"] + [("borrar", 1.6)],
    [("modo", 1.6), ("<", 1), (">", 1), ("espacio", 4.82), ("\\", 1), ("conectar", 2.75)],
]


def distribucion(simbolos):
    return SIMBOLOS if simbolos else LETRAS


def teclas(simbolos):
    """[(valor, rect en px del diseño)] de la distribución."""
    salida = []
    for (y, x0, x1), fila in zip(FILAS, distribucion(simbolos)):
        unidad = (x1 - x0 - HUECO * (len(fila) - 1)) / sum(p for _, p in fila)
        x = x0
        for valor, peso in fila:
            ancho = unidad * peso
            salida.append((valor, pygame.Rect(round(x), y, round(ancho), ALTO_TECLA)))
            x += ancho + HUECO
    return salida


class PantallaClave:
    def __init__(self, tam):
        self.esc = e = Escala(tam)
        self.tam = tam
        self.barra = BarraSuperior(e, tam[0])
        self.fuente = estilo.fuente(e.n(30), "Medium")
        self.fuente_especial = estilo.fuente(e.n(22), "Medium")
        self.fuente_conectar = estilo.fuente(e.n(24), "SemiBold")
        self.fuente_campo = estilo.fuente(e.n(26), "Bold")
        self.fuente_ver = estilo.fuente(e.n(20), "SemiBold")
        self.fuente_titulo = estilo.fuente(e.n(25), "SemiBold")
        self.fuente_aviso = fuente_aviso(e)
        # Fondo: magenta arriba (cabecera y campo) y blanco bajo el campo.
        self.fondo = pygame.Surface(tam).convert()
        self.fondo.fill(BLANCO)
        magenta = fondo_magenta(tam, e)
        abajo = e.p((0, ZONA_CAMPO.bottom))[1]
        self.fondo.blit(magenta, (0, 0), (0, 0, tam[0], abajo))
        self.fondo.blit(self.barra.fondo, (0, 0))
        r = e.r(CAMPO)
        campo = pygame.Surface(r.size, pygame.SRCALPHA)
        pygame.draw.rect(campo, BLANCO, campo.get_rect(), border_radius=r.height // 2)
        img, pos = estilo.con_sombra(campo, r.height // 2, e.n(2), e.n(5), (80, 0, 90, 60))
        self.fondo.blit(img, (r.x - pos[0], r.y - pos[1]))
        self._teclados = {}
        self._teclas = {}
        self._titulo = (None, None)

    def _tecla(self, valor, w, h, mayus=False, simbolos=False):
        """Botón de una tecla (con su estado pulsado), guardado por tamaño y estado."""
        letra = len(valor) == 1
        clave = (valor, w, h, mayus and letra, simbolos)
        if clave not in self._teclas:
            if valor == "conectar":
                b = estilo.Boton(w, h, self.esc.n(11), texto="Conectar", fuente_texto=self.fuente_conectar,
                                 tipo="principal")
            elif valor in ("mayus", "borrar"):
                svg = "icono-mayus.svg" if valor == "mayus" else "icono-borrar.svg"
                b = estilo.Boton(w, h, self.esc.n(11), glifo=svg, lado_glifo=h * .45)
            else:
                texto = {"modo": "abc" if simbolos else "?123", "espacio": "espacio"}.get(valor)
                f = self.fuente_especial if texto else self.fuente
                texto = texto or (valor.upper() if clave[3] else valor)
                b = estilo.Boton(w, h, self.esc.n(11), texto=texto, fuente_texto=f)
            self._teclas[clave] = b
        return self._teclas[clave]

    def teclado(self, mayus, simbolos):
        """Distribución completa pintada una vez, opaca sobre blanco."""
        clave = (mayus, simbolos)
        if clave not in self._teclados:
            e = self.esc
            sup = pygame.Surface(self.tam).convert()
            sup.fill(BLANCO)
            for valor, rect in teclas(simbolos):
                r = e.r(rect)
                # Mayúsculas activadas: la tecla se queda violeta.
                self._tecla(valor, r.width, r.height, mayus, simbolos).dibujar(
                    sup, r.center, valor == "mayus" and mayus)
            self._teclados[clave] = sup
        return self._teclados[clave]

    def _titulo_red(self, ssid):
        if self._titulo[0] != ssid:
            texto = estilo.recortar(self.fuente_titulo, f"Contraseña de {ssid}", self.esc.n(1000))
            self._titulo = (ssid, self.fuente_titulo.render(texto, True, BLANCO))
        return self._titulo[1]

    def dibujar(self, sup, ssid, texto, ver, mayus, simbolos, zona, aviso_texto="",
                resaltado=None, ocupado=False, hora=""):
        """'ocupado': conectando; el teclado no responde."""
        e = self.esc
        arriba = e.p((0, ZONA_CAMPO.bottom))[1]
        sup.blit(self.teclado(mayus, simbolos), (0, arriba), (0, arriba, sup.get_width(), sup.get_height() - arriba))
        sup.blit(self.fondo, (0, 0), (0, 0, sup.get_width(), arriba))
        banda(sup, e, self._titulo_red(ssid))
        # Campo: la clave oculta con puntos (o a la vista), el cursor y 'Mostrar'.
        r = e.r(CAMPO)
        boton = self.fuente_ver.render("Ocultar" if ver else "Mostrar", True, VIOLETA)
        rect_ver = boton.get_rect(midright=(r.right - e.n(24), r.centery))
        sup.blit(boton, rect_ver)
        visible = texto if ver else "•" * len(texto)
        t = self.fuente_campo.render(visible, True, estilo.NEGRO)
        x = r.x + e.n(26)
        hueco = rect_ver.x - e.n(30) - x
        sup.blit(t, (x, r.centery - t.get_height() // 2), pygame.Rect(max(0, t.get_width() - hueco), 0, hueco, t.get_height()))
        cursor_x = x + min(t.get_width(), hueco) + e.n(4)
        pygame.draw.rect(sup, MAGENTA, (cursor_x, r.centery - e.n(15), max(2, e.n(3)), e.n(30)))
        if not texto:
            p = self.fuente_especial.render("Escribe la contraseña", True, (150, 156, 168))
            sup.blit(p, (cursor_x + e.n(12), r.centery - p.get_height() // 2))
        if not ocupado:
            zona(rect_ver.inflate(e.n(40), e.n(30)), ("tecla", "ver"))
            for valor, rect in teclas(simbolos):
                tr = e.r(rect)
                zona(tr.inflate(e.n(HUECO), e.n(HUECO)), ("tecla", valor))
                if resaltado == ("tecla", valor):
                    self._tecla(valor, tr.width, tr.height, mayus, simbolos).dibujar(sup, tr.center, True)
        self.barra.dibujar(sup, zona, hora)
        if aviso_texto:                       # sobre el campo: no tapa el teclado
            aviso(sup, aviso_texto, self.fuente_aviso, r.centery)
