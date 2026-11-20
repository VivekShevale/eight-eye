import "dotenv/config";

// The only place process.env is read; every other file imports `config` from here.
const config = Object.freeze({
  nodeEnv: process.env.NODE_ENV || "development",
  port: Number(process.env.PORT || 5000),
  appName: process.env.APP_NAME || "Backend API",
  logLevel: process.env.LOG_LEVEL || "info",
  logToFile: (process.env.LOG_TO_FILE || "false").toLowerCase() === "true",
  // Not validated: a missing or unreachable database makes DB endpoints return 424, the app still starts.
  mongodbUri: process.env.MONGODB_URI || "",
  mongodbMaxPoolSize: Number(process.env.MONGODB_MAX_POOL_SIZE || 50),
  jwtSecret: process.env.JWT_SECRET || "",
  jwtExpiresIn: process.env.JWT_EXPIRES_IN || "30m",
  corsOrigins: (process.env.CORS_ORIGINS || "").split(",").map((origin) => origin.trim()).filter(Boolean),
});

export const validateConfig = () => {
  if (config.jwtSecret.length < 32) {
    throw new Error("JWT_SECRET must be set and at least 32 characters long.");
  }
  if (!Number.isInteger(config.port) || config.port <= 0) {
    throw new Error("PORT must be a positive integer.");
  }
};

validateConfig();

export default config;
