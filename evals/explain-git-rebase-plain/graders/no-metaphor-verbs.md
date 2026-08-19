---
type: regex
pattern: '녹여내|담아내|담아냈|굳혀|굳히|물꼬를 트|발판을 마련|초석을 다지|기반을 다지|날개를 달'
match: not_contains
target: last_message
weight: 1
---

일반 동사 자리에 비유 표현을 쓰면 실패한다. natural-korean rules.json의 R-41 패턴을 그대로 재사용한다.
