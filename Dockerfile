FROM golang:1.22-alpine AS builder

WORKDIR /app

COPY main.go .

RUN CGO_ENABLED=0 GOOS=linux go build -o kipoboard main.go

FROM alpine:latest

RUN apk --no-cache add ca-certificates

WORKDIR /app

COPY --from=builder /app/kipoboard .

EXPOSE 5003

CMD ["./kipoboard"]
