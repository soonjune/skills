---
description: 한국어 출력 A/B 피드백(적용 전 대비 👍/👎)을 로컬 상태에 기록
argument-hint: "[up|down] [misread] [짧은 메모]"
---

사용자의 한국어 출력 피드백을 기록한다. 인자: $ARGUMENTS

1. 판정이 없으면 "이번 세션의 한국어 설명이 평소보다 이해하기 나았는지"를 👍(up)/👎(down)로 짧게 한 번만 물어본다.
2. 아래 명령을 실행한다. misread는 Claude가 한 일을 사용자가 오해했던 사건이 있을 때만 붙인다.

   ```sh
   python3 ~/.claude/skills/natural-korean/scripts/feedback.py --verdict <up|down> [--misread] [--note "<짧은 메모>"]
   ```

3. 메모에 업무 문서 원문, 파일 경로, 수치를 넣지 않는다. 스크립트가 거부하면 메모를 빼고 다시 기록한다.
4. 기록 결과 한 줄을 사용자에게 확인해 준다. 집계가 궁금하다고 하면 `--summary`를 실행해 보여 준다.
