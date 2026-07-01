@echo off
cd /d "C:\Users\HRS0044.s03716\Documents\puppy_workspace\opd-pwa"
start "" /B uv run uvicorn main:app --host 0.0.0.0 --port 8000
