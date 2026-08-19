# natural-korean-understanding evals

상시 output style(`output-styles/natural-korean-understanding.md`)이 한국어 서술을 실제로 개선하는지, 그리고 코딩 작업과 natural-korean 스킬의 산출물 규칙을 해치지 않는지 측정한다. 같은 프롬프트를 스타일 없이(`*-plain`) / 스타일을 `append_system_prompt`로 주입해(`*-styled`) 각각 돌리고 점수 차이를 본다. output style은 eval 샌드박스에서 선택되지 않으므로 이 쌍 비교가 유일하게 유효한 방법이다.

## 실행

```sh
# plugin eval은 early access라 활성화 변수가 필요하다
CLAUDE_CODE_WALNUT_SPIRE=1 claude plugin eval /home/soonjun-park/skills \
  --ablation none --allow-tools Bash Write --threshold 0 --no-publish \
  --json evals/results/<이름>.json
```

- `--ablation none`은 필수다. 비교는 케이스 쌍이 담당하므로 CLI의 with-without 비교(플러그인 유무)를 꺼야 한다.
- `--case '<glob>'`으로 일부만 돌리고, triage가 필요하면 `--keep-temp`로 transcript를 남긴다.
- 저장소가 group-writable이면 CLI가 결과 쓰기를 거부한다. `chmod -R g-w` 상태를 유지한다.
- 결과는 gitignore된 `evals/results/`에 쌓인다.

## 케이스 구성

| 케이스 쌍 | 내용 | 목적 |
|---|---|---|
| `explain-git-rebase` | 기술 개념을 한국어로 설명 | 설명 품질 |
| `explain-error-log` | 영문 로그를 한국어로 해석 | 영어 자료 기반 설명 품질 |
| `narrate-work` | 파일 작성·실행 후 작업 경과를 서술 | 핵심 목표: 작업 서술 이해가능성 |
| `ppt-carveout` | 슬라이드 불릿 3개 + 다듬은 기준 설명 | 경계 감시: 스타일이 산출물의 개조식을 침범하지 않는지 |
| `coding-regression` | doctest 포함 구현과 검증 실행 | 스타일이 도구 사용과 정확성을 해치지 않는지 |

## Grader 원칙

한국어 품질이 의심되는 모델에게 한국어 평가를 통째로 맡기면 순환 평가가 되므로, 결정적 regex를 우선하고 llm grader는 보조로 쓴다. 공유 grader의 원본은 `shared-graders/`에 있고 각 케이스 디렉터리로 복사된다. R-30(PPT 서술형 종결), R-41(비유 동사) 패턴은 natural-korean `references/rules.json`을 재사용한다. llm grader는 `target`을 지원하지 않으므로 trace 증거 확인은 regex(`target: trace`)가 담당한다.

## styled 케이스는 생성물이다

`*-styled/` 디렉터리 전체는 `sync_style.py`가 만든다. 고칠 내용은 `*-plain/`이나 output style 파일에서 고치고 재생성한다.

```sh
python3 evals/sync_style.py          # 재생성
python3 evals/sync_style.py --check  # 커밋 전 신선도 검사
```

## 실패 triage 절차

실패를 발견하면 다음 순서로 스스로 해결한다.

1. 실패를 셋으로 분류한다: grader 결함(오탐·기술적 오류), 실제 문체 문제, 프롬프트 문제.
2. grader 결함이면 `shared-graders/`와 해당 `*-plain/graders/`의 패턴을 고치고 `sync_style.py`로 styled에 전파한다. 패턴 변경 diff는 사용자와 공유한다.
3. 실제 문체 문제가 styled arm에서 나오면 output style 문구를 조정하고 두 arm을 다시 돌린다.
4. 프롬프트 문제면 plain 프롬프트를 고치고 sync 후 두 arm을 다시 돌린다.
5. 해결하지 못한 실패는 아래 "알려진 한계"에 기록하고 넘어간다.

## A/B 프로토콜

- 객관 지표: 이 suite의 plain/styled 쌍 점수 차이. 판정 시점에 전체 스윕을 한 번 더 돌려 케이스당 arm별 6회(2회 스윕 × 3 runs)를 확보한다.
- 주관 지표: `scripts/kr-ab.sh` 래퍼가 인터랙티브 `claude` 세션마다 50% 확률로 스타일을 주입하고(`NK_AB_ARM` 노출), styled 세션 마무리에 "평소보다 이해하기 나았는지"를 👍/👎로 한 번 묻는다. 기록은 `skills/natural-korean/scripts/feedback.py`가 `~/.local/state/natural-korean-ab/`(learn.py 저장소와 분리, untracked 파일이 있으면 learn.py가 멈추기 때문)에 남긴다. 수동 기록은 `/kr-feedback`.
- 판정 규칙: `narrate-work`·`explain-*` 쌍의 styled−plain 점수 차이 ≥ +0.10 이고, `coding-regression` 차이 ≥ −0.05 이고, `ppt-carveout-styled` ≥ 0.9 이고, 주관 up-rate가 10건 이상에서 70%를 넘고 misread가 늘지 않으면 채택한다. 채택하면 `~/.claude/settings.json`에 `"outputStyle": "natural-korean-understanding"`을 영구 설정하고 래퍼를 제거한다. styled 개선이 전혀 없으면 "프롬프트 수준에서 해결 불가"로 기록한다(워터마크가 샘플링 레벨이라면 프롬프트로 제거할 수 없고, 이 결과 자체가 에스컬레이션 근거다).
- 포화 보정: 1차 측정에서 plain arm이 이미 대부분 1.00이라 "+0.10 개선" 기준은 성립할 수 없다. regex 지표가 양 arm에서 포화되어 있는 동안 객관 지표는 가드레일로만 쓴다(styled가 어느 케이스에서도 0.95 아래로 떨어지지 않을 것, coding-regression 차이 ≥ −0.05, ppt-carveout-styled ≥ 0.9). 채택 판정의 주 지표는 주관 up-rate다. 더 어려운 케이스가 추가되어 plain이 포화를 벗어나면 원래 기준으로 돌아간다.

## Baseline (2026-08-19, plain arm, runs=3)

| 케이스 | 평균 점수 | 비고 |
|---|---|---|
| explain-git-rebase-plain | 1.00 | 전 grader 통과 |
| explain-error-log-plain | 1.00 | 전 grader 통과 |
| narrate-work-plain | 1.00 | 전 grader 통과 |
| ppt-carveout-plain | 1.00 | 전 grader 통과 (아래 참고) |
| coding-regression-plain | 1.00 | doctest trace grader 포함 전 grader 통과 |

참고: ppt-carveout의 최초 실행은 0.67이었으나, 저장소가 group-writable이라 CLI가 manifest를 무시하던 환경에서 나온 결과였다. `chmod -R g-w` 후 재실행에서는 grader와 프롬프트를 바꾸지 않고 3회 모두 1.00이 나왔고, 이때 스킬은 불릿 명사형 유지·수치와 양태 보존·완결 문장 설명을 정확히 지켰다.

해석: 현재 기본 모델은 이 다섯 과제의 plain arm에서 전보식·엠대시 같은 기계적 실패를 내지 않았다. 따라서 regex grader들은 styled arm의 회귀를 막는 가드레일로 기능하고, 개선 신호는 llm grader와 주관 피드백(up-rate)에서 찾아야 한다. 더 어려운 케이스(긴 세션 요약, 컨텍스트 압축 후 서술 등)는 다듬으면서 추가한다.

## 1차 쌍 비교 (2026-08-19, arm당 runs=3)

| 케이스 | plain | styled | 차이 | 비고 |
|---|---|---|---|---|
| explain-git-rebase | 1.00 | 1.00 | 0.00 | |
| explain-error-log | 1.00 | 1.00 | 0.00 | |
| narrate-work | 1.00 | 0.97 | −0.03 | llm judge 3표 중 2표 실패 1회 (노이즈 수준) |
| ppt-carveout | 0.91 | 0.95 | +0.04 | 안정화 프롬프트 기준, 아래 참고 |
| coding-regression | 1.00 | 1.00 | 0.00 | 성능 회귀 없음, doctest 증거 포함 |

가드레일 판정: 스타일은 코딩 정확성(coding-regression 1.00), 산출물 경계(ppt-carveout-styled ≥ 0.9, 불릿 개조식 유지), 기계 지표 어디에서도 회귀를 만들지 않았다. 채택 여부는 주관 up-rate가 결정한다.

ppt-carveout 안정화 기록: styled 첫 스윕에서 3회 중 2회가 0.57로 떨어졌는데, transcript 확인(`--keep-temp` 재실행, 3회 모두 1.00) 결과 스타일 문제가 아니라 모델이 마지막 턴을 짧은 후속 코멘트로 끝내면 `last_message`에 본문이 빠지는 측정 아티팩트였다. 프롬프트에 "불릿과 설명을 마지막 한 번의 답변에 함께 담고, 추가 확인 질문으로 끝내지 마"라는 형식 제약을 추가해 안정화했고(위 표는 그 기준), 이 제약은 두 arm에 동일하게 적용되므로 비교는 공정하다.

## 알려진 한계

- llm grader는 기본 judge(haiku) 3표 중 2표 방식이라 한국어 미세 품질에는 둔감할 수 있다. 필요하면 `--judge-model`로 올린다.
- regex의 명사형 예외 목록(다음·마음·처음 등)은 transcript를 보며 계속 튜닝한다.
