@echo off
pushd "%~dp0kapt_monitor"
python main.py --open
popd
pause
