# Dockerfile
FROM alpine:3.20
RUN apk add --no-cache bash mysql-client ca-certificates
WORKDIR /app
COPY db/ db/
# Prefer TLS when hitting Railway's public proxy
ENV MYSQL_SSL_MODE=REQUIRED
# On start: run migrations, then idle so the service stays 'healthy'
CMD ["bash","-lc","bash db/scripts/migrate.sh && echo '✅ Migrations finished' && tail -f /dev/null"]
