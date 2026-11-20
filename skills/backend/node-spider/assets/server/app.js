import cors from "cors";
import express from "express";

import config from "./configs/env.js";
import { errorHandler, notFound } from "./middlewares/errorMiddleware.js";
import authRouter from "./routes/authRoutes.js";
import expenseRouter from "./routes/expenseRoutes.js";
import healthRouter from "./routes/healthRoutes.js";

// Assembly only: middleware, routers, 404, error handler. No listen() here, so tests can import the app.
const app = express();

app.disable("x-powered-by");
app.use(cors({ origin: config.corsOrigins, credentials: true }));
app.use(express.json({ limit: "1mb" }));

app.use("/health", healthRouter);
app.use("/api/v1/auth", authRouter);
app.use("/api/v1/expenses", expenseRouter);

app.use(notFound);
app.use(errorHandler);

export default app;
