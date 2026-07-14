# ==============================================================================
# SWARMWARM AUTOMATED VPS DEPLOYER & RUNNER (POWERSHELL)
# ==============================================================================

$vpsIp = "187.124.113.202"
$dest = "root@$vpsIp`:/root/SwarmWarm"

Clear-Host
Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "          SWARMWARM CLOUD VPS DEPLOYER" -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan

# 1. Sync updated files to VPS
Write-Host "[1/2] Uploading updated application assets to VPS..." -ForegroundColor Yellow
scp -r app scripts requirements.txt .env $dest

# 2. Remote execution sequence (cleanup, launch, and log tailing in one SSH session to minimize password prompts)
Write-Host "[2/2] Launching services and streaming logs on VPS..." -ForegroundColor Yellow
$remoteCmd = "pkill -9 -f 'uvicorn|celery'; cd /root/SwarmWarm && source venv/bin/activate && nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > uvicorn.log 2>&1 & sleep 2; cd /root/SwarmWarm && source venv/bin/activate && PYTHONPATH=. nohup celery -A app.core.celery_app worker --loglevel=info > celery.log 2>&1 & sleep 1; cd /root/SwarmWarm && source venv/bin/activate && PYTHONPATH=. nohup celery -A app.core.celery_app beat --loglevel=info > celerybeat.log 2>&1 & sleep 1; tail -f /root/SwarmWarm/uvicorn.log /root/SwarmWarm/celery.log /root/SwarmWarm/celerybeat.log"

ssh -t root@$vpsIp $remoteCmd
