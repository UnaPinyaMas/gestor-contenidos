"""Primera interfaz del media center. Pulsa Escape para salir."""
import os

# En Raspberry Pi OS sin escritorio, dibujamos directamente en la pantalla.
if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
    os.environ.setdefault("SDL_VIDEODRIVER", "kmsdrm")

import pygame

FONDO = (24, 27, 34)
BOTON = (55, 115, 210)
BOTON_ACTIVO = (75, 140, 235)
BLANCO = (255, 255, 255)
DURACION_MENSAJE = 2000


def main():
    pygame.display.init()
    pygame.font.init()
    try:
        pantalla = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        pygame.display.set_caption("Gestor de contenidos")
        ancho, alto = pantalla.get_size()
        fuente = pygame.font.Font(None, 48)
        boton = pygame.Rect(0, 0, 280, 90)
        boton.center = (ancho // 2, alto // 2)
        texto_boton = fuente.render("Aprietame", True, BLANCO)
        texto_mensaje = fuente.render("me has apretado", True, BLANCO)
        mensaje_hasta = None
        reloj = pygame.time.Clock()
        ejecutando = True

        while ejecutando:
            ahora = pygame.time.get_ticks()
            if mensaje_hasta is not None and ahora >= mensaje_hasta:
                mensaje_hasta = None

            for evento in pygame.event.get():
                if evento.type == pygame.QUIT:
                    ejecutando = False
                elif evento.type == pygame.KEYDOWN and evento.key == pygame.K_ESCAPE:
                    ejecutando = False
                elif (
                    evento.type == pygame.MOUSEBUTTONDOWN
                    and evento.button == 1
                    and mensaje_hasta is None
                    and boton.collidepoint(evento.pos)
                ):
                    mensaje_hasta = ahora + DURACION_MENSAJE

            pantalla.fill(FONDO)
            if mensaje_hasta is not None:
                pantalla.blit(texto_mensaje, texto_mensaje.get_rect(center=pantalla.get_rect().center))
            else:
                color = BOTON_ACTIVO if boton.collidepoint(pygame.mouse.get_pos()) else BOTON
                pygame.draw.rect(pantalla, color, boton, border_radius=14)
                pantalla.blit(texto_boton, texto_boton.get_rect(center=boton.center))

            pygame.display.flip()
            reloj.tick(60)
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
