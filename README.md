# 📚 LibrerIA

Asistente que recomienda libros **solo del catálogo de la librería o biblioteca**.
A diferencia de ChatGPT o Claude, nunca recomienda un libro que no esté disponible.

Pensado para quien prefiere no preguntar (personas autistas, con ansiedad social…),
para momentos en que el librero no llega a todo, y como apoyo cuando un tema no es su especialidad.

---

## Estructura

```
LibrerIA/
├── app.py                  ← interfaz web "Pregúntale a Lía"
├── consola.py              ← versión por terminal, para pruebas
├── preparar_datos.py       ← limpia el catálogo y calcula embeddings (una vez)
├── generar_qr.py           ← crea el cartel con el QR para la librería
├── requirements.txt
├── personalizacion/        ← TODO lo visual se cambia aquí, sin tocar código
│   ├── marca.json          ← nombre, textos por idioma, sugerencias, pictogramas, colores
│   ├── imagenes/           ← lia.png, logo.png, fondo.png, cabecera.png
│   └── pictogramas/        ← un dibujo por pictograma (misterio.png, amor.png...)
├── .streamlit/config.toml  ← tema base de Streamlit
├── libreria/
│   ├── config.py           ← ajustes técnicos (modelo, umbrales, pesos)
│   ├── interprete.py       ← entiende la petición: páginas, nota, lo que NO quiere
│   ├── motor.py            ← busca y ordena los libros
│   ├── goodreads.py        ← personalización con el CSV de Goodreads
│   ├── marca.py            ← lee la carpeta personalizacion/
│   ├── textos.py           ← textos de botones y mensajes en ES / EN / FR / DE
│   └── voz.py              ← dictado por voz (faster-whisper)
├── data/
│   └── books.csv           ← catálogo en bruto
└── ejemplos/
    └── goodreads_ejemplo.csv  ← CSV de prueba (datos inventados)
```

Equivalencia con los ficheros antiguos:

| Antes | Ahora |
|---|---|
| `explore_data.py` + `generate_embeddings.py` | `preparar_datos.py` |
| `interprete.py` | `libreria/interprete.py` |
| `motor_principal.py` | `libreria/motor.py` |
| `streamlit_app.py` | `app.py` |
| `app.py` | `consola.py` |
| `.env` | **borrado** (no se usaba; revoca esa API key) |

---

## Instalación desde cero (Windows, PowerShell)

Abre una terminal **dentro de la carpeta `LibrerIA`**:

```powershell
# 1. Crear un entorno virtual limpio (solo la primera vez)
python -m venv .venv

# 2. Activarlo (cada vez que abras una terminal nueva)
.venv\Scripts\activate
#    Si da error de "ejecución de scripts deshabilitada":
#    Set-ExecutionPolicy -Scope CurrentUser RemoteSigned   (y repite)

# 3. Instalar librerías (solo la primera vez)
pip install -r requirements.txt

# 4. Preparar datos (solo la primera vez o si cambias el catálogo)
python preparar_datos.py

# 5. Abrir la app
streamlit run app.py
```

En Mac/Linux, el paso 2 es `source .venv/bin/activate`.

El paso 4 descarga el modelo (~470 MB) y tarda unos minutos. Después, la app arranca en segundos.

**Cada día solo necesitas:** activar el entorno (paso 2) y `streamlit run app.py`.

---

## Personalizar (Lía, colores, dibujos, logo)

Todo está en `personalizacion/`. Después de cambiar algo, recarga la página
(si no se ve el cambio, para Streamlit con Ctrl+C y vuelve a lanzarlo).

**Textos y colores** → `personalizacion/marca.json`
- `asistente`: nombre de la asistente. `libreria`: nombre que sale arriba y en el cartel.
- `idiomas`: qué idiomas se ofrecen (`es`, `en`, `fr`, `de`). `idioma_por_defecto`: con cuál se abre.
- `textos` → un bloque por idioma con `titulo`, `subtitulo`, `saludo`, `placeholder`,
  `aviso_librero` y `sugerencias` (2 a 4 botones funcionan bien).
- `pictogramas`: la lista de botones con dibujo (ver abajo).
- `colores`: en formato `#RRGGBB`. `acento` es el color principal.
- `opacidad_fondo`: 0 = imagen de fondo a tope, 1 = no se ve. 0.85–0.9 va bien.

Los textos de los botones fijos (Escuchar, Empezar de nuevo…) están en `libreria/textos.py`.

**Imágenes** → `personalizacion/imagenes/` (el nombre del fichero es lo que cuenta):

| Fichero | Qué es | Tamaño recomendado |
|---|---|---|
| `lia.png` | Dibujo de Lía (avatar, se recorta en círculo) | cuadrado, ≥ 400×400 |
| `logo.png` | Logo de la librería (mejor PNG transparente) | ~ 300 px de alto |
| `fondo.png` | Fondo de toda la página (ej. libro abierto) | horizontal, ≥ 1920×1080 |
| `cabecera.png` | Ilustración grande encima del título (sustituye al avatar) | ~ 1200×400 |

También valen `.jpg`, `.webp` o `.svg` (el cartel QR no admite `.svg`).

**Pictogramas** → `personalizacion/pictogramas/`
- Un PNG por botón, con el `id` de `marca.json` como nombre: `misterio.png`, `amor.png`,
  `aventura.png`, `fantasia.png`, `ciencia_ficcion.png`, `miedo.png`, `risa.png`,
  `historia.png`, `infantil.png`, `poesia.png`, `vidas.png`, `corto.png`.
- Si falta alguno, se muestra su emoji. Cuadrados, ≥ 300×300, mismo estilo en todos.
- Para añadir o quitar botones, edita la lista `pictogramas` de `marca.json`:
  `id`, `emoji`, el texto en cada idioma y `busqueda` (lo que Lía busca al pulsarlo).

---

## Accesibilidad

Botón **♿ Accesibilidad** arriba a la derecha (cada persona elige lo suyo; no se guarda nada):

| Opción | Qué hace |
|---|---|
| Idioma (ES / EN / FR / DE) | Cambia todos los textos. Lía entiende búsquedas en los cuatro idiomas. |
| Letra grande | Aumenta todo el texto. |
| Letra más fácil de leer | Fuente Atkinson Hyperlegible, más espacio entre letras y líneas. |
| Alto contraste | Blanco y negro con azul oscuro, bordes marcados, sin imagen de fondo. |
| Quitar animaciones | Desactiva cualquier animación o transición. |
| Mostrar pictogramas | Botones con dibujos para elegir sin escribir. |
| Botones para escuchar | 🔊 en cada mensaje de Lía: lee en voz alta títulos, autores y páginas. Usa la voz del navegador (gratis, sin servidor). Velocidad ajustable. |
| 🎤 Prefiero hablar | Grabar lo que se busca en vez de escribirlo. |

- **Idioma por enlace:** `https://la-app/?idioma=fr` abre directamente en francés.
- **Dictado por voz:** usa faster-whisper en el propio ordenador/servidor (el audio no
  sale a ninguna empresa). La primera vez descarga el modelo (~150 MB) y tarda un poco.
  Se cambia el tamaño en `libreria/config.py` → `MODELO_VOZ` (`tiny`, `base`, `small`).
  Si faster-whisper no está instalado, el micrófono simplemente no aparece.
- Las descripciones de los libros salen en el idioma del catálogo (ahora, inglés).

---

## Cartel con QR

```powershell
python generar_qr.py https://la-direccion-de-la-app
python generar_qr.py https://la-direccion-de-la-app --idioma en   # cartel en inglés
python generar_qr.py https://la-direccion-de-la-app --idioma de   # cartel en alemán
```

Crea `personalizacion/cartel_qr.pdf` (A5, para imprimir), `cartel_qr.png` y `qr.png`
(con `--idioma en`: `cartel_qr_en.pdf`…, y el QR abre la app ya en inglés).
Usa los colores, el logo y el dibujo de Lía. Si guardas la dirección en
`url_publica` de `marca.json`, basta con `python generar_qr.py`.

---

## ¿Y Ollama?

**No hace falta.** La interfaz web ya no lo usa: las reglas entienden
"máximo 300 páginas", "no quiero menos de 400 páginas", "algo cortito",
"bien valorado", "que no sea romántica", etc. Además, en un servidor gratuito no se podría ejecutar.

Solo se puede probar desde la terminal: `python consola.py --ollama`. Si lo quieres usar:

```powershell
ollama --version          # ¿está instalado? Si no: https://ollama.com/download
ollama list               # ¿tienes el modelo?
ollama pull qwen3:1.7b    # si no aparece
```

Ollama es un programa aparte: descargar ficheros nuevos del proyecto **no** obliga a reinstalarlo.

---

## Goodreads

Goodreads no tiene API pública (la cerró en 2020), así que no se puede "conectar" una cuenta.
Lo que sí se puede es usar la exportación que cualquier usuario descarga:

**goodreads.com → My Books → Import and export → Export Library**

Se sube ese CSV en el desplegable "¿Usas Goodreads?" y LibrerIA:
1. Busca sus libros en el catálogo (por ISBN o título).
2. Crea un "perfil lector" con los que puntuó con 4-5 estrellas.
3. Mezcla ese perfil con la búsqueda (30 %, ajustable en `config.PESO_PERFIL`).
4. No recomienda libros que ya ha leído.

**No se guarda nada**: el CSV vive en memoria mientras la página está abierta.

Para probar: `ejemplos/goodreads_ejemplo.csv` (inventado, con libros del catálogo).

---

## Usar el catálogo de una librería o biblioteca

Sustituye `data/books.csv` por el suyo con al menos estas columnas:
`isbn13, title, authors, categories, description, average_rating, num_pages, ratings_count, thumbnail, subtitle, published_year`

Dos columnas opcionales que el código ya entiende:
- `stock` → no se recomiendan libros con stock 0.
- `seccion` → se muestra "📍 Dónde está" (estantería, signatura topográfica…).

Después, vuelve a ejecutar `python preparar_datos.py`.

---

## Limitaciones conocidas

- El dataset actual es de ejemplo (~6.300 libros en inglés), no el de una librería real.
- Los libros sin número de páginas desaparecen cuando se filtra por páginas.
- Las exclusiones ("que no sea X") penalizan los libros parecidos a X; no los eliminan del todo.
- Las palabras vagas usan valores fijos (corto = máx. 250 págs.; se cambian en `config.py`).
- Las reglas en inglés, francés y alemán son más básicas que en español.
- El botón 🔊 depende de las voces instaladas en el dispositivo (en móviles y Chrome suele haber de sobra).
