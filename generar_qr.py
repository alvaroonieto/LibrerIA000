"""
Genera el cartel con el código QR para poner en la librería.

    python generar_qr.py https://tu-app.streamlit.app
    python generar_qr.py https://tu-app.streamlit.app --idioma fr   (cartel en francés)

(o pon la dirección en "url_publica" dentro de personalizacion/marca.json
 y ejecuta solo:  python generar_qr.py)

Crea en la carpeta personalizacion/:
    cartel_qr.png  → para pantallas o redes
    cartel_qr.pdf  → para imprimir (tamaño A5)
    qr.png         → solo el código, por si lo quieres usar en otro diseño
"""

import sys

import qrcode
from PIL import Image, ImageDraw, ImageFont, JpegImagePlugin  # noqa: F401 (necesario para el PDF)

from libreria.marca import CARPETA, buscar_imagen, cargar_marca, textos_marca

# A5 a 150 ppp
ANCHO, ALTO = 874, 1240


def _hex(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def _fuente(tamano, negrita=False):
    # Fuentes que suelen existir en Windows / Mac / Linux; si no, la de Pillow
    candidatas = (
        ["georgiab.ttf", "Georgia Bold.ttf", "DejaVuSerif-Bold.ttf"] if negrita
        else ["georgia.ttf", "Georgia.ttf", "DejaVuSerif.ttf"]
    )
    for nombre in candidatas:
        try:
            return ImageFont.truetype(nombre, tamano)
        except OSError:
            continue
    return ImageFont.load_default(size=tamano)


def _abrir(nombre, lado):
    """Abre una imagen de personalizacion/imagenes (no SVG) ajustada a 'lado' px."""
    ruta = buscar_imagen(nombre)
    if ruta is None or ruta.suffix == ".svg":
        return None
    imagen = Image.open(ruta).convert("RGBA")
    imagen.thumbnail((lado, lado))
    return imagen


def _circulo(imagen):
    lado = min(imagen.size)
    imagen = imagen.crop((0, 0, lado, lado))
    mascara = Image.new("L", (lado, lado), 0)
    ImageDraw.Draw(mascara).ellipse((0, 0, lado, lado), fill=255)
    imagen.putalpha(mascara)
    return imagen


def _centrado(dibujo, y, texto, fuente, color, ancho_max):
    """Escribe texto centrado, partiéndolo en varias líneas si no cabe."""
    palabras, lineas, actual = texto.split(), [], ""
    for palabra in palabras:
        prueba = f"{actual} {palabra}".strip()
        if dibujo.textlength(prueba, font=fuente) <= ancho_max:
            actual = prueba
        else:
            lineas.append(actual)
            actual = palabra
    lineas.append(actual)
    alto_linea = fuente.size * 1.3
    for linea in lineas:
        x = (ANCHO - dibujo.textlength(linea, font=fuente)) / 2
        dibujo.text((x, y), linea, font=fuente, fill=color)
        y += alto_linea
    return int(y)


ESCANEA = {
    "es": "Escanea y cuéntale a {lia} qué te apetece leer",
    "en": "Scan and tell {lia} what you'd like to read",
    "fr": "Scanne et dis à {lia} ce que tu as envie de lire",
    "de": "Scanne und sag {lia}, was du lesen möchtest",
}


def generar(url, idioma=None):
    marca = cargar_marca()
    idioma = idioma or marca["idioma_por_defecto"]
    textos = textos_marca(marca, idioma)
    if idioma != marca["idioma_por_defecto"]:
        url += ("&" if "?" in url else "?") + f"idioma={idioma}"
    sufijo = "" if idioma == marca["idioma_por_defecto"] else f"_{idioma}"
    c = {k: _hex(v) for k, v in marca["colores"].items()}

    # Código QR
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=12, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    imagen_qr = qr.make_image(fill_color=c["texto"], back_color=c["tarjeta"]).convert("RGBA")
    imagen_qr.save(CARPETA / f"qr{sufijo}.png")

    cartel = Image.new("RGBA", (ANCHO, ALTO), c["fondo"])
    ImageDraw.Draw(cartel).rounded_rectangle(
        (28, 28, ANCHO - 28, ALTO - 28), radius=36, outline=c["acento"], width=4)

    # Dibujamos el contenido en una capa aparte para luego centrarlo en vertical
    capa = Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 0))
    dibujo = ImageDraw.Draw(capa)
    cartel_final = cartel
    cartel = capa

    y = 0
    # Logo de la librería o dibujo de Lía
    logo = _abrir("logo", 150)
    lia = _abrir("lia", 190)
    if logo:
        cartel.alpha_composite(logo, ((ANCHO - logo.width) // 2, y))
        y += logo.height + 30
    elif lia:
        lia = _circulo(lia)
        cartel.alpha_composite(lia, ((ANCHO - lia.width) // 2, y))
        y += lia.height + 30
    else:
        y += 20

    y = _centrado(dibujo, y, textos["titulo"], _fuente(68, negrita=True), c["texto"], ANCHO - 140)
    y += 10
    y = _centrado(dibujo, y, ESCANEA.get(idioma, ESCANEA["es"]).format(lia=marca["asistente"]),
                  _fuente(30), c["texto_suave"], ANCHO - 200)
    y += 40

    # Tarjeta blanca con el QR
    lado_qr = 460
    imagen_qr = imagen_qr.resize((lado_qr, lado_qr), Image.NEAREST)
    x_qr = (ANCHO - lado_qr) // 2
    dibujo.rounded_rectangle((x_qr - 30, y - 30, x_qr + lado_qr + 30, y + lado_qr + 30),
                             radius=28, fill=c["tarjeta"], outline=c["suave"], width=3)
    cartel.alpha_composite(imagen_qr, (x_qr, y))
    y += lado_qr + 70

    # Si hay logo arriba, ponemos a Lía pequeña abajo junto al nombre
    if logo and lia:
        lia = _circulo(lia).resize((90, 90))
        cartel.alpha_composite(lia, ((ANCHO - 90) // 2, y))
        y += 105

    y = _centrado(dibujo, y, marca["libreria"], _fuente(34, negrita=True), c["acento"], ANCHO - 140)

    y = min(y, ALTO - 80)
    cartel_final.alpha_composite(capa.crop((0, 0, ANCHO, y)), (0, (ALTO - y) // 2))
    cartel = cartel_final.convert("RGB")
    cartel.save(CARPETA / f"cartel_qr{sufijo}.png")
    cartel.save(CARPETA / f"cartel_qr{sufijo}.pdf", resolution=150)
    print(f"Cartel creado en {CARPETA}  (cartel_qr{sufijo}.png / .pdf, qr{sufijo}.png)  →  {url}")


if __name__ == "__main__":
    argumentos = sys.argv[1:]
    idioma_elegido = None
    if "--idioma" in argumentos:
        posicion = argumentos.index("--idioma")
        idioma_elegido = argumentos[posicion + 1]
        del argumentos[posicion:posicion + 2]
    direccion = argumentos[0] if argumentos else cargar_marca()["url_publica"]
    if not direccion:
        print("Falta la dirección. Uso:  python generar_qr.py https://tu-app.streamlit.app")
        sys.exit(1)
    generar(direccion, idioma_elegido)
