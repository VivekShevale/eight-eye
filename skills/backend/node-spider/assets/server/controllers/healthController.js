import { pingDB } from "../configs/db.js";
import { toHealthResponse } from "../schemas/healthSchema.js";

// GET /health: 200 when MongoDB answers; otherwise the error middleware returns 424.
export const checkHealth = async (req, res) => {
  await pingDB();
  res.status(200).json(toHealthResponse("ok"));
};
