#!/usr/bin/env python3
"""Tests del gate de buzón (A1) — FIX 2026-08-06: el gate ignoraba la duración.

Caso que lo parió (real, producción): llamada de 92s, endedReason=customer-ended-call,
transcript vacío → se marcó no_contesto con confianza 1.0. Era una conversación real.

Corre:  python3 test_gate_buzon.py
"""
import os
import sys

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-no-usada")

from aria_audit import (  # noqa: E402
    sin_conversacion_real,
    es_buzon_inequivoco,
    duracion_segundos,
    _MAX_SEG_SIN_TRANSCRIPT,
)

FALLOS = []


def check(nombre, real, esperado):
    ok = real == esperado
    print(f"  {'✅' if ok else '❌'} {nombre}  (esperado={esperado} real={real})")
    if not ok:
        FALLOS.append(nombre)


def llamada(dur_seg=0, transcript="", ended_reason="customer-did-not-answer"):
    """Construye un call_data de Vapi con la duración pedida."""
    base = "2026-08-06T12:00:00.000Z"
    fin = f"2026-08-06T12:{dur_seg // 60:02d}:{dur_seg % 60:02d}.000Z"
    return {
        "id": "test-call",
        "createdAt": base,
        "startedAt": base,
        "endedAt": fin if dur_seg else base,
        "endedReason": ended_reason,
        "transcript": transcript,
        "customer": {"number": "+13050000000"},
    }


print("\n═══ duracion_segundos ═══")
check("92s se calculan bien", duracion_segundos(llamada(92)), 92)
check("sin startedAt/endedAt → 0", duracion_segundos({"createdAt": "2026-08-06T12:00:00Z"}), 0)
check("basura no revienta → 0", duracion_segundos({"startedAt": "no-es-fecha", "endedAt": "x"}), 0)

print("\n═══ EL CASO REAL QUE FALLÓ EN PRODUCCIÓN ═══")
real_92s = llamada(92, transcript="", ended_reason="customer-ended-call")
check("llamada 92s sin transcript NO se auto-clasifica",
      sin_conversacion_real(real_92s), False)

print("\n═══ lo que SÍ debe seguir auto-clasificándose (el ahorro del 43%) ═══")
check("buzón típico 5s sin transcript", sin_conversacion_real(llamada(5)), True)
check("dur=0 sin transcript", sin_conversacion_real(llamada(0)), True)
check(f"justo en el umbral ({_MAX_SEG_SIN_TRANSCRIPT}s)",
      sin_conversacion_real(llamada(_MAX_SEG_SIN_TRANSCRIPT)), True)
check(f"un segundo pasado el umbral ({_MAX_SEG_SIN_TRANSCRIPT + 1}s)",
      sin_conversacion_real(llamada(_MAX_SEG_SIN_TRANSCRIPT + 1)), False)

print("\n═══ el patrón de máquina manda sobre la duración ═══")
buzon_largo = llamada(45, transcript=(
    "AI: Hola, habla Elena de Laser Place. ¿Cómo estás?\n"
    "User: At the tone, please record your message. When you have finished recording, "
    "you may hang up or press pound for more options."))
check("buzón inequívoco de 45s SÍ se auto-clasifica",
      sin_conversacion_real(buzon_largo), True)
check("es_buzon_inequivoco lo detecta", es_buzon_inequivoco(buzon_largo), True)

print("\n═══ conversación real: nunca se auto-clasifica ═══")
conversacion = llamada(120, transcript=(
    "AI: Hola, habla Elena de Laser Place. ¿Cómo estás?\n"
    "User: Bien gracias, dime.\n"
    "AI: Vi tu interés en el tratamiento de fillers, ¿te hago un par de preguntas?\n"
    "User: Sí claro, pero rápido que estoy en el trabajo.\n"
    "AI: Perfecto. ¿Qué es lo que más te molesta hoy?\n"
    "User: Las líneas de expresión sobre todo."))
check("conversación de 120s NO se auto-clasifica", sin_conversacion_real(conversacion), False)

print("\n═══ regresión: lo que decía el audit — un humano ocupado NO es buzón ═══")
humano = llamada(18, transcript=(
    "AI: Hola, habla Elena de Laser Place. ¿Cómo estás?\n"
    "User: Mira ahorita no puedo atenderte, te llamo más tarde."))
check("'no puedo atenderte' NO es buzón inequívoco (lead recuperable)",
      es_buzon_inequivoco(humano), False)

print("\n" + "═" * 60)
if FALLOS:
    print(f"❌ {len(FALLOS)} FALLO(S): {', '.join(FALLOS)}")
    sys.exit(1)
print("✅ TODOS VERDES — el gate ya no se traga conversaciones reales")
os._exit(0)  # threads non-daemon al importar aria_audit (deuda conocida desde abril)
