# AI Memory Vault · Bóveda de memoria multi-herramienta para IA

[English](README.en.md) | [简体中文](README.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | [Português](README.pt-BR.md) | [Русский](README.ru.md)

> Una estructura de directorios + reglamento + scripts de control para que **todas las herramientas de IA** — Claude Code, Codex, Cursor, Cline, Gemini CLI, Trae, Qoder, ZCode y más — compartan **una sola memoria**.
> **Filosofía central: casi cero configuración — no se despliega nada en local.** Todo el sistema son archivos Markdown más cuatro scripts de Python de solo librería estándar: copiarlo en un directorio Markdown plano *es* el despliegue. Sin dependencias, sin servicios, sin builds, sin placeholders que reemplazar. Las herramientas leen automáticamente el `AGENTS.md` raíz y empiezan a trabajar; los scripts detectan la ubicación de la memoria por sí solos.
>
> **No depende de Obsidian**: la bóveda de memoria es simplemente un directorio Markdown plano (`Memory/`). Cualquier agente que lea/escriba archivos y cualquier editor Markdown sirven. El autor la consulta en Obsidian — Templater / Dataview son mejoras opcionales, no dependencias.

**Por qué**: cada herramienta de IA guarda su propia "memoria" — `~/.claude/`, `~/.codex/`, `.workbuddy/memory/`, varios auto-memory forzados… Las herramientas no se entienden entre sí: cambiar de herramienta es amnesia, y la memoria enterrada en formatos privados no se puede leer ni auditar. Este proyecto concentra la **fuente única de memoria** en un único directorio Markdown plano que todas las herramientas pueden leer y escribir; en la configuración de cada herramienta solo vive un *puntero + gancho breve* — son el rótulo de la puerta, no la bóveda.

| Directorio | Qué es |
|---|---|
| [docs/](docs/) | **Fundamentos de diseño**: por qué está construido así, los incidentes reales tras cada control (chino) |
| [starter/](starter/) | **Esqueleto copiar-y-usar**: estructura + reglamento completo + proyecto de ejemplo |
| [scripts/](scripts/) | **Scripts de control**: índices, auditoría de tareas, guardián de codificación, sincronización de instrucciones |

## Principios centrales (resumen de siete)

1. **Casi cero configuración** — archivos Markdown + scripts de solo librería estándar; copiarlos a un directorio es toda la instalación.
2. **Un único lugar para la memoria** — en la configuración de cada herramienta solo vive un "puntero + gancho breve"; el contenido nunca.
3. **Capas estructuradas** — `Preferences` / `Plans` / `Decisions` / `Lessons` / `Workflows` / `Projects` + `Todo.md`·`Inbox/`·`Archive/`.
4. **Los índices son derivados** — los genera `mem_index.py` desde el frontmatter; el humano solo pule la línea-resumen y los re-generados no la borran.
5. **Hecho = movido** — la tarea terminada pasa a `working/completed.md` (con fecha) y se elimina de `Todo.md`; nunca un ✅ en el sitio.
6. **Solo los pasos con puerta de control se mantienen estables** — cada puerta nació de un incidente real ([docs/04](docs/04-演化史-门禁背后的事故.md)).
7. **Privacidad garantizada por guardas** — `.gitignore` + hook `pre-commit` que rechaza cualquier commit que toque `Memory/`.

## Despliegue en una frase

Envía este párrafo **tal cual a cualquier agente de IA** (Claude Code, Cursor, agentes web con acceso a archivos…):

```text
Clona (o descarga y descomprime) https://github.com/star-nebula/ai-memory-vault ,
copia todo el contenido de starter/ a la raíz de mi espacio de trabajo de memoria —
si ya tengo un repositorio de notas usa su raíz; si no, crea un directorio vacío.
Luego ejecuta python scripts/mem_index.py --write en ese directorio para generar los índices.
Por último lee el AGENTS.md de la raíz y Memory/_index.md, y repíteme:
cuándo leerás la memoria y cómo la escribirás.
```

## Despliegue manual

```bash
cp -r starter/* /ruta/a/tu-boveda/   # la única acción de "instalación"
```

No hay placeholders que reemplazar ni dependencias que instalar. Pasos opcionales:

```bash
python scripts/mem_index.py --write      # genera los índices por capa
python scripts/mem_index.py --check      # puerta: deriva de índices
python scripts/todo_audit.py --check     # puerta: archivado de tareas
python scripts/encoding_guard.py <ruta>  # puerta: codificación + caracteres de control
```

**Conectar herramientas de IA**: en `starter/Memory/Workflows/AI工具自定义指令.md` hay una versión completa (para cuadros de "instrucciones personalizadas") y una mínima (para el `AGENTS.md` raíz del proyecto). Ambas usan rutas relativas y funcionan tal cual se pegan.

## Scripts de control

| Script | Qué bloquea |
|---|---|
| `mem_index.py` | Deriva de índices manuales · divergencia entre tablas "idénticas palabra por palabra" · protocolo de frescura de lectura ausente |
| `todo_audit.py` | Tareas "hechas" pero no movidas · grupos sin directorio de proyecto · falsas afirmaciones de "ya movido a Todo" · tipos fuera de vocabulario |
| `encoding_guard.py` | No UTF-8 / BOM · caracteres de control dejados por escapes tragados por la IA (invisibles para grep) |
| `sync_memory_instructions.py` | Deriva entre el slot de instrucciones de cada herramienta y la fuente única · contaminación de la fuente |

> La documentación completa (filosofía, estructura, principios, historia de incidentes) está en el [README en chino](README.md) y en [docs/](docs/). **Si esta traducción se queda atrás, la versión china manda.**

## License

[MIT](LICENSE) — estructura, reglas y scripts de uso libre. Si te sirve, un Star o un Issue con tu adaptación son bienvenidos.
