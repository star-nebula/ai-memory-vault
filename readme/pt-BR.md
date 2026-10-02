# AI Memory Vault · Cofre de memória multi-ferramenta para IA

[English](../README.md) | [简体中文](zh-CN.md) | [日本語](ja.md) | [한국어](ko.md) | [Español](es.md) | [Português](pt-BR.md) | [Русский](ru.md)

> Uma estrutura de diretórios + livro de regras + scripts de controle para que **todas as ferramentas de IA** — Claude Code, Codex, Cursor, Cline, Gemini CLI, Trae, Qoder, ZCode e outras — compartilhem **uma única memória**.
> **Filosofia central: quase zero configuração — nada é implantado localmente.** O sistema inteiro são arquivos Markdown mais quatro scripts Python de biblioteca apenas padrão: copiar para um diretório Markdown puro *é* a implantação. Sem dependências, sem serviços, sem build, sem placeholders para substituir. As ferramentas leem automaticamente o `AGENTS.md` da raiz e já começam a trabalhar; os scripts detectam sozinhos onde fica a memória.
>
> **Não depende do Obsidian**: o cofre de memória é apenas um diretório Markdown puro (`Memory/`). Qualquer agente que leia/escreva arquivos e qualquer editor Markdown funcionam. O autor o consulta no Obsidian — Templater / Dataview são aprimoramentos opcionais, não dependências.

**Por quê**: cada ferramenta de IA guarda a própria "memória" — `~/.claude/`, `~/.codex/`, `.workbuddy/memory/`, vários auto-memory forçados… As ferramentas não se entendem: trocar de ferramenta é amnésia, e a memória enterrada em formatos privados não pode ser lida nem auditada. Este projeto concentra a **fonte única de memória** em um único diretório Markdown puro que todas as ferramentas podem ler e escrever; na configuração de cada ferramenta vive apenas um *ponteiro + gancho curto* — são a plaquinha da porta, não o cofre.

| Diretório | O que é |
|---|---|
| [docs/](../docs/) | **Fundamentos do projeto**: por que foi construído assim, os incidentes reais por trás de cada controle (chinês) |
| [starter/](../starter/) | **Esqueleto copiar-e-usar**: estrutura + livro de regras completo + projeto de exemplo |
| [scripts/](../scripts/) | **Scripts de controle**: índices, auditoria de tarefas, guarda de codificação, sincronização de instruções |

## Princípios centrais (resumo dos sete)

1. **Quase zero configuração** — arquivos Markdown + scripts só com a biblioteca padrão; copiar para um diretório é a instalação inteira.
2. **Um único lugar para a memória** — na configuração de cada ferramenta vive só um "ponteiro + gancho curto"; o conteúdo, nunca.
3. **Camadas estruturadas** — `Preferences` / `Plans` / `Decisions` / `Lessons` / `Workflows` / `Projects` + `Todo.md`·`Inbox/`·`Archive/`.
4. **Índices são derivados** — gerados pelo `mem_index.py` a partir do frontmatter; o humano só pule a linha-resumo, e regenerar não a apaga.
5. **Feito = movido** — a tarefa concluída vai para `working/completed.md` (com data) e sai de `Todo.md`; nunca um ✅ no lugar.
6. **Só etapas com porteira permanecem estáveis** — cada porteira nasceu de um incidente real ([docs/04](../docs/04-演化史-门禁背后的事故.md)).
7. **Privacidade garantida por guardas** — `.gitignore` + hook `pre-commit` que rejeita qualquer commit que toque `Memory/`.

## Implantação em uma frase

Envie este parágrafo **exatamente assim para qualquer agente de IA** (Claude Code, Cursor, agentes web com acesso a arquivos…):

```text
Clone (ou baixe e descompacte) https://github.com/star-nebula/ai-memory-vault ,
copie todo o conteúdo de starter/ para a raiz do meu espaço de trabalho de memória —
se eu já tiver um repositório de notas, use a raiz dele; senão, crie um diretório vazio.
Depois execute python scripts/mem_index.py --write nesse diretório para gerar os índices.
Por fim leia o AGENTS.md da raiz e o Memory/_index.md e repita para mim:
quando você vai ler a memória e como vai escrevê-la.
```

## Implantação manual

```bash
cp -r starter/* /caminho/do/seu-vault/   # a única ação de "instalação"
```

Não há placeholders para substituir nem dependências para instalar. Passos opcionais:

```bash
python scripts/mem_index.py --write      # gera os índices por camada
python scripts/mem_index.py --check      # porteira: deriva de índices
python scripts/todo_audit.py --check     # porteira: arquivamento de tarefas
python scripts/encoding_guard.py <caminho> # porteira: codificação + caracteres de controle
```

**Conectar ferramentas de IA**: em `starter/Memory/Workflows/AI工具自定义指令.md` há uma versão completa (para caixas de "instruções personalizadas") e uma mínima (para o `AGENTS.md` raiz do projeto). Ambas usam caminhos relativos e funcionam coladas como estão.

## Scripts de controle

| Script | O que bloqueia |
|---|---|
| `mem_index.py` | Deriva de índices manuais · divergência entre tabelas "idênticas palavra por palavra" · protocolo de frescor de leitura ausente |
| `todo_audit.py` | Tarefas "feitas" mas não movidas · grupos sem diretório de projeto · falsas alegações de "já movido ao Todo" · tipos fora do vocabulário |
| `encoding_guard.py` | Não UTF-8 / BOM · caracteres de controle deixados por escapes engolidos pela IA (invisíveis para o grep) |
| `sync_memory_instructions.py` | Deriva entre o slot de instruções de cada ferramenta e a fonte única · contaminação da fonte |

> A documentação completa (filosofia, estrutura, princípios, história dos incidentes) está em [docs/](../docs/) (em chinês); a visão geral, no [README em inglês](../README.md). **Se esta tradução estiver desatualizada, valem o README em inglês e os docs em chinês.**

## License

[MIT](../LICENSE) — estrutura, regras e scripts de uso livre. Se te ajudou, um Star ou uma Issue com a sua adaptação são muito bem-vindos.
