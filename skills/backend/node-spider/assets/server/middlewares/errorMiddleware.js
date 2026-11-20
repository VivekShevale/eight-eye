import mongoose from "mongoose";

import logger from "../configs/logger.js";
import AppError from "../utils/AppError.js";

const DATABASE_ERROR_NAMES = new Set(["MongooseServerSelectionError", "MongoServerSelectionError", "MongoNetworkError", "MongoNetworkTimeoutError", "MongoNotConnectedError"]);

const buildBody = (message, details) => (details ? { status: "error", message, details } : { status: "error", message });

const isDatabaseUnavailable = (error) => DATABASE_ERROR_NAMES.has(error.name) || (error instanceof mongoose.Error && /not connected|before initial connection|buffering/i.test(error.message));

// Map known errors to a status code and a safe message; anything else becomes a 500.
const classifyError = (error) => {
  if (error instanceof AppError) return { status: error.statusCode, message: error.message, details: error.details };
  if (error.type === "entity.parse.failed") return { status: 400, message: "Request body is not valid JSON." };
  if (error.type === "entity.too.large") return { status: 413, message: "Request body is too large." };
  if (error instanceof mongoose.Error.CastError) return { status: 404, message: "Resource not found." };
  if (error instanceof mongoose.Error.ValidationError) {
    const details = Object.values(error.errors).map((item) => ({ field: item.path, message: item.message }));
    return { status: 400, message: "Request validation failed.", details };
  }
  if (error.code === 11000) return { status: 409, message: "Resource already exists." };
  if (isDatabaseUnavailable(error)) return { status: 424, message: "Database dependency is unavailable." };
  return { status: 500, message: "An unexpected error occurred." };
};

export const notFound = (req, res, next) => {
  next(new AppError(404, "Route not found."));
};

// Express 5 forwards errors thrown in async handlers here; no try/catch or wrapAsync in controllers.
export const errorHandler = (error, req, res, next) => {
  const { status, message, details } = classifyError(error);
  const context = { method: req.method, path: req.originalUrl, status };
  if (status >= 500 && status !== 424) logger.error({ ...context, err: error }, "Unexpected error");
  else if (status === 424) logger.error({ ...context, errorType: error.name }, "Database unavailable");
  else logger.warn(context, "Request failed");
  res.status(status).json(buildBody(message, details));
};
