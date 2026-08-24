# AUDITORÍA PROFUNDA — ARIA + ELENA VOICE
**Fecha:** 2026-08-01 · **Autora:** Stephanee · **Encargo de Juan:** *"documéntate bien profundo en todo lo que es ARIA y Elena Voice... necesito el timeline completo para que no repitamos errores. Quiero optimizar a ARIA y usar esa data para optimizar a Elena."*
**Alcance:** read-only. **NADA fue modificado.** Todo verificado contra fuente primaria: código, Supabase live, API de Vapi, API/logs de Render, `count_tokens` de Anthropic, git (323 commits), 273 resúmenes.

---

## TESIS CENTRAL

**ARIA no está rota como JUEZ — está rota como INSTRUMENTO.**

Acierta el 95.5% clasificando (veredicto del propio Juan: 361 aprobadas / 17 rechazadas). Pero:
- mide a Elena contra un **playbook de marzo que ya no existe**,
- sus dos features más valiosas **murieron hace 4 meses por bugs de esquema silenciosos**,
- **el 70% de los "errores" que reporta es ruido**,
- y **todos los reportes que Juan lee son de UN bot de siete** — el que tiene el 7% del volumen.

Consecuencia: Juan ha estado decidiendo con un tablero que muestra la fracción equivocada de la realidad.

---

## 1. EL HALLAZGO DE NEGOCIO MÁS GRANDE

**Los 2 bots que hacen el 87% de las llamadas son los que peor convierten — y nadie lo ve.**

| Bot | Llamadas/semana (Vapi) | Ofreció cita | **Agendó** |
|---|---:|---:|---:|
| **radiesse** | **196** | 38% (el peor) | **12%** |
| **fillers** | **105** | 43% | **9%** (el peor) |
| botox | 24 | 50% | 17% |
| cicatrices | 8 | 50% | 17% |
| acné | 5 | 51% | 23% |
| rejuvenecimiento | 5 | 54% | 19% |
| lhr | 0 | — | — |

**Los reportes de ARIA (`/reporte`, diario, semanal, `/audit`, `/status`) son Botox-only**: `fetch_vapi_calls()` cae al env `VAPI_ASSISTANT_ID` = Botox cuando no se le pasa assistant explícito (`aria_audit.py:266,290`; verificado en Render). El `vapi_total` cuenta ~24 llamadas/semana mientras Supabase tiene 343 → `coverage_pct` da **>100%**.

> Juan lee el 7% del negocio creyendo que lee el 100%. Y justo el 7% que mejor performa.

**Nota:** la *auditoría* sí cubre los 7 bots al 100% (lo logra el polling, `:2758-2777`). Lo que está sesgado son los **reportes**.

---

## 2. LOS 5 BUGS SILENCIOSOS (mismo patrón: el fallo se loguea y se ignora)

| # | Bug | Impacto | Evidencia |
|---|---|---|---|
| **B1** | **`call_intelligence` muerta desde 2026-04-04** — `audit_id` es `bigint` en la tabla pero se le inserta un `uuid` (`:1003`) → PostgREST rechaza 22P02 → `supabase_upsert` devuelve `None` y **el retorno se ignora** (`:1021`) | **374 conversaciones reales sin extraer objeciones, barreras ni buying stage.** `/intel` y `/leads` viven de un fallback desde abril. 32 filas existentes, todas con `audit_id=NULL` (vienen del `/backfill`, que omite el campo) | Supabase: 6.472 audits / 32 intel |
| **B2** | **`daily_metrics` rota 4 meses** — se emite `unique_contacts`, columna que no existe | Métricas diarias sin escribir desde 2026-04-01 (5 filas). Error 400 **cada día** en los logs de Render, tragado | `PGRST204: Could not find the 'unique_contacts' column` |
| **B3** | **Reportes Botox-only** | Ver sección 1 | `:266,290` + env de Render |
| **B4** | **Alerta de degradación con el signo invertido** — `drop = scores[-1] - scores[0]` con `scores[0]`=hoy; `if drop <= -10` se cumple cuando **hoy MEJORÓ** | La alarma de caída de calidad **avisa al revés**. Elena se degradó 5 meses sin una sola alerta | `:2576-2577` |
| **B5** | **Reporte semanal con sección siempre vacía** — `audit_continuous.py:229` lee `aria_summary`, columna inexistente (es `aria_reasoning`) | *"Top 3 razones de no_agendo"* sale vacía todas las semanas | `:229`, metodología `:427` |

**Patrón común:** cinco fallos distintos, un solo modo de falla — **se escribe el error en un log que nadie lee y el programa sigue como si nada.** Es exactamente el mismo patrón que se reparó hoy en los canarios (2026-08-01).

---

## 3. EL 70% DE LOS "ERRORES" ES RUIDO

Sobre las 4.000 auditorías más recientes:

| Error | Casos | % en `no_contesto` | El propio prompt dice |
|---|---:|---:|---|
| `premature_greeting` | **1.767** (56% de todos los errores) | **95%** | *"En llamadas OUTBOUND, Elena siempre habla primero — NO es premature_greeting"* (`:597`) |
| `premature_endcall` | 462 | 69% | *"NO marques premature_endcall si el outcome es no_contesto"* (`:593`) |

**El juez ignora sus propias excepciones.** Todo reporte de "top errores" que ve Juan está dominado por esto.

Ejemplo real de la base:
> AI: *"Hola, habla Elena, de LaserPlace. ¿Cómo estás?"* → User: *"Person you're trying to reach is not available. At the tone, please record your message."*
> → ARIA marca `premature_greeting`. Elena hizo lo correcto.

**Además:** no hay whitelist de tipos de error (sí la hay para outcomes, `:937`). El LLM inventó 2 tipos fuera de los 10 definidos: `missed_callback_execution` (7), `premature_pitch` (6).

---

## 4. LA VARA ESTÁ VIEJA — por qué el `playbook_adherence_score` no es confiable

El playbook contra el que ARIA puntúa (`aria_audit.py:601-610`) **no cambia desde el commit fundacional del 2026-03-28**. Los prompts de Elena cambiaron 6 veces desde entonces.

| ARIA exige | Realidad live (verificada en Vapi) | Efecto |
|---|---|---|
| "preguntar si tiene **2 minutos**" | **Eliminado a propósito** el 2026-05-30 (commit `f0fd053`). Cero ocurrencias en los 7 prompts | ARIA penaliza por NO hacer algo prohibido |
| "proponer **Skin Reveal Analysis**" | Solo Botox lo usa; 6 bots dicen "consulta personalizada" / "evaluación gratuita" | 6 de 7 medidos contra un nombre muerto |
| "preguntar si los **martes** funcionan" | **4 de 7 bots** ya preguntan "¿qué día te funciona mejor?" | ARIA penaliza a 4 bots por obedecer su prompt |
| (no lo contempla) | STATE 3 exige **validar el dolor antes de ofrecer** — el paso más caro del flujo | ARIA no puntúa el cuello de botella real |

**El score de 0.66 es en buena parte artefacto de la vara.** Optimizar Elena con esa señal = optimizar contra un fantasma.

**Causa estructural:** el playbook de ARIA es un **resumen a mano** que hay que mantener sincronizado. Mientras siga siendo un resumen manual, volverá a desincronizarse.

---

## 5. POR QUÉ ELENA NO OFRECE CITA (medido, no supuesto)

Datos: n=399 conversaciones reales (>20s, outcome ≠ `no_contesto`).
`appointment_offered` 41% · `objection_handled` 38% · playbook 0.643 · **mediana de turnos del cliente: 4**

### Causa #1 — El playbook NO CABE en la llamada. Es aritmética.

| Turno | Qué consume el flujo obligatorio |
|---|---|
| 1 | `firstMessage` automático |
| 2 | STATE 1: presentación + pedir permiso |
| 3 | STATE 2 pregunta 1 |
| 4 | STATE 2 pregunta de profundización |
| 5 | STATE 3: validar dolor + puente |
| **6** | **STATE 4: recién aquí se puede proponer día** |

**La llamada mediana muere en el turno 4. La primera oportunidad de ofrecer cita es el turno 6.**
Reglas que lo hacen obligatorio: *"NO puedes saltar del STATE 1 al STATE 4 sin pasar por la exploración"* (`system_prompt.txt:95`) y *"NUNCA menciones el Skin Reveal Analysis sin antes validar el dolor"* (`:129`).

> **Obedecer el playbook garantiza no llegar a ofrecer la cita.**

### Causa #2 — El saludo se dice dos veces (el fix más barato del sistema)
El prompt cree que el sistema ya dijo el tratamiento y pidió permiso (`system_prompt.txt:111`). El `firstMessage` real en Vapi (los 7 idénticos) es solo: *"Hola, habla Elena de Laser Place. ¿Cómo estás?"*

Transcript real:
```
AI:   Hola, habla Elena, de LaserPlace. ¿Cómo estás?
User: Bien, gracias.
AI:   Perfecto, vi tu interés en los fillers... te hago un par de preguntas rápidas.
```
**Se quema el turno 2 de 4 repitiendo el saludo = 25% de la llamada mediana.**
Invisible porque `check_prompt_drift.py` trae el `firstMessage` pero **nunca lo compara** (`:171`).

### Causa #3 — No manejar la objeción es LA INSTRUCCIÓN, no el fallo
- *"Si insiste en que la llames luego → di 'te llamo mañana' y **ejecuta endCall**"* (`:155`) → capitula tras 1 intento. **`llamar_luego` es el outcome #1: 36% de las conversaciones reales.**
- *"Si el contador llegó a 2, **NO hagas más preguntas, NO intentes otro pivot**"* (`:209`).
- El bloque de objeciones solo se activa *"si el cliente se sale del STATE MACHINE"* → **no hay instrucción de detectar objeciones durante STATE 1-2**, que es donde ocurren casi todas.

### Señal para probar (correlación, no prueba)
| Familia | n | Ofreció | **Agendó** |
|---|---:|---:|---:|
| "martes primero" (botox/fillers/radiesse) | 221 | 46% | **14%** |
| "¿qué día te funciona?" (lhr/acné/cicatrices/rejuv) | 88 | 53% | **24%** |

Los bots que dejaron de empujar el martes **agendan casi el doble**. Muestras desiguales y tratamientos distintos → hipótesis a validar, no conclusión.

---

## 6. PRODUCCIÓN ROTA — hallazgos urgentes

1. **Prompt de LHR CORRUPTO y vivo en Vapi.** Search/replace roto dejó texto amputado (`system_prompt_lhr.txt:148,192`): *"¿Te agendo una esta semana?* ***isis facial avanzado que se llama evaluación gratuita***" y *"...sin compromiso.* ***ormalmente vale 350 dólares.***". Además se contradice: "13 años" vs "doce años" en el mismo archivo. P-004 dice `applied` pero solo arregló STATE 5.
2. **`schedule_callback` es una TOOL ZOMBI.** Se eliminó de los 7 bots el 2026-04-21 (commit `55c9e76`) porque causaba **bucle exponencial de llamadas** ("Elena la llamaba en buzones → forzaba llamar_luego → disparaba otra llamada. Ciclo exponencial confirmado"). **Verificación live de hoy: está presente en los 7 otra vez**, sin registro en git ni INCIDENTS.md. El prompt no la menciona, pero su `description` en Vapi le dice al modelo cuándo usarla. Riesgo de repetir el bucle.
3. **3 tools sin gobierno de prompt** (30% de la superficie): `schedule_callback`, `create_contact`, `request_human_handoff` — 0 menciones en los 7 prompts.
4. **Ediciones a medias del "martes"**: `lhr` STATE 4 ya no propone martes pero el punto 3 dice *"NUNCA vuelvas a mencionar el martes"*; `acne:121` y `rejuvenecimiento:121` **todavía dicen** *"¿El martes te queda mejor...?"*. La tool `check_availability` sigue con *"Prioriza martes"*.
5. **Botox (el bot insignia) corre con guardrails VIEJOS**: le falta `MULETILLAS Y REACCIONES NATURALES` (que tienen los otros 6) y tiene `BREVEDAD` 25 palabras vs `BREVEDAD ABSOLUTA` 15 de los demás. **Doctrina violada: un fix en uno debe replicarse en todos.**
6. **DECISIÓN DE JUAN PENDIENTE:** "Director clínico: Dr. Gonzalo Mosquera" está vivo en **6 de 7 bots de voz**. Juan lo sacó del website (`feedback_no_mosquera_en_website`). No es ilegal (él sí es MD) pero contradice una decisión explícita en otro canal.

**🟢 LEGAL FLORIDA: LIMPIO.** Laury aparece como "nuestra especialista" / "12+ años" en los 7 prompts. **Cero** "Dra.", "doctora" o "directora". Gilberto Fernández correctamente como "Nurse Practitioner".

---

## 7. TIMELINE (hitos que explican el presente)

| Fecha | Hito |
|---|---|
| 2026-03-28 | Nace ARIA v1.0 con **Sonnet 4.5** |
| 2026-03-30 | v2: webhook real-time, polling 3min, few-shot dinámico, Telegram en cada llamada |
| 2026-04-01 | **v3.0 → v3.1.1** (4 bugs + 13 comandos + `call_intelligence`). **La versión se congela aquí** |
| 2026-04-04 | **Muere `call_intelligence`** (bug uuid/bigint) |
| 2026-04-14 | **Rebrand cosmético** ARIA → "Elena Voice · Auditoría" (Opción A: solo lo que Juan ve) |
| 2026-04-15 | **5 assistants nuevos → 7 bots** = 7× llamadas auditadas |
| 2026-04-17 | **Incidente de costo:** $2-5/día → $22-38/día ≈ **$123 en 4 días** (7 bots × Sonnet) |
| **2026-04-19** | **Sonnet 4.5 → Haiku 4.5** (−~70% costo) |
| 2026-04-21 | Se **elimina `schedule_callback`** (bucle infinito de llamadas) |
| 2026-04-29/30 | Multi-tratamiento en ARIA + fix crítico: `.format()` rompía con las `{}` del JSON → **audit fallaba en silencio** |
| 2026-04-30→05-06 | **6 días sin auditorías**: VAPI key rotada sin propagar al servicio `elena` |
| 2026-05-06 | **Webhook ARIA eliminado; polling = mecanismo único** (Gunicorn recicla workers y mata threads de 30-60s) |
| 2026-05-07 | venv en `/tmp` borrado por reboot = **3 lunes sin reporte semanal** |
| 2026-05-18 | **Auto-corrección `no_agendo→no_contesto`** sin aprobación |
| 2026-05-22 | 7º outcome `seguimiento_humano` (**nunca se agregó a ARIA**) |
| **2026-05-25** | **ÚLTIMO CAMBIO A ARIA** (emojis). Congelada desde entonces: **68 días** |
| 2026-05-30 | Se elimina el "¿tienes 2 minutos?" de los prompts (ARIA sigue exigiéndolo) |
| 2026-06-20 | FIX 1 buzón en los 7 bots. **Su cron nunca corrió** (no está en crontab, log inexistente) |

---

## 8. CORRECCIONES DE JUAN — doctrina que NO se debe repetir

1. **"ARIA no falla — ARIA corrige"** (2026-06-20). *Elena/Vapi clasifica mal EN ORIGEN; ARIA es la red de seguridad.* → **Los fixes van al origen, no al auditor.**
2. **"NO tocar a ARIA"** — se propuso quitarle el LLM y Juan lo **vetó**.
3. **Outcomes = ramas de workflow; razones = tags de metadata. Nunca mezclar.** Juan: *"esos deben ser más que todo tags internos: agendo, no_agendo, error_tecnico, no_interesado, llamar_luego, no_contesto"*.
4. **"Si `schedule_callback` es inútil y provoca problemas, ¿por qué no borrarlo?"** — rechazó el fix por prompt como *"mediocre"*. **Doctrina: eliminar la causa, no parchear.**
5. **Fix por prompt descartado para el buzón:** *"Elena no lo respeta"* → fix estructural en config de Vapi. (Inteligencia en el sistema, no en el modelo.)
6. **Rebrand:** *"cambia solo lo que yo veo, no alteres el sistema, documenta todo"*.
7. Reportar un fix sin commit que lo respalde = ítem inventado → nació `INCIDENTS.md`.
8. Rechazó cortar horarios de llamada pese a 0% de conversión: *"enfría leads, daña continuidad"*.

### Intentado y DESCARTADO (no re-proponer)
- **Webhook ARIA en tiempo real** → revertido (Gunicorn mata threads largos).
- **`get_already_audited_ids` con ventana de 48h** → reemplazado por top-N DESC.
- **Polling silencioso** → revertido (nadie recibía notificaciones).
- **ARIA sin LLM** → vetado por Juan.
- **Renombrar archivos/tablas/bot** (Opción B del rebrand) → descartado; plan documentado en `REBRAND_ARIA.md`.
- **Mantener Sonnet** → rechazado por costo.
- **Ramas de workflow por razón de no-agendo** → rechazado (explota el workflow).
- **Prompt caching en ARIA** → **NO viable**: el prefijo estable son 2.063 tokens y el mínimo cacheable de Haiku 4.5 es 4.096.

---

## 9. COSTO (medido con `count_tokens`, no estimado)

| Caso | Input | Output | Costo |
|---|---:|---:|---:|
| `no_contesto` (90% del volumen) | 3.269 tok | ~368 tok | **$0.0051** |
| Conversación real | 3.531 tok | ~900 tok | ~$0.008 |

**~51 auditorías/día ≈ $0.26/día ≈ $7.8/mes.**
**De eso, ~$7/mes se gastan en que Haiku juzgue buzones de voz** (90% del volumen, mediana 12s, transcript <400 chars). Solo el 3,8% de las auditorías son conversaciones reales.
**No existe ningún logging de costo en ARIA** (cero referencias a `usage`/`input_tokens`).

---

## 10. DEUDA TÉCNICA ADICIONAL

- **E5 — El umbral de confianza es papel mojado:** `CONFIDENCE_THRESHOLD_CORRECTION=0.85` pero la confianza media real es **0.964**; solo 4 de 4.000 caen por debajo. Haiku nunca duda → el gate no filtra nada.
- **E7 — `check_error_pattern_alert` es código inalcanzable:** solo se llama desde `run_audit` (`:2647`), que retorna antes (`:2609`) porque el polling siempre va por delante.
- **E8 — Tope real de PostgREST = 1.000 filas.** `get_already_audited_ids` pide 10.000 ("cubre ~100 días") y recibe 1.000 (≈20 días); corre **cada 3 minutos**. `/tendencia` pide 2.000 **sin `order`** → 30 días de tendencia calculados sobre filas arbitrarias.
- **E9 — Fallos tragados:** si GHL falla al aplicar una corrección, queda `pending` pero **`feedback_log` igual registra "approved"** → la métrica de eficacia y GHL divergen.
- **E12 — Contexto que le falta al juez:** no recibe dirección de la llamada (outbound/inbound), ni `endedReason` interpretado. Con eso + duración, **el 90% de las clasificaciones no necesitaría LLM**.
- **Sesgo del few-shot:** con 95% de aprobaciones, casi todos los ejemplos dicen "ARIA tiene razón" → bucle auto-confirmatorio. Además van **sin transcript** (aprende un prior, no un criterio) y cuestan ~700 tokens en cada llamada, incluidos los buzones.
- **46 correcciones `pending`** sin decidir (más vieja: 2026-03-29), sin recordatorio.
- **3 listas de outcomes que no coinciden** dentro del sistema (prompt de ARIA / `_VALID_OUTCOMES` / `OUTCOME_LABELS`) + una cuarta en el `analysisPlan` de Vapi. `seguimiento_humano` no existe en ARIA → se mapea a `None` y **se pierde el `original_outcome`**.
- **Campos huérfanos:** `quality_notes` lo genera el LLM y se tira (no hay columna); `silence_duration_seconds` nunca se escribe; tabla `aria_config` jamás se lee.
- Threads non-daemon al importar `aria_audit.py`, parcheados con `os._exit(0)` en tests desde abril.

---

## 11. PLAN DE OPTIMIZACIÓN PROPUESTO (nada ejecutado — requiere OK de Juan)

### FASE 0 — Urgente (producción)
| # | Acción | Por qué |
|---|---|---|
| 0.1 | Reparar el prompt corrupto de **LHR** | Elena dice frases amputadas a pacientes reales |
| 0.2 | Decidir sobre **`schedule_callback`** zombi en los 7 bots | Causó bucle exponencial de llamadas; volvió sin registro |
| 0.3 | Decisión de Juan: **Dr. Mosquera** en 6 bots de voz | Contradice decisión del website |

### FASE 1 — Que ARIA diga la verdad (sin esto, todo lo demás mide humo)
| # | Acción | Impacto |
|---|---|---|
| 1.1 | **Gate de pre-filtro determinístico**: `no_contesto` sin LLM cuando `duración<20s AND transcript<400 chars AND endedReason` de no-respuesta | **−90% costo y −95% de `premature_greeting` de un golpe.** 3 sitios: `:2791`, `:1580`, `:1310` |
| 1.2 | Suprimir `premature_greeting`/`premature_endcall` cuando `outcome==no_contesto` + **whitelist** de tipos de error | Los "errores" vuelven a significar algo |
| 1.3 | **Pasar el assistant a los reportes** (o guardar `assistant_id`/tratamiento en `call_audits` — el código YA lo calcula en `:726-735` y lo tira) | Juan deja de leer el 7% del negocio |
| 1.4 | Fix `audit_id` uuid→bigint | **Resucita `call_intelligence`** = la mina de objeciones para Elena y para Josh |
| 1.5 | Fix `unique_contacts` (`daily_metrics`) y `aria_summary`→`aria_reasoning` (`audit_continuous.py:229`) | Métricas diarias y reporte semanal vuelven a existir |
| 1.6 | Corregir el **signo** de `check_degradation_alert` | La alarma de caída de calidad vuelve a funcionar |
| 1.7 | **Sincronizar el playbook de ARIA con el prompt real** — mejor: inyectar el prompt live del bot auditado en vez de un resumen a mano | El `playbook_adherence_score` se vuelve señal confiable |

### FASE 2 — Optimizar Elena con data ya confiable
| # | Acción | Impacto esperado |
|---|---|---|
| 2.1 | **Sincronizar `firstMessage` con STATE 1** (1 campo × 7 bots) | Recupera ~25% de la llamada mediana |
| 2.2 | **Comprimir el flujo a ≤3 turnos hasta la oferta** (1 pregunta de exploración; permitir ofrecer si el cliente ya dio señal) | Ataca la causa raíz del 59-65% sin oferta |
| 2.3 | **Rediseñar `llamar_luego`** (36% de las conversaciones): hoy el prompt ordena capitular tras 1 intento | El outcome #1 del sistema |
| 2.4 | **Atacar radiesse y fillers primero** (87% del volumen, peor conversión) | Donde está el dinero |
| 2.5 | Replicar a **Botox** los guardrails `MULETILLAS` + `BREVEDAD ABSOLUTA` | Doctrina: un fix va a todos |
| 2.6 | Limpiar las 3 ediciones a medias del "martes" + `check_availability` | Coherencia |
| 2.7 | Añadir `firstMessage` a `check_prompt_drift.py` | Cierra el hueco que ocultó 2.1 por 2 meses |

### FASE 3 — Lo que ARIA aún no ve (el gap del Five Star de Hormozi)
ARIA mide **cumplimiento** ("¿siguió el proceso?"), no **experiencia** ("¿la paciente se sintió bien atendida?"). Las dos dimensiones que faltan, baratas de agregar (2 campos al JSON del mismo llamado de Haiku): **Concern** (empatía) y **Courtesy** (tono/escucha activa). Más la pata obligatoria del framework: **preguntarle al paciente** (encuesta post-cita). **Sin FASE 1, esto sería teatro.**

---

## 12. INVARIANTES QUE FALTAN (para que esto no se repita)

Todo lo roto aquí falló **en silencio durante meses**. Aplicando la ley del Stephanee OS (*invariante + medición + alarma*):

1. **Canario de escrituras**: si `call_intelligence` / `daily_metrics` no reciben filas en N días teniendo audits nuevos → alerta. (Habría cazado B1 y B2 el día 2 en vez de 4 meses después.)
2. **Canario de drift ARIA↔Elena**: si el hash del prompt de un bot cambia y el playbook de ARIA no → alerta. (Habría cazado la vara vieja.)
3. **No tragar retornos**: `supabase_upsert` devuelve `None` en fallo y todos los llamadores lo ignoran. Debe fallar ruidoso.
4. **Cobertura de reportes**: invariante `vapi_total >= audits_en_supabase` — si `coverage_pct > 100%`, el reporte está mintiendo.
5. **Inventario de tools**: si una tool aparece/desaparece en Vapi sin commit → alerta (habría cazado el zombi de `schedule_callback`).

---

_Auditoría read-only. Nada modificado. Fuentes: código + Supabase live + API Vapi + API/logs Render + count_tokens Anthropic + git (323 commits) + 273 resúmenes._
