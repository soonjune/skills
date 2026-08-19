---
max_turns: 4
---

아래는 서비스 로그다. 무엇이 잘못됐고 어디를 먼저 확인해야 하는지 한국어 6~10문장으로 설명해줘. 코드 블록과 불릿 없이 문단으로만.

```
Traceback (most recent call last):
  File "app/worker.py", line 87, in process_job
    user_id = payload["user_id"]
KeyError: 'user_id'

[2026-08-18 02:14:07] ERROR worker: job f3a1 failed after 3 retries
[2026-08-18 02:14:07] WARN  queue: dead-letter queue size = 152
```
