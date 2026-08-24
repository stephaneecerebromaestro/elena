#!/usr/bin/env python3
"""
update_dates.py — Actualiza la fecha en los prompts de todos los assistants de Elena Voice
Corre diariamente via cron (reemplaza la dependencia de Manus).

Uso:
    python3 scripts/update_dates.py               # actualiza todos
    python3 scripts/update_dates.py --bot botox   # actualiza solo uno
    python3 scripts/update_dates.py --dry-run     # muestra qué haría sin aplicar
"""

import argparse
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytz
import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
VAPI_API = "https://api.vapi.ai"
TZ = pytz.timezone("America/New_York")

DAYS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MONTHS_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
             "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

BOTS = {
    "botox":           {"assistant_id": "1631c7cf-2914-45f9-bf82-6635cdf00aba", "mirror": "system_prompt.txt"},
    "lhr":             {"assistant_id": "3d5b77b5-f36c-4b95-88bc-4d6484277380", "mirror": "system_prompt_lhr.txt"},
    "acne":            {"assistant_id": "77392648-047e-4a40-9f8a-4f125f2ed6d6", "mirror": "system_prompt_acne.txt"},
    "cicatrices":      {"assistant_id": "b6b09524-06da-4bf7-b518-a71b6a1c7d8b", "mirror": "system_prompt_cicatrices.txt"},
    "fillers":         {"assistant_id": "a9494200-af37-485c-b0fb-fb85479b17a7", "mirror": "system_prompt_fillers.txt"},
    "radiesse":        {"assistant_id": "39bd6450-055e-4839-9c27-6522e08e8423", "mirror": "system_prompt_radiesse.txt"},
    "rejuvenecimiento":{"assistant_id": "65b3a4b0-2e08-471f-af56-e091e47f26bd", "mirror": "system_prompt_rejuvenecimiento.txt"},
}

# Patrón del bloque de fecha — empieza en ## ⚡ FECHA ACTUAL, termina antes de la siguiente sección
DATE_BLOCK_RE = re.compile(
    r"(## ⚡ FECHA ACTUAL \(ACTUALIZADO AUTOMÁTICAMENTE\)\n)"
    r".*?"
    r"(\*\*USA SIEMPRE estas fechas\. NUNCA inventes ni asumas una fecha diferente\.\*\*)",
    re.DOTALL,
)


def build_date_block(now: datetime) -> str:
    tomorrow = now + timedelta(days=1)
    hoy = f"{DAYS_ES[now.weekday()]} {now.day} de {MONTHS_ES[now.month - 1]} de {now.year}"
    manana = f"{DAYS_ES[tomorrow.weekday()]} {tomorrow.day} de {MONTHS_ES[tomorrow.month - 1]} de {tomorrow.year}"
    return (
        f"## ⚡ FECHA ACTUAL (ACTUALIZADO AUTOMÁTICAMENTE)\n"
        f"**HOY es {hoy}.** Zona horaria: Miami, Florida (Eastern Time, UTC-4).\n"
        f"**MAÑANA es {manana}.**\n"
        f"- Cuando el cliente diga **\"mañana\"** → se refiere al **{tomorrow.day} de {MONTHS_ES[tomorrow.month - 1]} de {tomorrow.year}** ({DAYS_ES[tomorrow.weekday()]})\n"
        f"- Cuando el cliente diga **\"hoy\"** → se refiere al **{now.day} de {MONTHS_ES[now.month - 1]} de {now.year}** ({DAYS_ES[now.weekday()]})\n"
        f"- Cuando el cliente diga **\"esta semana\"** → los días restantes de esta semana desde hoy\n"
        f"**USA SIEMPRE estas fechas. NUNCA inventes ni asumas una fecha diferente.**"
    )


def inject_date(prompt_text: str, date_block: str) -> tuple[str, bool]:
    """Reemplaza el bloque de fecha en el texto. Retorna (nuevo_texto, cambió)."""
    new_text, n = DATE_BLOCK_RE.subn(date_block, prompt_text)
    if n == 0:
        return prompt_text, False
    return new_text, new_text != prompt_text


def strip_file_header(text: str) -> str:
    """Quita el bloque de comentarios # del inicio del archivo local."""
    lines = text.splitlines(keepends=True)
    i = 0
    while i < len(lines) and (lines[i].lstrip().startswith("#") or lines[i].strip() == ""):
        i += 1
    return "".join(lines[i:]).strip("\n")


def patch_vapi(api_key: str, assistant_id: str, new_prompt: str, dry_run: bool) -> bool:
    """Hace PATCH al assistant en Vapi preservando tools y analysisPlan. Retorna True si OK."""
    r = requests.get(f"{VAPI_API}/assistant/{assistant_id}",
                     headers={"Authorization": f"Bearer {api_key}"}, timeout=30)
    r.raise_for_status()
    current = r.json()
    model_cfg = current.get("model", {}) or {}
    current_tools = model_cfg.get("tools", [])
    current_analysis_plan = current.get("analysisPlan")

    if dry_run:
        live_prompt = (model_cfg.get("messages") or [{}])[0].get("content", "")
        if live_prompt == new_prompt:
            print("    [dry-run] Sin cambios necesarios en Vapi")
        else:
            print("    [dry-run] PATCH se aplicaría")
        return True

    patch_body = {
        "model": {
            **model_cfg,
            "messages": [{"role": "system", "content": new_prompt}],
            "tools": current_tools,
            "toolIds": [],
        }
    }
    if current_analysis_plan is not None:
        patch_body["analysisPlan"] = current_analysis_plan

    resp = requests.patch(
        f"{VAPI_API}/assistant/{assistant_id}",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=patch_body, timeout=30,
    )
    if resp.status_code >= 300:
        print(f"    ERROR PATCH {resp.status_code}: {resp.text[:300]}", file=sys.stderr)
        return False
    return True


def update_bot(bot: str, info: dict, api_key: str, date_block: str, dry_run: bool) -> bool:
    mirror_path = REPO_ROOT / info["mirror"]
    if not mirror_path.exists():
        print(f"  [{bot}] SKIP — mirror no existe: {info['mirror']}")
        return True

    raw = mirror_path.read_text(encoding="utf-8")
    prompt_body = strip_file_header(raw)
    new_prompt, changed = inject_date(prompt_body, date_block)

    if not changed:
        print(f"  [{bot}] SKIP — bloque de fecha no encontrado en {info['mirror']}")
        return True

    print(f"  [{bot}] Aplicando fecha...")
    ok = patch_vapi(api_key, info["assistant_id"], new_prompt, dry_run)
    if ok and not dry_run:
        # Actualizar el mirror local también
        header_end = raw.find(prompt_body[:40])
        if header_end >= 0:
            header = raw[:header_end]
            mirror_path.write_text(header + new_prompt + "\n", encoding="utf-8")
        print(f"  [{bot}] ✓ OK — Vapi + mirror actualizados")
    elif ok:
        print(f"  [{bot}] ✓ OK (dry-run)")
    else:
        print(f"  [{bot}] ✗ FAIL")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Actualiza fechas en prompts de Elena Voice")
    parser.add_argument("--bot", choices=sorted(BOTS.keys()), default=None,
                        help="Actualizar solo un bot (default: todos)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Mostrar qué haría sin aplicar cambios")
    args = parser.parse_args()

    api_key = os.environ.get("VAPI_API_KEY") or os.environ.get("VAPI_KEY") or ""
    if not api_key:
        secrets_file = Path("/root/.secrets/vapi_key")
        if secrets_file.exists():
            api_key = secrets_file.read_text().strip()
    if not api_key:
        print("ERROR: no se encontró VAPI_API_KEY. Exportar o poner en /root/.secrets/vapi_key",
              file=sys.stderr)
        return 2

    now = datetime.now(TZ)
    date_block = build_date_block(now)
    print(f"Fecha a inyectar: {now.strftime('%Y-%m-%d %H:%M %Z')}")
    print(f"Bloque:\n  HOY es {DAYS_ES[now.weekday()]} {now.day} de {MONTHS_ES[now.month - 1]} de {now.year}")
    print()

    bots_to_update = {args.bot: BOTS[args.bot]} if args.bot else BOTS
    failures = 0
    for bot, info in bots_to_update.items():
        if not update_bot(bot, info, api_key, date_block, args.dry_run):
            failures += 1

    print()
    if failures == 0:
        print(f"✓ Completado sin errores ({len(bots_to_update)} assistants)")
    else:
        print(f"✗ {failures}/{len(bots_to_update)} fallaron")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
