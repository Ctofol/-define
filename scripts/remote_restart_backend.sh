set -e

PROJECT_ROOT="${1:-/home/libingze/wildlife-demo}"
BACKEND_DIR="$PROJECT_ROOT/backend"
LOG_DIR="$PROJECT_ROOT/storage/logs"

echo "== code check =="
grep -n 'append_reviewed\|SUPPLEMENT_SKIP\|list_knowledge_open_set' "$BACKEND_DIR/app/services/reference_sample_service.py" || true

echo "== stop old backend =="
old_pid=""
if command -v ss >/dev/null 2>&1; then
  old_pid=$(ss -ltnp 2>/dev/null | sed -n 's/.*:5001 .*pid=\([0-9]*\).*/\1/p' | head -1)
elif command -v netstat >/dev/null 2>&1; then
  old_pid=$(netstat -ltnp 2>/dev/null | sed -n 's/.*:5001 .*\/.*/\1/p' | awk '{print $NF}' | head -1)
fi
echo "old_pid=${old_pid:-none}"
if [ -n "$old_pid" ]; then
  kill "$old_pid" || true
  sleep 2
fi

echo "== start backend =="
cd "$BACKEND_DIR"
mkdir -p "$LOG_DIR"
nohup .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 5001 > "$LOG_DIR/formal-backend.out.log" 2> "$LOG_DIR/formal-backend.err.log" &
new_pid=$!
echo "new_pid=$new_pid"
sleep 3

echo "== listen check =="
if command -v ss >/dev/null 2>&1; then
  ss -ltnp 2>/dev/null | grep ':5001' || true
elif command -v netstat >/dev/null 2>&1; then
  netstat -ltnp 2>/dev/null | grep ':5001' || true
fi

echo "== recent backend errors =="
tail -40 "$LOG_DIR/formal-backend.err.log" || true
