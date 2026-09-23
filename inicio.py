import pygame
from pathlib import Path
from video_player import VideoPlayer
import menu


ANCHO = 800
ALTO = 480
FPS = 60


BASE = Path(__file__).resolve().parent
VIDEO_INICIO = BASE / "recursos" / "videos" / "intro.mp4"
LOGO = BASE / "recursos" / "imagenes" / "logo.png"


def mostrar_inicio():

    pantalla = pygame.display.set_mode((ANCHO, ALTO))
    pygame.display.set_caption("TerraHub")

    reloj = pygame.time.Clock()

    logo = pygame.image.load(LOGO).convert_alpha()
    logo = pygame.transform.smoothscale(logo, (250, 250))

    logo_rect = logo.get_rect()
    logo_rect.center = (ANCHO // 2, ALTO // 2)

    alpha = 0
    esperando = False
    ejecutando = True

    reproductor = None

    try:

        if VIDEO_INICIO.exists():
            reproductor = VideoPlayer(VIDEO_INICIO, audio=false)

        while ejecutando:

            for evento in pygame.event.get():

                if evento.type == pygame.QUIT:
                    ejecutando = False

                if evento.type == pygame.KEYDOWN:

                    ejecutando = False

                if evento.type == pygame.MOUSEBUTTONDOWN:

                    ejecutando = False

                if evento.type == pygame.FINGERDOWN:

                    ejecutando = False

            if reproductor:

                reproductor.update()

                if reproductor.ended:
                    esperando = True

            pantalla.fill((10, 15, 20))

            if reproductor:

                pantalla.blit(
                    reproductor.surface,
                    (0, 15)
                )

            if alpha < 255:
                alpha += 5

            logo.set_alpha(alpha)

            pantalla.blit(
                logo,
                logo_rect
            )

            pygame.display.flip()

            reloj.tick(FPS)

    finally:

        if reproductor:
            reproductor.close()

    if ejecutando:
        menu.mostrar_menu()