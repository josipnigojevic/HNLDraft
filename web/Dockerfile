FROM node:22.13.0-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG NEXT_PUBLIC_SIM_API_URL=http://localhost:8002
ENV NEXT_PUBLIC_SIM_API_URL=$NEXT_PUBLIC_SIM_API_URL

RUN npm run build

FROM node:22.13.0-alpine AS runtime

ENV NODE_ENV=production \
    NEXT_PUBLIC_SIM_API_URL=http://localhost:8002

WORKDIR /app

COPY --from=build --chown=node:node /app /app

USER node

EXPOSE 3000

CMD ["npm", "run", "start", "--", "--hostname", "0.0.0.0", "--port", "3000"]
