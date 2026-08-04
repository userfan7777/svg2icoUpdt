#!/usr/bin/env python3
# coding=utf-8
"""
svg2icoUpdt - Export extension for Inkscape 1.x
Converts the current SVG document into a Windows .ico file
with multiple embedded resolutions, using the Inkscape binary
itself to rasterize and Pillow to package the .ico.
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
                "The Pillow module (PIL) was not found in the Python of "
                "Inkscape. Reinstall Inkscape 1.x, which includes it by "
                "default, or install Pillow in the interpreter you are using for "
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
                        "Alert: could not generate the {0}px size; skipping it.".format(size)
                    )

            if not png_paths:
                raise inkex.AbortExtension(
                    "No intermediate PNG was generated; it is not possible to create the .ico file."
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
        """Use the Inkscape binary to export a square PNG of
        'size' x 'size' pixels from the source SVG."""
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
                "Error rasterizing size {0}px: {1}".format(size, exc)
            )


if __name__ == "__main__":
    Svg2Ico().run()
