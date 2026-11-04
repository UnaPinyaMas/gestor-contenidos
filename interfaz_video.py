"""Iconos y piezas del reproductor, al estilo de YouTube, dibujados con Pygame."""
import math
import pygame

BLANCO = (255, 255, 255)
ROJO_YT = (255, 0, 0)
GRIS_BARRA = (110, 110, 110)


def formato_tiempo(segundos):
    segundos = max(0, int(segundos or 0))
    h, resto = divmod(segundos, 3600)
    m, s = divmod(resto, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def degradado(ancho, alto, hacia_abajo, opacidad=210):
    """Franja negra translúcida que se oscurece hacia el borde de la pantalla."""
    franja = pygame.Surface((ancho, alto), pygame.SRCALPHA)
    for y in range(alto):
        t = y / (alto - 1)
        alpha = int(opacidad * (t if hacia_abajo else 1 - t))
        pygame.draw.line(franja, (0, 0, 0, alpha), (0, y), (ancho - 1, y))
    return franja


def play(sup, centro, tam=14, color=BLANCO):
    x, y = centro
    pygame.draw.polygon(sup, color, [(x - tam * .7, y - tam), (x - tam * .7, y + tam),
                                     (x + tam, y)])


def pausa(sup, centro, tam=14, color=BLANCO):
    x, y = centro
    ancho = max(3, round(tam * .45))
    for dx in (-tam * .55, tam * .55):
        pygame.draw.rect(sup, color, (round(x + dx - ancho / 2), y - tam, ancho, tam * 2))


def saltar(sup, centro, fuente, adelante, radio=15, color=BLANCO):
    """Flecha circular con '10' dentro: atrás (⟲) o adelante (⟳)."""
    x, y = centro
    rect = pygame.Rect(0, 0, radio * 2, radio * 2)
    rect.center = centro
    # Arco abierto por arriba; la punta queda en el extremo del sentido de giro.
    pygame.draw.arc(sup, color, rect, math.radians(120), math.radians(420), 3)
    a = math.radians(120 if adelante else 60)
    px, py = x + radio * math.cos(a), y - radio * math.sin(a)
    tx, ty = (math.sin(a), math.cos(a)) if adelante else (-math.sin(a), -math.cos(a))
    nx, ny = math.cos(a), -math.sin(a)
    pygame.draw.polygon(sup, color, [(px + tx * 8, py + ty * 8), (px + nx * 6, py + ny * 6),
                                     (px - nx * 6, py - ny * 6)])
    texto = fuente.render("10", True, color)
    sup.blit(texto, texto.get_rect(center=(x, y + 1)))


def volumen(sup, centro, nivel, silencio, color=BLANCO):
    x, y = centro
    pygame.draw.polygon(sup, color, [(x - 14, y - 5), (x - 8, y - 5), (x, y - 12),
                                     (x, y + 12), (x - 8, y + 5), (x - 14, y + 5)])
    if silencio or nivel == 0:
        pygame.draw.line(sup, color, (x + 5, y - 6), (x + 15, y + 6), 3)
        pygame.draw.line(sup, color, (x + 5, y + 6), (x + 15, y - 6), 3)
        return
    for i, radio in enumerate((7, 13)):
        if nivel > i * 50:
            rect = pygame.Rect(0, 0, radio * 2, radio * 2)
            rect.center = (x, y)
            pygame.draw.arc(sup, color, rect, math.radians(-50), math.radians(50), 3)


def atras(sup, centro, color=BLANCO):
    x, y = centro
    pygame.draw.line(sup, color, (x - 12, y), (x + 13, y), 4)
    pygame.draw.lines(sup, color, False, [(x - 1, y - 12), (x - 13, y), (x - 1, y + 12)], 4)


def inicio(sup, centro, color=BLANCO):
    x, y = centro
    pygame.draw.lines(sup, color, False, [(x - 15, y - 1), (x, y - 14), (x + 15, y - 1)], 4)
    pygame.draw.lines(sup, color, False, [(x - 10, y - 4), (x - 10, y + 13), (x + 10, y + 13),
                                          (x + 10, y - 4)], 4)


def nota(sup, centro, tam=60, color=BLANCO):
    """Nota musical para la pantalla de audio."""
    x, y = centro
    r = tam // 5
    for dx in (-tam // 2, tam // 2):
        pygame.draw.circle(sup, color, (x + dx - r + 2, y + tam // 2), r)
        pygame.draw.line(sup, color, (x + dx + 1, y + tam // 2), (x + dx + 1, y - tam // 2), 5)
    pygame.draw.polygon(sup, color, [(x - tam // 2 - 1, y - tam // 2), (x + tam // 2 + 3, y - tam // 2 - 14),
                                     (x + tam // 2 + 3, y - tam // 2 - 2), (x - tam // 2 - 1, y - tam // 2 + 12)])


def boton_central(sup, centro, en_pausa):
    """Círculo translúcido con play/pausa en el centro del vídeo."""
    circulo = pygame.Surface((96, 96), pygame.SRCALPHA)
    pygame.draw.circle(circulo, (0, 0, 0, 150), (48, 48), 48)
    sup.blit(circulo, circulo.get_rect(center=centro))
    (play if en_pausa else pausa)(sup, (centro[0] + (4 if en_pausa else 0), centro[1]), 22)


def barra(sup, rect, fraccion, color=ROJO_YT, fondo=GRIS_BARRA, perilla=8):
    """Barra de progreso o de volumen con perilla al final de la parte llena."""
    rect = pygame.Rect(rect)
    fraccion = max(0.0, min(1.0, fraccion))
    pygame.draw.rect(sup, fondo, rect, border_radius=2)
    lleno = rect.copy()
    lleno.width = round(rect.width * fraccion)
    if lleno.width:
        pygame.draw.rect(sup, color, lleno, border_radius=2)
    pygame.draw.circle(sup, color, (rect.x + lleno.width, rect.centery), perilla)
