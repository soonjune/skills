# natural-korean 평가 사례

두 종류의 회귀 자료를 둔다.

- `trigger-cases.json`: 클라이언트가 `natural-korean`을 열어야 하는 요청과 열지 않아야 하는 요청
- `output-cases.json`: 스킬을 적용한 결과가 지켜야 할 의미·레지스터·장르 불변 조건

## Trigger 평가

각 질의를 같은 조건에서 최소 3회 실행하고, 에이전트가 실제로 `SKILL.md`를 읽었는지
로그나 도구 호출 기록으로 확인한다. `should_trigger`와 실제 결과가 같은 비율을 기록한다.
description은 라우팅 힌트이므로 한 번의 성공만으로 자동 발동을 보장한다고 판단하지 않는다.

## Output 평가

정답 문장을 하나로 고정하지 않는다. 각 결과를 다음 순서로 채점한다.

1. `must_preserve`의 사실·수치·양태가 모두 남았는지 확인
2. `must_avoid`가 산출물에 없는지 확인
3. `rubric` 항목을 사람이 검토
4. 스킬 디렉터리에서 `python3 scripts/check.py --genre report /absolute/path/to/output.md`처럼 실제 장르와 산출물 절대 경로를 지정해 실행

사람이 실제로 검토하지 않은 결과는 성공 0건으로 기록하지 않는다. 업무 문장이나 문서명은
평가 파일에 추가하지 말고, 같은 현상을 재현하는 새 합성 사례를 만든다.
