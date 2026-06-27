# Build stage
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod ./
COPY main.go ./
RUN CGO_ENABLED=0 GOOS=linux go build -o kipoboard main.go

# Final stage
FROM alpine:3.19
RUN apk --no-cache add ca-certificates && \
    addgroup -S appgroup && adduser -S appuser -G appgroup
WORKDIR /app
COPY --from=builder /app/kipoboard .
USER appuser
EXPOSE 5005
CMD ["./kipoboard"]
