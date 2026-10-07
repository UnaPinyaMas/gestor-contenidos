#!/bin/sh
# Ejecutar desde cualquier carpeta: sudo sh deploy/instalar.sh
set -eu
BASE=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if [ "$(id -u)" -ne 0 ]; then
    echo 'Ejecuta este instalador con sudo.' >&2
    exit 1
fi
if [ "$BASE" != /home/joviat/gestor-contenidos ]; then
    echo 'Adapta User, WorkingDirectory y ExecStart del servicio a esta instalación.' >&2
    exit 1
fi
apt-get install -y python3-pygame libmpv2 python3-pymupdf retroarch
test -f /home/joviat/.config/retroarch/cores/gearboy_libretro.so || {
    echo 'Falta el núcleo Gearboy: ~/.config/retroarch/cores/gearboy_libretro.so' >&2
    exit 1
}
install -m 644 "$BASE/deploy/terrahub.service" /etc/systemd/system/terrahub.service
install -m 644 "$BASE/deploy/99-terrahub-touch.rules" /etc/udev/rules.d/99-terrahub-touch.rules
udevadm control --reload-rules
udevadm trigger --subsystem-match=input --action=change
systemctl daemon-reload
systemctl enable terrahub.service
systemctl restart terrahub.service
