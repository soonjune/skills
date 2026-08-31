# 로컬 취향 프로필 계약

이 문서는 `natural-korean`이 선택적으로 읽는 로컬 취향 상태의 중립 계약을 정의한다. 이 프로필은 특정 에이전트에 묶이지 않은 사용자 선호이므로 같은 상태 디렉터리를 설정한 Claude와 Codex가 공유해 읽을 수 있다. 공개 스킬은 이 상태를 포함하지 않으며, 프로필이 없어도 기본 스타일 가이드만으로 동작한다. 비공개 상태 파일은 이 저장소에 복사하거나 커밋하지 않는다.

## 상태 디렉터리 선택

`scripts/learn.py`는 아래 순서로 상태 디렉터리를 정한다.

1. 명령에서 명시한 `--data-dir`
2. `NATURAL_KOREAN_DATA_DIR`
3. 호스트가 `CLAUDE_PLUGIN_DATA`를 제공할 때 그 아래 `natural-korean`

어느 것도 없으면 임의의 홈 디렉터리나 공개 스킬 폴더를 찾아 쓰지 않는다. 쓰기 작업에서 로컬 프로필을 읽을 때도 같은 설정만 사용한다.

상태 디렉터리는 공개 스킬 저장소나 다른 Git 저장소 안에 둘 수 없다. 직장에서만 사용할 프로필이라면 직장 환경에만 데이터 디렉터리를 설정한다. 다른 환경에서는 이 스킬의 링크·초기화·학습 명령을 실행하지 않는다.

상태 디렉터리는 현재 POSIX 사용자가 소유한 `0700` 디렉터리여야 한다. `init`은 새 디렉터리를 이 권한으로 만들고 Git 작업에도 `umask 077`을 적용한다. 기존 디렉터리나 내부 Git 데이터의 소유권·권한이 더 넓으면 자동으로 완화하지 않고 중단한다. 이때는 전체 트리를 직접 점검해 권한을 고치거나 새 상태 디렉터리에 다시 초기화한다. `.git`은 상태 디렉터리 안의 실제 디렉터리여야 하며 symlink, 별도 git-dir, 외부 common/object 디렉터리, object alternate를 허용하지 않는다. bare 저장소 안에도 상태를 만들지 않는다.

## `profile.json`

UTF-8 JSON 객체로 저장한다. 에이전트와 외부 취향 도구는 읽기 전에 현재 파일의 실제 `schema_version`과 필드를 확인한다.

```json
{
  "schema_version": 1,
  "preferences": [
    {
      "id": "LOCAL-0001",
      "instruction": "보고서 요약 불릿은 명사형으로 쓴다.",
      "genres": ["report"],
      "avoid": "요약했습니다",
      "prefer": "요약",
      "confirmations": 1,
      "sources": ["explicit"]
    }
  ],
  "candidates": [
    {
      "id": "LOCAL-0002",
      "instruction": "이메일 맺음은 한 문장으로 줄인다.",
      "genres": ["email"],
      "avoid": null,
      "prefer": null,
      "confirmations": 1,
      "sources": ["observed"]
    }
  ]
}
```

필드 원칙:

- `preferences`에 들어간 항목은 활성 취향이다. `candidates`는 작성에 적용하지 않는다.
- `genres`는 `all`, `ppt`, `report`, `email`, `code` 중 적용 범위를 담는다.
- `instruction`은 일반화한 취향, `avoid`와 `prefer`는 짧은 실제 리터럴 문자열 또는 `null`이다.
- `confirmations`는 서로 다른 검토 맥락에서 확인된 횟수, `sources`는 `explicit`, `correction`, `observed`의 집합이다.
- `--avoid`는 정규식이나 `~입니다` 같은 표기용 패턴이 아니다. 실제로 찾을 문자열(예: `입니다`)만 넣는다.
- 원문·수정문, 실제 업무 문장, 문서 경로, 프롬프트, 인명·회사명·수치·식별자는 저장하지 않는다.
- `record`는 숫자와 조직명처럼 보이는 문자열도 거부한다. 이름과 값을 빼고 `회사명은 일반화`, `구체 수치는 저장하지 않음`처럼 다시 추상화한다.

충돌 시 `SKILL.md`의 문체 우선순위를 따른다. 배열 순서를 최신성으로 해석하지 않는다. 같은 범위의 활성 취향끼리 충돌하면 현재 지시나 사용자 확인으로 해소하고, 필요하면 로컬 Git `history`에서 변경 시점을 확인한다.

## `reviews.json`

사람이 실제로 검토한 산출물만 집계한다. 문서명과 날짜별 원문은 저장하지 않는다.

```json
{
  "schema_version": 1,
  "totals": {
    "artifacts": 1,
    "chars": 800,
    "corrections": 2,
    "false_positives": 1
  },
  "by_genre": {
    "report": {
      "artifacts": 1,
      "chars": 800,
      "corrections": 2,
      "false_positives": 1
    }
  }
}
```

`artifacts`는 검토 완료 산출물 수다. `chars`를 함께 기록해 장르별 1,000자당 교정 수를 계산할 수 있고, `status`는 전체 교정률과 산출물당 오탐률을 보여준다. 미검토 산출물은 0건으로 넣지 않는다.

## `rules.local.json`

검사기가 읽는 파생 파일이다. `learn.py`가 `preferences` 중 `avoid` 리터럴이 있는 항목만 `LOCAL-NNNN` 규칙으로 변환한다. 리터럴은 `re.escape`로 이스케이프하고, 규칙은 `review` 수준·줄 단위·1회 임계값으로 생성한다.

- 후보는 이 파일에 들어가지 않는다.
- 공개 `references/rules.json`과 같은 엄격한 schema를 쓰므로 직접 편집하지 않는다.
- `check.py --state-dir <상태 디렉터리>`가 base와 local ID 충돌, 잘못된 정규식, 누락 필드를 거부한다.

## 외부 취향 프로필 연결

호스트나 다른 취향 관리 도구가 프로필을 제공할 수 있다. 공급자 이름과 저장 경로를 스킬에 결합하지 말고 아래 최소 형태로 정규화해 읽는다.

```json
{
  "schema_version": 1,
  "preferences": [
    {
      "genres": ["ppt"],
      "instruction": "슬라이드 본문은 명사형 불릿으로 쓴다."
    }
  ],
  "candidates": []
}
```

외부 프로필은 읽기 전용이다. `preferences` 중 현재 장르와 맞는 항목만 사용하고 `candidates`나 추론 항목은 무시한다. 외부 프로필에 쓰거나 동기화하려면 사용자가 별도 연결 방식을 명시해야 한다.
