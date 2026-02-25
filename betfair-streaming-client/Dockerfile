# NetBet Betfair Streaming Client - Java Spring Boot
# Multi-stage: build with Maven, run with JRE Alpine

# Stage 1: Build
FROM maven:3.9-eclipse-temurin-21-alpine AS build
WORKDIR /build

COPY pom.xml .
RUN mvn dependency:go-offline -B -q

COPY src ./src
RUN mvn clean package -B -DskipTests -q

# Stage 2: Run
FROM eclipse-temurin:21-jre-alpine
WORKDIR /app

COPY --from=build /build/target/betfair-streaming-client-*.jar app.jar

# Logs directory for CSV output (volume mounted at runtime)
RUN mkdir -p /app/logs

ENTRYPOINT ["java", "-jar", "app.jar"]
