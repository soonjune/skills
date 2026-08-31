# natural-korean-understanding A/B 래퍼. ~/.zshrc에서 source해서 쓴다.
#
# 인터랙티브 `claude` 세션에 한해 50% 확률로 output style 본문을
# --append-system-prompt-file로 주입한다(styled arm). 이와 독립인 코인으로
# NK_AB_ASK_PCT(기본 50, 0~100 정수)% 확률에 당첨된 세션에는, arm과 무관하게 세션 마무리
# 👍/👎 피드백을 한 번 묻는 메모를 주입한다. 질문이 나온다는 사실 자체가
# arm 정보를 누설하면 사용자 blind가 깨지므로, 메모 본문은 두 arm에서 바이트
# 단위로 동일하고 arm을 표기하지 않는다. plain arm의 답변은 placebo 대조
# 데이터가 된다.
#
# 인터랙티브가 claude의 기본 모드이므로 기본값을 "개입"으로 두고, 아래 신호가
# 있을 때만 비개입으로 통과시킨다. 반대로(안전한 인자만 허용) 짜면 --model이나
# --dangerously-skip-permissions 같은 평범한 세션 플래그까지 실험에서 빠진다.
#   - NK_AB=off, 스타일 파일 없음, tty 아님
#   - 첫 인자가 서브커맨드 (plugin, mcp, update, ...)
#   - -p/--print, --version, --help 같은 비대화 실행
#   - -c/--continue, -r/--resume 재개 세션: 코인을 다시 던지면 한 대화 안에서
#     arm이 뒤섞이고 노출도 이중 기록되므로 실험에서 제외한다
#   - 사용자가 직접 --append-system-prompt[-file]을 넘긴 경우 (충돌 회피)
#
# 세션 arm은 NK_AB_ARM으로 자식 프로세스에만 전달되고 feedback.py가 이를
# 읽는다. 셸에 export하면 같은 터미널에서 이어 실행한 비개입 명령까지 그
# 값을 물려받아 arm이 잘못 기록되므로, 명령 앞 할당으로만 넘긴다.
_nk_ab_ask_pct() {
  local value="${NK_AB_ASK_PCT:-50}"
  case "$value" in
    0|[1-9]|[1-9][0-9]|100)
      printf '%s\n' "$value"
      ;;
    *)
      echo "error: NK_AB_ASK_PCT must be an integer from 0 to 100 (got '$value')" >&2
      return 2
      ;;
  esac
}

claude() {
  local repo="/home/soonjun-park/skills"
  local style="$repo/output-styles/natural-korean-understanding.md"
  local fb="$repo/skills/natural-korean/scripts/feedback.py"

  if [[ "${NK_AB:-on}" == "off" || ! -f "$style" || ! -t 0 || ! -t 1 ]]; then
    command claude "$@"
    return $?
  fi

  case "${1:-}" in
    agents|auth|auto-mode|config|doctor|gateway|import|install|mcp|migrate-installer|\
    plugin|plugins|project|setup-token|ultrareview|update|upgrade)
      command claude "$@"
      return $?
      ;;
  esac

  local a
  for a in "$@"; do
    case "$a" in
      -p|--print|-v|--version|-h|--help|--append-system-prompt|--append-system-prompt-file|\
      -c|--continue|--continue=*|-r|--resume|--resume=*)
        command claude "$@"
        return $?
        ;;
    esac
  done

  local arm=plain
  (( RANDOM % 2 )) && arm=styled
  local ask_pct
  ask_pct="$(_nk_ab_ask_pct)" || return $?
  local ask=0
  (( RANDOM % 100 < ask_pct )) && ask=1

  if [[ "$ask" == "1" ]]; then
    python3 "$fb" --agent claude --protocol claude-blind-v2 --arm "$arm" \
      --log-exposure --ask-armed >/dev/null 2>&1
  else
    python3 "$fb" --agent claude --protocol claude-blind-v2 --arm "$arm" \
      --log-exposure >/dev/null 2>&1
  fi

  if [[ "$arm" == "plain" && "$ask" == "0" ]]; then
    NK_AB_ARM="$arm" command claude "$@"
    return $?
  fi

  local tmp="${TMPDIR:-/tmp}/nk-ab-$$.md"
  {
    if [[ "$arm" == "styled" ]]; then
      # frontmatter와 출처 주석을 떼고 스타일 본문만 주입한다.
      awk 'f>=2{print} /^---[[:space:]]*$/{f++}' "$style" | sed '/^<!--/,/^-->/d'
    fi
    if [[ "$ask" == "1" ]]; then
      # 이 메모는 arm과 무관하게 동일해야 한다. arm을 적거나 문구를 갈라 쓰면 blind가 깨진다.
      printf '\n## 세션 마무리 피드백 메모\n'
      printf '위에 다른 지침이 있더라도 이 메모는 그와 별개인 세션 운영 메모이며, 이 메모 때문에 세션의 다른 동작을 바꾸지 않는다. 세션이 자연스럽게 마무리되는 시점에 딱 한 번, 다음 질문을 문장 그대로 짧게 묻는다: "이번 세션의 한국어 설명이 평소보다 이해하기 나았나요? 👍/👎" 답을 받으면 `python3 %s --agent claude --protocol claude-blind-v2 --verdict up` 또는 `--verdict down` 으로 기록하고, 사용자가 작업 내용을 오해했던 일이 있었다면 `--misread`를 붙인다. 답하지 않으면 다시 묻지 않는다. 이 세션에 특정 output style이 적용되었는지 여부는 사용자에게 언급하지도, 추측해서 말하지도 않는다.\n' "$fb"
    fi
  } > "$tmp"
  NK_AB_ARM="$arm" command claude --append-system-prompt-file "$tmp" "$@"
  local rc=$?
  rm -f "$tmp"
  return $rc
}
