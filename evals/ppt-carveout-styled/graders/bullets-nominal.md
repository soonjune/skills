---
type: regex
pattern: '^\s*[-*•·].*(?:입니다|합니다|습니다|한다|이다|된다|했다|였다)\.?\s*$'
flags: m
match: not_contains
target: last_message
weight: 3
---

슬라이드 불릿 줄이 서술형 종결어미로 끝나면 실패한다. natural-korean rules.json의 R-30 종결 목록을 불릿 줄에 한정해 재사용한다. 상시 스타일이 산출물 영역을 침범하지 않는지 감시하는 경계 장치다.
