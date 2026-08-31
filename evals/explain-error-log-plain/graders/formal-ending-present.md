---
type: regex
pattern: '(?:습니다|합니다|입니다|됩니다|한다|이다|된다|예요|에요|해요)[.!?]'
match: contains
target: last_message
weight: 1
---

종결어미로 완결된 문장이 최소 하나는 있어야 통과한다.
