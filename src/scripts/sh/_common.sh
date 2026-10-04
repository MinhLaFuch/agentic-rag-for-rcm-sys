# Dùng chung cho mọi script trong scripts/sh/ (được `source`, không chạy trực tiếp).
# Việc của file này: cd về gốc project, đặt PYTHONPATH, và đọc config từ configs/*.yaml.
# Mọi tham số (domain, đường dẫn, ngưỡng, model...) nằm trong configs/ — không sửa trong .sh.
#
# Biến môi trường (tuỳ chọn):
#   PYTHON   interpreter, vd PYTHON=.venv/Scripts/python
#   DOMAINS  ghi đè danh sách domain trong data.yaml, vd DOMAINS="Video_Games Toys_and_Games"
#   TAG      ghi đè data.yaml → run_tag, vd TAG=vg_toys (để không ghi đè bản chạy đủ)
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
export PYTHONPATH=".${PYTHONPATH:+:$PYTHONPATH}"
PYTHON="${PYTHON:-python}"

# cfg data.paths.raw_dir  ->  in một giá trị trong configs/ (list thì mỗi phần tử một dòng)
cfg() { "$PYTHON" -m package.config "$1" | tr -d '\r'; }

# Điền DOMAIN_LIST từ $DOMAINS hoặc data.yaml.
load_domains() {
  if [[ -n "${DOMAINS:-}" ]]; then
    read -r -a DOMAIN_LIST <<< "$DOMAINS"
  else
    mapfile -t DOMAIN_LIST < <(cfg data.domains)
  fi
  [[ ${#DOMAIN_LIST[@]} -gt 0 ]] || { echo "No domains found (configs/data.yaml → domains)"; exit 1; }
}

# Điền TAG từ $TAG hoặc data.yaml → run_tag.
resolve_tag() { TAG="${TAG:-$(cfg data.run_tag)}"; }

# Tách --force khỏi các tham số còn lại: FORCE=true|false, FORCE_ARGS=(--force), PASS_ARGS=(...)
FORCE=false; FORCE_ARGS=(); PASS_ARGS=()
parse_flags() {
  local a
  for a in "$@"; do
    if [[ "$a" == "--force" ]]; then FORCE=true; FORCE_ARGS=(--force); else PASS_ARGS+=("$a"); fi
  done
}
