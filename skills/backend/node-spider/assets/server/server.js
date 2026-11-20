import app from "./app.js";
import { connectDB, disconnectDB } from "./configs/db.js";
import config from "./configs/env.js";
import logger from "./configs/logger.js";

await connectDB();

const server = app.listen(config.port, () => {
  logger.info({ port: config.port, env: config.nodeEnv }, "Server started");
});

// Close the HTTP server first (stop new requests), then the database pool.
const shutdown = (signal) => {
  logger.info({ signal }, "Shutting down");
  server.close(async () => {
    await disconnectDB();
    process.exit(0);
  });
};

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
