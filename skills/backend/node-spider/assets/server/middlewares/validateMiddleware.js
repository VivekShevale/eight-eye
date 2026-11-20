import AppError from "../utils/AppError.js";

// validate(schema, "body" | "query" | "params"): unknown fields are rejected, values are converted and trimmed.
// The result goes to req.validated[source]; Express 5 makes req.query read-only, so it is never overwritten.
export const validate = (schema, source = "body") => (req, res, next) => {
  const { value, error } = schema.validate(req[source] ?? {}, { abortEarly: false, stripUnknown: false, convert: true });
  if (error) {
    const details = error.details.map((item) => ({ field: `${source}.${item.path.join(".")}`, message: item.message.replace(/"/g, "") }));
    throw new AppError(400, "Request validation failed.", details);
  }
  req.validated = { ...req.validated, [source]: value };
  next();
};
