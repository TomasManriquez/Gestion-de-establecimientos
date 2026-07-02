FROM node:22-alpine

WORKDIR /app

# Copy dependency definitions
COPY package.json .
# Copy lockfile if it exists (using wildcard to prevent build crash if missing)
COPY package-lock.json* ./

# Install dependencies
RUN npm install

# Copy the rest of the application
COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host"]
