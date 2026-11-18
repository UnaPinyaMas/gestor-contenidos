"""Estilo final de TerraHub (entrega de diseño v2): paleta, tipografía, vidrio y burbujas.

Paleta: blanco (fondo), negro (logo, barra superior y texto) y magenta #CE42CE para
todo lo que se toca. Apoyo: azul oscuro #2B3442 (glifos de los controles), vidrio
#D3DEEA (degradado de los botones) y violeta #6C58FC (estado pulsado).

Todo se monta una vez como imagen (con su sombra) y en cada fotograma solo se copia:
el pygame de la Raspberry no usa NEON y mezclar transparencias o difuminar por
fotograma es lo más lento.
"""
import io
import re
from pathlib import Path
import numpy as np
import pygame

BASE = Path(__file__).resolve().parent
INTERFAZ = BASE / "recursos" / "interfaz"
FUENTES = BASE / "recursos" / "fuentes"

BLANCO = (255, 255, 255)
NEGRO = (0, 0, 0)
TEXTO = (17, 17, 17)
MAGENTA = (206, 66, 206)            # #CE42CE
MAGENTA_CLARO = (224, 111, 224)     # arriba del degradado del botón principal
AZUL_OSCURO = (43, 52, 66)          # #2B3442
VIDRIO = (211, 222, 234)            # #D3DEEA
VIOLETA = (108, 88, 252)            # #6C58FC
VIOLETA_CLARO = (135, 119, 255)     # arriba del degradado pulsado
BORDE_VIDRIO = (176, 187, 200)
GRIS = (100, 108, 120)              # textos secundarios
PISTA = (214, 222, 234)             # pistas de las barras y huecos sin imagen
NEGRO_SUAVE = (26, 29, 36)          # huecos del visor de imágenes


def mezcla(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


# --- tipografía ------------------------------------------------------------------------
_fuentes = {}


def _olvidar_fuentes():
    _fuentes.clear()


def fuente(tam, peso="SemiBold"):
    """Inter (OFL, recursos/fuentes) a 'tam' px; si falta, la de pygame.

    Tras pygame.quit() las fuentes ya no valen (usarlas en pygame 2.6 cuelga el
    proceso): se olvidan al cerrar pygame. pygame.quit() también vacía su lista de
    funciones de cierre, así que se registra de nuevo al cargar la primera.
    """
    clave = (max(6, round(tam)), peso)
    if not _fuentes:
        pygame.register_quit(_olvidar_fuentes)
    if clave not in _fuentes:
        try:
            _fuentes[clave] = pygame.font.Font(str(FUENTES / f"Inter-{peso}.ttf"), clave[0])
        except (OSError, pygame.error):
            _fuentes[clave] = pygame.font.Font(None, round(clave[0] * 1.35))
    return _fuentes[clave]


def recortar(f, texto, ancho):
    """Texto acortado con '...' para que quepa en 'ancho' px."""
    if f.size(texto)[0] <= ancho:
        return texto
    while len(texto) > 1 and f.size(texto + "...")[0] > ancho:
        texto = texto[:-1]
    return texto.rstrip() + "..."


# --- imágenes del diseño ------------------------------------------------------------
def icono(nombre, lado, color=AZUL_OSCURO):
    """Icono SVG de trazo (recursos/interfaz) a 'lado' px de ancho y del color dado."""
    texto = (INTERFAZ / nombre).read_text(encoding="utf-8")
    hexa = "#%02X%02X%02X" % tuple(color[:3])
    texto = re.sub(r'(stroke|fill)="(?!none|url)[^"]+"', lambda m: f'{m.group(1)}="{hexa}"', texto)
    w = float(re.search(r'width="([\d.]+)"', texto).group(1))
    h = float(re.search(r'height="([\d.]+)"', texto).group(1))
    f = lado / w
    texto = re.sub(r'width="[\d.]+"', f'width="{w * f:.2f}"', texto, count=1)
    texto = re.sub(r'height="[\d.]+"', f'height="{h * f:.2f}"', texto, count=1)
    return pygame.image.load(io.BytesIO(texto.encode("utf-8")), "i.svg").convert_alpha()


def imagen(nombre, alto=None, ancho=None):
    """PNG del diseño (logotipo, títulos en Zrnic) escalado a un alto o un ancho en px."""
    img = pygame.image.load(str(INTERFAZ / nombre)).convert_alpha()
    if alto:
        tam = (max(1, round(img.get_width() * alto / img.get_height())), max(1, round(alto)))
    elif ancho:
        tam = (max(1, round(ancho)), max(1, round(img.get_height() * ancho / img.get_width())))
    else:
        return img
    return pygame.transform.smoothscale(img, tam)


# --- formas ------------------------------------------------------------------------
def _rgba(c):
    return tuple(c) if len(c) == 4 else (*c, 255)


def degradado(w, h, arriba, abajo, radio=0):
    """Rectángulo (redondeado si 'radio') con degradado vertical; colores RGB o RGBA."""
    w, h = max(1, round(w)), max(1, round(h))
    arriba, abajo = _rgba(arriba), _rgba(abajo)
    sup = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(h):
        pygame.draw.line(sup, mezcla(arriba, abajo, y / max(1, h - 1)), (0, y), (w - 1, y))
    if radio:
        forma = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(forma, (255, 255, 255, 255), forma.get_rect(), border_radius=round(radio))
        sup.blit(forma, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    return sup


def difuminar(sup, radio):
    """Desenfoque aproximado (reducir y ampliar), para sombras."""
    w, h = sup.get_size()
    f = max(2, round(radio))
    peq = pygame.transform.smoothscale(sup, (max(1, w // f), max(1, h // f)))
    return pygame.transform.smoothscale(peq, (w, h))


def sombra(ancho, alto, radio, dy, desenfoque, color):
    """Sombra de un rectángulo redondeado (o círculo): (superficie, desplazamiento respecto
    al centro de la forma)."""
    margen = round(desenfoque * 2.5)
    s = pygame.Surface((ancho + margen * 2, alto + margen * 2), pygame.SRCALPHA)
    pygame.draw.rect(s, color, (margen, margen, ancho, alto), border_radius=radio)
    return difuminar(s, desenfoque).convert_alpha(), (-s.get_width() // 2, -s.get_height() // 2 + dy)


def con_sombra(forma, radio, dy, desenfoque, color):
    """Forma con su sombra debajo en una sola superficie: (superficie, posición de la forma)."""
    s, d = sombra(forma.get_width(), forma.get_height(), radio, round(dy), max(1, desenfoque), color)
    w = max(s.get_width(), forma.get_width())
    h = max(s.get_height() + abs(d[1] + s.get_height() // 2) * 2, forma.get_height())
    sup = pygame.Surface((w, h), pygame.SRCALPHA)
    cx, cy = w // 2, h // 2
    sup.blit(s, (cx + d[0], cy + d[1]))
    pos = (cx - forma.get_width() // 2, cy - forma.get_height() // 2)
    sup.blit(forma, pos)
    return sup.convert_alpha(), pos


# --- controles -----------------------------------------------------------------------
SOMBRA_VIDRIO = (13, 31, 64, 60)


def _recortar_forma(sup, radio):
    """Deja 'sup' con la forma del botón (lo que se haya salido, fuera)."""
    forma = pygame.Surface(sup.get_size(), pygame.SRCALPHA)
    pygame.draw.rect(forma, (255, 255, 255, 255), forma.get_rect(), border_radius=round(radio))
    sup.blit(forma, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    return sup


def base_boton(w, h, radio, tipo="vidrio", pulsado=False):
    """Fondo de un botón (sin sombra). Tipos: 'vidrio' (blanco -> #D3DEEA), 'principal'
    (magenta) y 'oscuro' (reproducir del audio). Pulsado: violeta para todos."""
    return _recortar_forma(_base_boton(w, h, radio, tipo, pulsado), radio)


def _base_boton(w, h, radio, tipo, pulsado):
    grosor = max(1, round(h / 48))
    if pulsado:
        base = degradado(w, h, VIOLETA_CLARO, VIOLETA, radio)
        # Sombra interior arriba: el botón parece hundido.
        hondo = degradado(w, max(2, h // 5), (40, 20, 120, 70), (40, 20, 120, 0), radio)
        base.blit(hondo, (0, 0))
        pygame.draw.rect(base, (255, 255, 255, 70), base.get_rect(), grosor, border_radius=round(radio))
        return base
    if tipo == "principal":
        base = degradado(w, h, MAGENTA_CLARO, MAGENTA, radio)
        pygame.draw.rect(base, (255, 255, 255, 60), base.get_rect(), grosor, border_radius=round(radio))
        return base
    if tipo == "oscuro":
        base = degradado(w, h, (74, 83, 99), (31, 37, 48), radio)
        luz = degradado(w * .8, h * .45, (255, 255, 255, 60), (255, 255, 255, 0), radio)
        base.blit(luz, (w * .1, h * .05))
        return base
    base = degradado(w, h, BLANCO, VIDRIO, radio)
    luz = degradado(w - 4 * grosor, h * .5, (255, 255, 255, 190), (255, 255, 255, 0), max(0, radio - grosor))
    base.blit(luz, (2 * grosor, grosor))
    pygame.draw.rect(base, BORDE_VIDRIO, base.get_rect(), grosor, border_radius=round(radio))
    return base


class Boton:
    """Botón con sus dos estados (normal y pulsado) ya montados con sombra.

    Medidas en px de pantalla. 'glifo' es un SVG de recursos/interfaz; 'texto' un
    rótulo. El glifo es azul oscuro sobre vidrio y blanco en los demás casos.
    """
    def __init__(self, ancho, alto, radio=None, glifo=None, lado_glifo=None, texto=None,
                 fuente_texto=None, tipo="vidrio", sombra_px=None):
        w, h = max(1, round(ancho)), max(1, round(alto))
        r = round(min(w, h) / 2 if radio is None else radio)
        self.tam = (w, h)
        s = sombra_px if sombra_px is not None else max(2, h / 14)
        self.imgs = []
        for pulsado in (False, True):
            base = base_boton(w, h, r, tipo, pulsado)
            color = BLANCO if (pulsado or tipo != "vidrio") else AZUL_OSCURO
            if glifo:
                g = icono(glifo, lado_glifo or h * .5, color)
                base.blit(g, g.get_rect(center=(w // 2, h // 2)))
            if texto:
                t = fuente_texto.render(texto, True, color)
                base.blit(t, t.get_rect(center=(w // 2, h // 2)))
            if pulsado:
                img = con_sombra(base, r, s * .3, s * .5, (60, 40, 160, 50))
            elif tipo == "principal":
                img = con_sombra(base, r, s * .5, s, (150, 40, 150, 70))
            else:
                img = con_sombra(base, r, s * .5, s, SOMBRA_VIDRIO)
            self.imgs.append(img)

    def rect(self, centro):
        r = pygame.Rect(0, 0, *self.tam)
        r.center = (round(centro[0]), round(centro[1]))
        return r

    def dibujar(self, sup, centro, pulsado=False):
        img, (ox, oy) = self.imgs[bool(pulsado)]
        r = self.rect(centro)
        sup.blit(img, (r.x - ox, r.y - oy))
        return r


# --- burbujas magenta ------------------------------------------------------------------
_FILTRO = re.compile(r'\sfilter="[^"]*"')


def glifo_burbuja(nombre, diametro):
    """Solo el glifo blanco de una burbuja del Figma (recursos/interfaz/burbuja-*.svg),
    escalado para una esfera de 'diametro' px: (imagen, posición respecto al centro)."""
    texto = (INTERFAZ / nombre).read_text(encoding="utf-8")
    cx, cy, r = (float(v) for v in re.search(r'<circle cx="([\d.]+)" cy="([\d.]+)" r="([\d.]+)"', texto).groups())
    w = float(re.search(r'width="([\d.]+)"', texto).group(1))
    h = float(re.search(r'height="([\d.]+)"', texto).group(1))
    grupo = re.search(r'<g id="glifo".*?</g>', texto, re.S).group(0)
    grupo = _FILTRO.sub("", grupo)
    f = diametro / (2 * r)
    svg = (f'<svg width="{w * f:.2f}" height="{h * f:.2f}" viewBox="0 0 {w} {h}" fill="none" '
           f'xmlns="http://www.w3.org/2000/svg">{grupo}</svg>')
    img = pygame.image.load(io.BytesIO(svg.encode("utf-8")), "g.svg").convert_alpha()
    return img, (-round(cx * f), -round(cy * f))


def esfera(diametro, pulsada=False, aro=0):
    """Esfera magenta de vidrio (bombolla de secció): degradado radial, borde más oscuro
    abajo y brillo elíptico arriba. Se calcula con numpy una sola vez.

    'aro': grosor de un borde blanco (el círculo de la barra superior lo lleva).
    """
    d = max(4, round(diametro))
    yy, xx = np.mgrid[0:d, 0:d].astype(np.float32) + .5
    c = d / 2
    nx, ny = (xx - c) / c, (yy - c) / c
    rr = np.sqrt(nx * nx + ny * ny)
    # Luz desde un poco por encima del centro: claro en el centro, oscuro en el borde.
    u = np.clip(np.sqrt(nx * nx + (ny + .12) ** 2) / 1.12, 0, 1)
    puntos = np.array([0, .45, .78, 1.0], np.float32)
    colores = np.array([(240, 146, 240), (218, 92, 218), (201, 64, 201), (170, 47, 170)], np.float32)
    rgb = np.stack([np.interp(u, puntos, colores[:, i]) for i in range(3)], -1)
    abajo = (np.clip((ny - .3) / .7, 0, 1) ** 1.6 * np.clip(rr, 0, 1))[..., None]
    rgb = rgb * (1 - .45 * abajo) + np.array((120, 26, 120), np.float32) * .45 * abajo
    # Brillo superior: elipse blanca que se desvanece hacia abajo.
    ex, ey = nx / .70, (ny + .50) / .39
    e = np.sqrt(ex * ex + ey * ey)
    borde_brillo = np.clip((1 - e) / .14, 0, 1)
    fuerza = np.clip(.88 - (ny + .89) / .78 * .55, .25, .88)
    a = (borde_brillo * fuerza)[..., None]
    if pulsada:
        rgb = rgb * .70
        a = a * .55
    rgb = rgb * (1 - a) + 255 * a
    alfa = np.clip((1 - rr) * c + .5, 0, 1)                  # borde suavizado
    if aro:
        en_aro = np.clip((rr - (1 - aro / c)) * c + .5, 0, 1)[..., None]
        rgb = rgb * (1 - en_aro) + 255 * en_aro
    rgba = np.concatenate([np.clip(rgb, 0, 255), (alfa * 255)[..., None]], -1).astype(np.uint8)
    return pygame.image.frombuffer(np.ascontiguousarray(rgba).tobytes(), (d, d), "RGBA").convert_alpha()


def burbuja(diametro, glifo=None, pulsada=False, fondo=None, aro=0):
    """Esfera con sombra suave rosada y, si se da, el glifo de un SVG de burbuja.

    Con 'fondo' (color) devuelve una imagen opaca (más rápida de copiar). Devuelve
    (imagen, posición del centro de la esfera dentro de la imagen).
    """
    d = max(4, round(diametro))
    if pulsada:
        d = round(d * .95)
    bola = esfera(d, pulsada, aro)
    if glifo:
        g, (gx, gy) = glifo_burbuja(glifo, d)
        if pulsada:
            g.fill((235, 215, 235, 255), special_flags=pygame.BLEND_RGBA_MULT)
        bola.blit(g, (d // 2 + gx, d // 2 + gy))
    s, desp = sombra(d, d, d // 2, round(d * .045), max(2, d * .07), (150, 40, 150, 70 if not pulsada else 40))
    w = max(s.get_width(), d)
    h = s.get_height() + abs(desp[1] + s.get_height() // 2) * 2
    img = pygame.Surface((w, max(h, d)), pygame.SRCALPHA)
    centro = (w // 2, img.get_height() // 2)
    img.blit(s, (centro[0] + desp[0], centro[1] + desp[1]))
    img.blit(bola, (centro[0] - d // 2, centro[1] - d // 2))
    if fondo is not None:
        opaca = pygame.Surface(img.get_size()).convert()
        opaca.fill(fondo)
        opaca.blit(img, (0, 0))
        return opaca, centro
    return img.convert_alpha(), centro


# --- piezas de pantalla --------------------------------------------------------------
def subrayado(sup, centro_x, y, ancho, alto):
    """Línea magenta redondeada bajo los títulos."""
    r = pygame.Rect(0, 0, ancho, max(2, alto))
    r.midtop = (centro_x, y)
    pygame.draw.rect(sup, MAGENTA, r, border_radius=r.height // 2)


def aviso(sup, texto, f, y):
    """Mensaje breve (píldora azul oscuro con texto blanco), centrado en 'y'."""
    t = f.render(texto, True, BLANCO)
    caja = t.get_rect(center=(sup.get_width() // 2, y)).inflate(round(t.get_height() * 1.6), round(t.get_height() * .9))
    pygame.draw.rect(sup, AZUL_OSCURO, caja, border_radius=caja.height // 2)
    sup.blit(t, t.get_rect(center=caja.center))


def tirador(lado, borde):
    """Tirador de las barras de progreso: círculo blanco con aro magenta y sombra."""
    lado = max(6, round(lado))
    s = pygame.Surface((lado, lado), pygame.SRCALPHA)
    pygame.draw.circle(s, MAGENTA, (lado // 2, lado // 2), lado // 2)
    pygame.draw.circle(s, BLANCO, (lado // 2, lado // 2), lado // 2 - max(1, round(borde)))
    return con_sombra(s, lado // 2, lado * .06, lado * .12, (13, 31, 64, 70))


class Barra:
    """Barra de progreso: pista, parte llena magenta y tirador. Medidas en px de pantalla."""
    def __init__(self, rect, pista=PISTA, alto_tirador=None):
        self.rect = pygame.Rect(rect)
        self.pista = pista
        self.tirador = tirador(alto_tirador or self.rect.height * 3.4, max(2, self.rect.height * .5))

    def dibujar(self, sup, fraccion, con_tirador=True):
        f = max(0.0, min(1.0, fraccion or 0))
        r = self.rect
        pygame.draw.rect(sup, self.pista, r, border_radius=r.height // 2)
        lleno = round(r.width * f)
        if lleno:
            pygame.draw.rect(sup, MAGENTA, (r.x, r.y, max(r.height, lleno), r.height), border_radius=r.height // 2)
        if con_tirador:
            img, (ox, oy) = self.tirador
            lado = img.get_width() - 2 * ox
            sup.blit(img, (r.x + lleno - lado // 2 - ox, r.centery - lado // 2 - oy))


def cubrir(img, w, h, arriba=.5):
    """Escala 'img' para cubrir w x h (recortando lo que sobre) sin deformarla.
    'arriba' = qué parte se conserva en vertical (0 arriba, .5 centro)."""
    f = max(w / img.get_width(), h / img.get_height())
    tam = (max(1, round(img.get_width() * f)), max(1, round(img.get_height() * f)))
    img = pygame.transform.smoothscale(img, tam)
    x = (tam[0] - w) // 2
    y = round((tam[1] - h) * arriba)
    return img.subsurface(pygame.Rect(x, y, w, h)).copy()


def caber(img, w, h):
    """Escala 'img' para que quepa entera en w x h sin deformarla."""
    f = min(w / img.get_width(), h / img.get_height())
    tam = (max(1, round(img.get_width() * f)), max(1, round(img.get_height() * f)))
    return pygame.transform.smoothscale(img, tam)


def redondear(img, radio):
    """Copia de 'img' con las esquinas redondeadas (transparentes)."""
    img = img.convert_alpha()
    forma = pygame.Surface(img.get_size(), pygame.SRCALPHA)
    pygame.draw.rect(forma, (255, 255, 255, 255), forma.get_rect(), border_radius=round(radio))
    img.blit(forma, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    return img


def circular(img, lado):
    """'img' recortada en círculo de 'lado' px (tipo 'cover')."""
    img = cubrir(img, lado, lado).convert_alpha()
    forma = pygame.Surface((lado, lado), pygame.SRCALPHA)
    pygame.draw.circle(forma, (255, 255, 255, 255), (lado // 2, lado // 2), lado // 2)
    img.blit(forma, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    return img
