FROM node:24-alpine AS build
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
ARG NEXT_PUBLIC_TELEGRAM_BOT
ENV NEXT_PUBLIC_TELEGRAM_BOT=$NEXT_PUBLIC_TELEGRAM_BOT
RUN npx next build

FROM node:24-alpine
WORKDIR /web
ENV NODE_ENV=production
COPY --from=build /web ./
EXPOSE 3100
CMD ["npx", "next", "start", "--port", "3100"]
