import jwt from "jsonwebtoken";

import config from "../configs/env.js";
import User from "../models/User.js";
import AppError from "../utils/AppError.js";

// protect: requires "Authorization: Bearer <token>" and a user that still exists; sets req.user.
export const protect = async (req, res, next) => {
  const [scheme, token] = (req.headers.authorization || "").split(" ");
  if (scheme !== "Bearer" || !token) {
    throw new AppError(401, "Not authenticated.");
  }
  let claims;
  try {
    claims = jwt.verify(token, config.jwtSecret);
  } catch {
    throw new AppError(401, "Invalid or expired token.");
  }
  const user = await User.findById(claims.sub).select("_id email").lean();
  if (!user) {
    throw new AppError(401, "Invalid or expired token.");
  }
  req.user = { id: user._id.toString(), email: user.email };
  next();
};
