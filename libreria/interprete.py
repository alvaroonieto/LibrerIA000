"""
Intérprete: convierte lo que escribe el usuario en filtros + consulta semántica.

    "Novela negra en Escocia, no quiero menos de 300 páginas, que no sea romántica"
        → consulta_semantica = "Novela negra en Escocia"
        → min_paginas = 300
        → excluir = ["romántica"]

Funciona con reglas (rápido, sin internet, sin Ollama) en español, inglés, francés y alemán.
Ollama es opcional: solo completa lo que las reglas no han entendido.
"""

import json
import re
import unicodedata

from libreria import config


# --------------------------------------------------
# UTILIDADES
# --------------------------------------------------

def _letra_base(c):
    """'é' → 'e', 'ç' → 'c', '’' → "'" (siempre 1 carácter)."""
    c = c.lower()[:1] or c
    if c == "’":
        return "'"
    return unicodedata.normalize("NFD", c)[0]


def _normalizar(texto):
    """Minúsculas y sin tildes, SIN cambiar la longitud (para que las posiciones
    coincidan con el texto original)."""
    return "".join(_letra_base(c) for c in texto)


def _hay_negacion_antes(texto_norm, inicio):
    """¿Hay una negación en la misma frase, justo antes de 'inicio'?"""
    antes = texto_norm[:inicio]
    # La frase empieza tras el último signo de puntuación o 'pero' / 'but' / 'mais' / 'aber'
    corte = max(antes.rfind(","), antes.rfind("."), antes.rfind(";"),
                antes.rfind(" pero "), antes.rfind(" but "), antes.rfind(" mais "), antes.rfind(" aber "))
    frase = antes[corte + 1:]
    return re.search(_NEGACIONES, frase) is not None


_NEGACIONES = (
    r"\b(?:no|ni|nada"                                 # español
    r"|not|don't|dont|doesn't|isn't|isnt|aren't|wasn't|won't|nothing|never"  # inglés
    r"|ne|n'|pas|rien|jamais"                          # francés
    r"|nicht|kein|keine|keinen|keiner|keines|nichts|nie)\b|\bn'"  # alemán
)


class _Texto:
    """Guarda el texto original y marca qué trozos ya se han 'consumido' como filtro."""

    def __init__(self, texto):
        self.original = texto
        self.norm = _normalizar(texto)
        self.consumido = [False] * len(texto)

    def buscar(self, patron):
        """Busca solo en lo que todavía no se ha usado (lo usado se ve como espacios)."""
        visible = "".join(" " if usado else c for c, usado in zip(self.norm, self.consumido))
        return list(re.finditer(patron, visible))

    def consumir(self, inicio, fin):
        for i in range(inicio, fin):
            self.consumido[i] = True

    def restante(self):
        return "".join(" " if usado else c for c, usado in zip(self.original, self.consumido))


# --------------------------------------------------
# PÁGINAS
# --------------------------------------------------

_PAG = r"(?:pages|seiten|p(?:aginas|ags?\.?)|pp\.?)(?![a-z])"
_NUM = r"(\d+)"

_COMPARADORES_ANTES = {
    # palabra → qué límite fija
    "menos de": "max", "como maximo": "max", "maximo de": "max", "maximo": "max",
    "como mucho": "max", "hasta": "max", "no mas de": "max", "max.": "max", "max": "max",
    "mas de": "min", "como minimo": "min", "minimo de": "min", "minimo": "min",
    "al menos": "min", "por lo menos": "min", "no menos de": "min", "min.": "min", "min": "min",
    # inglés
    "less than": "max", "fewer than": "max", "under": "max", "at most": "max", "maximum": "max",
    "max of": "max", "up to": "max", "no more than": "max", "not more than": "max",
    "more than": "min", "over": "min", "at least": "min", "minimum": "min", "min of": "min",
    "no less than": "min", "not less than": "min",
    # francés
    "moins de": "max", "au plus": "max", "au maximum": "max", "jusqu'a": "max", "pas plus de": "max",
    "plus de": "min", "au moins": "min", "au minimum": "min", "pas moins de": "min",
    # alemán (sin diéresis: el texto se normaliza, "höchstens" → "hochstens")
    "weniger als": "max", "hochstens": "max", "maximal": "max", "bis zu": "max", "unter": "max",
    "nicht mehr als": "max",
    "mehr als": "min", "uber": "min", "mindestens": "min", "wenigstens": "min",
    "nicht weniger als": "min",
}
_PREFIJOS_NEGADOS = ("no ", "not ", "pas ", "nicht ")
_COMPARADORES_DESPUES = {
    "o menos": "max", "como maximo": "max", "maximo": "max", "como mucho": "max",
    "o mas": "min", "como minimo": "min", "minimo": "min",
    "or less": "max", "or fewer": "max", "at most": "max", "max": "max", "maximum": "max", "tops": "max",
    "or more": "min", "at least": "min", "minimum": "min", "min": "min",
    "ou moins": "max", "au plus": "max", "au maximum": "max",
    "ou plus": "min", "au moins": "min", "au minimum": "min",
    "oder weniger": "max", "hochstens": "max", "maximal": "max",
    "oder mehr": "min", "mindestens": "min",
}


def _alternativas(opciones):
    # Las más largas primero, para que "como maximo" gane a "maximo"
    return "|".join(re.escape(o) for o in sorted(opciones, key=len, reverse=True))


def _invertir(tipo):
    return "min" if tipo == "max" else "max"


def _extraer_paginas(t, pref):

    # 1) "entre 200 y 400 páginas"
    for m in t.buscar(rf"(?:entre|between|zwischen)\s+{_NUM}\s+(?:y|and|et|und)\s+{_NUM}\s+{_PAG}"):
        a, b = sorted([int(m.group(1)), int(m.group(2))])
        pref["min_paginas"], pref["max_paginas"] = a, b
        t.consumir(m.start(), m.end())

    # 2) "menos de 400 páginas", "no quiero menos de 400 páginas"
    patron = rf"(?:de\s+)?\b({_alternativas(_COMPARADORES_ANTES)})\s+{_NUM}\s+{_PAG}"
    for m in t.buscar(patron):
        tipo = _COMPARADORES_ANTES[m.group(1)]
        if _hay_negacion_antes(t.norm, m.start()) and not m.group(1).startswith(_PREFIJOS_NEGADOS):
            tipo = _invertir(tipo)   # "no quiero MENOS de 400" = mínimo 400
        pref[f"{tipo}_paginas"] = int(m.group(2))
        t.consumir(m.start(), m.end())

    # 3) "400 páginas o menos", "300 páginas como mínimo"
    patron = rf"{_NUM}\s+{_PAG}\s+({_alternativas(_COMPARADORES_DESPUES)})\b"
    for m in t.buscar(patron):
        tipo = _COMPARADORES_DESPUES[m.group(2)]
        pref[f"{tipo}_paginas"] = int(m.group(1))
        t.consumir(m.start(), m.end())

    # 4) Número suelto: "no quiero un tocho de 400 páginas" / "un libro de 300 páginas"
    for m in t.buscar(rf"(?:de\s+)?\b{_NUM}[\s-]+{_PAG}"):
        n = int(m.group(1))
        if _hay_negacion_antes(t.norm, m.start()):
            pref["max_paginas"] = n
        else:
            pref["min_paginas"], pref["max_paginas"] = int(n * 0.75), int(n * 1.25)
        t.consumir(m.start(), m.end())


# --------------------------------------------------
# RATING
# --------------------------------------------------

def _extraer_rating(t, pref):

    patrones = [
        # "al menos 4 estrellas", "más de 3,5 de nota"
        r"(?:al menos|minimo(?: de)?|mas de|por lo menos|como minimo)\s+(?:un[a]?\s+)?"
        r"(\d(?:[.,]\d+)?)\s*(?:estrellas?|de (?:rating|nota|valoracion)|puntos)",
        # "4 estrellas o más"
        r"(\d(?:[.,]\d+)?)\s*estrellas?\s+o\s+mas",
        # "rating de al menos 4", "nota mínima de 4"
        r"(?:rating|nota|valoracion)\s+(?:minim[ao]\s+)?(?:de\s+)?(?:al menos\s+|mas de\s+|minimo\s+)?"
        r"(\d(?:[.,]\d+)?)",
        # inglés: "at least 4 stars", "4 stars or more", "rated above 4"
        r"(?:at least|minimum|more than|over|above)\s+(\d(?:[.,]\d+)?)\s*(?:stars?|rating|points)",
        r"(\d(?:[.,]\d+)?)\s*stars?\s+(?:or more|and up|or higher)",
        r"(?:rating|rated)\s+(?:of\s+)?(?:at least\s+|above\s+|over\s+)?(\d(?:[.,]\d+)?)",
        # francés: "au moins 4 étoiles", "4 étoiles ou plus", "note d'au moins 4"
        r"(?:au moins|minimum|plus de)\s+(\d(?:[.,]\d+)?)\s*(?:etoiles?|de note)",
        r"(\d(?:[.,]\d+)?)\s*etoiles?\s+ou\s+plus",
        r"note\s+(?:minimale\s+)?(?:de\s+|d'au moins\s+|d'|superieure a\s+)?(\d(?:[.,]\d+)?)",
        # alemán: "mindestens 4 Sterne", "4 Sterne oder mehr", "Bewertung von mindestens 4"
        r"(?:mindestens|wenigstens|mehr als|uber)\s+(\d(?:[.,]\d+)?)\s*(?:sternen?|punkte)",
        r"(\d(?:[.,]\d+)?)\s*sternen?\s+oder\s+mehr",
        r"bewertung\s+(?:von\s+)?(?:mindestens\s+|uber\s+|mehr als\s+)?(\d(?:[.,]\d+)?)",
    ]
    for patron in patrones:
        for m in t.buscar(patron):
            valor = float(m.group(1).replace(",", "."))
            if 0 <= valor <= 5:
                pref["min_rating"] = valor
                t.consumir(m.start(), m.end())


# --------------------------------------------------
# PALABRAS VAGAS ("corto", "tocho", "bien valorado")
# --------------------------------------------------

_CORTO = (
    r"\b(?:muy\s+|very\s+|tres\s+|sehr\s+)?(?:cortit[oa]s?|cort[oa]s?|breves?|ligerit[oa]s?|liger[oa]s?|"
    r"rapido de leer|que se lea rapido"
    r"|short|brief|quick read|light read|easy to finish"
    r"|courts?|courtes?|legers?|legeres?|rapide a lire"
    r"|kurz(?:e[snrm]?)?|dunn(?:e[snrm]?)?|schnell (?:zu lesen|gelesen))\b"
)
_LARGO = (
    r"\b(?:muy\s+|demasiado\s+|too\s+|very\s+|trop\s+|tres\s+|zu\s+|sehr\s+)?(?:tochos?|larg[oa]s?|extens[oa]s?|"
    r"gord[oa]s?|pesad[oa]s?"
    r"|long|lengthy|chunky|thick|doorstopper"
    r"|longs?|longues?|paves?|epais|epaisses?"
    r"|lang(?:e[snrm]?)?|dick(?:e[snrm]?)?|walzer)\b"
)
_BIEN_VALORADO = (
    r"\b(?:muy\s+)?(?:bien valorad[oa]s?|buenas (?:criticas|resenas|valoraciones)|"
    r"muy valorad[oa]s?|bien puntuad[oa]s?|con buena nota"
    r"|highly rated|well rated|top rated|well reviewed|good reviews"
    r"|(?:tres )?bien notes?|bonnes critiques|bien critiques?"
    r"|(?:sehr )?(?:gut|hoch) bewertet(?:e[snrm]?)?|gute (?:bewertungen|kritiken|rezensionen))\b"
)


def _extraer_vagas(t, pref):

    for m in t.buscar(_CORTO):
        negado = _hay_negacion_antes(t.norm, m.start())
        if negado and pref["min_paginas"] is None:
            pref["min_paginas"] = config.PAGINAS_CORTO
        elif not negado and pref["max_paginas"] is None:
            pref["max_paginas"] = config.PAGINAS_CORTO
        t.consumir(m.start(), m.end())

    for m in t.buscar(_LARGO):
        cerca = t.norm[max(0, m.start() - 8):m.end() + 6]
        if any(f in cerca for f in ("a lo largo", "long ago", "all day long", "long time",
                                    "seit lange", "lange zeit", "langer zeit", "so lange")):
            continue  # "a lo largo de la historia" / "long ago" no hablan de páginas
        negado = _hay_negacion_antes(t.norm, m.start())
        if negado and pref["max_paginas"] is None:
            pref["max_paginas"] = config.PAGINAS_NO_LARGO
        elif not negado and pref["min_paginas"] is None:
            pref["min_paginas"] = config.PAGINAS_LARGO
        t.consumir(m.start(), m.end())

    for m in t.buscar(_BIEN_VALORADO):
        if pref["min_rating"] is None:
            pref["min_rating"] = config.RATING_BIEN_VALORADO
        t.consumir(m.start(), m.end())


# --------------------------------------------------
# EXCLUSIONES ("que no sea romántica", "nada de terror")
# --------------------------------------------------

_INICIO_EXCLUSION = (
    r"(?:que no (?:sea|sean|tenga|tengan|trate|traten)(?: de| sobre)?"
    r"|no quiero(?: nada de| ningun| ninguna| libros? de| novelas? de)?"
    r"|no me (?:gusta|gustan|interesa|interesan)"
    r"|nada de|sin"
    # inglés
    r"|(?:that|which) (?:is|are)(?:n't| not)(?: about)?|not about|nothing(?: about)?|without"
    r"|(?:i )?(?:don't|dont|do not) (?:want|like)(?: any)?|no more"
    # francés
    r"|qui ne (?:soit|soient) pas|(?:je )?ne veux pas(?: de| d')?|pas de|pas d'|rien de|sans"
    # alemán
    r"|(?:ich (?:will|mochte|mag) )?(?:bitte )?kein(?:e|en|er|es)?(?: bucher uber| romane uber)?"
    r"|nichts (?:mit|uber|von)|nicht uber|ohne)\s+"
)
_ARTICULOS = (
    r"^(?:(?:un|una|unos|unas|el|la|los|las|de|del|nada de|libros? de|novelas? de"
    r"|a|an|the|any|books? about|novels? about"
    r"|le|la|les|une|des|du|de la|livres? de|romans? de|d'"
    r"|der|die|das|den|dem|ein|eine|einen|etwas)\s*)+"
)


def _extraer_exclusiones(t, pref):

    patron = r"\b" + _INICIO_EXCLUSION + r"([^,.;]+?)(?=[,.;]| pero | y que | y con | y de | but | and | mais | et | aber | und |$)"
    for m in t.buscar(patron):
        inicio_grupo = m.start(1)
        fragmento = t.restante()[inicio_grupo:m.end(1)]
        # "que no sea romance ni fantasía" → dos exclusiones
        for trozo in re.split(r"\s+(?:ni|o|or|nor|ou|oder|noch)\s+", fragmento, flags=re.IGNORECASE):
            trozo = re.sub(_ARTICULOS, "", trozo.strip(), flags=re.IGNORECASE).strip(" ,.;")
            if len(trozo) >= 3:
                pref["excluir"].append(trozo)
        t.consumir(m.start(), m.end())


# --------------------------------------------------
# LIMPIEZA DE LA CONSULTA SEMÁNTICA
# --------------------------------------------------

_RELLENO = (
    r"\b(?:quiero|quisiera|busco|estoy buscando|me apetece(?: leer)?|me gustaria(?: leer)?|"
    r"recomiendame|recomiendeme|dame|por favor|algo que|que sea|que tenga|y que"
    r"|i want|i'd like|i would like|i'm looking for|im looking for|looking for|recommend me|give me|please"
    r"|i don't want|i dont want|i do not want"
    r"|je ne veux pas|je ne veux|je veux|je voudrais|je cherche|conseille-moi|conseillez-moi|donne-moi|s'il (?:te|vous) plait"
    r"|ich will|ich mochte(?: lesen)?|ich hatte gern(?:e)?|ich suche|empfiehl mir|gib mir|bitte|etwas,? das)\b"
)


def _limpiar_consulta(texto):
    norm = _normalizar(texto)
    trozos = []
    ultimo = 0
    for m in re.finditer(_RELLENO, norm):
        trozos.append(texto[ultimo:m.start()])
        ultimo = m.end()
    trozos.append(texto[ultimo:])
    limpio = re.sub(r"\s+", " ", "".join(trozos))
    limpio = re.sub(r"\s+([,.;])", r"\1", limpio)
    limpio = re.sub(r"[,.;]{2,}", ",", limpio)
    # Quitar conectores sueltos al principio o al final
    conectores = (r"(?:y|e|o|de|con|que|un|una|el|la|pero|ni|no"
                  r"|and|or|with|a|an|the|but|of|et|ou|avec|mais|le|les|une|des|du"
                  r"|und|oder|mit|aber|ein|eine|einen|der|die|das|von|etwas|,|\.|;)")
    anterior = None
    while anterior != limpio:
        anterior = limpio
        limpio = re.sub(rf"^\s*{conectores}\s+", "", limpio, flags=re.IGNORECASE)
        limpio = re.sub(rf"\s+{conectores}\s*$", "", limpio, flags=re.IGNORECASE)
        limpio = limpio.strip(" ,.;-")
    return limpio


# --------------------------------------------------
# REGLAS (siempre)
# --------------------------------------------------

def interpretar_con_reglas(texto):

    pref = {
        "consulta_semantica": texto,
        "max_paginas": None,
        "min_paginas": None,
        "min_rating": None,
        "excluir": [],
        "ollama": "no usado",
    }

    t = _Texto(texto)
    _extraer_paginas(t, pref)
    _extraer_rating(t, pref)
    _extraer_vagas(t, pref)
    _extraer_exclusiones(t, pref)

    pref["consulta_semantica"] = _limpiar_consulta(t.restante())

    # Si hay contradicción (mín > máx), los intercambiamos
    if pref["min_paginas"] and pref["max_paginas"] and pref["min_paginas"] > pref["max_paginas"]:
        pref["min_paginas"], pref["max_paginas"] = pref["max_paginas"], pref["min_paginas"]

    return pref


# --------------------------------------------------
# OLLAMA (opcional)
# --------------------------------------------------

_PROMPT_OLLAMA = """Convierte esta petición de libros en JSON. Devuelve SOLO el JSON.

Formato:
{{"max_paginas": null, "min_paginas": null, "min_rating": null, "excluir": []}}

Reglas:
- Usa números solo si la petición los da o se deducen con seguridad. Si no, null.
- min_rating va de 0 a 5.
- "excluir": temas o géneros que el usuario NO quiere.

Ejemplos:
"No quiero menos de 400 páginas" -> {{"max_paginas": null, "min_paginas": 400, "min_rating": null, "excluir": []}}
"algo de misterio pero nada de sangre" -> {{"max_paginas": null, "min_paginas": null, "min_rating": null, "excluir": ["sangre"]}}

Petición: "{texto}"
"""


def interpretar_con_ollama(texto):
    """Devuelve un dict con lo que ha entendido Ollama, o None si no está disponible."""
    import requests

    try:
        respuesta = requests.post(
            config.OLLAMA_URL,
            json={
                "model": config.OLLAMA_MODELO,
                "prompt": _PROMPT_OLLAMA.format(texto=texto),
                "format": "json",      # obliga a Ollama a devolver JSON válido
                "stream": False,
                "think": False,        # qwen3 no "piensa" en voz alta → más rápido
                "options": {"temperature": 0},
            },
            timeout=config.OLLAMA_TIMEOUT,
        )
        respuesta.raise_for_status()
        contenido = respuesta.json().get("response", "")
        contenido = re.sub(r"<think>.*?</think>", "", contenido, flags=re.DOTALL).strip()
        return json.loads(contenido)
    except Exception as error:  # Ollama apagado, modelo no descargado, JSON roto...
        print(f"[Ollama] No disponible: {error}")
        return None


def _numero(valor):
    try:
        return float(valor) if valor is not None else None
    except (TypeError, ValueError):
        return None


# --------------------------------------------------
# FUNCIÓN PRINCIPAL
# --------------------------------------------------

def interpretar_consulta(texto, usar_ollama=False):

    pref = interpretar_con_reglas(texto)

    if not usar_ollama:
        return pref

    datos = interpretar_con_ollama(texto)
    if datos is None:
        pref["ollama"] = "no disponible"
        return pref

    # Las reglas mandan. Ollama solo rellena lo que ellas no encontraron.
    for campo in ["max_paginas", "min_paginas"]:
        valor = _numero(datos.get(campo))
        if pref[campo] is None and valor and valor > 0:
            pref[campo] = int(valor)

    valor = _numero(datos.get("min_rating"))
    if pref["min_rating"] is None and valor is not None and 0 < valor <= 5:
        pref["min_rating"] = valor

    for termino in datos.get("excluir") or []:
        if isinstance(termino, str) and termino.strip() and termino not in pref["excluir"]:
            pref["excluir"].append(termino.strip())

    pref["ollama"] = "usado"
    return pref


def resumen(pref, idioma="es"):
    """Frase corta que explica lo que se ha entendido (se muestra al usuario)."""
    from libreria.textos import t

    partes = []
    if pref["min_paginas"] and pref["max_paginas"]:
        partes.append(t(idioma, "r_entre", a=pref["min_paginas"], b=pref["max_paginas"]))
    elif pref["max_paginas"]:
        partes.append(t(idioma, "r_max", n=pref["max_paginas"]))
    elif pref["min_paginas"]:
        partes.append(t(idioma, "r_min", n=pref["min_paginas"]))
    if pref["min_rating"]:
        partes.append(t(idioma, "r_nota", n=pref["min_rating"]))
    if pref["excluir"]:
        partes.append(t(idioma, "r_sin", x=", ".join(pref["excluir"])))
    return " · ".join(partes)


# --------------------------------------------------
# PRUEBA RÁPIDA:  python -m libreria.interprete
# --------------------------------------------------

if __name__ == "__main__":
    while True:
        texto = input("\n¿Qué libro buscas? (Enter para salir): ").strip()
        if not texto:
            break
        p = interpretar_consulta(texto)
        print(json.dumps(p, ensure_ascii=False, indent=2))
