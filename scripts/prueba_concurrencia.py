#!/usr/bin/env python3
"""Prueba de concurrencia de POST /asistencias (Integrante B, seccion 6.6).

Usa el flujo real: crea una sesion con POST /sesiones y dispara solicitudes
simultaneas (todas arrancan a la vez con una barrera). Solo libreria estandar.

Escenarios (cada uno con su propia sesion):
  1. MISMO estudiante N veces  -> esperado: 1 x 200 y (N-1) x 409 (sin duplicados)
  2. N estudiantes DISTINTOS   -> esperado: N x 200 (sin errores ni 429/5xx)

Uso:
  python scripts/prueba_concurrencia.py                 # N=100, lee ApiUrl del stack
  python scripts/prueba_concurrencia.py -n 50 --api-url https://xxxx.execute-api.us-east-1.amazonaws.com
  # verificar ademas cuantas filas quedaron en DynamoDB (requiere AWS CLI con credenciales):
  python scripts/prueba_concurrencia.py --tabla gtn-<equipo>-asistencias
Codigo 0 en los resultados = sin respuesta (timeout o error de red), no es un codigo HTTP.
Genera evidencias/concurrencia-<fecha>.md con resultados y tiempos.
"""
import argparse
import json
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path

STACK = "gtn-asistencia-qr"


def api_url_desde_stack():
    out = subprocess.run(
        ["aws", "cloudformation", "describe-stacks", "--stack-name", STACK,
         "--query", "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue",
         "--output", "text", "--no-cli-pager"],
        capture_output=True, text=True)
    return out.stdout.strip()


def filas_en_servidor(tabla, session_id):
    """Cuenta las asistencias de la sesion en DynamoDB (None si no se puede)."""
    try:
        out = subprocess.run(
            ["aws", "dynamodb", "query", "--table-name", tabla,
             "--key-condition-expression", "sessionId = :s",
             "--expression-attribute-values", json.dumps({":s": {"S": session_id}}),
             "--select", "COUNT", "--query", "Count", "--output", "text",
             "--consistent-read", "--no-cli-pager"],
            capture_output=True, text=True, timeout=30)
        return int(out.stdout.strip()) if out.returncode == 0 else None
    except Exception:
        return None


def post(url, cuerpo, timeout=15):
    """Devuelve (codigo_http, segundos). Codigo 0 = error de red/timeout."""
    datos = json.dumps(cuerpo).encode()
    req = urllib.request.Request(url, data=datos, method="POST",
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            r.read()
            return r.status, time.perf_counter() - t0
    except urllib.error.HTTPError as e:
        e.read()
        return e.code, time.perf_counter() - t0
    except Exception:
        return 0, time.perf_counter() - t0


def crear_sesion(api, course="GC-101", duracion=300):
    req = urllib.request.Request(
        f"{api}/sesiones", method="POST",
        data=json.dumps({"courseId": course, "durationSeconds": duracion}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())["sessionId"]


def disparar(api, session_id, ids):
    """Lanza len(ids) solicitudes a la vez; devuelve lista de (codigo, seg)."""
    n = len(ids)
    barrera = threading.Barrier(n)
    resultados = [None] * n

    def worker(i):
        barrera.wait()
        resultados[i] = post(f"{api}/asistencias",
                             {"sessionId": session_id, "studentId": ids[i]})

    hilos = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    t0 = time.perf_counter()
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    return resultados, time.perf_counter() - t0


def percentil(valores, p):
    v = sorted(valores)
    return v[min(len(v) - 1, int(round(p / 100 * (len(v) - 1))))]


def resumen(nombre, esperado, resultados, total_s, session_id="", filas_esperadas=None, tabla=""):
    codigos = Counter(c for c, _ in resultados)
    tiempos_ms = [t * 1000 for _, t in resultados]
    ok = codigos == Counter(esperado)
    filas_bd = filas_en_servidor(tabla, session_id) if tabla else None
    if filas_bd is not None and filas_bd != filas_esperadas:
        ok = False
    fila = {
        "nombre": nombre, "ok": ok, "codigos": dict(sorted(codigos.items())),
        "esperado": esperado, "total_s": total_s, "session": session_id,
        "filas_bd": filas_bd, "filas_esperadas": filas_esperadas,
        "p50": statistics.median(tiempos_ms), "p95": percentil(tiempos_ms, 95),
        "max": max(tiempos_ms),
    }
    print(f"[{'OK   ' if ok else 'FALLO'}] {nombre}: {fila['codigos']} "
          f"(esperado {esperado}) p50={fila['p50']:.0f}ms p95={fila['p95']:.0f}ms "
          f"max={fila['max']:.0f}ms total={total_s:.2f}s")
    if codigos.get(0):
        print(f"        ! {codigos[0]} solicitud(es) sin respuesta (timeout/red)")
    if tabla:
        print(f"        filas en DynamoDB para la sesion: {filas_bd} (esperado {filas_esperadas})")
    return fila


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=100, help="solicitudes simultaneas por escenario")
    ap.add_argument("--api-url", default="")
    ap.add_argument("--tabla", default="", help="tabla Asistencias para verificar filas (opcional)")
    args = ap.parse_args()

    api = (args.api_url or api_url_desde_stack()).rstrip("/")
    if not api:
        sys.exit("No pude obtener la URL de la API. Usa --api-url.")
    n = args.n
    print(f"API: {api}\nSolicitudes por escenario: {n}\n")

    filas = []

    sid1 = crear_sesion(api)
    res, tot = disparar(api, sid1, ["2000000001"] * n)
    filas.append(resumen(f"Mismo estudiante x{n}", {200: 1, 409: n - 1}, res, tot,
                         sid1, 1, args.tabla))

    sid2 = crear_sesion(api)
    ids = [str(2000000001 + i) for i in range(n)]
    res, tot = disparar(api, sid2, ids)
    filas.append(resumen(f"{n} estudiantes distintos", {200: n}, res, tot,
                         sid2, n, args.tabla))

    # Reporte markdown para evidencias/
    ahora = datetime.now()
    ruta = Path(__file__).resolve().parent.parent / "evidencias" / f"concurrencia-{ahora:%Y%m%d-%H%M}.md"
    ruta.parent.mkdir(exist_ok=True)
    lineas = [
        f"# Prueba de concurrencia POST /asistencias ({ahora:%Y-%m-%d %H:%M})",
        f"API: `{api}` - {n} solicitudes simultaneas por escenario.\n",
        "| Escenario | Codigos (0 = sin respuesta) | Esperado | Filas BD | p50 ms | p95 ms | max ms | Resultado |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for f in filas:
        bd = "n/d" if f["filas_bd"] is None else f"{f['filas_bd']} (esp. {f['filas_esperadas']})"
        lineas.append(f"| {f['nombre']} | {f['codigos']} | {f['esperado']} | {bd} | {f['p50']:.0f} | "
                      f"{f['p95']:.0f} | {f['max']:.0f} | {'OK' if f['ok'] else 'FALLO'} |")
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print(f"\nReporte: {ruta}")
    sys.exit(0 if all(f["ok"] for f in filas) else 1)


if __name__ == "__main__":
    main()
