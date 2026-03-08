# ── Stage 1: deps ────────────────────────────────────────────────────────────
FROM node:20-alpine AS deps
WORKDIR /app

# Install native build tools (needed by some optional Prisma packages).
RUN apk add --no-cache libc6-compat

COPY package.json package-lock.json* ./
RUN npm ci

# ── Stage 2: builder ─────────────────────────────────────────────────────────
FROM node:20-alpine AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Generate Prisma client before building.
RUN npx prisma generate

ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build

# ── Stage 3: migrator ─────────────────────────────────────────────────────────
# Standalone image used exclusively to run `prisma migrate deploy` once per
# deployment (via workflow 03). Keeping CLI deps out of the runtime image avoids
# chasing Prisma's transitive dep tree (effect, fast-check, etc.) across upgrades.
FROM node:20-alpine AS migrator
WORKDIR /app

RUN apk add --no-cache libc6-compat

COPY --from=builder /app/prisma ./prisma
COPY --from=builder /app/node_modules ./node_modules

CMD ["sh", "-c", "node_modules/.bin/prisma migrate deploy"]

# ── Stage 4: runner ──────────────────────────────────────────────────────────
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Add a non-root user for Container Apps security best practices.
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Next.js standalone output bundles only the required files.
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

# Prisma runtime only — @prisma/client + generated query engine.
# The Prisma CLI is intentionally excluded; migrations run from the
# migrator stage in workflow 03 before this container is deployed.
COPY --from=builder /app/node_modules/.prisma ./node_modules/.prisma
COPY --from=builder /app/node_modules/@prisma ./node_modules/@prisma

RUN chown -R nextjs:nodejs ./node_modules/.prisma ./node_modules/@prisma

USER nextjs

EXPOSE 3000

CMD ["node", "server.js"]
