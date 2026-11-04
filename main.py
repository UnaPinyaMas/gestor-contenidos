"""Punto de entrada de TerraHub."""
import argparse
import os
if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
    os.environ.setdefault("SDL_VIDEODRIVER", "kmsdrm")
os.environ.setdefault("SDL_TOUCH_MOUSE_EVENTS", "0")

import pygame
import inicio
import menu


def main(argv=None):
    # --carpeta/--aviso los usa juegos.relanzar al volver del emulador.
    parser = argparse.ArgumentParser()
    parser.add_argument("--carpeta")
    parser.add_argument("--aviso", default="")
    args = parser.parse_args(argv)
    pygame.display.init()
    pygame.font.init()
    try:
        pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        pygame.display.set_caption("TerraHub")
        if args.carpeta or inicio.mostrar_inicio():
            menu.mostrar_menu(args.carpeta, args.aviso)
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
