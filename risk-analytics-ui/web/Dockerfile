# Build
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
ENV VITE_API_URL=/api
RUN npm run build

# Serve
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
RUN echo 'server { listen 80; root /usr/share/nginx/html; index index.html; location = /index.html { add_header Cache-Control "no-store, no-cache"; } location / { try_files $uri $uri/ /index.html; } location /api/ { proxy_pass http://risk-analytics-ui-api:8000/; proxy_http_version 1.1; proxy_set_header Host $host; proxy_set_header X-Real-IP $remote_addr; } }' > /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
