---
name: nightshift
description: Executes a user-written handoff document overnight as an unattended autonomous work session — running prioritized missions (implementation and verification, performance improvement, research, data generation, long-running job babysitting) under strict guardrails with an append-only journal, then producing a polished Korean morning report for 조간보고/scrum by a hard deadline. Use when the user prepares to leave work for the night or asks for overnight execution — requests like "nightshift", "야간 작업", "밤새 돌려줘", "밤새 작업해줘", "overnight run", "handoff 실행해줘", "핸드오프 작성", "인수인계 문서 만들어줘", "아침 보고서", "조간보고 준비", "poll cadence", "heartbeat 주기" — including drafting or validating the handoff document itself, adjusting the observation cadence of an active night run, and rebuilding or converting a morning report (HTML, PPT, Markdown) from a run journal. Do not use for cron or scheduled automation, or for recurring checks outside a night run.
license: MIT
metadata:
  author: soonjune
  source: https://github.com/soonjune/skills
---

# Nightshift

Turn a handoff document into guarded unattended work, durable evidence, and a morning report that is ready by a fixed deadline. Keep the workflow independent of any particular model or agent harness.

## When to use

- Author or validate an end-of-day handoff while the user is still present.
- Execute prioritized missions overnight in the current session and report the results in the morning.
- Set a heartbeat or polling cadence for an already active night run.
- Rebuild an HTML report from a run journal or convert it to Markdown or PPT.
- Do not use for cron or scheduled automation. The active agent session is the runner.

## Modes

Choose one entry mode and reuse the later phases instead of duplicating them.

1. **Handoff authoring or validation:** Draft a handoff from current evidence or validate an existing handoff.
2. **Night run:** Validate the handoff, perform attended intake, execute missions, wrap up, and produce the report.
3. **Report rebuild or conversion:** Replay a journal into a fresh report without rerunning missions.

When the user says to implement, execute, or start during Mode 1, transition directly to Mode 2 in the same session with the handoff just written. Once execution starts, always finish through the reporting phase, even when every mission fails or becomes blocked.

## Native goals and cadence

Keep native goal state, observation cadence, and recurring scheduling separate.

- Use a host's persistent goal mode only when the user explicitly invokes or requests it. Do not create a native goal merely because Nightshift is active.
- Treat a native goal as a persistence aid for the objective, pause/resume state, and an explicitly requested token budget. Do not assume it provides a configurable wall-clock cadence, and keep `journal.jsonl` as the authoritative execution state.
- Accept an optional run-level `heartbeat_cadence`. Default to 5 minutes, allow 30 seconds through 10 minutes, and obey any stricter host update requirement.
- Let a mission's `poll_cadence` override the heartbeat for that mission. Use the shorter of the effective cadence, time remaining to `wrapup_at`, and any service reset or scheduler checkpoint.
- At each heartbeat, perform only cheap read-only checks and append a `step` with `action` set to `heartbeat`, including current mission, last evidence time, observed progress, next action, and seconds remaining to wrap-up and deadline.
- Treat cadence as a target observation interval, not an exact scheduler guarantee. Record drift after long tool calls, rate-limit waits, machine sleep, or host continuation delays; never let cadence postpone a safety or deadline check.
- A request to start new runs daily, weekly, or on a recurrence rule belongs to the host's scheduled-task surface after this workflow has passed manual validation. Do not add cron or a launcher to this skill.

## Run identity and storage

Capture the session's original absolute working directory before changing directories. Treat it as the default report destination.

1. Form the run ID as `<YYMMDD>-<slug>` in local time. Derive a short lowercase ASCII slug from the handoff title, collapse separators to single hyphens, and use `run` if no safe slug remains.
2. Use `~/nightshift/<run-id>/` as the default run directory. Let the handoff override the central root or retention policy explicitly.
3. Keep this structure:

   ```text
   <run-dir>/
   ├── handoff.md
   ├── journal.jsonl
   ├── artifacts/
   ├── logs/
   └── nightshift-report-<run-id>.<format>
   ```

4. Copy the exact handoff into the run directory and hash that copy with SHA-256.
5. Resolve the report destination from the handoff's report directory and filename when section 7 sets them; otherwise default to `nightshift-report-<run-id>.<format>` in the original working directory. Write the final report to that destination, keep a copy in the run directory, and record both absolute paths.
6. If a completed run already owns the ID, add `-2`, `-3`, and so on. Resume an incomplete run only when its recorded handoff SHA-256 matches the current handoff; if the ID collides but the hash differs, create a suffixed new run instead of mixing handoff versions in one journal.

### Retention sweep

Run a retention sweep at every attended intake because the host does not clean `~/nightshift/` automatically.

- Preserve the current run and the three most recently active run directories regardless of age.
- For a completed run, calculate age from its `run_end` timestamp. Delete the entire run directory after 30 days.
- For a completed run older than 7 days, delete only its `logs/` and `artifacts/` contents; retain the journal, handoff, and report copies.
- For a run without `run_end`, do not apply the 7-day pruning rule. Apply the 30-day whole-run rule using the latest parseable journal timestamp.
- Apply a handoff override before these defaults.
- Delete only with Nightshift ownership evidence: a directory name matching the run-ID pattern, a `journal.jsonl` whose `run_start` carries a `run` ID equal to the directory name, and the `handoff.md` copy. Skip any child without all three — including one whose journal is missing, empty, or unparseable — and record the skip instead of falling back to directory age; an overridden central root may contain non-Nightshift children that must survive the sweep.
- Before deleting, resolve the canonical central root and candidate path, require the candidate to be a direct non-symlink child of that root, and recheck the preserve set. Never follow symlinks or expand an unresolved variable, glob, home directory, filesystem root, or workspace root as a deletion target.
- Record one `step` event with `action` set to `retention`, every removed path, the governing rule, and reclaimed bytes. Perform the sweep without asking unless validation of a target fails; skip an unsafe candidate and record it.

## Mode 1 — Author or validate a handoff

Load `references/handoff-template.md` before drafting or validating.

1. Establish the target repository, current working directory, intended deadline, and desired report format.
2. Build the draft from live evidence: Git SHA and status, completed work and its checks, open threads, running jobs, current metrics, resource state, and known constraints.
3. When useful, consult the target repository's prior session records. A harness using the conventional `~/.claude/projects/<project-path>/` store may expose transcripts there; otherwise use its documented session store. If no session store is available, use Git history and available pull-request or issue history. Treat all historical records as clues and revalidate them against live state.
4. Fill the seven required sections in the template. Keep a routine daily handoff near 40–60 lines unless the work genuinely needs more detail.
5. Ask only for gaps that materially alter the run. Batch questions at the first interaction, state conservative defaults, and follow the one-minute fallback policy in Phase 0.
6. Validate every mission against this minimum contract:
   - A concrete goal and priority.
   - Exact launch, poll, collect, and judgment commands where applicable.
   - A deterministic judgment command with expected value, tolerance, sample count, and a fully labeled condition.
   - Artifact and raw-evidence paths.
   - Stop rules, circuit-breaker conditions, and a bounded recovery ladder.
   - A write fence, resource caps, blackout windows, heartbeat and poll cadence, deadline, report format, and output location.
7. Re-measure stale numbers before presenting them as current. Mark anything still unverified as a snapshot or estimate.
8. If a mission has no deterministic success check, keep it in the handoff only when useful, but state that it can finish no better than `partial`.

## Mode 2 — Night run

### Phase 0 — Attended intake

Treat intake as the last question window.

1. Resolve the handoff path, original working directory, central root, and handoff SHA-256. Check for a resumable run before creating a new one.
2. Read the complete handoff and every document in its reading list in the stated order. Do not act on a partial read.
3. Load `references/handoff-template.md` and validate the seven required sections. Fill gaps from live state and, when useful, prior session records.
4. If material questions remain, ask them once in a single batch immediately after the initial command. State these defaults:
   - Deadline: the next 06:30 in the session's local timezone.
   - Wrap-up start: 60 minutes before the deadline.
   - Report: self-contained HTML in the original working directory, with a copy in the run directory.
   - Journal root and retention: the defaults in this skill.
   - Heartbeat cadence: 5 minutes, with a 10-minute hard maximum and per-mission poll overrides.
   - Token and API budget: unlimited unless the handoff, service, or runtime imposes a limit.
   - Permissions: only capabilities already available to the session; never infer approval for privileged, destructive, irreversible, or out-of-fence actions.
5. Allow about one minute for an answer. If the host supports a timed question, use it. Otherwise create the run directory now if it does not exist, write `QUESTIONS.md` there, poll for `ANSWERS.md` for at most 60 seconds, and then proceed with the stated defaults. Record each unanswered default as a `decision` event. Never treat silence as approval for a guarded action.
6. Create or adopt the run directory, copy and hash the handoff, and create `artifacts/` and `logs/`. Resolve the deadline, wrap-up margin, and cadence with a runtime date parser rather than mental arithmetic. Round-trip both epochs into the intended timezone and assert `deadline_epoch - wrapup_epoch = wrapup_margin_seconds`. Append `run_start` only after these checks pass.
7. Perform the retention sweep and journal its exact outcome.
8. Revalidate live state against the handoff: repository root, branch, SHA, dirty files, running jobs, host, resources, dependencies, and fresh values for decision-critical metrics. Append a `state_check` for every relevant match or drift.
9. Run a pre-flight smoke test without triggering real mission side effects:
   - Assert every referenced path and required executable exists.
   - Exercise one safe representative operation for each permission class needed overnight, including target reads, a temporary write inside the write fence, run-directory writes, process launch and polling, and network access only when allowed and required.
   - For every planned detached mechanism, launch a canary with that exact mechanism. Make the canary outlive the launch invocation and require the launch invocation to return while it is still running. In a second invocation, verify command identity and process start time, scheduler state, or reconnectable session ID while the completion sentinel is still absent; in a later invocation, verify the sentinel and exit state. A bare `kill -0` check is insufficient because PID namespaces can change and PIDs can be reused.
   - If the canary fails any cross-invocation check, do not use plain `nohup`; select a persistent scheduler, a host-supported long-lived execution session, or a single persistent shell that contains both launch and polling, and record its reconnect identifier.
   - Verify exact launch, poll, collect, and judgment commands parse and can reach their inputs.
   - Ask the user to confirm machine sleep is disabled, or inspect available power state safely. If it cannot be confirmed, record the risk as a `decision`.
   - Remove only temporary files created by this smoke test.
10. Re-read the persisted deadline, wrap-up epoch, timezone, and cadence before declaring readiness. If the current epoch is already at or after wrap-up, skip mission execution and enter Phase 2, which then records a terminal `skipped` for every mission before reporting.
11. Append one `intake` event containing question/default pairs and all pre-flight checks. Declare readiness, then enter the unattended loop. Ask no further questions after this point.

### Phase 1 — Execution loop

Process missions strictly in handoff priority order unless a recorded quota or deadline constraint requires reprioritization.

Maintain the next heartbeat timestamp across missions and waits. After every tool call or wait, check the real clock before deciding whether a heartbeat, poll, wrap-up, or deadline action is due.

For each mission:

1. Read the current epoch immediately before `mission_start`. If it is at or after `wrapup_at`, append `mission_end` as `skipped` with the deadline reason, without appending `mission_start` or dispatching work, and enter wrap-up.
2. Append `mission_start` with the exact goal.
3. Recheck mission preconditions against live state. Record drift before adapting.
4. Read the epoch again immediately before the first mission command. If tool or model latency crossed `wrapup_at`, append `mission_end` as `skipped` and enter wrap-up without dispatching. An earlier plan, decision, or reprioritization never reserves a start slot past the boundary.
5. Run the handoff's commands as written inside the write fence. Redirect long output to `logs/` and inspect bounded tails or targeted matches.
6. Append a `step` for each meaningful action with command, exit code, log path, and concise note. Do not put credentials, tokens, or secret-bearing command text in the journal.
7. Run only the mission's declared deterministic checks for judgment. First append one `result` per metric with raw value, unit, full condition label, expectation, tolerance, sample count when relevant, command, and evidence path.
8. Judge from those results and then append `mission_end` with exactly one status: `pass`, `fail`, `partial`, `skipped`, or `blocked`.
9. Continue to the next mission after a terminal status unless the deadline or a global safety condition requires wrap-up.

#### Maximum-effort recovery

Do not mark an ordinary error blocked immediately.

1. Follow the handoff's hypothesis ladder in order.
2. Attempt bounded recovery inside all guardrails: limited retries, a reversible alternative approach, targeted log inspection, fresh state checks, and prior session history.
3. When existing session policy permits network research, consult primary or authoritative sources and journal the source and resulting decision without copying large passages.
4. Keep every attempt, changed assumption, and observed result in the journal.
5. If recovery still fails, append `mission_end` as `blocked` and continue. Put the exact user action or decision needed in the morning report.

Do not attempt recovery for an irreversible or destructive action, unattended remote restart, permission approval only the user can grant, or any operation outside the write fence. Fail closed, record the reason, and skip it.

#### Long-running job babysitting

Launch long work only with the persistence mechanism proven during pre-flight, a dedicated log, a PID file or completion sentinel, and enough metadata to reconnect after a crash. On a conventional persistent host shell, a typical pattern is:

```sh
nohup sh -c 'actual command' > /absolute/run/logs/job.log 2>&1 & echo $! > /absolute/run/job.pid
```

Do not treat a successful launch exit code or a PID visible only in the launch invocation as proof that the job persists. Verify command identity and start time, not only PID existence, from the next invocation. If command calls run in isolated containers, reap children, or expose different PID namespaces, use the handoff's scheduler or reconnectable long-lived session instead of plain `nohup`; record the scheduler job ID or session ID.

Append `job_launch` immediately. Poll with the cheapest read-only progress command at the effective poll cadence; inspect a bounded tail instead of rereading the full log. Append `poll` every time. Use the host's recurring wait facility when available; otherwise sleep in chunks no longer than the effective cadence or 10 minutes, whichever is shorter, and obey any stricter host update cadence. Compare expected and actual elapsed time so machine sleep or clock jumps become recorded decisions.

Detect completion from the declared sentinel, process state, or scheduler state. Then collect artifacts, run deterministic judgment, and either finish or perform the next bounded experiment. Never relaunch merely because a PID is absent; first inspect the sentinel, logs, scheduler, and artifacts.

#### Circuit breakers and usage constraints

- After three consecutive infrastructure failures for a mission, append `breaker` with kind `infra`, stop that mission, and continue.
- After five identical failures for one scenario, append `breaker` with kind `identical_failure` and drop that scenario. Reset consecutive counters only after a genuinely successful probe.
- Assume no token or API ceiling by default, but obey declared budgets and actual service limits.
- Treat rate limits, quotas, and exhausted budgets as `constraint` events, not mission failures. Record the reset window when known, back off until it, and reprioritize remaining work by value, remaining time, cost, and availability of cheap verification.
- Check the current epoch between steps. At `wrapup_at`, stop starting work and enter Phase 2 even if missions remain; Phase 2 gives every unterminated mission its terminal event.

### Phase 2 — Wrap-up and report

Reserve the final 60 minutes for this phase unless the handoff explicitly chooses another margin. Never skip the report.

1. Append `wrapup_start` with the trigger.
2. Give every handoff mission exactly one terminal `mission_end` before anything else can end the run: append `skipped` with the reason for each mission never started, and an honest `partial`, `blocked`, or `fail` — judged only from evidence already recorded — for a mission interrupted mid-execution. Report counts and crash replay depend on these terminal events.
3. Put each running job into the handoff's declared safe state. Do not invent a stop or remote restart command.
4. Capture final repository, process, resource, and artifact state. Append `state_check` entries comparing it with intake.
5. Update an allowed handoff or follow-up document with actual results when the write fence permits it, leaving evidence usable by the next worker.
6. Load `references/report-guide.md`. For the default HTML format, copy `references/report-template.html` as a file and fill it according to its top placeholder map; do not load the entire template into conversational context. For a requested Markdown or PPT format, skip the HTML template and follow the guide's format-specific rules, keeping the same section order and evidence rules.
7. Derive factual outcome claims only from `result`, `decision`, `mission_end`, and linked evidence. Use the other journal events — `run_start`, `mission_start`, `job_launch`, `poll`, `breaker`, `constraint`, `wrapup_start` — for the run period, timeline, and operational metadata. If evidence is sparse, still create an honest journal-only report.
8. Scan the report and copied artifacts for likely credentials or secret values. Remove secret material while retaining safe environment-variable names and file paths.
9. Validate the report for its format. For HTML: self-contained, no script or external asset request, no unresolved required placeholder or template/sample comment, and working internal navigation and print styling. For Markdown or a PPT outline: every required section present in order, no unresolved placeholder, and evidence paths and condition labels preserved.
10. Complete all cleanup and validation on a temporary report file. Replace the resolved destination only after validation, copy the final bytes into the run directory, and require both copies to have the same hash.
11. Append `report` only after both validated copies exist.
12. Append exactly one `run_end` as the terminal Mode 2 event with the honest aggregate status and mission counts. After it is appended, perform no more tool calls, journal appends, report edits, or cleanup; return only the final user-facing response.

## Guardrails

- **Revalidate snapshots.** Treat the handoff and prior records as snapshots. Check live state immediately before every consequential action.
- **Require external evidence.** Never accept a process's self-reported success as proof. Use the declared deterministic external check and attach raw evidence.
- **Record numbers before judgment.** Append measured values as `result` events before writing pass or fail.
- **Never game a metric.** Do not modify production code, tests, datasets, thresholds, tolerances, or sample selection merely to make a check pass.
- **Label conditions completely.** Include dataset or cohort, code revision, configuration, hardware or service, seed, sample count, and protocol whenever relevant. Never merge different protocols into one unlabeled table or headline number.
- **Honor the write fence.** Preserve pre-existing user changes. Do not run Git checkout, stash, reset, or clean against the user's tree. Do not push. Make local commits only when the handoff authorizes them. Use a separate Git worktree for parallel code work.
- **Honor resource limits.** Enforce GPU, CPU, memory, disk, API, cost, concurrency, and blackout constraints from the handoff and live environment.
- **Fail closed only for dangerous actions.** Skip unattended remote restarts, irreversible or destructive changes, permission elevation, and out-of-fence writes. For normal errors, pursue bounded recovery before declaring blocked.
- **Bound context growth.** Stream long output to files, read small tails or targeted excerpts, and externalize state to the journal.
- **Keep secrets out.** Never write credential values, tokens, private keys, secret-bearing URLs, or raw sensitive environment dumps into commands, logs selected for retention, the journal, or the report. Record safe variable names or credential-file paths only.
- **Treat retention as a narrow exception.** Delete only validated aged contents under the configured central run root according to the retention policy. Never use retention to clean a repository or arbitrary user path.

## Append-only journal

Use one JSON object per line in `journal.jsonl`. Never rewrite, sort, truncate, or repair existing lines in place. Add a corrective event if an earlier event is wrong. Keep timestamps in ISO 8601 with a numeric UTC offset.

Use a JSON parser to serialize each event instead of interpolating shell text. This portable pattern validates the payload before appending it:

```sh
python3 -c 'import datetime,json,sys; event=json.load(sys.stdin); event.setdefault("ts",datetime.datetime.now().astimezone().isoformat()); print(json.dumps(event,ensure_ascii=False,separators=(",",":")))' >> "/absolute/run/journal.jsonl" <<'JSON'
{"run":"260806-example","type":"step","mission":"M1","action":"probe","cmd":"safe command summary","exit_code":0,"log":"logs/probe.log","note":"raw output retained in log"}
JSON
```

Include `ts`, `run`, and `type` in every event. Use these type-specific fields:

| Type | Required type-specific fields |
| --- | --- |
| `run_start` | `handoff`, `handoff_sha256`, `deadline`, `wrapup_at`, `report_format`, `report_dir`, `cwd`, `host`, optional `heartbeat_cadence_seconds` |
| `intake` | `questions` as question/answer pairs, `preflight` as objects with `check`, `ok`, `detail` |
| `state_check` | `scope`, `expected`, `observed`, `match` |
| `mission_start` | `mission`, `goal` |
| `mission_end` | `mission`, `status`, `summary`, `artifacts` |
| `step` | `mission` when applicable, `action`, `cmd`, `exit_code`, `log`, `note` |
| `job_launch` | `mission`, `cmd`, `pid`, `log`, `sentinel` |
| `poll` | `mission`, `pid`, `alive`, `progress` |
| `result` | `mission`, `metric`, `value`, `unit`, `condition`, `expected`, `tolerance`, `pass`, `cmd`, `evidence` |
| `decision` | optional `mission`, `question`, `choice`, `rationale`, `reversible` |
| `breaker` | `mission`, `kind` as `infra` or `identical_failure`, `count`, `action` |
| `constraint` | `kind` as `rate_limit`, `quota`, or `budget`, `detail`, `action`, `resume_at` |
| `wrapup_start` | `reason` |
| `report` | `path`, `format`, `copies` |
| `run_end` | `status`, `missions_total`, `missions_done` |

A pass or fail claim must have an earlier `result` event. Reports may derive factual outcome claims only from `result`, `decision`, and `mission_end` events, with paths to supporting evidence.

## Crash resume

Before starting a new run, compute the handoff SHA-256 and scan `~/nightshift/*/journal.jsonl`, or the overridden root, for the newest `run_start` with the same hash and no later `run_end`.

- Adopt that run directory after validating its canonical path and handoff copy.
- Replay the journal in order to reconstruct decisions, completed missions, counters, running jobs, deadline, and wrap-up state.
- Never rerun a mission that has `mission_end`. For an interrupted mission, first verify host, PID namespace, scheduler or long-lived-session identity, then inspect process state, sentinel, logs, and artifacts before deciding whether to reconnect, recover, or mark partial.
- Continue appending after the last valid JSON line. If a crash left one malformed final line, preserve its bytes; when the file does not end with a newline, first write a single newline terminator so the malformed bytes stay on their own line, then append the recovery note as a new line, and make journal replay skip only that documented malformed line.
- If the matching run has `run_end`, create a suffixed new run unless the request is Mode 3.
- Treat any Mode 2 `run_end` as terminal. Never append a duplicate `run_end` or reopen mission execution after it.
- Keep the report reproducible from the journal even if all live processes and conversational context are lost.

## Mode 3 — Rebuild or convert a report

1. Accept a run directory or journal path and validate it stays within the user-provided scope.
2. Replay the journal without executing mission commands.
3. Load `references/report-guide.md` and follow the same evidence and secret-handling rules as Phase 2.
4. For HTML, copy and fill `references/report-template.html`.
5. For Markdown, preserve the HTML report's section order, status labels, evidence paths, decisions, and next steps.
6. For PPT, use an available workplace presentation skill when one exists. Otherwise produce a slide-by-slide Markdown outline and clearly state that no PPT-generation capability was available.
7. For a completed run, record regeneration in a separate `report-rebuild.jsonl` sidecar when writable and authorized. Never append another `run_end` or reopen the execution journal; otherwise leave the source untouched.

## Reference loading

- Load `references/handoff-template.md` when authoring, validating, or performing intake on a handoff.
- Load `references/report-guide.md` immediately before generating, rebuilding, or converting a report.
- Treat `references/report-template.html` as a file template. Read only its top placeholder map and the specific marked block being cloned; do not inject the full HTML into conversational context.
