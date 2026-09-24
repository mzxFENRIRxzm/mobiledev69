FROM debian:bookworm-slim AS flutter-build

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git unzip xz-utils \
    && rm -rf /var/lib/apt/lists/*

# Official Flutter 3.44.2 Linux SDK, verified against the release archive checksum.
RUN curl -fsSL \
        https://storage.googleapis.com/flutter_infra_release/releases/stable/linux/flutter_linux_3.44.2-stable.tar.xz \
        -o /tmp/flutter.tar.xz \
    && echo "b0de1d19754688ec6769c9a067db3b0594479d3d767f971bfecfc132904c8d5e  /tmp/flutter.tar.xz" | sha256sum -c - \
    && tar -xJf /tmp/flutter.tar.xz -C /opt \
    && rm /tmp/flutter.tar.xz
ENV PATH="/opt/flutter/bin:/opt/flutter/bin/cache/dart-sdk/bin:$PATH"
RUN git config --global --add safe.directory /opt/flutter \
    && flutter --version \
    && flutter precache --web

WORKDIR /build/frontend
COPY frontend/pubspec.yaml frontend/pubspec.lock ./
RUN flutter pub get --enforce-lockfile
COPY frontend/ ./
ARG APP_ORIGIN
RUN test -n "$APP_ORIGIN" \
    && flutter build web --release --no-wasm-dry-run --no-web-resources-cdn \
        --dart-define="API_URL=$APP_ORIGIN" \
        --dart-define="FRONTEND_URL=$APP_ORIGIN"

FROM caddy:2-alpine
COPY --from=flutter-build /build/frontend/build/web /srv/flutter
COPY deploy/Caddyfile /etc/caddy/Caddyfile
EXPOSE 80 443
