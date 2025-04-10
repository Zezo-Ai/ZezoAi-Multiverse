@echo off
setlocal EnableDelayedExpansion

REM Read first argument (e.g., enable_pause)
set "ENABLE_PAUSE=%1"
set "CMAKE_TOOL_CHAIN=%1"

REM Check if it matches "enable_pause"
if "!ENABLE_PAUSE!"=="enable_pause" (
    echo Pause is enabled
    set "SHOULD_PAUSE=1"
    set "CMAKE_TOOL_CHAIN=%2"
) else (
    echo Pause not enabled
    set "SHOULD_PAUSE=0"
)

set "MULTIVERSE_DIR=%~dp0multiverse"
set "CONFIG=Release"
set "MSYS2_BIN_DIR=%MULTIVERSE_DIR%\external\msys2\mingw64\bin"
set "CMAKE_BUILD_DIR=%MULTIVERSE_DIR%\build\CMake"
set "CMAKE_EXECUTABLE=%CMAKE_BUILD_DIR%\bin\cmake.exe"
if not exist "%CMAKE_EXECUTABLE%" (
    for /f "delims=" %%i in ('where cmake') do (
        set "CMAKE_EXECUTABLE=%%i"
        goto :found
    )

    :found
    if not exist "%CMAKE_EXECUTABLE%" (
        echo "CMake executable not found"
        exit /b 1
    )
)
set "PYTHON_EXECUTABLE=%USERPROFILE%\Envs\multiverse\Scripts\python.exe"
if not exist "%PYTHON_EXECUTABLE%" (
    echo "Python executable not found: %PYTHON_EXECUTABLE%"
    exit /b 1
)

if exist "%MULTIVERSE_DIR%\build\CMakeCache.txt" del /F "%MULTIVERSE_DIR%\build\CMakeCache.txt"

set "BUILD_WITH_VCPKG=1"
set "BUILD_WITH_MSYS2=1"

pushd "%MULTIVERSE_DIR%"
git submodule update --init --depth 1 resources
pushd  "%MULTIVERSE_DIR%\resources"
git submodule update --init --depth 1

powershell -Command "if (-not ($env:PATH.Split(';') -contains '%MULTIVERSE_DIR%\bin')) {[Environment]::SetEnvironmentVariable('PATH', [Environment]::GetEnvironmentVariable('Path', 'User') + ';%MULTIVERSE_DIR%\bin', [EnvironmentVariableTarget]::User)}"
powershell -Command "$pp = [Environment]::GetEnvironmentVariable('PYTHONPATH', 'User'); if (-not $pp) { $pp = '' }; if (-not ($pp.Split(';') -contains '%MULTIVERSE_DIR%\lib\dist-packages')) {[Environment]::SetEnvironmentVariable('PYTHONPATH', ($pp + ';%MULTIVERSE_DIR%\lib\dist-packages').Trim(';'), 'User')}"

echo Start building multiverse

if "!CMAKE_TOOL_CHAIN!"=="vcpkg" (
    echo Building with vcpkg
    echo Building with CMake executable: %CMAKE_EXECUTABLE%

    if not exist "%MULTIVERSE_DIR%\external\vcpkg" (
        git clone https://github.com/Microsoft/vcpkg.git "%MULTIVERSE_DIR%\external\vcpkg"
        cd "%MULTIVERSE_DIR%\external\vcpkg"
        bootstrap-vcpkg.bat
        vcpkg integrate install
    )

    powershell -NoProfile -Command "& '%CMAKE_EXECUTABLE%' -S %MULTIVERSE_DIR% -B %MULTIVERSE_DIR%\build -DCMAKE_TOOLCHAIN_FILE=%MULTIVERSE_DIR%\external\vcpkg\scripts\buildsystems\vcpkg.cmake -DCMAKE_INSTALL_PREFIX:PATH=%MULTIVERSE_DIR% -Wno-deprecated -DBUILD_SRC=ON -DBUILD_MODULES=OFF -DBUILD_TESTS=OFF -DPYTHON_EXECUTABLE=%PYTHON_EXECUTABLE%"
    powershell -NoProfile -Command "& '%CMAKE_EXECUTABLE%' --build %MULTIVERSE_DIR%\build --config %CONFIG% --target INSTALL"
    powershell -NoProfile -Command "& '%CMAKE_EXECUTABLE%' -S %MULTIVERSE_DIR% -B %MULTIVERSE_DIR%\build -DCMAKE_INSTALL_PREFIX:PATH=%MULTIVERSE_DIR% -Wno-deprecated -DBUILD_SRC=OFF -DBUILD_MODULES=ON -DBUILD_TESTS=OFF -DPYTHON_EXECUTABLE=%PYTHON_EXECUTABLE%"

    if "!SHOULD_PAUSE!"=="1" (
        pause
    )
) else if "!CMAKE_TOOL_CHAIN!"=="msys2" (
    echo Building with msys2
    echo Building with CMake executable: %MSYS2_BIN_DIR%\cmake.exe

    if exist "%MSYS2_BIN_DIR%\cmake.exe" if exist "%MSYS2_BIN_DIR%\ninja.exe" (
        set "PATH=%MSYS2_BIN_DIR%;%PATH%"
        powershell -NoProfile -Command "%MSYS2_BIN_DIR%\cmake.exe -S %MULTIVERSE_DIR% -B %MULTIVERSE_DIR%\build -G Ninja -DCMAKE_MAKE_PROGRAM=%MSYS2_BIN_DIR%\ninja.exe -D CMAKE_C_COMPILER=%MSYS2_BIN_DIR%\gcc.exe -D CMAKE_CXX_COMPILER=%MSYS2_BIN_DIR%\g++.exe -DCMAKE_INSTALL_PREFIX:PATH=%MULTIVERSE_DIR% -Wno-deprecated -Wno-dev -DBUILD_SRC=ON -DBUILD_MODULES=OFF -DBUILD_TESTS=OFF -DPYTHON_EXECUTABLE=%PYTHON_EXECUTABLE%"
        powershell -NoProfile -Command "%MSYS2_BIN_DIR%\cmake.exe --build %MULTIVERSE_DIR%\build --config %CONFIG%"
        powershell -NoProfile -Command "%MSYS2_BIN_DIR%\cmake.exe --install %MULTIVERSE_DIR%\build"
        
        copy /Y "%MSYS2_BIN_DIR%\libstdc++-6.dll" "%MULTIVERSE_DIR%\lib\dist-packages"
        copy /Y "%MSYS2_BIN_DIR%\libwinpthread-1.dll" "%MULTIVERSE_DIR%\lib\dist-packages"
        copy /Y "%MSYS2_BIN_DIR%\libzmq.dll" "%MULTIVERSE_DIR%\lib\dist-packages"
        copy /Y "%MSYS2_BIN_DIR%\libgcc_s_seh-1.dll" "%MULTIVERSE_DIR%\lib\dist-packages"
        copy /Y "%MSYS2_BIN_DIR%\libsodium-26.dll" "%MULTIVERSE_DIR%\lib\dist-packages"

        if "!SHOULD_PAUSE!"=="1" (
            pause
        )
    ) else (
        echo %MSYS2_BIN_DIR%\cmake.exe not found. Please run install.bat first.
        if "!SHOULD_PAUSE!"=="1" (
            pause
        )
    )
) else if "!CMAKE_TOOL_CHAIN!"=="" (
    echo Building src with vcpkg
    echo Building src with CMake executable: %CMAKE_EXECUTABLE%

    if exist "%MULTIVERSE_DIR%\external\vcpkg" (
        echo Remove existing vcpkg directory
        rmdir /S /Q "%MULTIVERSE_DIR%\external\vcpkg"
    )

    git clone https://github.com/Microsoft/vcpkg.git "%MULTIVERSE_DIR%\external\vcpkg"
    cd "%MULTIVERSE_DIR%\external\vcpkg"
    bootstrap-vcpkg.bat
    vcpkg integrate install

    powershell -NoProfile -Command "& '%CMAKE_EXECUTABLE%' -S %MULTIVERSE_DIR% -B %MULTIVERSE_DIR%\build -DCMAKE_TOOLCHAIN_FILE=%MULTIVERSE_DIR%\external\vcpkg\scripts\buildsystems\vcpkg.cmake -DCMAKE_INSTALL_PREFIX:PATH=%MULTIVERSE_DIR% -Wno-deprecated -DBUILD_SRC=ON -DBUILD_MODULES=OFF -DBUILD_TESTS=OFF -DPYTHON_EXECUTABLE=%PYTHON_EXECUTABLE%"
    powershell -NoProfile -Command "& '%CMAKE_EXECUTABLE%' --build %MULTIVERSE_DIR%\build --config %CONFIG% --target INSTALL"

    set "KEEP_ITEMS=blender;mujoco;pybind11;USD"

    for /d %%F in ("%MULTIVERSE_DIR%\build\*") do (
        set ITEM_NAME=%%~nF
        set "KEEP_ITEM=0"
        for %%K in (!KEEP_ITEMS!) do (
            if "!ITEM_NAME!"=="%%K" (
                set "KEEP_ITEM=1"
            )
        )
        if "!KEEP_ITEM!"=="0" (
            echo Removing directory: %%F
            rmdir /S /Q "%%F"
        )
    )
    for %%F in ("%MULTIVERSE_DIR%\build\*") do (
        if not exist "%%F\" (
            echo Removing file: %%F
            del /F "%%F"
        )
    )

    echo Building src with msys2
    echo Building src with CMake executable: %MSYS2_BIN_DIR%\cmake.exe

    if exist "%MSYS2_BIN_DIR%\cmake.exe" if exist "%MSYS2_BIN_DIR%\ninja.exe" (
        set "PATH=%MSYS2_BIN_DIR%;%PATH%"
        powershell -NoProfile -Command "%MSYS2_BIN_DIR%\cmake.exe -S %MULTIVERSE_DIR% -B %MULTIVERSE_DIR%\build -G Ninja -DCMAKE_MAKE_PROGRAM=%MSYS2_BIN_DIR%\ninja.exe -D CMAKE_C_COMPILER=%MSYS2_BIN_DIR%\gcc.exe -D CMAKE_CXX_COMPILER=%MSYS2_BIN_DIR%\g++.exe -DCMAKE_INSTALL_PREFIX:PATH=%MULTIVERSE_DIR% -Wno-deprecated -Wno-dev -DBUILD_SRC=ON -DBUILD_MODULES=OFF -DBUILD_TESTS=OFF -DPYTHON_EXECUTABLE=%PYTHON_EXECUTABLE%"
        powershell -NoProfile -Command "%MSYS2_BIN_DIR%\cmake.exe --build %MULTIVERSE_DIR%\build --config %CONFIG%"
        powershell -NoProfile -Command "%MSYS2_BIN_DIR%\cmake.exe --install %MULTIVERSE_DIR%\build"
        
        copy /Y "%MSYS2_BIN_DIR%\libstdc++-6.dll" "%MULTIVERSE_DIR%\lib\dist-packages"
        copy /Y "%MSYS2_BIN_DIR%\libwinpthread-1.dll" "%MULTIVERSE_DIR%\lib\dist-packages"
        copy /Y "%MSYS2_BIN_DIR%\libzmq.dll" "%MULTIVERSE_DIR%\lib\dist-packages"
        copy /Y "%MSYS2_BIN_DIR%\libgcc_s_seh-1.dll" "%MULTIVERSE_DIR%\lib\dist-packages"
        copy /Y "%MSYS2_BIN_DIR%\libsodium-26.dll" "%MULTIVERSE_DIR%\lib\dist-packages"

        if "!SHOULD_PAUSE!"=="1" (
            pause
        )
    ) else (
        echo %MSYS2_BIN_DIR%\cmake.exe not found. Please run install.bat first.
        if "!SHOULD_PAUSE!"=="1" (
            pause
        )
    )

    for /d %%F in ("%MULTIVERSE_DIR%\build\*") do (
        set ITEM_NAME=%%~nF
        set "KEEP_ITEM=0"
        for %%K in (!KEEP_ITEMS!) do (
            if "!ITEM_NAME!"=="%%K" (
                set "KEEP_ITEM=1"
            )
        )
        if "!KEEP_ITEM!"=="0" (
            echo Removing directory: %%F
            rmdir /S /Q "%%F"
        )
    )
    for %%F in ("%MULTIVERSE_DIR%\build\*") do (
        if not exist "%%F\" (
            echo Removing file: %%F
            del /F "%%F"
        )
    )

    echo Building modules with vcpkg
    echo Building modules with CMake executable: %CMAKE_EXECUTABLE%

    rmdir /S /Q "%MULTIVERSE_DIR%\external\vcpkg"
    git clone https://github.com/Microsoft/vcpkg.git "%MULTIVERSE_DIR%\external\vcpkg"
    cd "%MULTIVERSE_DIR%\external\vcpkg"
    bootstrap-vcpkg.bat
    vcpkg integrate install
    vcpkg install zeromq:x64-windows

    powershell -NoProfile -Command "& '%CMAKE_EXECUTABLE%' -S %MULTIVERSE_DIR% -B %MULTIVERSE_DIR%\build -DCMAKE_TOOLCHAIN_FILE=%MULTIVERSE_DIR%\external\vcpkg\scripts\buildsystems\vcpkg.cmake -DCMAKE_INSTALL_PREFIX:PATH=%MULTIVERSE_DIR% -Wno-deprecated -DBUILD_SRC=OFF -DBUILD_MODULES=ON -DBUILD_TESTS=OFF -DPYTHON_EXECUTABLE=%PYTHON_EXECUTABLE%"

    if "!SHOULD_PAUSE!"=="1" (
        pause
    )
) else (
    echo Unknown CMake toolchain: "!CMAKE_TOOL_CHAIN!"
    exit /b 1
)

echo Done