"""Prueba una conversación completa contra la API en ejecución.

Uso (desde backend/, con el servidor encendido):
    python scripts/probar_conversacion.py
    python scripts/probar_conversacion.py --escenario escalera
    python scripts/probar_conversacion.py --url https://tu-app.onrender.com

Cada ejecución crea un estudiante nuevo (prueba-<hora>) y escribe sus logs en la
tabla `logs`. Los mensajes están pensados para el problema P001.
"""
import argparse
import json
import secrets
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.decision import decidir  # noqa: E402
from app.domain.enums import Clasificacion  # noqa: E402
from app.domain.state import calcular_estado  # noqa: E402
from app.services.tutor_writer import contiene_codigo  # noqa: E402

ESCENARIOS = {
    # Recorre varias clasificaciones: inactivo, solicitud, error, parcial y acierto.
    "mixto": [
        "no sé por dónde empezar",
        "dame el código de una vez",
        "creo que hay que multiplicar 1500 por 200 y ya",
        "guardo el 1500 en algo, pero no sé cómo sumarle los 200",
        "Creo una variable precio con 1500. Luego la actualizo asignándole precio más 200, "
        "y así queda en 1700.",
        # Responde a la variación que plantee el tutor, sea cual sea.
        "uso la misma variable: le sumo cada aumento al valor que ya tiene guardado "
        "y reemplazo el contenido con el resultado, paso por paso",
    ],
    # Errores seguidos: debe escalar de nivel y terminar en retroceso.
    "escalera": [
        "Creo que hay que restar 200 a 1500",
        "Multiplico 1500 por 200",
        "Divido 1500 entre 200",
        "Sumo 1500 más 1500",
        "Resto 200 otra vez",
        "Multiplico otra vez",
    ],
}
CAMPOS_PRIVADOS = ("criterio_correcto", "pista_nivel1", "pista_nivel2", "analogia", "pseudocodigo_parcial")


def llamar(metodo, url, cuerpo=None):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    peticion = urllib.request.Request(url, data=datos, method=metodo,
                                      headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(peticion, timeout=90) as respuesta:
            return respuesta.status, json.loads(respuesta.read())
    except urllib.error.HTTPError as exc:
        return exc.code, {"detail": exc.read().decode(errors="replace")}


def comprobar_catalogo(base, problema):
    estado, problemas = llamar("GET", f"{base}/problems")
    if estado != 200:
        return [f"GET /problems devolvió {estado}"]
    fallos = []
    if problema not in [p.get("id") for p in problemas]:
        fallos.append(f"el problema {problema} no aparece en /problems")
    expuestos = {c for p in problemas for c in CAMPOS_PRIVADOS if c in p}
    if expuestos:
        fallos.append(f"/problems expone campos privados: {sorted(expuestos)}")
    return fallos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--escenario", choices=ESCENARIOS, default="mixto")
    ap.add_argument("--problema", default="P001")
    ap.add_argument("--estudiante", default=f"prueba-{int(time.time())}-{secrets.token_hex(2)}")
    args = ap.parse_args()
    base = args.url.rstrip("/")

    print(f"Estudiante: {args.estudiante} | Problema: {args.problema} | Escenario: {args.escenario}\n")
    fallos = [f"[catálogo] {f}" for f in comprobar_catalogo(base, args.problema)]
    for f in fallos:
        print("FALLO", f)

    historial, logs_simulados = [], []
    registrados = tokens = tok_clas = tok_red = tok_cache = 0

    for turno, texto in enumerate(ESCENARIOS[args.escenario], 1):
        historial.append({"role": "user", "content": texto})
        inicio = time.time()
        estado, datos = llamar("POST", f"{base}/chat", {
            "student_id": args.estudiante, "problem_id": args.problema, "messages": historial})
        segundos = time.time() - inicio

        print(f"--- Turno {turno} ---\nEstudiante: {texto}")
        if estado != 200:
            print(f"FALLO: /chat devolvió {estado}: {datos}\n")
            fallos.append(f"turno {turno}: HTTP {estado}")
            historial.pop()
            continue

        respuesta, meta, perfil = datos["response"], datos["metadata"], datos["profile"]
        print(f"Tutor: {respuesta}")
        avisos = []
        if respuesta.count("?") > 1:
            avisos.append(f"{respuesta.count('?')} preguntas")
        if len(respuesta.split()) > 120:
            avisos.append(f"{len(respuesta.split())} palabras")
        if avisos:
            print(f"AVISO de estilo: {', '.join(avisos)}")

        if not meta.get("registrado"):
            print(f"AVISO: turno no registrado ({meta.get('motivo')}); sin comprobaciones\n")
            historial.append({"role": "assistant", "content": respuesta})
            continue

        registrados += 1
        tokens += meta.get("tokens_totales", 0)
        tok_clas += meta.get("tokens_clasificador", 0)
        tok_red += meta.get("tokens_redactor", 0)
        tok_cache += meta.get("tokens_en_cache", 0)
        clasificacion = meta["clasificacion"]
        esperado = decidir(Clasificacion(clasificacion), calcular_estado(logs_simulados))
        logs_simulados.append({"clasificacion": clasificacion, "nivel_intervencion": meta["nivel_intervencion"]})

        comprobaciones = {
            "nivel y acción coinciden con la matriz":
                (meta["nivel_intervencion"], meta["accion"]) == (esperado.nivel_intervencion, esperado.accion.value),
            "respuesta sin código": not contiene_codigo(respuesta),
            "respuesta sin metadata": "METADATA" not in respuesta and not respuesta.lstrip().startswith("{"),
            "respuesta no vacía": bool(respuesta.strip()),
            "perfil al día": perfil.get("total_interacciones") == registrados,
            "sin mensaje de respaldo": not meta.get("con_respaldo"),
        }
        print(f"[{clasificacion} | Bloom {meta['nivel_bloom']} | Nivel {meta['nivel_intervencion']} | "
              f"{meta['accion']} | {meta.get('tokens_totales', 0)} tokens "
              f"(clasif. {meta.get('tokens_clasificador', 0)} + redact. {meta.get('tokens_redactor', 0)}, "
              f"caché {meta.get('tokens_en_cache', 0)}) | {segundos:.1f} s]")
        print(f"Modelos: clasif. {meta.get('modelo_clasificador')} | redact. {meta.get('modelo_redactor')}")
        print(f"Justificación: {meta.get('justificacion')}")
        for nombre, ok in comprobaciones.items():
            if not ok:
                print(f"FALLO: {nombre} (esperado: nivel {esperado.nivel_intervencion}, {esperado.accion.value})")
                fallos.append(f"turno {turno}: {nombre}")
        print()
        historial.append({"role": "assistant", "content": respuesta})

    print("=== Resumen ===")
    print(f"Turnos registrados: {registrados} | Tokens totales: {tokens} | "
          f"Promedio por turno: {tokens // registrados if registrados else 0}")
    if registrados:
        print(f"Clasificador: {tok_clas // registrados}/turno | Redactor: {tok_red // registrados}/turno | "
              f"En caché: {tok_cache} de {tokens}")
    if fallos:
        print(f"{len(fallos)} fallo(s):")
        for f in fallos:
            print(" -", f)
        sys.exit(1)
    print("Todas las comprobaciones pasaron.")


if __name__ == "__main__":
    main()