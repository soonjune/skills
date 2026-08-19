---
type: regex
pattern: 'passed and 0 failed|Test passed'
match: contains
target: trace
weight: 2
---

대화 기록(trace)에 doctest 성공 출력이 실제로 남아 있어야 통과한다. 프롬프트가 `-v` 실행을 요구하므로 성공 시 "N passed and 0 failed" 또는 "Test passed"가 도구 출력에 나타난다. llm grader는 `target`을 지원하지 않아 실행 증거는 이 regex가 담당한다.
