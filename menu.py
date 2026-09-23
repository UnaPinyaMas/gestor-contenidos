import pygame


ANCHO = 800
ALTO = 480


FONDO = (10, 15, 20)
VERDE = (46, 125, 50)
AZUL = (21, 101, 192)
AMARILLO = (255, 193, 7)
ROJO = (165, 55, 65)
BLANCO = (255, 255, 255)


def mostrar_menu():

    pantalla = pygame.display.get_surface()
    reloj = pygame.time.Clock()

    fuente_titulo = pygame.font.Font(None, 50)
    fuente_boton = pygame.font.Font(None, 32)

    botones = [
        ("Videos", pygame.Rect(40, 100, 220, 120)),
        ("Juegos", pygame.Rect(290, 100, 220, 120)),
        ("EPUB", pygame.Rect(540, 100, 220, 120)),

        ("Fotos", pygame.Rect(165, 250, 220, 120)),
        ("Archivos", pygame.Rect(415, 250, 220, 120))
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

                if evento.button == 1:

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

        pantalla.fill(FONDO)

        titulo = fuente_titulo.render(
            "TerraHub",
            True,
            BLANCO
        )

        pantalla.blit(
            titulo,
            titulo.get_rect(
                center=(ANCHO // 2, 45)
            )
        )

        for nombre, rect in botones:

            color = VERDE

            if nombre == "Juegos":
                color = AZUL

            elif nombre == "EPUB":
                color = AMARILLO

            elif nombre == "Archivos":
                color = AZUL

            pygame.draw.rect(
                pantalla,
                color,
                rect,
                border_radius=15
            )

            texto = fuente_boton.render(
                nombre,
                True,
                BLANCO
            )

            pantalla.blit(
                texto,
                texto.get_rect(
                    center=rect.center
                )
            )

        pygame.display.flip()

        reloj.tick(60)