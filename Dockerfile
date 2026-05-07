# syntax=docker/dockerfile:1

FROM golang:1.23-alpine AS builder

WORKDIR /app

RUN apk add --no-cache ca-certificates

COPY go.mod ./

COPY . .

RUN CGO_ENABLED=0 go build -ldflags="-s -w" -o dinterest .

FROM alpine:latest

RUN apk add --no-cache ca-certificates

WORKDIR /app

COPY --from=builder /app/dinterest .

EXPOSE 5003

CMD ["./dinterest"]