# Dockerfile
FROM alpine:3.20
RUN apk add --no-cache mysql-client ca-certificates
WORKDIR /app

# Copy scripts and migrations
COPY db/ db/
COPY start.sh ./start.sh

# Normalize line endings (strip CRLF) & ensure executables
RUN sed -i 's/\r$//' /app/start.sh /app/db/scripts/migrate.sh \
 && chmod +x /app/start.sh /app/db/scripts/migrate.sh

# Railway public proxy prefers TLS
ENV MYSQL_SSL_MODE=REQUIRED

CMD ["./start.sh"]
