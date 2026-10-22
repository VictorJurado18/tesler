@echo off
rem Inicia o DragShift (ambiente conda "dragshift"). Instala componentes novos quando preciso.
cd /d "%~dp0"
set ENVDIR=%USERPROFILE%\miniconda3\envs\dragshift
if not exist "%ENVDIR%\pythonw.exe" (
  echo Ambiente conda "dragshift" nao encontrado em %ENVDIR%
  echo Rode: conda create -n dragshift python=3.12 -y ^&^& conda activate dragshift ^&^& pip install -r requirements.txt
  pause
  exit /b 1
)
"%ENVDIR%\python.exe" -m dragshift.deps
if errorlevel 1 (
  pause
  exit /b 1
)
start "" "%ENVDIR%\pythonw.exe" -m dragshift
