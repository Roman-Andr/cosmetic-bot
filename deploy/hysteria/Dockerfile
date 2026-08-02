FROM alpine:3.23@sha256:fd791d74b68913cbb027c6546007b3f0d3bc45125f797758156952bc2d6daf40

ARG HYSTERIA_VERSION=2.9.2
ARG HYSTERIA_SHA256=86fef8e2f1b2bf41318ac96724eee6c3b449e4e510022cc89658b63a6713922a

RUN apk add --no-cache ca-certificates wget \
    && wget -q -O /usr/local/bin/hysteria \
        "https://github.com/apernet/hysteria/releases/download/app/v${HYSTERIA_VERSION}/hysteria-linux-amd64" \
    && echo "${HYSTERIA_SHA256}  /usr/local/bin/hysteria" | sha256sum -c - \
    && chmod 0555 /usr/local/bin/hysteria \
    && addgroup -S hysteria \
    && adduser -S -D -H -G hysteria hysteria

USER hysteria
ENTRYPOINT ["/usr/local/bin/hysteria"]
CMD ["client", "--config", "/run/secrets/hysteria.yaml"]
