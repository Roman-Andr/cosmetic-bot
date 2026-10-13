FROM alpine:3.24@sha256:294b683cb724975bec92580e1e685676bd4b50bda910ddb8c51d4cabeaec77e6

ARG HYSTERIA_VERSION=2.13.0
ARG HYSTERIA_SHA256=907ba8c9693edb104b20582681fb7dc15639d5b64a9cbb616a7b539190a86691

RUN apk add --no-cache ca-certificates wget \
    && wget -q -O /usr/local/bin/hysteria \
        "https://github.com/apernet/hysteria/releases/download/app/v${HYSTERIA_VERSION}/hysteria-linux-amd64" \
    && echo "${HYSTERIA_SHA256}  /usr/local/bin/hysteria" | sha256sum -c - \
    && chmod 0555 /usr/local/bin/hysteria \
    && addgroup -S -g 101 hysteria \
    && adduser -S -D -H -u 100 -G hysteria hysteria

USER hysteria
ENTRYPOINT ["/usr/local/bin/hysteria"]
CMD ["client", "--config", "/run/secrets/hysteria.yaml"]
