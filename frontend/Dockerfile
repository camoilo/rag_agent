# RAG 知识库助手 · 前端镜像（多阶段构建）
# 阶段 1：node 构建 dist；阶段 2：nginx 托管静态文件并反代后端容器
FROM node:22-alpine AS build
WORKDIR /app

# 先装依赖（利用层缓存），再拷源码
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# ---- 运行镜像 ----
FROM nginx:alpine

# dist 覆盖 nginx 默认站点内容
COPY --from=build /app/dist /usr/share/nginx/html
# 容器版站点配置：proxy_pass 指向 compose 服务名 backend
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
