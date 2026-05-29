import requests
import os
import json
import unicodedata
from datetime import datetime, timezone
import pytz

# ─── CONFIGURACIÓN ───────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID        = os.environ["CHAT_ID"]
ZONA           = pytz.timezone("America/Argentina/Buenos_Aires")

JUGADORES = [
    {"nombre": "Shea Langeliers",    "equipo": "ATH"},
    {"nombre": "Sal Stewart",        "equipo": "CIN"},
    {"nombre": "Luis Arraez",        "equipo": "SF"},
    {"nombre": "JJ Wetherholt",      "equipo": "STL"},
    {"nombre": "Elly De La Cruz",    "equipo": "CIN"},
    {"nombre": "Fernando Tatis Jr.", "equipo": "SD"},
    {"nombre": "Jose Caballero",     "equipo": "NYY"},
    {"nombre": "Chase DeLauter",     "equipo": "CLE"},
    {"nombre": "Christian Yelich",   "equipo": "MIL"},
    {"nombre": "Sal Frelick",        "equipo": "MIL"},
    {"nombre": "Dillon Dingler",     "equipo": "DET"},
    {"nombre": "Richie Palacios",    "equipo": "CLE"},
    {"nombre": "Colson Montgomery",  "equipo": "CWS"},
    {"nombre": "Jarren Duran",       "equipo": "BOS"},
    {"nombre": "Josh Naylor",        "equipo": "SEA"},
    {"nombre": "Brice Turang",       "equipo": "MIL"},
    {"nombre": "Ernie Clement",      "equipo": "TOR"},
    {"nombre": "Bobby Witt Jr.",     "equipo": "KC"},
    {"nombre": "Jung Hoo Lee",       "equipo": "SF"},
    {"nombre": "Wilyer Abreu",       "equipo": "BOS"},
    {"nombre": "Michael Harris II",  "equipo": "ATL"},
    {"nombre": "Shohei Ohtani",      "equipo": "LAD"},
    {"nombre": "Angel Martinez",     "equipo": "CLE"},
    {"nombre": "Carlos Cortes",      "equipo": "ATH"},
    {"nombre": "Keibert Ruiz",       "equipo": "WSH"},
    {"nombre": "Nolan Arenado",      "equipo": "AZ"},
    {"nombre": "Otto Lopez",         "equipo": "MIA"},
    {"nombre": "Wyatt Langford",     "equipo": "TEX"},
    {"nombre": "Ivan Herrera",       "equipo": "STL"},
    {"nombre": "Nick Kurtz",         "equipo": "ATH"},
    {"nombre": "Luke Keaschall",     "equipo": "MIN"},
    {"nombre": "Junior Caminero",    "equipo": "TB"},
    {"nombre": "Kevin McGonigle",    "equipo": "DET"},
    {"nombre": "Corbin Carroll",     "equipo": "AZ"},
    {"nombre": "Julio Rodriguez",    "equipo": "SEA"},
    {"nombre": "Munetaka Murakami",  "equipo": "CWS"},
    {"nombre": "Jeff McNeil",        "equipo": "ATH"},
    {"nombre": "Jac Caglianone",     "equipo": "KC"},
    {"nombre": "CJ Abrams",          "equipo": "WSH"},
    {"nombre": "Dalton Rushing",     "equipo": "LAD"},
    {"nombre": "Oswald Peraza",      "equipo": "LAA"},
]

def normalizar(texto):
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto.lower().strip()

JUGADORES_NORM = {}
for j in JUGADORES:
    clave = normalizar(j["nombre"])
    if clave not in JUGADORES_NORM:
        JUGADORES_NORM[clave] = j

# ─── ESTADO (archivo JSON para no repetir alertas del mismo día) ──
STATE_FILE = "alertas_state.json"

def cargar_estado():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def guardar_estado(estado):
    with open(STATE_FILE, "w") as f:
        json.dump(estado, f)

# ─── TELEGRAM ────────────────────────────────────────────────────
def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}, timeout=10)
        print(f"[Telegram] Status: {r.status_code} — {r.text}")
        return r.status_code == 200
    except Exception as e:
        print(f"[Telegram ERROR] {e}")
        return False

# ─── MLB API ─────────────────────────────────────────────────────
def get_juegos_hoy():
    hoy = datetime.now(ZONA).strftime("%Y-%m-%d")
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={hoy}"
    try:
        r = requests.get(url, timeout=15)
        data = r.json()
        juegos = []
        for fecha in data.get("dates", []):
            for juego in fecha.get("games", []):
                juegos.append(juego)
        print(f"{len(juegos)} juego(s) hoy ({hoy})")
        return juegos
    except Exception as e:
        print(f"[MLB API ERROR] {e}")
        return []

def get_boxscore(game_pk):
    url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"
    try:
        r = requests.get(url, timeout=15)
        return r.json()
    except:
        return {}

# ─── VERIFICAR ALINEACIONES ──────────────────────────────────────
def verificar():
    hoy   = datetime.now(ZONA).strftime("%Y-%m-%d")
    estado = cargar_estado()

    # Limpiar estado de días anteriores
    estado = {k: v for k, v in estado.items() if k.startswith(hoy)}

    juegos = get_juegos_hoy()
    nuevas_alertas = 0

    for juego in juegos:
        game_pk    = juego.get("gamePk")
        estado_juego = juego.get("status", {}).get("abstractGameState", "")
        teams      = juego.get("teams", {})
        home_abrev = teams.get("home", {}).get("team", {}).get("abbreviation", "")
        away_abrev = teams.get("away", {}).get("team", {}).get("abbreviation", "")

        if estado_juego not in ("Preview", "Live", "Final"):
            continue

        boxscore    = get_boxscore(game_pk)
        equipos_box = boxscore.get("teams", {})

        for lado in ("home", "away"):
            equipo_data   = equipos_box.get(lado, {})
            abrev         = equipo_data.get("team", {}).get("abbreviation", "")
            rival         = away_abrev if lado == "home" else home_abrev
            batting_order = equipo_data.get("battingOrder", [])
            titulares_ids = set(str(b) for b in batting_order)
            players       = equipo_data.get("players", {})

            for player_key, pdata in players.items():
                nombre_completo = pdata.get("person", {}).get("fullName", "")
                nombre_norm     = normalizar(nombre_completo)
                person_id       = str(pdata.get("person", {}).get("id", ""))

                jugador_info = None
                for nombre_key, info in JUGADORES_NORM.items():
                    if nombre_key in nombre_norm or nombre_norm in nombre_key:
                        if normalizar(info["equipo"]) == normalizar(abrev):
                            jugador_info = info
                            break

                if not jugador_info:
                    continue

                clave_dia = f"{hoy}_{jugador_info['nombre']}"
                if clave_dia in estado:
                    continue

                if titulares_ids and person_id not in titulares_ids:
                    estado[clave_dia] = True

                    status_code = pdata.get("status", {}).get("code", "")
                    motivo = "🚑 *LESIONADO / IL*" if status_code in ("D10", "D15", "D60", "IL") else "🪑 *SUPLENTE* — no está en la alineación"

                    hora_utc = juego.get("gameDate", "")
                    try:
                        dt_utc  = datetime.strptime(hora_utc, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                        hora_txt = dt_utc.astimezone(ZONA).strftime("%H:%M hs Argentina")
                    except:
                        hora_txt = hora_utc

                    mensaje = (
                        f"⚾ *ALERTA MLB — Fantasy*\n"
                        f"*{jugador_info['nombre']}* ({abrev})\n"
                        f"{motivo}\n"
                        f"vs {rival} — {hora_txt}"
                    )
                    print(f"ALERTA: {jugador_info['nombre']} no titular ({abrev}) vs {rival}")
                    enviar_telegram(mensaje)
                    nuevas_alertas += 1

    guardar_estado(estado)
    print(f"Verificación completa. {nuevas_alertas} alerta(s) enviada(s).")

if __name__ == "__main__":
    verificar()
