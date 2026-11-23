# BasilCare WildFly image: iam.war + api.war + both PWAs + hosting/HTTPS configuration.
# Build context is the repository root:
#   docker build -f deploy/wildfly/Dockerfile -t basilcare-wildfly .
# CI publishes it for linux/amd64 and linux/arm64 (Apple Silicon) as
# ghcr.io/<owner>/basilcare-wildfly, so nobody needs Java or Maven to run the stack.

# The WARs are platform-independent: compile once, natively, on the build machine.
FROM --platform=$BUILDPLATFORM maven:3.9-eclipse-temurin-25 AS build
WORKDIR /src
COPY middleware/iam/pom.xml middleware/iam/
COPY middleware/api/pom.xml middleware/api/
COPY middleware/iam/src middleware/iam/src
COPY middleware/api/src middleware/api/src
# Tests run in CI before an image is published (release.yml); skipped here to keep builds fast.
RUN --mount=type=cache,target=/root/.m2 \
    mvn -B -q -f middleware/iam/pom.xml package -DskipTests \
 && mvn -B -q -f middleware/api/pom.xml package -DskipTests \
 && mkdir /empty

FROM quay.io/wildfly/wildfly:42.0.0.Final-jdk25
ARG WILDFLY=/opt/jboss/wildfly
COPY --chown=jboss:root --from=build /src/middleware/iam/target/iam.war /src/middleware/api/target/api.war $WILDFLY/standalone/deployments/
COPY --chown=jboss:root deploy/wildfly/ $WILDFLY/hosting/
COPY --chown=jboss:root frontends/frontoffice/ $WILDFLY/frontends/farmer/
COPY --chown=jboss:root frontends/backoffice/ $WILDFLY/frontends/admin/
# Writable home of the TLS keystore (a named volume in Compose, so the certificate survives
# container replacement and only has to be trusted once). No RUN step: arm64 builds need no emulation.
COPY --chown=jboss:root --from=build /empty $WILDFLY/certs/

ENV BASILCARE_HOSTING_PROPERTIES=$WILDFLY/hosting/pwas-prod.properties
EXPOSE 8080 8443
CMD ["/bin/bash", "/opt/jboss/wildfly/hosting/start.sh"]
