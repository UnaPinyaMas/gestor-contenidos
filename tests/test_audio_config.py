import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from audio_config import dispositivo_audio


class AudioConfigTest(unittest.TestCase):
    def test_hdmi_conectado_por_nombre_estable(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            root = Path(tmp)
            for num, connected in [(1, False), (2, True)]:
                card = root / f'card{num}'
                card.mkdir()
                (card / 'id').write_text(f'vc4hdmi{num-1}\n')
                (card / 'eld#0').write_text('monitor_name\tMPI5001\nsad_count\t1\n' if connected else 'sad_count\t0\n')
            self.assertEqual(dispositivo_audio(root), 'plughw:CARD=vc4hdmi1,DEV=0')

    def test_sin_hdmi_y_override(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            self.assertEqual(dispositivo_audio(Path(tmp)), 'default')
            os.environ['TERRAHUB_AUDIO_DEVICE'] = 'plughw:CARD=Headphones,DEV=0'
            self.assertEqual(dispositivo_audio(Path(tmp)), 'plughw:CARD=Headphones,DEV=0')
