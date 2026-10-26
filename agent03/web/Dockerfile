FROM node:22-alpine AS build
WORKDIR /web
COPY package.json ./
RUN corepack enable && pnpm install --no-frozen-lockfile
COPY . ./
RUN pnpm build

FROM nginx:1.27-alpine
COPY --from=build /web/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80

