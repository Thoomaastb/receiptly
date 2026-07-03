FROM node:20-slim AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

FROM node:20-slim AS runtime
RUN groupadd -r receiptly && useradd -r -g receiptly receiptly
WORKDIR /app
COPY --from=build /app/build ./build
COPY --from=build /app/package.json ./
RUN npm install --omit=dev
RUN chown -R receiptly:receiptly /app
USER receiptly

ENV PORT=3000
EXPOSE 3000
CMD ["node", "build"]
