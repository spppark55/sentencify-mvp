FROM node:20-alpine

WORKDIR /app

ENV NODE_ENV=development

# 의존성 설치 (캐시 활용을 위해 먼저 복사)
COPY package.json package-lock.json ./
RUN npm ci

# 나머지 소스 코드 복사
COPY . .

EXPOSE 5173

# Vite 개발 서버 실행 (컨테이너 외부 접속 허용)
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
