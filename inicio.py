"""Introduccion: terminar o saltar el video abre el menu."""
from pathlib import Path
import pygame
from video_player import VideoPlayer
from menu import Vista, ANCHO, ALTO

BASE = Path(__file__).resolve().parent
VIDEO_INICIO = BASE / "recursos" / "videos" / "intro.mp4"
LOGO = BASE / "recursos" / "imagenes" / "logo.png"


def mostrar_inicio():
    vista = Vista()
    reloj = pygame.time.Clock()
    reproductor = None
    logo = None
    try:
        try:
            logo = pygame.image.load(str(LOGO)).convert_alpha()
            logo = pygame.transform.smoothscale(logo, (250, 250))
        except (OSError, pygame.error) as error:
            print("Logo no disponible:", error, flush=True)
        if VIDEO_INICIO.is_file():
            try:
                reproductor = VideoPlayer(VIDEO_INICIO)
            except (OSError, RuntimeError) as error:
                print("Intro no disponible:", error, flush=True)

        inicio = pygame.time.get_ticks()
        ultimo_alpha = -1
        while True:
            mover = False
            for evento in pygame.event.get():
                if evento.type == pygame.QUIT:
                    return False
                if evento.type == pygame.KEYDOWN:
                    if evento.key == pygame.K_ESCAPE:
                        return False
                    return True
                if vista.posicion(evento) is not None:
                    return True
                if evento.type in (pygame.MOUSEMOTION, pygame.WINDOWEXPOSED):
                    mover = True

            nuevo = False
            if reproductor:
                try:
                    nuevo = reproductor.update()
                    if reproductor.ended:
                        if reproductor.error:
                            print(reproductor.error, flush=True)
                        return True
                except RuntimeError as error:
                    print("Error en la intro:", error, flush=True)
                    return True
            elif pygame.time.get_ticks() - inicio >= 1200:
                return True

            alpha = min(255, (pygame.time.get_ticks() - inicio) * 255 // 850)
            if nuevo or alpha != ultimo_alpha:
                vista.lienzo.fill((10, 15, 20))
                if reproductor:
                    vista.lienzo.blit(reproductor.surface, (0, 75))
                if logo:
                    logo.set_alpha(alpha)
                    vista.lienzo.blit(logo, logo.get_rect(center=(ANCHO // 2, ALTO // 2)))
                else:
                    vista.texto("TerraHub", (400, 300))
                vista.preparar()
                ultimo_alpha = alpha
                mover = True
            if mover:
                vista.presentar()
            reloj.tick(60)
    finally:
        if reproductor:
            reproductor.close()
