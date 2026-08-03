FROM node:22-alpine AS build
WORKDIR /src
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build:all

FROM nginx:1.27-alpine
COPY --from=build /src/dist /usr/share/nginx/html/mobile
COPY --from=build /src/dist-admin /usr/share/nginx/html/admin
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
