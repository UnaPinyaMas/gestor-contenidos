import pygame


ANCHO = 800
ALTO = 480


def mostrar_menu():

    pantalla = pygame.display.get_surface()
    reloj = pygame.time.Clock()

    fuente_titulo = pygame.font.Font(None, 50)
    fuente_boton = pygame.font.Font(None, 32)

    botones = [
        ("Videos", pygame.Rect(40, 110, 220, 120)),
        ("Juegos", pygame.Rect(290, 110, 220, 120)),
        ("EPUB", pygame.Rect(540, 110, 220, 120)),
        ("Fotos", pygame.Rect(165, 270, 220, 120)),
        ("Archivos", pygame.Rect(415, 270, 220, 120))
    ]

    ejecutando = True

    while ejecutando:

        for evento in pygame.event.get():

            if evento.type == pygame.QUIT:
                ejecutando = False

            if evento.type == pygame.KEYDOWN:

                if evento.key == pygame.K_ESCAPE:
                    ejecutando = False

            if evento.type == pygame.MOUSEBUTTONDOWN:

                posicion = evento.pos

                for nombre, rect in botones:

                    if rect.collidepoint(posicion):
                        print("Has pulsado:", nombre)

            if evento.type == pygame.FINGERDOWN:

                posicion = (
                    int(evento.x * ANCHO),
                    int(evento.y * ALTO)
                )

                for nombre, rect in botones:

                    if rect.collidepoint(posicion):
                        print("Has pulsado:", nombre)

        pantalla.fill((10, 15, 20))

        titulo = fuente_titulo.render(
            "TerraHub",
            True,
            (255, 255, 255)
        )

        pantalla.blit(
            titulo,
            titulo.get_rect(center=(ANCHO // 2, 50))
        )

        for nombre, rect in botones:

            pygame.draw.rect(
                pantalla,
                (46, 125, 50),
                rect,
                border_radius=15
            )

            texto = fuente_boton.render(
                nombre,
                True,
                (255, 255, 255)
            )

            pantalla.blit(
                texto,
                texto.get_rect(center=rect.center)
            )

        pygame.display.flip()

        reloj.tick(60)