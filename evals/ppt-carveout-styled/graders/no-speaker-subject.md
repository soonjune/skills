---
type: regex
pattern: '(?:^|[\s(])(?:우리|저희)(?:는|가)\s'
flags: m
match: not_contains
target: last_message
weight: 1
---

원문에 없던 화자 주어(우리는/저희가)를 불릿에 넣으면 실패한다. R-31 재사용.
