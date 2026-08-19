---
type: regex
pattern: '(?=.*18%)(?=.*4시간)(?=.*2시간)'
flags: s
match: contains
target: last_message
weight: 1
---

세 가지 수치(18%, 4시간, 2시간)가 모두 보존되어야 한다.
