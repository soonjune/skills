# natural-korean-understanding A/B 래퍼. ~/.zshrc에서 source해서 쓴다.
#
# 인터랙티브 `claude` 세션에 한해 50% 확률로 output style 본문을
# --append-system-prompt-file로 주입한다. styled arm에는 세션 마무리에 👍/👎
# 피드백을 한 번 묻는 메모를 함께 주입한다.
#
# 인터랙티브가 claude의 기본 모드이므로 기본값을 "개입"으로 두고, 아래 신호가
# 있을 때만 비개입으로 통과시킨다. 반대로(안전한 인자만 허용) 짜면 --model이나
# --dangerously-skip-permissions 같은 평범한 세션 플래그까지 실험에서 빠진다.
#   - NK_AB=off, 스타일 파일 없음, tty 아님
#   - 첫 인자가 서브커맨드 (plugin, mcp, update, ...)
#   - -p/--print, --version, --help 같은 비대화 실행
#   - 사용자가 직접 --append-system-prompt[-file]을 넘긴 경우 (충돌 회피)
#
# 세션 arm은 NK_AB_ARM으로 자식 프로세스에만 전달되고 feedback.py가 이를
# 읽는다. 셸에 export하면 같은 터미널에서 이어 실행한 비개입 명령까지 그
# 값을 물려받아 arm이 잘못 기록되므로, 명령 앞 할당으로만 넘긴다.
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
      -p|--print|-v|--version|-h|--help|--append-system-prompt|--append-system-prompt-file)
        command claude "$@"
        return $?
        ;;
    esac
  done

  local arm=plain
  (( RANDOM % 2 )) && arm=styled
  NK_AB_ARM="$arm" python3 "$fb" --log-exposure >/dev/null 2>&1

  if [[ "$arm" == "styled" ]]; then
    local tmp="${TMPDIR:-/tmp}/nk-ab-styled-$$.md"
    {
      # frontmatter와 출처 주석을 뗀 스타일 본문만 주입한다(evals의 sync_style.py와 동일 처치).
      awk 'f>=2{print} /^---[[:space:]]*$/{f++}' "$style" | sed '/^<!--/,/^-->/d'
      printf '\n## A/B 세션 메모 (위 한국어 지침의 일부가 아님)\n'
      printf '이 세션은 스타일 적용(styled) arm이다. 세션이 자연스럽게 마무리되는 시점에 딱 한 번, 이번 세션의 한국어 설명이 평소보다 이해하기 나았는지 👍/👎 로 짧게 묻는다. 답을 받으면 `python3 %s --verdict up` 또는 `--verdict down` 으로 기록하고, 사용자가 작업 내용을 오해했던 일이 있었다면 `--misread`를 붙인다. 답하지 않으면 다시 묻지 않는다.\n' "$fb"
    } > "$tmp"
    NK_AB_ARM="$arm" command claude --append-system-prompt-file "$tmp" "$@"
    local rc=$?
    rm -f "$tmp"
    return $rc
  fi

  NK_AB_ARM="$arm" command claude "$@"
}
