# natural-korean-understanding A/B 래퍼. ~/.zshrc에서 source해서 쓴다.
#
# 인터랙티브 `claude` 실행(인자 없음, 또는 -c/--continue만)에 한해 50% 확률로
# output style 본문을 --append-system-prompt-file로 주입한다. styled arm에는
# 세션 마무리에 👍/👎 피드백을 한 번 묻는 메모를 함께 주입한다.
# - NK_AB=off 로 전체를 끈다.
# - 서브커맨드·플래그가 있는 실행(claude -p, claude plugin ...)은 건드리지
#   않으므로 nightshift 같은 스크립트 경로에는 영향이 없다.
# - 세션 arm은 NK_AB_ARM으로 노출되고 feedback.py가 이를 읽는다.
claude() {
  local repo="/home/soonjun-park/skills"
  local style="$repo/output-styles/natural-korean-understanding.md"
  local fb="$repo/skills/natural-korean/scripts/feedback.py"

  if [[ "${NK_AB:-on}" == "off" || ! -f "$style" || ! -t 0 || ! -t 1 ]]; then
    command claude "$@"
    return $?
  fi
  local a
  for a in "$@"; do
    case "$a" in
      -c|--continue) ;;
      *) command claude "$@"; return $? ;;
    esac
  done

  local arm=plain
  (( RANDOM % 2 )) && arm=styled
  export NK_AB_ARM="$arm"
  python3 "$fb" --log-exposure >/dev/null 2>&1

  if [[ "$arm" == "styled" ]]; then
    local tmp="${TMPDIR:-/tmp}/nk-ab-styled-$$.md"
    {
      # frontmatter와 출처 주석을 뗀 스타일 본문만 주입한다(evals의 sync_style.py와 동일 처치).
      awk 'f>=2{print} /^---[[:space:]]*$/{f++}' "$style" | sed '/^<!--/,/^-->/d'
      printf '\n## A/B 세션 메모 (위 한국어 지침의 일부가 아님)\n'
      printf '이 세션은 스타일 적용(styled) arm이다. 세션이 자연스럽게 마무리되는 시점에 딱 한 번, 이번 세션의 한국어 설명이 평소보다 이해하기 나았는지 👍/👎 로 짧게 묻는다. 답을 받으면 `python3 %s --verdict up` 또는 `--verdict down` 으로 기록하고, 사용자가 작업 내용을 오해했던 일이 있었다면 `--misread`를 붙인다. 답하지 않으면 다시 묻지 않는다.\n' "$fb"
    } > "$tmp"
    command claude --append-system-prompt-file "$tmp" "$@"
    local rc=$?
    rm -f "$tmp"
    return $rc
  fi

  command claude "$@"
}
