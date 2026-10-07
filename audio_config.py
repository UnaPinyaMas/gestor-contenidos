"""Salida ALSA común para mpv y RetroArch; preferir la pantalla HDMI conectada."""
import os
from pathlib import Path


def dispositivo_audio(base=Path('/proc/asound')):
    override = os.environ.get('TERRAHUB_AUDIO_DEVICE')
    if override:
        return override
    for eld in sorted(base.glob('card*/eld*')):
        try:
            info = dict(line.split(None, 1) for line in eld.read_text().splitlines()
                        if len(line.split(None, 1)) == 2)
            if int(info.get('sad_count', '0')) > 0 and info.get('monitor_name', '').strip():
                card = (eld.parent / 'id').read_text().strip()
                return f'plughw:CARD={card},DEV=0'
        except (OSError, ValueError):
            continue
    return 'default'
