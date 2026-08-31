---
type: llm
weight: 1
---

마지막 답변이 doctest 검증을 실제로 실행해 통과했다고 일관되게 보고하는지 확인한다. rle 구현 설명이 예시("aaabcc" → "a3b1c2", "" → "")와 일치해야 한다. 검증을 건너뛰었다고 하거나 실패를 남긴 채 끝냈으면 불통과. 실행 증거 자체는 doctest-trace-passed grader가 trace에서 별도로 확인한다.
