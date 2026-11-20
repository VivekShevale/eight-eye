import pino from "pino";

import config from "./env.js";

// Console always; with LOG_TO_FILE=true also logs/app.N.log, rotated at 5 MB, 5 files kept.
const targets = [{ target: "pino/file", options: { destination: 1 }, level: config.logLevel }];
if (config.logToFile) {
  targets.push({ target: "pino-roll", options: { file: "logs/app", extension: ".log", size: "5m", limit: { count: 5 }, mkdir: true }, level: config.logLevel });
}

const logger = pino({ level: config.logLevel, base: { app: config.appName }, timestamp: pino.stdTimeFunctions.isoTime }, pino.transport({ targets }));

export default logger;
