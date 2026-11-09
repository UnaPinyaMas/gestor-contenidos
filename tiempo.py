"""Reloj de TerraHub.

pygame.time.get_ticks() (y por tanto pygame.time.Clock) devuelve siempre 0 si no se
ha llamado a pygame.init(), y main.py solo inicia la pantalla y las fuentes. Con el
reloj parado, los avisos no caducaban, las animaciones iban a cámara lenta y el
bucle no limitaba los fotogramas. Este reloj usa time.monotonic() y no depende de SDL.
"""
import time

_INICIO = time.monotonic()


def ms():
    """Milisegundos desde que se cargó TerraHub (como pygame.time.get_ticks)."""
    return int((time.monotonic() - _INICIO) * 1000)


class Reloj:
    """Sustituto de pygame.time.Clock: tick(fps) espera lo que falte del fotograma."""
    def __init__(self):
        self._ultimo = time.monotonic()

    def tick(self, fps):
        espera = self._ultimo + 1 / fps - time.monotonic()
        if espera > 0:
            time.sleep(espera)
        self._ultimo = time.monotonic()
