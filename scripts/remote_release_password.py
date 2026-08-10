from __future__ import annotations

import argparse
import os
import posixpath
import secrets
import sys
from pathlib import Path

import paramiko


PROBE_SCRIPT = r'''
set +e
echo "== Identity =="; whoami; pwd; hostname
echo ""
echo "== Ports =="; (ss -ltnp 2>/dev/null || netstat -ltnp 2>/dev/null) | grep -E ':(5001|5002)\b' || true
echo ""
echo "== Processes =="; ps -ef | grep -E 'uvicorn|vite|node|python|gunicorn|nginx|5001|5002' | grep -v grep || true
echo ""
echo "== Project candidates =="
for root in /www /www/wwwroot /var/www /opt /srv /home /root; do
  [ -d "$root" ] && find "$root" -maxdepth 5 \( -name backend -o -name reference_species -o -name species_catalog_service.py -o -name package.json \) 2>/dev/null | head -120
done
echo ""
echo "== Frontend candidates =="
for root in /www /www/wwwroot /var/www /opt /srv /home /root; do
  [ -d "$root" ] && find "$root" -maxdepth 6 -type f -name index.html 2>/dev/null | while read f; do
    if grep -q 'assets/index-' "$f" 2>/dev/null; then
      d=$(dirname "$f")
      echo "$d"
      ls -la "$d" | head -20
    fi
  done
done
echo ""
echo "== Nginx =="
[ -d /etc/nginx ] && grep -R "5001\|5002\|root \|proxy_pass" /etc/nginx 2>/dev/null | head -160 || true
echo ""
echo "== Systemd =="
command -v systemctl >/dev/null 2>&1 && systemctl list-units --type=service --all 2>/dev/null | grep -Ei 'wildlife|senzhi|uvicorn|frontend|backend|5001|5002|nginx' || true
'''


def connect(args: argparse.Namespace) -> paramiko.SSHClient:
    password = os.environ.get("SENZHIYAN_REMOTE_PASSWORD")
    if not password:
        raise SystemExit("SENZHIYAN_REMOTE_PASSWORD is not set")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        args.host,
        port=args.port,
        username=args.user,
        password=password,
        timeout=15,
        banner_timeout=15,
        auth_timeout=15,
    )
    return client


def run(client: paramiko.SSHClient, command: str, timeout: int = 120) -> str:
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    if out:
        print(out, end="" if out.endswith("\n") else "\n")
    if err:
        print(err, file=sys.stderr, end="" if err.endswith("\n") else "\n")
    if code != 0:
        raise SystemExit(f"remote command failed with exit code {code}: {command}")
    return out


def put(client: paramiko.SSHClient, local_path: Path, remote_path: str) -> None:
    if not local_path.is_file():
        raise SystemExit(f"local file not found: {local_path}")
    with client.open_sftp() as sftp:
        sftp.put(str(local_path), remote_path)


def configure_platform(client: paramiko.SSHClient, project_path: str) -> None:
    env_path = posixpath.join(project_path, "backend", ".env")
    initial_admin_password = secrets.token_urlsafe(16)
    updates = {
        "WILDLIFE_DATABASE_URL": "sqlite:///runtime/platform.db",
        "WILDLIFE_JWT_SECRET": secrets.token_hex(32),
        "WILDLIFE_BOOTSTRAP_ADMIN_USERNAME": "admin",
        "WILDLIFE_BOOTSTRAP_ADMIN_PASSWORD": initial_admin_password,
        "WILDLIFE_TASK_BACKEND": "local",
        "WILDLIFE_OBJECT_STORAGE_ENABLED": "false",
        "WILDLIFE_COOKIE_SECURE": "false",
        "WILDLIFE_PLANT_RECOGNITION_ENABLED": "false",
    }
    with client.open_sftp() as sftp:
        try:
            with sftp.open(env_path, "r") as source:
                current = source.read().decode("utf-8")
        except OSError:
            current = ""
        retained = [line for line in current.splitlines() if line.split("=", 1)[0] not in updates]
        content = "\n".join([*retained, *[f"{key}={value}" for key, value in updates.items()]]) + "\n"
        with sftp.open(env_path, "w") as target:
            target.write(content)
        sftp.chmod(env_path, 0o600)
    backend_path = posixpath.join(project_path, "backend")
    command = f"cd {sh_quote(backend_path)} && .venv/bin/python -m pip install SQLAlchemy==2.0.43 python-jose[cryptography]==3.5.0"
    run(client, "bash -lc " + sh_quote(command), timeout=300)
    print("Platform runtime configured (JWT secret redacted).")
    print(f"INITIAL_ADMIN_USERNAME=admin")
    print(f"INITIAL_ADMIN_PASSWORD={initial_admin_password}")


def sh_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def deploy_frontend(client: paramiko.SSHClient, package: Path, remote_path: str) -> None:
    remote_package = "/tmp/senzhiyan-frontend-release.tar.gz"
    remote_extract = "/tmp/senzhiyan-frontend-release"
    put(client, package, remote_package)
    script = f"""
set -e
remote_path={sh_quote(remote_path)}
rm -rf {sh_quote(remote_extract)}
mkdir -p {sh_quote(remote_extract)}
tar -xzf {sh_quote(remote_package)} -C {sh_quote(remote_extract)}
mkdir -p "$remote_path"
backup="${{remote_path}}_backup_$(date +%Y%m%d_%H%M%S)"
if [ -n "$(ls -A "$remote_path" 2>/dev/null)" ]; then
  cp -a "$remote_path" "$backup"
fi
find "$remote_path" -mindepth 1 -maxdepth 1 -exec rm -rf {{}} +
cp -a {sh_quote(remote_extract)}/. "$remote_path"/
rm -rf {sh_quote(remote_extract)} {sh_quote(remote_package)}
echo "Frontend deployed to $remote_path"
echo "Backup: $backup"
"""
    run(client, "bash -lc " + sh_quote(script), timeout=180)


def deploy_backend_data(client: paramiko.SSHClient, package: Path, project_path: str) -> None:
    remote_package = "/tmp/senzhiyan-backend-data-release.tar.gz"
    remote_extract = "/tmp/senzhiyan-backend-data-release"
    put(client, package, remote_package)
    script = f"""
set -e
project_path={sh_quote(project_path)}
if [ ! -d "$project_path" ]; then
  echo "Remote project path does not exist: $project_path" >&2
  exit 1
fi
rm -rf {sh_quote(remote_extract)}
mkdir -p {sh_quote(remote_extract)}
tar -xzf {sh_quote(remote_package)} -C {sh_quote(remote_extract)}
backup="${{project_path}}/data_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$backup"
if [ -d "$project_path/reference_species/_supplement_candidates" ]; then
  mkdir -p "$backup/reference_species"
  cp -a "$project_path/reference_species/_supplement_candidates" "$backup/reference_species/"
fi
if [ -d "$project_path/reference_species/pdf_guangxi_species_images_v2" ]; then
  mkdir -p "$backup/reference_species"
  cp -a "$project_path/reference_species/pdf_guangxi_species_images_v2" "$backup/reference_species/"
fi
for species in "豹猫" "大灵猫" "野猪" "黑熊" "梅花鹿" "水鹿" "中华斑羚"; do
  if [ -d "$project_path/reference_species/$species" ]; then
    mkdir -p "$backup/reference_species"
    cp -a "$project_path/reference_species/$species" "$backup/reference_species/"
  fi
done
if [ -f "$project_path/storage/training/species_manifest_v20_round5_cleaned.csv" ]; then
  mkdir -p "$backup/storage/training"
  cp -a "$project_path/storage/training/species_manifest_v20_round5_cleaned.csv" "$backup/storage/training/"
fi
if [ -f "$project_path/docs/viverrid_source_verification/knowledge_open_set_candidates.csv" ]; then
  mkdir -p "$backup/docs/viverrid_source_verification"
  cp -a "$project_path/docs/viverrid_source_verification/knowledge_open_set_candidates.csv" "$backup/docs/viverrid_source_verification/"
fi
mkdir -p "$project_path/reference_species" "$project_path/docs/viverrid_source_verification" "$project_path/storage/training"
rm -rf "$project_path/reference_species/_supplement_candidates"
cp -a {sh_quote(remote_extract)}/reference_species/_supplement_candidates "$project_path/reference_species/"
rm -rf "$project_path/reference_species/pdf_guangxi_species_images_v2"
cp -a {sh_quote(remote_extract)}/reference_species/pdf_guangxi_species_images_v2 "$project_path/reference_species/"
for species in "豹猫" "大灵猫" "野猪" "黑熊" "梅花鹿" "水鹿" "中华斑羚"; do
  rm -rf "$project_path/reference_species/$species"
  cp -a {sh_quote(remote_extract)}/reference_species/$species "$project_path/reference_species/"
done
cp -a {sh_quote(remote_extract)}/storage/training/species_manifest_v20_round5_cleaned.csv "$project_path/storage/training/"
cp -a {sh_quote(remote_extract)}/docs/viverrid_source_verification/knowledge_open_set_candidates.csv "$project_path/docs/viverrid_source_verification/"
rm -rf {sh_quote(remote_extract)} {sh_quote(remote_package)}
echo "Backend data deployed to $project_path"
echo "Backup: $backup"
"""
    run(client, "bash -lc " + sh_quote(script), timeout=300)


def deploy_backend_code(client: paramiko.SSHClient, package: Path, project_path: str) -> None:
    remote_package = "/tmp/senzhiyan-backend-code-release.tar.gz"
    remote_extract = "/tmp/senzhiyan-backend-code-release"
    put(client, package, remote_package)
    script = f"""
set -e
project_path={sh_quote(project_path)}
backend_path="$project_path/backend"
if [ ! -d "$backend_path" ]; then
  echo "Remote backend path does not exist: $backend_path" >&2
  exit 1
fi
rm -rf {sh_quote(remote_extract)}
mkdir -p {sh_quote(remote_extract)}
tar -xzf {sh_quote(remote_package)} -C {sh_quote(remote_extract)}
backup="${{project_path}}/code_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$backup/backend"
cp -a "$backend_path/app" "$backup/backend/"
cp -a "$backend_path/requirements.txt" "$backup/backend/" 2>/dev/null || true
cp -a "$backend_path/requirements-models.txt" "$backup/backend/" 2>/dev/null || true
rm -rf "$backend_path/app"
cp -a {sh_quote(remote_extract)}/backend/app "$backend_path/"
cp -a {sh_quote(remote_extract)}/backend/requirements.txt "$backend_path/" 2>/dev/null || true
cp -a {sh_quote(remote_extract)}/backend/requirements-models.txt "$backend_path/" 2>/dev/null || true
rm -rf {sh_quote(remote_extract)} {sh_quote(remote_package)}
echo "Backend code deployed to $backend_path"
echo "Backup: $backup"
"""
    run(client, "bash -lc " + sh_quote(script), timeout=300)


def restart_backend(client: paramiko.SSHClient, project_path: str) -> None:
    script = f"""
set -e
project_path={sh_quote(project_path)}
backend_path="$project_path/backend"
log_dir="$project_path/storage/logs"
old_pid=""
if command -v ss >/dev/null 2>&1; then
  old_pid=$(ss -ltnp 2>/dev/null | sed -n 's/.*:5001 .*pid=\\([0-9]*\\).*/\\1/p' | head -1)
elif command -v netstat >/dev/null 2>&1; then
  old_pid=$(netstat -ltnp 2>/dev/null | sed -n 's/.*:5001 .*\\/.*\\/\\([0-9]*\\).*/\\1/p' | head -1)
fi
echo "old_pid=${{old_pid:-none}}"
if [ -n "$old_pid" ]; then
  kill "$old_pid" || true
  sleep 2
fi
cd "$backend_path"
mkdir -p "$log_dir"
nohup .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 5001 > "$log_dir/formal-backend.out.log" 2> "$log_dir/formal-backend.err.log" &
echo "new_pid=$!"
sleep 4
tail -40 "$log_dir/formal-backend.err.log" || true
"""
    run(client, "bash -lc " + sh_quote(script), timeout=120)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["probe", "exec", "put-file", "deploy-frontend", "deploy-backend-data", "deploy-backend-code", "configure-platform", "restart-backend", "deploy-all"])
    parser.add_argument("--host", default="82.156.50.58")
    parser.add_argument("--user", default="libingze")
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument("--frontend-package", default="frontend-dist-formal-latest.tar.gz")
    parser.add_argument("--backend-data-package", default="backend-data-formal-latest.tar.gz")
    parser.add_argument("--backend-code-package", default="backend-code-formal-latest.tar.gz")
    parser.add_argument("--remote-frontend-path", default="")
    parser.add_argument("--remote-project-path", default="")
    parser.add_argument("--remote-command", default="")
    parser.add_argument("--local-path", default="")
    parser.add_argument("--remote-path", default="")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    frontend_package = (root / args.frontend_package).resolve()
    backend_data_package = (root / args.backend_data_package).resolve()
    backend_code_package = (root / args.backend_code_package).resolve()

    client = connect(args)
    try:
        if args.command == "probe":
            run(client, "bash -lc " + sh_quote(PROBE_SCRIPT), timeout=90)
        elif args.command == "exec":
            if not args.remote_command:
                raise SystemExit("--remote-command is required")
            run(client, "bash -lc " + sh_quote(args.remote_command), timeout=180)
        elif args.command == "put-file":
            if not args.local_path or not args.remote_path:
                raise SystemExit("--local-path and --remote-path are required")
            put(client, (root / args.local_path).resolve(), args.remote_path)
            print(f"Uploaded {args.local_path} -> {args.remote_path}")
        elif args.command == "deploy-frontend":
            if not args.remote_frontend_path:
                raise SystemExit("--remote-frontend-path is required")
            deploy_frontend(client, frontend_package, args.remote_frontend_path)
        elif args.command == "deploy-backend-data":
            if not args.remote_project_path:
                raise SystemExit("--remote-project-path is required")
            deploy_backend_data(client, backend_data_package, args.remote_project_path)
        elif args.command == "deploy-backend-code":
            if not args.remote_project_path:
                raise SystemExit("--remote-project-path is required")
            deploy_backend_code(client, backend_code_package, args.remote_project_path)
        elif args.command == "configure-platform":
            if not args.remote_project_path:
                raise SystemExit("--remote-project-path is required")
            configure_platform(client, args.remote_project_path)
        elif args.command == "restart-backend":
            if not args.remote_project_path:
                raise SystemExit("--remote-project-path is required")
            restart_backend(client, args.remote_project_path)
        elif args.command == "deploy-all":
            if not args.remote_frontend_path or not args.remote_project_path:
                raise SystemExit("--remote-frontend-path and --remote-project-path are required")
            deploy_frontend(client, frontend_package, args.remote_frontend_path)
            deploy_backend_code(client, backend_code_package, args.remote_project_path)
            deploy_backend_data(client, backend_data_package, args.remote_project_path)
            restart_backend(client, args.remote_project_path)
    finally:
        client.close()


if __name__ == "__main__":
    main()
