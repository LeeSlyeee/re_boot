@echo off
title KWS_Local_Agent
echo ============================================
echo   KWS Local Agent (Python Standalone)
echo ============================================
call C:\ProgramData\anaconda3\condabin\conda.bat activate kws
cd /d %~dp0
python kws_agent_standalone.py
pause
