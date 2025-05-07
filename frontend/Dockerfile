FROM node:18

# Set workdir
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy rest of frontend
COPY . .

# Build the frontend
RUN npm run build

# Use serve to host static files
RUN npm install -g serve
EXPOSE 5173
CMD ["serve", "-s", "dist", "-l", "5173"]