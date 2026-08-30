FROM node:22-alpine AS dev

WORKDIR /app

# Install deps first (cache layer)
COPY package.json package-lock.json ./
RUN npm ci

# Copy source
COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev"]
