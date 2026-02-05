@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "MAVEN_PROJECTBASEDIR=%SCRIPT_DIR%"
set "WRAPPER_JAR=%MAVEN_PROJECTBASEDIR%.mvn\wrapper\maven-wrapper.jar"
set "WRAPPER_PROPS=%MAVEN_PROJECTBASEDIR%.mvn\wrapper\maven-wrapper.properties"

if not exist "%WRAPPER_JAR%" (
  if exist "%WRAPPER_PROPS%" (
    for /f "usebackq tokens=2 delims==" %%a in (`findstr /b "wrapperUrl=" "%WRAPPER_PROPS%"`) do set WRAPPER_URL=%%a
    if defined WRAPPER_URL (
      echo Downloading Maven wrapper...
      powershell -NoProfile -Command "Invoke-WebRequest -Uri '%WRAPPER_URL%' -OutFile '%WRAPPER_JAR%' -UseBasicParsing"
    )
  )
  if not exist "%WRAPPER_JAR%" (
    echo Maven wrapper jar not found. Run: mvn wrapper:wrapper
    exit /b 1
  )
)

java -jar "%WRAPPER_JAR%" %*
endlocal
