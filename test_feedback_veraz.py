#!/usr/bin/env python3
"""Tests D7 — feedback_log decía que la corrección se aplicó aunque GHL fallara.

Por qué importa el doble: (1) la métrica de eficacia divergía de GHL, y (2) el
FEW-SHOT lee feedback_log, así que ARIA aprendía de un desenlace que nunca ocurrió.

Corre:  python3 -u test_feedback_veraz.py
"""
import os
import sys

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-no-usada")

import aria_audit  # noqa: E402
from aria_audit import apply_correction  # noqa: E402

FALLOS = []


def check(nombre, real, esperado):
    ok = real == esperado
    print(f"  {'✅' if ok else '❌'} {nombre}  (esperado={esperado} real={real})")
    if not ok:
        FALLOS.append(nombre)


CORRECCION = {
    "id": "corr-1", "correction_status": "pending", "ghl_contact_id": "gh-1",
    "old_value": "no_contesto", "new_value": "llamar_luego",
    "audit_id": 42, "vapi_call_id": "call-abc",
}


class RespFake:
    status_code = 200

    def json(self):
        return [CORRECCION]


def montar(ghl_resultado):
    """Intercepta todo lo externo y captura lo que se escribiría."""
    capt = {"feedback": None, "corrections": None, "telegram": None}
    aria_audit.requests.get = lambda *a, **k: RespFake()
    aria_audit.update_ghl_contact_outcome_detallado = lambda c, v: ghl_resultado

    def fake_insert(tabla, data):
        if tabla == "feedback_log":
            capt["feedback"] = data
        return {"ok": True}

    def fake_update(tabla, filtros, data):
        if tabla == "aria_corrections":
            capt["corrections"] = data
        return True

    aria_audit.supabase_insert = fake_insert
    aria_audit.supabase_update = fake_update
    aria_audit.telegram_send = lambda t, *a, **k: capt.__setitem__("telegram", t) or {"ok": 1}
    os.environ["SUPABASE_SERVICE_KEY"] = "fake-key"
    return capt


print("\n═══ CASO 1 · Juan aprueba y GHL aplica bien ═══")
capt = montar((True, 200, "OK"))
res = apply_correction("corr-1", approved=True)
check("la corrección queda applied", capt["corrections"]["correction_status"], "applied")
check("final_outcome = el valor nuevo", capt["feedback"]["final_outcome"], "llamar_luego")
check("feedback_type = approved", capt["feedback"]["feedback_type"], "approved")
check("se guarda el código REAL de GHL", capt["corrections"]["ghl_response_code"], 200)

print("\n═══ CASO 2 · EL BUG: Juan aprueba pero GHL RECHAZA ═══")
capt = montar((False, 500, "internal error"))
res = apply_correction("corr-1", approved=True)
check("la corrección NO queda applied", capt["corrections"]["correction_status"], "pending")
check("🔴 final_outcome = el valor REAL en GHL (antes mentía)",
      capt["feedback"]["final_outcome"], "no_contesto")
check("feedback_type sigue approved (el juicio de Juan es válido)",
      capt["feedback"]["feedback_type"], "approved")
check("el código real de GHL se guarda (antes se fabricaba un 500)",
      capt["corrections"]["ghl_response_code"], 500)
check("las notas dicen la verdad", "GHL NO aplicó" in capt["feedback"]["notes"], True)
check("Telegram avisa con el código real", "500" in str(capt["telegram"]), True)
check("apply_correction reporta el fallo", res["success"], False)

print("\n═══ CASO 3 · timeout de red contra GHL ═══")
capt = montar((False, None, "excepción: timeout"))
res = apply_correction("corr-1", approved=True)
check("no revienta, queda pending", capt["corrections"]["correction_status"], "pending")
check("final_outcome sigue siendo el real", capt["feedback"]["final_outcome"], "no_contesto")

print("\n═══ CASO 4 · Juan RECHAZA (no se toca GHL) ═══")
capt = montar((True, 200, "OK"))
res = apply_correction("corr-1", approved=False)
check("queda reverted", capt["corrections"]["correction_status"], "reverted")
check("final_outcome = el valor original", capt["feedback"]["final_outcome"], "no_contesto")
check("feedback_type = rejected", capt["feedback"]["feedback_type"], "rejected")
check("no se inventa código de GHL", capt["corrections"]["ghl_response_code"], None)

print("\n" + "═" * 60)
if FALLOS:
    print(f"❌ {len(FALLOS)} FALLO(S): {', '.join(FALLOS)}")
    sys.stdout.flush()
    os._exit(1)
print("✅ TODOS VERDES — feedback_log ya no dice que se aplicó lo que GHL rechazó")
sys.stdout.flush()
os._exit(0)
