import Joi from "joi";

import config from "../configs/env.js";

// ---- Request schemas ----

// Password policy only at registration, never at login.
const PASSWORD_PATTERN = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z\d\s])\S{8,72}$/;

export const registerSchema = Joi.object({
  email: Joi.string().trim().lowercase().email().max(254).required(),
  password: Joi.string().pattern(PASSWORD_PATTERN).required().messages({
    "string.pattern.base": "Password must be 8-72 characters with upper and lower case letters, a digit, a symbol and no spaces.",
  }),
});

export const loginSchema = Joi.object({
  email: Joi.string().trim().lowercase().email().required(),
  password: Joi.string().min(1).max(72).required(),
});

// ---- Response schemas ----

export const toUserResponse = (user) => ({
  id: user.id ?? user._id.toString(),
  email: user.email,
  createdAt: user.createdAt,
});

export const toCurrentUserResponse = (currentUser) => ({
  id: currentUser.id,
  email: currentUser.email,
});

export const toTokenResponse = (accessToken) => ({
  accessToken,
  tokenType: "Bearer",
  expiresIn: config.jwtExpiresIn,
});
