# AI Memory Vault · Bóveda de memoria multi-herramienta para IA

[English](../README.md) | [简体中文](zh-CN.md) | [日本語](ja.md) | [한국어](ko.md) | [Español](es.md) | [Português](pt-BR.md) | [Русский](ru.md)

> Una estructura de directorios + reglamento + scripts de control para que **todas las herramientas de IA** — Claude Code, Codex, Cursor, Cline, Gemini CLI, Trae, Qoder, ZCode y más — compartan **una sola memoria**.
> **Filosofía central: casi cero configuración — no se despliega nada en local.** Todo el sistema son archivos Markdown más ocho scripts de Python de solo librería estándar: copiarlo en un directorio Markdown plano *es* el despliegue. Sin dependencias, sin servicios, sin builds, sin placeholders que reemplazar. Las herramientas leen automáticamente el `AGENTS.md` raíz y empiezan a trabajar; los scripts detectan la ubicación de la memoria por sí solos.
>
> **No depende de Obsidian**: la bóveda de memoria es simplemente un directorio Markdown plano (`Memory/`). Cualquier agente que lea/escriba archivos y cualquier editor Markdown sirven. El autor la consulta en Obsidian — Templater / Dataview son mejoras opcionales, no dependencias.

**Por qué**: cada herramienta de IA guarda su propia "memoria" — `~/.claude/`, `~/.codex/`, `.workbuddy/memory/`, varios auto-memory forzados… Las herramientas no se entienden entre sí: cambiar de herramienta es amnesia, y la memoria enterrada en formatos privados no se puede leer ni auditar. Este proyecto concentra la **fuente única de memoria** en un único directorio Markdown plano que todas las herramientas pueden leer y escribir; en la configuración de cada herramienta solo vive un *puntero + gancho breve* — son el rótulo de la puerta, no la bóveda.

| Directorio | Qué es |
|---|---|
| [docs/](../docs/) | **Fundamentos de diseño**: por qué está construido así, los incidentes reales tras cada control (chino) |
| [starter/](../starter/) | **Esqueleto copiar-y-usar**: estructura + reglamento completo + proyecto de ejemplo |
| [scripts/](../scripts/) | **Scripts de control**: índices, auditoría de tareas, guardián de codificación, sincronización de instrucciones |

## Principios centrales (resumen de siete)

1. **Casi cero configuración** — archivos Markdown + scripts de solo librería estándar; copiarlos a un directorio es toda la instalación.
2. **Un único lugar para la memoria** — en la configuración de cada herramienta solo vive un "puntero + gancho breve"; el contenido nunca.
3. **Capas estructuradas** — `Preferences` / `Decisions` / `Lessons` / `Workflows` / `Projects` + `Todo.md`·`Inbox/`·`Archive/`. Los planes viven dentro de cada proyecto en `working/plan.md`.
4. **Contexto mínimo por defecto** — el agente no navega todo el árbol. `memory_boot.py` crea un paquete de inicio acotado y `memory_query.py` devuelve fragmentos ordenados solo cuando hace falta.
5. **Cerrado = movido** — la tarea terminada o cancelada pasa a `working/completed/YYYY-QX.md` (con fecha, resultado, motivo y origen) y se elimina de `Todo.md`; nunca un ✅ ni un tachado permanente en el sitio.
6. **Solo los pasos con puerta de control se mantienen estables** — cada puerta nació de un incidente real ([docs/04](../docs/04-演化史-门禁背后的事故.md)).
7. **Privacidad garantizada por guardas** — `.gitignore` + hook `pre-commit` que rechaza cualquier commit que toque `Memory/`.

## Despliegue en una frase

Envía este párrafo **tal cual a cualquier agente de IA** (Claude Code, Cursor, agentes web con acceso a archivos…):

```text
Clona (o descarga y descomprime) https://github.com/star-nebula/ai-memory-vault ,
copia todo el contenido de starter/ a la raíz de mi espacio de trabajo de memoria —
si ya tengo un repositorio de notas usa su raíz; si no, crea un directorio vacío.
También copia el directorio scripts/ en ese espacio de trabajo (las puertas no están dentro de starter/).
Luego ejecuta python scripts/memory_boot.py --cwd . --json y python scripts/memory_query.py "test" --json.
Por último lee el AGENTS.md de la raíz y repíteme:
cuándo leerás la memoria y cómo la escribirás.
```

## Despliegue manual

```bash
cp -r starter/* scripts /ruta/a/tu-boveda/   # la única acción de "instalación"
```

No hay placeholders que reemplazar ni dependencias que instalar. Pasos opcionales:

```bash
python scripts/todo_audit.py --check     # puerta: archivado de tareas
python scripts/encoding_guard.py <ruta>  # puerta: codificación + caracteres de control
```

**Conectar herramientas de IA**: en `starter/Memory/Workflows/AI工具自定义指令.md` hay una versión completa (para cuadros de "instrucciones personalizadas") y una mínima (para el `AGENTS.md` raíz del proyecto). Ambas usan rutas relativas y funcionan tal cual se pegan.

## Scripts de control

| Script | Qué bloquea |
|---|---|
| `memory_boot.py` | Inicio sin límite · truncado silencioso de secciones · falta de contexto del proyecto |
| `memory_query.py` | Expansión de notas completas · fuga de project/scope · archived/superseded incluidos por defecto |
| `state_audit.py` | `_state.md` de proyectos activos ausente, provisional, obsoleto o demasiado largo (solo informe por defecto) |
| `memory_review.py` | Falta de status/review o afirmaciones volátiles sin verificar/vencidas en memoria larga (solo informe por defecto) |
| `todo_audit.py` | Tareas "hechas" pero no movidas · grupos sin directorio de proyecto · falsas afirmaciones de "ya movido a Todo" · tipos fuera de vocabulario · acumulación de auditoría de Inbox (solo informe) |
| `encoding_guard.py` | No UTF-8 / BOM · caracteres de control dejados por escapes tragados por la IA (invisibles para grep) |
| `sync_memory_instructions.py` | Deriva entre el slot de instrucciones de cada herramienta y la fuente única · contaminación de la fuente · pseudo-valor `<项目名>` |

> La documentación completa (filosofía, estructura, principios, historia de incidentes) está en [docs/](../docs/) (en chino); el panorama general, en el [README en inglés](../README.md). **Si esta traducción se queda atrás, mandan el README en inglés y los docs en chino.**

## License

[MIT](../LICENSE) — estructura, reglas y scripts de uso libre. Si te sirve, un Star o un Issue con tu adaptación son bienvenidos.
