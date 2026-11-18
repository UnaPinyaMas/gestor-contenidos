"""Introducción (entrega v2, 6.1): el logotipo blanco aparece sobre fondo negro.

Si hay recursos/videos/intro.mp4 se reproduce detrás; terminarla, o tocar la pantalla,
abre el menú. Es la única pantalla sin barra superior ni controles.
"""
from pathlib import Path
import pygame
from video_player import VideoPlayer
import estilo
import tiempo

BASE = Path(__file__).resolve().parent
VIDEO_INICIO = BASE / "recursos" / "videos" / "intro.mp4"
DURACION_MS = 1600                    # sin vídeo: lo que se ve el logotipo
APARECER_MS = 850


def mostrar_inicio():
    pantalla = pygame.display.get_surface()
    w, h = pantalla.get_size()
    reloj = tiempo.Reloj()
    reproductor = None
    logo = None
    try:
        try:
            logo = estilo.imagen("logo-vertical-blanco.png", alto=h * .46)
        except (OSError, pygame.error) as error:
            print("Logo no disponible:", error, flush=True)
        if VIDEO_INICIO.is_file():
            try:
                reproductor = VideoPlayer(VIDEO_INICIO, size=(w, h))
            except (OSError, RuntimeError) as error:
                print("Intro no disponible:", error, flush=True)

        inicio = tiempo.ms()
        ultimo_alpha = -1
        while True:
            mover = False
            for evento in pygame.event.get():
                if evento.type == pygame.QUIT:
                    return False
                if evento.type == pygame.KEYDOWN:
                    return evento.key != pygame.K_ESCAPE
                if evento.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN):
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
            elif tiempo.ms() - inicio >= DURACION_MS:
                return True

            alpha = min(255, (tiempo.ms() - inicio) * 255 // APARECER_MS)
            if nuevo or alpha != ultimo_alpha:
                pantalla.fill((0, 0, 0))
                if reproductor:
                    pantalla.blit(reproductor.surface, reproductor.surface.get_rect(center=(w // 2, h // 2)))
                if logo:
                    logo.set_alpha(alpha)
                    pantalla.blit(logo, logo.get_rect(center=(w // 2, h // 2)))
                ultimo_alpha = alpha
                mover = True
            if mover:
                pygame.display.flip()
            reloj.tick(60)
    finally:
        if reproductor:
            reproductor.close()
