# Monta, em uma pasta à parte, só os arquivos que o Space do Hugging Face precisa.
# Uso (a partir de D:\Code\TCC2\defectlens_v3):  .\deploy\montar_space.ps1 -Destino D:\space_defectlens

param([Parameter(Mandatory = $true)][string]$Destino)

$Origem = Split-Path -Parent $PSScriptRoot

New-Item -ItemType Directory -Force $Destino | Out-Null
New-Item -ItemType Directory -Force "$Destino\frente3_web" | Out-Null

foreach ($item in "Dockerfile", "iniciar.sh", "requirements-deploy.txt", "config.py", ".dockerignore") {
    Copy-Item "$Origem\$item" "$Destino\$item" -Force
}

foreach ($pasta in "extrator", "frente2_predicao", "modelos") {
    robocopy "$Origem\$pasta" "$Destino\$pasta" /MIR /XD __pycache__ /NFL /NDL /NJH /NJS | Out-Null
}

robocopy "$Origem\frente3_web\backend" "$Destino\frente3_web\backend" /MIR /XD __pycache__ /XF db.sqlite3 chave_secreta.txt /NFL /NDL /NJH /NJS | Out-Null
robocopy "$Origem\frente3_web\web" "$Destino\frente3_web\web" /MIR /XD node_modules .next /XF tsconfig.tsbuildinfo /NFL /NDL /NJH /NJS | Out-Null

Copy-Item "$Origem\deploy\README_SPACE.md" "$Destino\README.md" -Force

Write-Host "Pasta do Space montada em $Destino"
