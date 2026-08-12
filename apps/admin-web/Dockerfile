FROM node:22-alpine AS dependencies
WORKDIR /app
COPY apps/admin-web/package.json apps/admin-web/package-lock.json ./
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=dependencies /app/node_modules ./node_modules
COPY apps/admin-web .
ARG API_GATEWAY_URL=http://api-gateway:8000
ENV API_GATEWAY_URL=$API_GATEWAY_URL
RUN npm run build

FROM node:22-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN addgroup --system web && adduser --system --ingroup web web
COPY --from=builder --chown=web:web /app/.next/standalone ./
COPY --from=builder --chown=web:web /app/.next/static ./.next/static
COPY --from=builder --chown=web:web /app/public ./public
USER web
EXPOSE 3000
CMD ["node", "server.js"]
