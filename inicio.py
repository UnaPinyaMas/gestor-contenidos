import pygame
import menu


ANCHO = 800
ALTO = 480
FPS = 60


def mostrar_inicio():

    pantalla = pygame.display.set_mode((ANCHO, ALTO))
    pygame.display.set_caption("TerraHub")

    reloj = pygame.time.Clock()

    logo = pygame.image.load("recursos/logo.png").convert_alpha()
    logo = pygame.transform.smoothscale(logo, (250, 250))

    logo_rect = logo.get_rect()
    logo_rect.center = (ANCHO // 2, ALTO // 2)

    alpha = 0
    esperando = False
    ejecutando = True

    while ejecutando:

        for evento in pygame.event.get():

            if evento.type == pygame.QUIT:
                return

            if esperando:

                if evento.type == pygame.KEYDOWN:
                    ejecutando = False

                if evento.type == pygame.MOUSEBUTTONDOWN:
                    ejecutando = False

                if evento.type == pygame.FINGERDOWN:
                    ejecutando = False

        pantalla.fill((10, 15, 20))

        if alpha < 255:
            alpha += 5

        else:
            esperando = True

        logo.set_alpha(alpha)

        pantalla.blit(logo, logo_rect)

        pygame.display.flip()

        reloj.tick(FPS)

    menu.mostrar_menu()