#!/bin/sh
# Maven Wrapper: use Maven from distributionUrl (download if needed). Requires Java.
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MAVEN_PROJECTBASEDIR="${MAVEN_BASEDIR:-$SCRIPT_DIR}"
WRAPPER_JAR="$MAVEN_PROJECTBASEDIR/.mvn/wrapper/maven-wrapper.jar"
WRAPPER_PROPS="$MAVEN_PROJECTBASEDIR/.mvn/wrapper/maven-wrapper.properties"

if [ ! -f "$WRAPPER_JAR" ]; then
  if [ -f "$WRAPPER_PROPS" ]; then
    wrapperUrl=$(grep '^wrapperUrl=' "$WRAPPER_PROPS" | cut -d'=' -f2-)
    if [ -n "$wrapperUrl" ]; then
      echo "Downloading Maven wrapper from $wrapperUrl"
      (cd "$MAVEN_PROJECTBASEDIR/.mvn/wrapper" && curl -sSL -o maven-wrapper.jar "$wrapperUrl" 2>/dev/null || wget -q -O maven-wrapper.jar "$wrapperUrl" 2>/dev/null) || true
    fi
  fi
  if [ ! -f "$WRAPPER_JAR" ]; then
    echo "Maven wrapper jar not found. Run: mvn wrapper:wrapper"
    exit 1
  fi
fi

exec java -jar "$WRAPPER_JAR" "$@"
