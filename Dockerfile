# syntax=docker/dockerfile:1

FROM golang:1.23-alpine AS builder

WORKDIR /app

COPY . .

RUN go build -o dinterest .

FROM alpine:latest

WORKDIR /app

COPY --from=builder /app/dinterest .

EXPOSE 5003

CMD ["./dinterest"]