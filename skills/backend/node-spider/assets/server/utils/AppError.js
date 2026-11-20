// Expected errors: controllers and middlewares throw these, errorMiddleware turns them into JSON.
export default class AppError extends Error {
  constructor(statusCode, message, details = undefined) {
    super(message);
    this.name = "AppError";
    this.statusCode = statusCode;
    this.details = details;
  }
}
