# Vite bakes VITE_* variables into the built JS at build time, not at
# container start — so the deploy target's API URL has to be a build ARG,
# not a runtime env var like the backend services get away with.

FROM node:20-slim AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG VITE_API_BASE_URL=http://localhost:8000/api/v1
ARG VITE_RECAPTCHA_SITE_KEY=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_RECAPTCHA_SITE_KEY=$VITE_RECAPTCHA_SITE_KEY
RUN npm run build

FROM nginx:1.27-alpine AS serve
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
# 127.0.0.1, not "localhost": nginx here only binds IPv4 (see nginx.conf's
# plain `listen 80`), and busybox wget's "localhost" resolution can prefer
# the ::1 entry in /etc/hosts, which nothing is listening on — a real,
# reproducible "Connection refused" this exact image hit until pinned to
# the literal IPv4 address.
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
    CMD wget -qO- http://127.0.0.1:80/health >/dev/null || exit 1
