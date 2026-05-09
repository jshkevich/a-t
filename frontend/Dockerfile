# frontend/Dockerfile

# Этап 1: Сборка проекта
FROM node:20-alpine as build

WORKDIR /app
COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

# Этап 2: Раздача статики через Nginx
FROM nginx:alpine

# Копируем собранные файлы из папки dist (Vite собирает туда) в папку nginx
COPY --from=build /app/dist /usr/share/nginx/html

# Открываем 80 порт
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]