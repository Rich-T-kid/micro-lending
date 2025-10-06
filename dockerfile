FROM alpine:3.20
RUN apk add --no-cache mysql-client ca-certificates
WORKDIR /app

# copy migrations + scripts
COPY db/ db/
COPY start.sh ./start.sh

# make sure scripts are executable
RUN chmod +x /app/start.sh /app/db/scripts/migrate.sh

# Railway public proxy expects TLS; safe to keep on
ENV MYSQL_SSL_MODE=REQUIRED

CMD ["./start.sh"]
