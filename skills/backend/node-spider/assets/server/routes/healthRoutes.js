import express from "express";

import { checkHealth } from "../controllers/healthController.js";

const healthRouter = express.Router();

healthRouter.get("/", checkHealth);

export default healthRouter;
