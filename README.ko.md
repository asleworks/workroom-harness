# Workroom Harness

Codex와 Claude Code용 AI 코딩 에이전트 실행 하네스입니다.

하네스가 소유하는 파일은 모두 `.workroom/` 안에 설치됩니다. 기존 프로젝트의 `docs/`, `scripts/`, `AGENTS.md`와 충돌하지 않게 하기 위해서입니다.

```text
.workroom/
├── AGENTS.md        Workroom 전용 에이전트 규칙
├── docs/            PRD, 아키텍처, ADR, 테스트 전략
├── workflows/       plan, phase, harness, review, fix 워크플로우
├── scripts/         설치, 검증, phase 실행 스크립트
├── phases/          생성되는 phase 계획과 실행 상태
└── templates/       phase 템플릿

.agents/skills/      Codex용 skill
.claude/skills/      Claude Code용 skill
```

## 설치

Codex용:

```bash
curl -fsSL https://raw.githubusercontent.com/asleworks/workroom-harness/main/.workroom/scripts/install-codex.sh | bash
```

Claude Code용:

```bash
curl -fsSL https://raw.githubusercontent.com/asleworks/workroom-harness/main/.workroom/scripts/install-claude.sh | bash
```

포크나 테스트 레포를 설치할 때는 환경변수로 대상 저장소를 바꿀 수 있습니다.

```bash
WORKROOM_HARNESS_REPO=your-account/workroom-harness \
  curl -fsSL https://raw.githubusercontent.com/asleworks/workroom-harness/main/.workroom/scripts/install-codex.sh | bash
```

설치 전 미리보기:

```bash
curl -fsSL https://raw.githubusercontent.com/asleworks/workroom-harness/main/.workroom/scripts/install-codex.sh | bash -s -- --dry-run
```

설치 후 확인:

```bash
python3 .workroom/scripts/doctor.py
```

처음 설치한 직후에는 `doctor.py`가 하네스는 설치됐지만 프로젝트 문서는 아직 준비되지 않았다고 경고할 수 있습니다. `$workroom-plan`을 실행하기 전이라면 정상입니다.

기존 설치를 업데이트할 때는 `--overwrite`를 붙여 다시 실행합니다.

```bash
curl -fsSL https://raw.githubusercontent.com/asleworks/workroom-harness/main/.workroom/scripts/install-codex.sh | bash -s -- --overwrite
```

Claude Code만 설치한 프로젝트라면 Claude 설치 스크립트에 같은 옵션을 붙입니다.

```bash
curl -fsSL https://raw.githubusercontent.com/asleworks/workroom-harness/main/.workroom/scripts/install-claude.sh | bash -s -- --overwrite
```

`--overwrite`는 하네스 소유의 scripts, workflows, templates, skills를 갱신합니다. 프로젝트 상태 파일인 `.workroom/AGENTS.md`, `.workroom/docs/`, `.workroom/phases/`, `.workroom/scripts/verify.sh`는 보존합니다.

## 사용법

사용자가 알면 되는 명령은 세 개입니다.

### 1. 문서 채우기

Codex:

```text
$workroom-plan
```

Claude Code:

```text
/workroom-plan
```

아이디어를 말하면 에이전트가 질문을 하면서 `.workroom/AGENTS.md`와 `.workroom/docs/`를 채웁니다. 마지막에는 fresh docs reviewer run과 `python3 .workroom/scripts/validate_docs.py`를 통과해야 끝납니다. 리뷰가 승인하지 않으면 문서를 고치고 다시 리뷰합니다.

### 2. Phase 설계

Codex:

```text
$workroom-phase
```

Claude Code:

```text
/workroom-phase
```

채워진 문서를 기반으로 `.workroom/phases/{task-name}/` 아래에 phase 계획을 만듭니다. 구현은 하지 않습니다. 마지막에는 fresh phase-plan reviewer run과 `python3 .workroom/scripts/validate_phases.py {task-name}`를 통과해야 끝납니다. 리뷰가 승인하지 않으면 phase 파일을 고치고 다시 리뷰합니다.

### 3. 하네스 실행

Codex:

```text
$workroom-harness
```

Claude Code:

```text
/workroom-harness
```

만들어진 phase를 처음부터 끝까지 실행합니다.

```text
fresh worker run
-> verify.sh
-> fresh reviewer run
-> fix
-> reviewer approval
-> next phase
```

Codex는 내부적으로 `codex exec`를 쓰고, Claude Code는 기본적으로 `claude -p --permission-mode bypassPermissions`를 씁니다. non-interactive worker가 명령 승인 대기 때문에 멈추지 않게 하기 위해서입니다. 더 엄격한 모드가 필요하면 `WORKROOM_CLAUDE_PERMISSION_MODE`로 바꿀 수 있습니다.

검증이나 리뷰가 실패하면 하네스는 실패 내용을 작업자에게 다시 전달하고, 실패 내용이나 repository diff가 바뀌는 동안은 계속 시도합니다. 같은 실패와 같은 repository 상태가 반복되어 진전이 없거나 phase별 safety budget을 다 쓴 경우에만 멈춥니다. 이때 phase는 `pending` 상태와 `last_failure_reason`, `last_failure_log`를 남기며, 이 retry 가능한 pause는 기본적으로 CLI 에러로 처리하지 않습니다. 외부 자동화에서 non-zero exit이 필요할 때만 `--strict-exit-codes`를 씁니다.

컴파일, lint, test, 리뷰 실패는 기본적으로 워커에게 다시 전달되는 내부 fix-loop 입력입니다. 하네스는 매 시도마다 전체 에러를 터미널에 쏟지 않고 진행 상황과 로그 경로만 출력합니다. 매 시도별 상세 출력을 터미널에서 보고 싶을 때만 `--verbose`를 씁니다.

리뷰 에이전트는 자연어로 지적 사항을 쓰고 마지막에 `REVIEW_DECISION: APPROVED` 또는 `REVIEW_DECISION: CHANGES_REQUESTED`만 남깁니다. 하네스는 이 결정 줄만 파싱하고, 리뷰 본문은 그대로 워커 피드백으로 전달합니다.

API key 입력, 계정 연결, 외부 서비스 수동 확인처럼 구현 이후에 필요한 작업은 `deferred_requirements`로 기록합니다. 하네스는 중간에 멈추는 대신 `completed_with_deferred_requirements`로 끝내고 마지막에 남은 사용자 액션을 출력할 수 있습니다.

## 직접 수정할 파일

처음 설치 후 주로 바꾸는 파일은 이 정도입니다.

```text
.workroom/AGENTS.md
.workroom/docs/PRD.md
.workroom/docs/ARCHITECTURE.md
.workroom/docs/ADR.md
.workroom/docs/TEST_STRATEGY.md
.workroom/scripts/verify.sh
```

`verify.sh`에는 실제 프로젝트의 검증 명령을 넣습니다.

```bash
npm run lint
npm run typecheck
npm run test
npm run build
```

## 로컬 설치

레포를 직접 받아둔 상태라면:

```bash
python3 /path/to/workroom-harness/.workroom/scripts/install.py /path/to/your-project --agent codex
python3 /path/to/workroom-harness/.workroom/scripts/install.py /path/to/your-project --agent claude
```

## 원칙

프로젝트 지식, 실행 상태, 스크립트는 `.workroom/` 안에 둡니다.

도구별 skill과 runner는 분리하고, `.workroom/`의 문서/phase/스크립트는 공유합니다.

```text
Codex skill:  .agents/skills/
Claude skill: .claude/skills/
Codex runner: codex exec
Claude runner: claude -p
```
