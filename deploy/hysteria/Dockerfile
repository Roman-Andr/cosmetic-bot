FROM alpine:3.24@sha256:28bd5fe8b56d1bd048e5babf5b10710ebe0bae67db86916198a6eec434943f8b

ARG HYSTERIA_VERSION=2.9.2
ARG HYSTERIA_SHA256=86fef8e2f1b2bf41318ac96724eee6c3b449e4e510022cc89658b63a6713922a

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
