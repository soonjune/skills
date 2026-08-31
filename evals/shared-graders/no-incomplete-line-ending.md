---
type: regex
pattern: '^(?!\s*(?:[-*+>#|]|\d+[.)])).*[가-힣](?:은|는|이|가|을|를|와|과|의|에|로|으로|에서|에게|부터|까지)\s*$'
flags: m
match: not_contains
target: last_message
weight: 1
---

본문 줄이 조사로 끝나 서술어가 탈락한 형태면 실패한다. 헤더·불릿·표 줄은 제외한다.
