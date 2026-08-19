---
type: regex
pattern: '[—–―]'
match: not_contains
target: last_message
weight: 2
---

엠대시(—)·엔대시(–)·가로줄(―) 문자가 있으면 실패한다. upstream 스타일 "구 단위 4번"(엠대시는 콜론이나 접속사로 대체) 근거.
