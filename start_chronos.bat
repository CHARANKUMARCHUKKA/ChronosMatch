@echo off
title ChronosMatch Launcher
color 0b

echo ===================================================================
echo             CHRONOSMATCH // ONE-CLICK SYSTEM LAUNCHER
echo ===================================================================
echo.
echo [1/3] Verifying Cython C-Extension build...
python setup.py build_ext --inplace > nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [WARN] Cython build failed or already compiled. Proceeding...
) else (
    echo [OK] Matching engine compiled successfully.
)

echo.
echo [2/3] Spawning ChronosMatch Matching Engine & WebSocket Feed...
start "ChronosMatch Engine & Live Feed" cmd /k "title ChronosMatch Backend && color 0a && python main.py"

echo.
echo [3/3] Launching Institutional Quant Web Dashboard...
start "ChronosMatch Web Dashboard" cmd /k "title ChronosMatch Streamlit && color 09 && python -m streamlit run web_dashboard.py"

timeout /t 3 /nobreak > nul
echo.
echo Opening browser to http://localhost:8501 ...
start http://localhost:8501

echo.
echo ===================================================================
echo  All systems active! Press any key in this window to close launcher.
echo ===================================================================
pause > nul

:: Chronos Launcher
:: Build Validation
:: Process Spawning
