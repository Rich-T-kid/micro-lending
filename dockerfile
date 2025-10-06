# Dockerfile
FROM alpine:3.20
RUN apk add --no-cache bash mysql-client ca-certificates
WORKDIR /app

# copy migrations + scripts
COPY db/ db/

# copy start.sh to /app and ensure executable
COPY start.sh ./start.sh
RUN chmod +x /app/start.sh /app/db/scripts/migrate.sh

ENV MYSQL_SSL_MODE=REQUIRED
CMD ["./start.sh"]
