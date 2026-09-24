@echo off
REM Canonical Step-Code Dispatcher (H1 Mandate 1.1)

REM 1. Prefer authentic production Step-Code binary if available in STEP_CODE_BIN
if defined STEP_CODE_BIN (
    if exist "%STEP_CODE_BIN%" (
        "%STEP_CODE_BIN%" %*
        exit /b %ERRORLEVEL%
    )
)

REM 2. Check for explicit test double flag or test environment
if "%SCLASS_TEST_DOUBLE%"=="1" (
    node "%~dp0\..\tools\step_code_rpc_test_double.js" %*
    exit /b %ERRORLEVEL%
)

for %%a in (%*) do (
    if "%%a"=="--test-double" (
        node "%~dp0\..\tools\step_code_rpc_test_double.js" %*
        exit /b %ERRORLEVEL%
    )
)

REM 3. In test fixtures/suites, if SCLASS_ENV is test, allow test double
if "%SCLASS_ENV%"=="test" (
    node "%~dp0\..\tools\step_code_rpc_test_double.js" %*
    exit /b %ERRORLEVEL%
)

echo ERROR: Real Step-Code runtime binary 'step' was not found in PATH or STEP_CODE_BIN. 1>&2
echo Notice: tools\step_code_rpc_test_double.js is an unauthenticated simulation test double. 1>&2
echo To invoke the test double explicitly for mock testing, pass --test-double or set SCLASS_TEST_DOUBLE=1. 1>&2
exit /b 1
