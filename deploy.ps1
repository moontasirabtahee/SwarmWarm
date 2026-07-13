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
Write-Host "[1/3] Uploading updated application assets to VPS..." -ForegroundColor Yellow
scp -r app scripts requirements.txt .env $dest

# 2. Terminate legacy instances
Write-Host "[2/3] Cleaning up active execution processes on VPS..." -ForegroundColor Yellow
ssh root@$vpsIp "pkill -9 -f 'uvicorn|celery|python'"

# 3. Launch updated server and worker nodes
Write-Host "[3/3] Launching FastAPI gateway and Celery cluster..." -ForegroundColor Yellow
ssh root@$vpsIp "cd /root/SwarmWarm && source venv/bin/activate && nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > uvicorn.log 2>&1 &"
ssh root@$vpsIp "cd /root/SwarmWarm && source venv/bin/activate && PYTHONPATH=. nohup celery -A app.core.celery_app worker --loglevel=info > celery.log 2>&1 &"

Write-Host "`n[SUCCESS] Deployment complete! Dashboard running at http://srv1764813.hstgr.cloud/" -ForegroundColor Green
Write-Host "To inspect live logs, SSH into VPS and run: tail -f /root/SwarmWarm/uvicorn.log" -ForegroundColor Gray
