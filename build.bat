@echo off
rem Builds dist\Hangazonosito\Hangazonosito.exe (portable folder) and the installer.
rem Use a clean environment with the CPU build of PyTorch to keep the package small:
rem   python -m venv .buildenv
rem   .buildenv\Scripts\python -m pip install torch==2.5.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cpu
rem   .buildenv\Scripts\python -m pip install -r requirements.txt pyinstaller
cd /d "%~dp0"
set PY=.buildenv\Scripts\python.exe
if not exist %PY% set PY=python
%PY% -m unittest discover tests || exit /b 1
%PY% make_icon.py || exit /b 1
%PY% -m PyInstaller --noconfirm --clean --onedir --noconsole --name Hangazonosito --icon app.ico ^
  --version-file version_info.txt ^
  --add-data "pretrained_models\spkrec-ecapa-voxceleb;pretrained_models\spkrec-ecapa-voxceleb" ^
  --add-data "app.ico;." ^
  --collect-all speechbrain --collect-all hyperpyyaml --collect-submodules torchaudio ^
  --exclude-module matplotlib --exclude-module IPython --exclude-module pandas --exclude-module tensorboard ^
  main.py || exit /b 1

set ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
if exist "%ISCC%" ("%ISCC%" installer.iss) else echo Inno Setup not found - installer skipped.
