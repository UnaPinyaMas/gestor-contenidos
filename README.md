# TerraHub

Media center de clase para Raspberry Pi 4, Raspberry Pi OS de 32 bits sin escritorio, Python y Pygame. Interfaz tactil de 800 x 600, adaptada proporcionalmente a la pantalla conectada.

## Ejecutar

```bash
cd ~/gestor-contenidos
python3 main.py
```

Dependencias: `sudo apt install python3-pygame libmpv2`.

## Inicio y menu

La introduccion utiliza `recursos/videos/intro.mp4` y `recursos/imagenes/logo.png`. Al terminar el video se abre el menu. Un clic, un toque o una tecla permiten saltarla; Escape sale. Si faltan los recursos o falla la introduccion, se permite continuar al menu.

Cada boton abre su carpeta, con Actualizar, Anterior/Siguiente y Volver. Se muestran cinco entradas por pagina, incluidas subcarpetas. Las rutas distinguen mayusculas de minusculas:

| Boton | Carpeta |
|---|---|
| Videos | `recursos/videos/` |
| Juegos | `recursos/juegos/` |
| EPUB | `recursos/epub/` |
| Fotos | `recursos/imagenes/` |
| Archivos | `recursos/archivos/` |

Los videos compatibles se reproducen al seleccionarlos, con Pausar/Continuar, Volver y Salir. Al terminar se vuelve a la carpeta. Las imagenes compatibles se pueden visualizar. Juegos, EPUB y otros archivos muestran su nombre y tamano; los emuladores y lectores todavia no estan implementados. Los enlaces fuera de la carpeta de la seccion no se abren.

Salir siempre cierra la aplicacion. Escape vuelve atras, o sale desde el menu principal. Espacio pausa/continua un video.

Ejemplo de envio desde PowerShell:

```powershell
scp "C:\ruta\video.mp4" joviat@10.1.17.54:/home/joviat/gestor-contenidos/recursos/videos/
```

El contenido nuevo de estas carpetas se excluye de Git. El logo y la introduccion que ya estaban versionados se mantienen. `.gitkeep` conserva las carpetas vacias.

## Archivos de codigo

- `main.py`: inicializacion, paso de la introduccion al menu y cierre seguro.
- `inicio.py`: video y logo de bienvenida; devuelve si se debe continuar.
- `menu.py`: menu, explorador, imagenes y controles de reproduccion; cache del dibujo para evitar redibujar con cada movimiento del raton.
- `video_player.py`: motor libmpv. Renderiza a 800x450 por software y mantiene la proporcion del video. El rendimiento depende del codec, resolucion y bitrate.

La pantalla tactil fisica y el sonido deben comprobarse con el hardware final.
