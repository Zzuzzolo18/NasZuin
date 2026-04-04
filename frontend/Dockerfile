# BUILD STAGE
FROM node:20-alpine AS build

WORKDIR /app
COPY package.json package-lock.json* ./

# Se non hai package-lock.json installiamo usando npm install
RUN npm install

COPY . .

# Crea la build statica
RUN npm run build

# SERVE STAGE
FROM nginx:alpine

# Copia la configurazione personalizzata di Nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copia la build dal primo stage nella cartella di nginx
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
