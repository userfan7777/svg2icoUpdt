#!/usr/bin/env python3
# coding=utf-8
"""
svg2ico - Extension de exportacion para Inkscape 1.x
Convierte el documento SVG actual a un archivo .ico de Windows
con multiples resoluciones incrustadas, usando el propio binario
de Inkscape para rasterizar y Pillow para empacar el .ico.
"""

import io
import os
import sys
import tempfile
import subprocess

import inkex
from inkex.command import inkscape as run_inkscape

try:
    from PIL import Image
except ImportError:
    Image = None


class Svg2Ico(inkex.OutputExtension):

    def add_arguments(self, pars):
        pars.add_argument("--tab", type=str, default="options")
        pars.add_argument("--sizes", type=str, default="256,128,64,48,32,16")
        pars.add_argument("--dpi", type=int, default=96)

    def parse_sizes(self):
        raw = self.options.sizes or ""
        sizes = []
        for chunk in raw.replace(";", ",").split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            try:
                val = int(float(chunk))
            except ValueError:
                continue
            if 1 <= val <= 1024:
                sizes.append(val)
        # quitar duplicados conservando orden, mayor a menor
        seen = set()
        ordered = []
        for s in sorted(set(sizes), reverse=True):
            if s not in seen:
                seen.add(s)
                ordered.append(s)
        return ordered or [256, 128, 64, 48, 32, 16]

    def save(self, stream):
        if Image is None:
            raise inkex.AbortExtension(
                "No se encontro el modulo Pillow (PIL) en el Python de "
                "Inkscape. Reinstala Inkscape 1.x, que lo incluye por "
                "defecto, o instala Pillow en el interprete que usa "
                "Inkscape."
            )

        sizes = self.parse_sizes()

        # Guardar el documento actual (posiblemente con cambios no
        # guardados en disco) a un SVG temporal para rasterizarlo.
        tmp_dir = tempfile.mkdtemp(prefix="svg2ico_")
        src_svg = os.path.join(tmp_dir, "source.svg")
        with open(src_svg, "wb") as f:
            self.document.write(f)

        png_paths = []
        try:
            for size in sizes:
                png_path = os.path.join(tmp_dir, "icon_{0}.png".format(size))
                self.render_png(src_svg, png_path, size)
                if os.path.exists(png_path):
                    png_paths.append(png_path)
                else:
                    inkex.errormsg(
                        "Aviso: no se pudo generar el tamano {0}px, se omite.".format(size)
                    )

            if not png_paths:
                raise inkex.AbortExtension(
                    "No se genero ningun PNG intermedio; no es posible crear el .ico."
                )

            images = []
            for p in sorted(png_paths, key=self.png_width, reverse=True):
                with Image.open(p) as im:
                    images.append(im.convert("RGBA"))

            base_img = images[0]
            ico_sizes = [(img.width, img.height) for img in images]

            # Inkscape entrega en Windows un stream sin soporte para
            # .tell(), que Pillow necesita para escribir un .ico.
            # Por eso armamos el .ico en un buffer en memoria y luego
            # copiamos los bytes ya listos al stream real.
            buffer = io.BytesIO()
            base_img.save(
                buffer,
                format="ICO",
                sizes=ico_sizes,
                append_images=images[1:],
            )
            stream.write(buffer.getvalue())

        finally:
            for p in png_paths:
                try:
                    os.remove(p)
                except OSError:
                    pass
            try:
                os.remove(src_svg)
            except OSError:
                pass
            try:
                os.rmdir(tmp_dir)
            except OSError:
                pass

    @staticmethod
    def png_width(path):
        with Image.open(path) as im:
            return im.width

    def render_png(self, src_svg, out_png, size):
        """Usa el binario de Inkscape para exportar un PNG cuadrado de
        'size' x 'size' pixeles a partir del SVG fuente."""
        args = [
            src_svg,
            "--export-type=png",
            "--export-filename={0}".format(out_png),
            "--export-width={0}".format(size),
            "--export-height={0}".format(size),
            "--export-area-page",
            "--export-background-opacity=0",
        ]
        try:
            run_inkscape(*args)
        except Exception as exc:
            inkex.errormsg(
                "Error al rasterizar tamano {0}px: {1}".format(size, exc)
            )


if __name__ == "__main__":
    Svg2Ico().run()
