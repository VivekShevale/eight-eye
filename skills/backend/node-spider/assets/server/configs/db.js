import mongoose from "mongoose";

import config from "./env.js";
import logger from "./logger.js";

// Fail fast while disconnected instead of queueing queries for 10 s; the error handler answers 424.
mongoose.set("bufferCommands", false);

// One connection pool per process, opened at startup; the app still starts when MongoDB is down.
export const connectDB = async () => {
  if (!config.mongodbUri) {
    logger.error({ setting: "MONGODB_URI" }, "MongoDB is not configured");
    return;
  }
  try {
    await mongoose.connect(config.mongodbUri, { maxPoolSize: config.mongodbMaxPoolSize, serverSelectionTimeoutMS: 5000, socketTimeoutMS: 20000 });
    await mongoose.syncIndexes();
    logger.info({ database: mongoose.connection.name }, "MongoDB connected");
  } catch (error) {
    logger.error({ errorType: error.name }, "MongoDB unavailable at startup");
  }
};

export const disconnectDB = async () => {
  await mongoose.disconnect();
  logger.info("MongoDB connection closed");
};

export const pingDB = async () => {
  if (mongoose.connection.readyState !== 1) {
    throw new mongoose.Error("Database is not connected.");
  }
  await mongoose.connection.db.admin().ping();
};
