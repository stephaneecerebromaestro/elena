#!/usr/bin/env python3
"""Tests del few-shot balanceado — FIX 2026-08-06: bucle auto-confirmatorio.

Antes: "los 20 más recientes por fecha" sobre un feedback_log con 95,5% de
aprobaciones → 10 ejemplos que casi siempre decían "ARIA tiene razón", y que
además repetían ~3 lecciones (los 361 aprobados tienen solo 16 pares distintos).

Corre:  python3 -u test_fewshot_balance.py
"""
import os
import sys

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-no-usada")

import aria_audit  # noqa: E402
from aria_audit import _dedup_por_par, build_fewshot_block, get_recent_feedback  # noqa: E402

FALLOS = []


def check(nombre, real, esperado):
    ok = real == esperado
    print(f"  {'✅' if ok else '❌'} {nombre}  (esperado={esperado} real={real})")
    if not ok:
        FALLOS.append(nombre)


def fb(tipo, orig, aria, final="x", cid="c1"):
    return {"feedback_type": tipo, "original_outcome": orig,
            "aria_outcome": aria, "final_outcome": final, "vapi_call_id": cid}


print("\n═══ _dedup_por_par ═══")
d = _dedup_por_par([fb("approved", "no_contesto", "llamar_luego"),
                    fb("approved", "no_contesto", "llamar_luego"),
                    fb("approved", "no_agendo", "no_contesto")])
check("colapsa pares repetidos", len(d), 2)

print("\n═══ BALANCE — el corazón del fix ═══")
# Reproduce la proporción real de producción: 95,5% aprobados
falso_log = ([fb("rejected", "no_contesto", "no_agendo", cid="r1"),
              fb("rejected", "agendo", "no_agendo", cid="r2"),
              fb("rejected", "no_agendo", "agendo", cid="r3"),
              fb("rejected", "no_contesto", "no_interesado", cid="r4")]
             + [fb("approved", "no_contesto", "llamar_luego", cid=f"a{i}") for i in range(40)]
             + [fb("approved", "no_agendo", "no_contesto", cid=f"b{i}") for i in range(40)]
             + [fb("approved", "no_agendo", "no_interesado", cid="c0")]
             + [fb("approved", "no_contesto", "no_agendo", cid="d0")])

aria_audit.supabase_query = lambda t, q: falso_log          # noqa: E731
aria_audit._fewshot_cache = {"ts": 0.0, "data": None}

ej = get_recent_feedback(limit=10)
n_rej = sum(1 for e in ej if e["feedback_type"] == "rejected")
n_apr = len(ej) - n_rej
print(f"     → {len(ej)} ejemplos: {n_rej} rechazados / {n_apr} aprobados")
check("incluye rechazados (antes: casi nunca)", n_rej >= 4, True)
check("no son todos aprobados", n_apr < len(ej), True)

pares = {(e["original_outcome"], e["aria_outcome"]) for e in ej}
check("cada ejemplo enseña un par DISTINTO", len(pares), len(ej))

print("\n═══ el bloque marca los rechazos ═══")
bloque = build_fewshot_block(ej)
check("anuncia los rechazos", "RECHAZOS" in bloque, True)
check("los rechazos van primero", bloque.index("RECHAZÓ") < bloque.index("APROBÓ"), True)

print("\n═══ fail-safe: si Supabase cae, ARIA no se cae ═══")
def boom(t, q):
    raise RuntimeError("supabase caído")
aria_audit.supabase_query = boom
aria_audit._fewshot_cache = {"ts": 0.0, "data": None}
check("devuelve lista vacía sin reventar", get_recent_feedback(limit=10), [])
check("build_fewshot_block con [] no revienta", build_fewshot_block([]), "")

print("\n═══ caché: no consulta Supabase en cada auditoría ═══")
llamadas = {"n": 0}
def contando(t, q):
    llamadas["n"] += 1
    return falso_log
aria_audit.supabase_query = contando
aria_audit._fewshot_cache = {"ts": 0.0, "data": None}
for _ in range(5):
    get_recent_feedback(limit=10)
check("5 auditorías = 1 sola query", llamadas["n"], 1)

print("\n" + "═" * 60)
if FALLOS:
    print(f"❌ {len(FALLOS)} FALLO(S): {', '.join(FALLOS)}")
    sys.stdout.flush()
    os._exit(1)
print("✅ TODOS VERDES — el few-shot ya no se da la razón a sí mismo")
sys.stdout.flush()
os._exit(0)  # threads non-daemon al importar aria_audit (deuda conocida)
