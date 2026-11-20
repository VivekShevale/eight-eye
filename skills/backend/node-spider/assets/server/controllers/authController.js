import bcrypt from "bcrypt";
import jwt from "jsonwebtoken";

import config from "../configs/env.js";
import logger from "../configs/logger.js";
import User from "../models/User.js";
import { toCurrentUserResponse, toTokenResponse, toUserResponse } from "../schemas/authSchema.js";
import AppError from "../utils/AppError.js";

const BCRYPT_ROUNDS = 12;

const createAccessToken = (userId) => jwt.sign({ sub: userId }, config.jwtSecret, { expiresIn: config.jwtExpiresIn });

// POST /api/v1/auth/register
export const register = async (req, res) => {
  const { email, password } = req.validated.body;
  // Cheap duplicate check before the expensive hash; the unique index still guards concurrent sign-ups (11000 -> 409).
  if (await User.exists({ email })) {
    throw new AppError(409, "Email is already registered.");
  }
  const user = await User.create({ email, password: await bcrypt.hash(password, BCRYPT_ROUNDS) });
  logger.info({ userId: user.id }, "User registered");
  res.status(201).json(toUserResponse(user));
};

// POST /api/v1/auth/login
export const login = async (req, res) => {
  const { email, password } = req.validated.body;
  const user = await User.findOne({ email }).select("+password");
  // Same message for unknown email and wrong password; bcrypt.compare is async and doesn't block the server.
  if (!user || !(await bcrypt.compare(password, user.password))) {
    logger.warn({ reason: "invalid_credentials" }, "Login rejected");
    throw new AppError(401, "Invalid email or password.");
  }
  logger.info({ userId: user.id }, "User logged in");
  res.status(200).json(toTokenResponse(createAccessToken(user.id)));
};

// GET /api/v1/auth/me
export const getMe = async (req, res) => {
  res.status(200).json(toCurrentUserResponse(req.user));
};
