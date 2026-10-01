import pygame
import subprocess
from pathlib import Path


BASE = Path(__file__).resolve().parent

JUEGOS = BASE / "recursos" / "juegos"

EXTENSIONES = {
    ".gb",
    ".gbc",
    ".sgb"
}

RETROARCH = "retroarch"
CORE = str(
    Path.home() /
    ".config" /
    "retroarch" /
    "cores" /
    "gearboy_libretro.so"
)


def buscar_juegos():

    JUEGOS.mkdir(
        parents=True,
        exist_ok=True
    )

    juegos = []

    for archivo in JUEGOS.rglob("*"):

        if not archivo.is_file():
            continue

        if archivo.suffix.lower() in EXTENSIONES:

            juegos.append(archivo)

    return sorted(
        juegos,
        key=lambda archivo: archivo.name.casefold()
    )


def ejecutar_juego(juego):
    juego = Path(juego)

    if not juego.exists():
        raise FileNotFoundError(f"No existe el juego: {juego}")

    pygame.display.quit()

    comando = [
        RETROARCH,
        "-L",
        CORE,
        str(juego)
    ]

    subprocess.run(
	comando,
	check=False,
	stdout=subprocess.DEVNULL,
	stderr=subprocess.DEVNULL
)

    pygame.display.init()
    pygame.display.set_mode((800, 480))
