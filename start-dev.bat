@echo off
set "PATH=C:\Program Files\nodejs;%PATH%"
cd /d "%~dp0"

where node >nul 2>&1
if errorlevel 1 (
  echo Node.js를 찾을 수 없습니다. https://nodejs.org 에서 설치 후 다시 실행하세요.
  pause
  exit /b 1
)

if not exist node_modules (
  echo 의존성 설치 중...
  call npm install
  if errorlevel 1 exit /b 1
)

echo.
echo 개발 서버 시작: http://localhost:5173
echo 종료하려면 Ctrl+C 를 누르세요.
echo.
call npm run dev
