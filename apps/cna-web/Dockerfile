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

# ── Stage 3: runner ──────────────────────────────────────────────────────────
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

# Prisma schema, generated client, and CLI (needed at runtime for migrations).
# @prisma/client + .prisma = runtime query engine
# prisma = CLI binary required by `prisma migrate deploy`
COPY --from=builder /app/prisma ./prisma
COPY --from=builder /app/node_modules/.prisma ./node_modules/.prisma
COPY --from=builder /app/node_modules/@prisma ./node_modules/@prisma
COPY --from=builder /app/node_modules/prisma ./node_modules/prisma

# Fix ownership so the nextjs user can execute the prisma CLI and read the schema.
RUN chown -R nextjs:nodejs ./node_modules/.prisma ./node_modules/@prisma ./node_modules/prisma ./prisma

USER nextjs

EXPOSE 3000

# Run Prisma migrations then start the server.
# `prisma migrate deploy` is idempotent — already-applied migrations are skipped.
# Use node_modules/.bin/prisma directly to avoid npx network lookup.
CMD ["sh", "-c", "node_modules/.bin/prisma migrate deploy && node server.js"]
