#!/usr/bin/env python3
"""Simulador de telemetría: genera sesiones realistas y las envía a la API de Ingesta.

Solo usa la biblioteca estándar, así que funciona sin instalar nada:

    python tools/simulador.py --token token-dev-piloto-1 --sesiones 20
    python tools/simulador.py --solo-imprimir --sesiones 1      # muestra el JSON sin enviarlo
"""

import argparse
import json
import random
import sys
import urllib.error
import urllib.request

# Tiempos de referencia por sector (ms) de cada coche en cada circuito, en seco.
CATALOGO = {
    "assetto_corsa_competizione": {
        "vehiculos": ["porsche_992_gt3_r", "ferrari_296_gt3", "bmw_m4_gt3"],
        "circuitos": {
            "spa_francorchamps": [41800, 59200, 37300],
            "monza": [34900, 37600, 33200],
            "nurburgring": [38100, 42700, 32900],
        },
    },
    "f1_25": {
        "vehiculos": ["red_bull_rb21", "ferrari_sf25", "mclaren_mcl39"],
        "circuitos": {
            "silverstone": [28900, 34100, 24700],
            "monaco": [19800, 34200, 18600],
        },
    },
}
FACTOR_VEHICULO = (1.000, 1.004, 1.008)
FACTOR_MOJADO = 1.11


def generar_setup(rng: random.Random) -> dict:
    return {
        "presiones_psi": {r: round(rng.uniform(26.5, 28.0), 1) for r in ("di", "dd", "ti", "td")},
        "aero": {"ala_trasera": rng.randint(2, 10), "splitter": rng.randint(0, 5)},
        "suspension": {
            "altura_del_mm": rng.randint(48, 60),
            "altura_tra_mm": rng.randint(62, 78),
            "barra_del": rng.randint(1, 6),
            "barra_tra": rng.randint(1, 6),
        },
    }


def generar_sesion(rng: random.Random) -> dict:
    juego = rng.choice(list(CATALOGO))
    datos = CATALOGO[juego]
    indice = rng.randrange(len(datos["vehiculos"]))
    circuito = rng.choice(list(datos["circuitos"]))
    mojado = rng.random() < 0.2
    habilidad = rng.uniform(1.0, 1.03)  # lo lejos que está el piloto del tiempo de referencia
    regularidad = rng.uniform(0.001, 0.006)

    base = [
        s * FACTOR_VEHICULO[indice] * habilidad * (FACTOR_MOJADO if mojado else 1)
        for s in datos["circuitos"][circuito]
    ]
    vueltas = []
    for numero in range(1, rng.randint(3, 12) + 1):
        sectores = [round(s * rng.gauss(1, regularidad)) for s in base]
        valida = rng.random() > 0.1  # ~10 % de vueltas con límites de pista excedidos
        if rng.random() < 0.05:  # algún trompo o tráfico: vuelta anómala
            sectores[rng.randrange(len(sectores))] += rng.randint(8000, 20000)
        vueltas.append(
            {
                "numero": numero,
                "tiempo_ms": sum(sectores),
                "sectores_ms": sectores,
                "valida": valida,
            }
        )

    return {
        "juego": juego,
        "vehiculo": datos["vehiculos"][indice],
        "circuito": circuito,
        "condiciones": {
            "pista": "mojado" if mojado else "seco",
            "temp_aire_c": rng.randint(8, 18) if mojado else rng.randint(15, 32),
            "temp_pista_c": rng.randint(10, 22) if mojado else rng.randint(20, 48),
        },
        "setup": generar_setup(rng),
        "vueltas": vueltas,
    }


def enviar(url: str, token: str, sesion: dict, timeout: float) -> tuple[int, dict]:
    peticion = urllib.request.Request(
        f"{url.rstrip('/')}/api/telemetria",
        data=json.dumps(sesion).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(peticion, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--url", default="http://localhost:8001", help="URL base de la Ingesta")
    p.add_argument("--token", default="token-dev-piloto-1", help="token Bearer del piloto")
    p.add_argument("--sesiones", type=int, default=10, help="número de sesiones a generar")
    p.add_argument("--semilla", type=int, default=None, help="semilla para resultados repetibles")
    p.add_argument("--timeout", type=float, default=5.0)
    p.add_argument("--solo-imprimir", action="store_true", help="imprime el JSON y no envía nada")
    args = p.parse_args(argv)

    rng = random.Random(args.semilla)
    errores = 0
    for i in range(1, args.sesiones + 1):
        sesion = generar_sesion(rng)
        if args.solo_imprimir:
            print(json.dumps(sesion, ensure_ascii=False, indent=2))
            continue
        try:
            estado, cuerpo = enviar(args.url, args.token, sesion, args.timeout)
        except OSError as e:
            print(f"[{i}/{args.sesiones}] sin conexión con {args.url}: {e}", file=sys.stderr)
            return 2
        ok = estado == 202
        errores += not ok
        detalle = cuerpo.get("id_sesion") if ok else cuerpo
        print(
            f"[{i}/{args.sesiones}] {estado} {sesion['vehiculo']} @ {sesion['circuito']}: {detalle}"
        )
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
