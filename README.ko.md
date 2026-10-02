# AI Memory Vault · 크로스 도구 AI 기억 라이브러리

[English](README.en.md) | [简体中文](README.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | [Português](README.pt-BR.md) | [Русский](README.ru.md)

> Claude Code / Codex / Cursor / Cline / Gemini CLI / Trae / Qoder / ZCode 등 **모든 AI 도구가 같은 기억을 공유**하게 만드는 디렉터리 구조 + 규칙 + 게이트 스크립트.
> **핵심 철학: 거의 제로 구성 — 로컬에 아무것도 배포하지 않는다.** 전부 Markdown 파일 + 표준 라이브러리만 쓰는 파이썬 스크립트 4개. 순수 Markdown 디렉터리에 복사하는 것이 곧 "배포"입니다. 의존성·서비스·빌드·플레이스홀더 치환 없음. 도구는 워크스페이스 루트의 `AGENTS.md`를 자동으로 읽고, 스크립트는 기억 라이브러리 위치를 자동 탐지합니다.
>
> **Obsidian에 종속되지 않음**: 기억 라이브러리의 실체는 그냥 Markdown 디렉터리(`Memory/`)입니다. 파일을 읽고 쓸 수 있는 어떤 에이전트, 어떤 Markdown 에디터로도 사용할 수 있습니다. 저자 본인은 Obsidian으로 열람하며(Templater / Dataview는 선택적 확장일 뿐) 의존성이 아닙니다.

**왜 필요한가**: 모든 AI 도구는 저마다의 "기억" 자리를 둡니다 — `~/.claude/`, `~/.codex/`, `.workbuddy/memory/`, auto-memory… 도구끼리 기억이 통하지 않아 도구를 바꾸면 기억상실, 도구 전용 포맷에 묻힌 기억은 읽을 수도 감사할 수도 없습니다. 이 프로젝트는 **기억의 유일한 저장소**를 모든 도구가 읽고 쓸 수 있는 하나의 Markdown 디렉터리로 수렴시키고, 도구 쪽에는 "포인터 + 짧은 훅"만 남겨둡니다.

| 디렉터리 | 내용 |
|---|---|
| [docs/](docs/) | **설계 배경**: 왜 이렇게 설계했는가, 모든 게이트 뒤에 있는 실제 사고(중국어) |
| [starter/](starter/) | **복사 즉시 사용 골격**: 디렉터리 구조 + 규칙 전체 + 예시 프로젝트 |
| [scripts/](scripts/) | **게이트 스크립트**: 인덱스 생성 / 할 일 감사 / 인코딩 검사 / 지시문 동기화 |

## 핵심 원칙 (7가지 요약)

1. **거의 제로 구성** — Markdown 파일 + 표준 라이브러리 전용 스크립트. 디렉터리에 복사하는 것이 설치의 전부.
2. **기억의 저장소는 하나** — 도구 쪽 설정에는 "포인터 + 짧은 훅"만. 기억 내용은 쓰지 않는다.
3. **구조화된 계층** — `Preferences` / `Plans` / `Decisions` / `Lessons` / `Workflows` / `Projects` + `Todo.md`·`Inbox/`·`Archive/`.
4. **인덱스는 파생물** — frontmatter에서 `mem_index.py`가 생성. 사람은 한 줄 소개만 다듬고, 재생성해도 지워지지 않음.
5. **완료 = 이동** — 끝낸 할 일은 `working/completed.md`로 옮기고 Todo에서는 삭제. 자리에 ✅ 표시하지 않음.
6. **게이트 있는 공정만 무너지지 않는다** — 모든 게이트에는 실제 사고의 배경이 있음([docs/04](docs/04-演化史-门禁背后的事故.md)).
7. **프라이버시는 가드로** — `.gitignore` + `pre-commit` 훅이 `Memory/` 관련 커밋을 거부.

## 한 줄 배포

아래 문단을 **아무 AI 에이전트에게 그대로 보내면** 됩니다 (Claude Code, Cursor, 파일 조작 가능한 웹 에이전트 등):

```text
https://github.com/star-nebula/ai-memory-vault 를 클론(안 되면 zip 다운로드 후 압축 해제)하고,
starter/ 아래의 모든 내용을 내 기억 라이브러리 워크스페이스 루트에 복사하세요 —
이미 노트 저장소가 있으면 그 루트를, 없으면 빈 디렉터리를 새로 만듭니다.
그다음 그 디렉터리에서 python scripts/mem_index.py --write 로 인덱스를 생성.
마지막으로 워크스페이스 루트의 AGENTS.md와 Memory/_index.md를 읽고,
"언제 기억을 읽고 어떻게 쓰는지"를 나에게 되풀이해 주세요.
```

## 수동 배포

```bash
cp -r starter/* /path/to/your-vault/   # 유일한 "설치" 동작
```

치환할 플레이스홀더도, 설치할 의존성도 없습니다. 선택적 후속 단계:

```bash
python scripts/mem_index.py --write      # 계층별 인덱스 생성
python scripts/mem_index.py --check      # 인덱스 드리프트 게이트
python scripts/todo_audit.py --check     # 할 일 아카이브 게이트
python scripts/encoding_guard.py <path>  # 인코딩 + 제어 문자 게이트
```

**AI 도구 연결**: `starter/Memory/Workflows/AI工具自定义指令.md`에 전체판(사용자 지정 지시창에 붙여넣기)과 최소판(프로젝트 루트 `AGENTS.md`에 두기) 두 가지가 동봉되어 있습니다. 기본이 상대 경로 표기라 그대로 붙여도 동작합니다.

## 게이트 스크립트

| 스크립트 | 잡아내는 것 |
|---|---|
| `mem_index.py` | 수동 관리 인덱스의 드리프트 · "축자 일치" 쌍 표 불일치 · 판독 시 신선도 프로토콜 결여 |
| `todo_audit.py` | 완료 표시만 하고 이동하지 않은 항목 · 그룹명↔프로젝트 dir 불일치 · "Todo에 옮겼다"는 허위 보고 · 어휘 밖 type |
| `encoding_guard.py` | 비 UTF-8 / BOM · AI의 이스케이프 탈취가 남긴 제어 문자(grep에서 보이지 않는 지뢰) |
| `sync_memory_instructions.py` | 도구 지시 자리와 단일 진원의 드리프트 · 진원의 제어 문자 오염 |

> 상세 문서(설계 철학·구조·원칙·진화사)는 [중국어판 README](README.md)와 [docs/](docs/)를 참고하세요. **번역이 최신이 아니면 중국어판이 정본입니다.**

## License

[MIT](LICENSE) — 구조·규칙·스크립트는 자유롭게 사용하세요. 도움이 되었다면 Star이나 Issue로 여러분의 개조 사례를 공유해 주면 기쁩니다.
