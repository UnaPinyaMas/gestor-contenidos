"""Punto de entrada de TerraHub."""
import os
if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
    os.environ.setdefault("SDL_VIDEODRIVER", "kmsdrm")
os.environ.setdefault("SDL_TOUCH_MOUSE_EVENTS", "0")

import pygame
import inicio
import menu


def main():
    pygame.display.init()
    pygame.font.init()
    try:
        pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        pygame.display.set_caption("TerraHub")
        if inicio.mostrar_inicio():
            menu.mostrar_menu()
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
