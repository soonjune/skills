---
type: regex
pattern: '^(?!\s*(?:[-*+>#|`]|\d+[.)]))\s*\S.*[가-힣](?:함|됨|짐|(?<![다마처물웃믿얼울걸])음|(?<![책모])임)\s*[.]?\s*$'
flags: m
match: not_contains
target: last_message
weight: 3
---

설명 문장이 `~함/됨/임/음/짐` 명사형으로 끝나면 실패한다. 헤더·불릿·표·인용 줄은 검사에서 제외한다. 음/임 앞의 예외 글자 목록(다음·마음·처음 등)은 baseline transcript를 근거로 튜닝하며, 변경 시 diff를 공유한다.
