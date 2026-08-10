param(
    [string]$RemoteHost = "82.156.50.58",
    [string]$RemoteUser = "root",
    [int]$SshPort = 22
)

$ErrorActionPreference = "Stop"

function Invoke-NativeChecked {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [string[]]$Arguments = @()
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$FilePath failed with exit code $LASTEXITCODE"
    }
}

$Target = "${RemoteUser}@${RemoteHost}"
$RemoteScriptPath = "/tmp/senzhiyan-probe-release-paths.sh"
$LocalScriptPath = Join-Path $env:TEMP "senzhiyan-probe-release-paths.sh"
$RemoteScript = @'
set +e
echo "== Identity =="
whoami
pwd
hostname

echo ""
echo "== Listening ports 5001/5002 =="
if command -v ss >/dev/null 2>&1; then
  ss -ltnp 2>/dev/null | grep -E ':(5001|5002)\b' || true
elif command -v netstat >/dev/null 2>&1; then
  netstat -ltnp 2>/dev/null | grep -E ':(5001|5002)\b' || true
else
  echo "No ss/netstat available"
fi

echo ""
echo "== Process hints =="
ps -ef | grep -E 'uvicorn|vite|node|python|gunicorn|nginx|5001|5002' | grep -v grep || true

echo ""
echo "== Candidate project roots =="
for root in /www /www/wwwroot /var/www /opt /srv /root /home; do
  if [ -d "$root" ]; then
    find "$root" -maxdepth 4 \( -name "backend" -o -name "reference_species" -o -name "species_catalog_service.py" -o -name "package.json" \) 2>/dev/null | head -80
  fi
done

echo ""
echo "== Candidate frontend directories =="
for root in /www /www/wwwroot /var/www /opt /srv /root /home; do
  if [ -d "$root" ]; then
    find "$root" -maxdepth 5 -type f -name "index.html" 2>/dev/null | while read file; do
      if grep -q "assets/index-" "$file" 2>/dev/null; then
        dir=$(dirname "$file")
        echo "$dir"
        ls -la "$dir" 2>/dev/null | head -20
      fi
    done
  fi
done

echo ""
echo "== Service manager hints =="
if command -v systemctl >/dev/null 2>&1; then
  systemctl list-units --type=service --all 2>/dev/null | grep -Ei 'wildlife|senzhi|uvicorn|frontend|backend|5001|5002|nginx' || true
fi

echo ""
echo "== Nginx hints =="
if [ -d /etc/nginx ]; then
  grep -R "5001\|5002\|root \|proxy_pass" /etc/nginx 2>/dev/null | head -120 || true
fi
'@

Write-Host "Probing remote release paths on $Target..."
Set-Content -Path $LocalScriptPath -Value $RemoteScript -Encoding UTF8
try {
    Invoke-NativeChecked -FilePath "scp" -Arguments @("-P", "$SshPort", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", $LocalScriptPath, "${Target}:${RemoteScriptPath}")
    Invoke-NativeChecked -FilePath "ssh" -Arguments @("-p", "$SshPort", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", $Target, "sh $RemoteScriptPath; rm -f $RemoteScriptPath")
} finally {
    Remove-Item $LocalScriptPath -Force -ErrorAction SilentlyContinue
}
