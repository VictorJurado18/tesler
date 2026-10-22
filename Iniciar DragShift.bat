@echo off
rem Inicia o DragShift sem janela de terminal (usa o ambiente conda "dragshift").
cd /d "%~dp0"
set PYW=%USERPROFILE%\miniconda3\envs\dragshift\pythonw.exe
if not exist "%PYW%" (
  echo Ambiente conda "dragshift" nao encontrado: %PYW%
  echo Rode: conda create -n dragshift python=3.12 -y ^&^& conda activate dragshift ^&^& pip install -r requirements.txt
  pause
  exit /b 1
)
start "" "%PYW%" -m dragshift
