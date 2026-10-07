"""RetroArch con controles táctiles y recuperación de la pantalla al terminar."""
import os
from pathlib import Path
import shutil
import subprocess
import pygame

BASE = Path(__file__).resolve().parent
JUEGOS = BASE / 'recursos' / 'juegos'
EXTENSIONES = {'.gb', '.gbc', '.sgb'}
CORE = Path.home() / '.config/retroarch/cores/gearboy_libretro.so'


def buscar_juegos():
    JUEGOS.mkdir(parents=True, exist_ok=True)
    return sorted((p for p in JUEGOS.rglob('*') if p.is_file()
                   and p.suffix.lower() in EXTENSIONES
                   and p.resolve().is_relative_to(JUEGOS.resolve())),
                  key=lambda p: p.name.casefold())


def configurar_controles():
    cache = BASE / '.cache' / 'emulador'
    cache.mkdir(parents=True, exist_ok=True)
    controles = [
        ('up', 'Arriba', .14, .59, .055, .065),
        ('down', 'Abajo', .14, .85, .055, .065),
        ('left', 'Izq.', .07, .72, .055, .065),
        ('right', 'Der.', .21, .72, .055, .065),
        ('b', 'B', .80, .79, .065, .085),
        ('a', 'A', .92, .64, .065, .085),
        ('select', 'Select', .41, .91, .075, .055),
        ('start', 'Start', .59, .91, .075, .055),
        ('exit_emulator', 'Volver', .89, .07, .095, .055),
    ]
    imagen = pygame.Surface((1000, 600), pygame.SRCALPHA)
    fuente = pygame.font.Font(None, 30)
    lines = ['overlays = 1', 'overlay0_overlay = "controles.png"',
             'overlay0_rect = "0,0,1,1"', 'overlay0_full_screen = true',
             'overlay0_normalized = true', f'overlay0_descs = {len(controles)}']
    for i, (bind, label, x, y, rx, ry) in enumerate(controles):
        rect = pygame.Rect(round((x-rx)*1000), round((y-ry)*600),
                           round(rx*2000), round(ry*1200))
        pygame.draw.rect(imagen, (24, 45, 65, 225), rect, border_radius=12)
        pygame.draw.rect(imagen, (160, 205, 240, 255), rect, 2, border_radius=12)
        text = fuente.render(label, True, 'white')
        imagen.blit(text, text.get_rect(center=rect.center))
        lines.append(f'overlay0_desc{i} = "{bind},{x},{y},rect,{rx},{ry}"')
    pygame.image.save(imagen, str(cache / 'controles.png'))
    overlay = cache / 'controles.cfg'
    overlay.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    saves = Path.home() / '.local/share/terrahub/partidas'
    saves.mkdir(parents=True, exist_ok=True)
    config = cache / 'retroarch.cfg'
    settings = {
        'input_overlay': str(overlay), 'input_overlay_enable': 'true',
        'input_overlay_enable_autopreferred': 'false',
        'input_overlay_hide_when_gamepad_connected': 'false',
        'input_overlay_opacity': '0.85', 'input_overlay_auto_scale': 'false',
        'input_overlay_auto_rotate': 'false', 'input_overlay_scale_landscape': '1.0',
        'input_overlay_scale_portrait': '1.0', 'input_overlay_hide_in_menu': 'false',
        'input_enable_hotkey': 'nul', 'input_enable_hotkey_btn': 'nul',
        'input_exit_emulator': 'escape', 'quit_press_twice': 'false',
        'quit_on_close_content': '1', 'config_save_on_exit': 'false',
        'video_fullscreen': 'true', 'video_driver': 'gl',
        'input_driver': 'udev', 'input_joypad_driver': 'udev',
        'savefile_directory': str(saves), 'savestate_directory': str(saves),
    }
    if not os.environ.get('DISPLAY') and not os.environ.get('WAYLAND_DISPLAY'):
        settings['video_context_driver'] = 'kms'
        settings['audio_driver'] = 'alsa'
    config.write_text(''.join(f'{k} = "{v}"\n' for k, v in settings.items()), encoding='utf-8')
    return config, cache / 'retroarch.log'


def ejecutar_juego(juego):
    juego = Path(juego)
    if not juego.is_file():
        raise FileNotFoundError(f'No existe el juego: {juego}')
    executable = shutil.which('retroarch')
    if not executable or not CORE.is_file():
        raise RuntimeError('Falta RetroArch o el núcleo Gearboy.')
    config, log = configurar_controles()
    surface = pygame.display.get_surface()
    size, flags = surface.get_size(), surface.get_flags()
    pygame.display.quit()
    try:
        with log.open('w') as output:
            result = subprocess.run([executable, '--appendconfig', str(config),
                                     '-L', str(CORE), str(juego)],
                                    stdout=output, stderr=subprocess.STDOUT, check=False)
        if result.returncode:
            raise RuntimeError(f'El emulador terminó con error. Consulta {log}')
    finally:
        pygame.display.init()
        pygame.display.set_mode(size, flags)
        pygame.display.set_caption('TerraHub')
        pygame.event.clear()
