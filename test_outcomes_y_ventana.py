#!/usr/bin/env python3
"""Tests D3 (fuente única de outcomes) y D4 (ventana de get_already_audited_ids).

D3: había 3 listas de outcomes divergiendo en silencio. `seguimiento_humano`
    (7º outcome de Elena Voice, 2026-05-22) nunca se agregó a ARIA → se mapeaba
    a None y se perdía el original.
D4: `limit=10000` con docstring "covers ~100 days". Ambas cosas falsas: el tope
    real de PostgREST es 1.000, y esto corre cada 3 min.

Corre:  python3 -u test_outcomes_y_ventana.py
"""
import os
import sys

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-no-usada")

import aria_audit  # noqa: E402
from aria_audit import OUTCOMES_ARIA, OUTCOME_LABELS, get_already_audited_ids  # noqa: E402

FALLOS = []


def check(nombre, real, esperado):
    ok = real == esperado
    print(f"  {'✅' if ok else '❌'} {nombre}  (esperado={esperado} real={real})")
    if not ok:
        FALLOS.append(nombre)


print("\n═══ D3 · fuente única de outcomes ═══")
check("los 6 outcomes que Juan definió", len(OUTCOMES_ARIA), 6)
check("todos tienen etiqueta (invariante que revienta al importar)",
      all(o in OUTCOME_LABELS for o in OUTCOMES_ARIA), True)
check("seguimiento_humano tiene etiqueta para reportes",
      "seguimiento_humano" in OUTCOME_LABELS, True)
check("...pero ARIA NO puede emitirlo (lo emite el origen)",
      "seguimiento_humano" in OUTCOMES_ARIA, False)
check("numero_invalido igual: etiqueta sí, emisión no",
      ("numero_invalido" in OUTCOME_LABELS, "numero_invalido" in OUTCOMES_ARIA),
      (True, False))

print("\n═══ D3 · el valor descartado ya no se pierde ═══")
fuente = open(os.path.join(os.path.dirname(__file__), "aria_audit.py")).read()
check("se persiste outcomes_descartados en raw_vapi_data",
      '"outcomes_descartados": outcomes_descartados or None' in fuente, True)
check("el fallo dejó de ser un warning silencioso",
      "log.error(\n            f\"aria_outcome inválido" in fuente
      or 'log.error(' in fuente.split("aria_outcome inválido")[0][-200:], True)

print("\n═══ D4 · la query ya no pide 10.000 ni miente ═══")
capturado = {}


def fake_query(tabla, qs):
    capturado["tabla"] = tabla
    capturado["qs"] = qs
    return [{"vapi_call_id": f"c{i}"} for i in range(8)]


aria_audit.supabase_query = fake_query
ids = get_already_audited_ids()
check("consulta call_audits", capturado.get("tabla"), "call_audits")
check("ya NO pide limit=10000", "limit=10000" in capturado.get("qs", ""), False)
check("acota por ventana temporal", "created_at=gte." in capturado.get("qs", ""), True)
check("pide como mucho el tope real de PostgREST",
      "limit=1000" in capturado.get("qs", ""), True)
check("devuelve el set de ids", len(ids), 8)

print("\n═══ D4 · si se alcanza el tope, lo dice en voz alta ═══")
gritos = []
_err_original = aria_audit.log.error
aria_audit.log.error = lambda m, *a, **k: gritos.append(str(m))
aria_audit.supabase_query = lambda t, q: [{"vapi_call_id": f"c{i}"} for i in range(1000)]
get_already_audited_ids()
aria_audit.log.error = _err_original
check("alerta al llegar a 1.000 filas (antes truncaba en silencio)",
      any("tope de PostgREST" in g for g in gritos), True)

print("\n═══ regresión: la ventana por defecto cubre el polling (25h) ═══")
import inspect  # noqa: E402
sig = inspect.signature(get_already_audited_ids)
check("default de 48h ≥ 25h del polling",
      sig.parameters["hours_back"].default >= 25, True)

print("\n" + "═" * 60)
if FALLOS:
    print(f"❌ {len(FALLOS)} FALLO(S): {', '.join(FALLOS)}")
    sys.stdout.flush()
    os._exit(1)
print("✅ TODOS VERDES — outcomes con fuente única y ventana acotada")
sys.stdout.flush()
os._exit(0)
