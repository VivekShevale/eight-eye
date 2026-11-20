---
name: node-spider
description: Builds and maintains Node.js REST API backends with Express 5. Covers ES modules, the routes, controllers and services layering (controllers are exported functions, not classes), Joi validation middleware, Mongoose for MongoDB and Prisma for SQL, JWT with bcrypt or Clerk auth, one AppError plus a central error middleware with the shared JSON error shape and 424 when the database is down, pino logging from LOG_LEVEL and LOG_TO_FILE, configs read once from .env, and tests with node:test and supertest, with a tested starter project. Use this whenever the user creates or changes an Express or Node.js backend, adds routes, controllers, models, middleware, validation, auth, file uploads, AI calls or background jobs in Node, or pastes a Node/Express error, even if they don't say Express. Apply together with backend-silk and mongodb-silk or sql-silk for the principles.
---

# Node Spider

Builds Node.js + Express backends on top of the shared standards. Load these too:

- `backend-silk` (always): layers, edge cases, status codes, error shape, security, cross-repo rules, workflow. Its Python code is Python; its rules apply here.
- `mongodb-silk` (MongoDB) or `sql-silk` (PostgreSQL/MySQL) for data rules: ownership filters, indexes, pagination, migrations, pooling.
- `rag-spider` / `mcp-spider` for the rules on LLM features and tool calling (the code there is Python; port the behaviour).

## Structure

```text
server/
├── server.js               # connect DB, app.listen, graceful shutdown (SIGINT/SIGTERM)
├── app.js                  # assembly only: cors, json, routers, notFound, errorHandler; exported for tests
├── configs/
│   ├── env.js              # reads .env once, validates secrets, exports a frozen config object
│   ├── db.js               # mongoose connect/disconnect/ping (or prisma.js: one shared PrismaClient)
│   └── logger.js           # pino: LOG_LEVEL, LOG_TO_FILE (rotating file)
├── routes/                 # <domain>Routes.js: REST paths -> middleware chain -> controller
├── controllers/            # <domain>Controller.js: business logic (the helpers layer), sends the response
├── services/               # <name>Service.js: external systems (AI, ImageKit/Cloudinary, email, other repos)
├── models/                 # Mongoose models, schema + model in one file (SQL: prisma/schema.prisma)
├── schemas/                # <domain>Schema.js: Joi request schemas + toXResponse response functions
├── middlewares/            # authMiddleware.js, validateMiddleware.js, errorMiddleware.js, uploadMiddleware.js
├── utils/                  # AppError.js and small shared pure functions
├── prompts/                # LLM prompt constants (only with an LLM)
├── jobs/                   # background jobs, e.g. Inngest functions (only when needed)
├── scripts/seed.js         # seed data (never commented-out seed routes in app code)
├── tests/
├── .env  .env.example  .gitignore  package.json
```

Folder and file names: `configs/`, `middlewares/`, camelCase `resumeController.js`, `resumeRoutes.js`, `authMiddleware.js`; models in PascalCase (`User.js`). Create folders when their first file is needed. Starter (tested): `assets/server/`.

## Layers

| Layer | Does | Doesn't |
|---|---|---|
| `routes/` | `express.Router()`, REST paths, middleware chain (`protect`, `validate(schema)`, upload), one controller per route | Logic, queries, try/catch |
| `controllers/` | Read `req.validated` and `req.user`, ownership checks, queries through the model or Prisma, call services, log business events, send the response with the right status | Create SDK clients, call third-party APIs directly, hold prompts |
| `services/` | One external system each (AI, file storage, email, other repos), with timeouts and error mapping to `AppError` (502/503/504) | Read `req`/`res` |
| `models/` | Mongoose schemas and indexes; `password` with `select: false` | Business logic, response shaping |
| `schemas/` + `validateMiddleware` | Request: Joi schemas run by one generic `validate(schema, source)` middleware. Response: `toXResponse` / `toXListResponse` functions that pick exactly the fields the API returns | Database checks (duplicates, ownership: controller) |
| `middlewares/` | Cross-cutting request steps: auth, validation, upload, 404, error handler | Feature logic |
| `configs/` | Clients and settings created once (DB, logger, AI, storage) | Logic |

A check repeated in several controllers (e.g. "is the user team lead of this project") becomes one exported function or a middleware, not copies.

## Code rules (Node versions of the shared rules)

1. **ES modules** (`"type": "module"`, `import`/`export`), named exports for controllers, schemas, middlewares and services. Classes only where they earn it (`AppError extends Error`, or a service that holds state); idiomatic Express code uses exported functions for controllers.
2. **Express 5**: async handlers' errors reach the error middleware automatically. No `wrapAsync`/`catchAsync`, no try/catch in controllers: `throw new AppError(404, "Expense not found.")`. Catch only to translate a specific error (e.g. a JWT verify error to 401).
3. **Never pass `req.body` to `create`/`update`/`findOneAndUpdate`/Prisma `data`**: only `req.validated.body`, whose schema has no server-owned fields (`user`, `userId`, `projectId`, `role`, timestamps). `req.query` is read-only in Express 5, so validated values go to `req.validated.query`.
4. **No `console.log`** in app code: `logger.info({ expenseId, userId }, "Expense created")`. Never log `req.headers`, tokens, passwords or request bodies.
5. **No blocking calls** on the request path: `bcrypt.hash`/`bcrypt.compare` (async, never `compareSync`), `fs.promises` (never `unlinkSync`/`readFileSync` in handlers).
6. Functions around 40–50 lines, no names starting with `_`, imports at the top, no commented-out code, no unused imports or packages (`body-parser` is not needed with `express.json()`).
7. User input never builds a regex or query operator unescaped: escape search text (`escapeRegex`) and validate types with Joi first.
8. **Request and response schemas for every endpoint**: input only through `validate(schema)`; output only through the domain's response functions, with the status set explicitly: `res.status(201).json(toExpenseResponse(expense))`, `res.status(200).json(toExpenseListResponse(items, page, pageSize, total))`, `res.status(204).end()`. Never `res.json(document)`, never an object literal assembled in the controller, never "success" when nothing was found or saved.
9. Field names are camelCase across the API (`expenseDate`, `pageSize`, `totalPages`, `accessToken`), in query parameters and responses alike.

## Errors and status codes

- One shape everywhere: `{ "status": "error", "message": "...", "details": [{ "field", "message" }] }` (`details` only for field errors), from `middlewares/errorMiddleware.js`.
- Mapping in the error middleware: `AppError` → its status; Joi via `validate` → 400 with details; invalid JSON → 400; body too large → 413; Mongoose `CastError` → 404; Mongoose `ValidationError` → 400; duplicate key `11000` (Prisma `P2002`) → 409; Prisma `P2025` → 404; MongoDB/Prisma connection errors → 424; everything else → 500 with a generic message and the stack only in the log.
- Status codes from `backend-silk`: 401 bad credentials (not 400), 404 for another user's record, 409 duplicates, 424 database down, 502/503/504 for other services and AI providers.
- `mongoose.set("bufferCommands", false)` so queries fail immediately (424) while disconnected instead of hanging.

## Auth

- Own auth: bcrypt (12 rounds, async) + jsonwebtoken. Token `sub` = user id, expiry from `JWT_EXPIRES_IN`, secret ≥ 32 chars from `.env`. `protect` reads `Authorization: Bearer <token>`, verifies it, checks the user still exists, sets `req.user = { id, email }`.
- Clerk projects: `clerkMiddleware()` in `app.js`, `protect` calls `req.auth()`; user and organisation sync through Clerk webhooks or Inngest jobs; never trust ids from the body.
- Register: validate → duplicate check (409) → hash → create; the unique index guards races. Login: one message, "Invalid email or password.", 401.
- CORS: explicit origins from `CORS_ORIGINS`, never `cors()` with no options in production.

## Database

- **MongoDB (default)**: Mongoose, one connection at startup (`configs/db.js`), `maxPoolSize` and timeouts set, app still starts when MongoDB is down, indexes declared on schemas, every query scoped by `user`, `timestamps: true` (never `default: Date.now()`, which is evaluated once). Rules: `mongodb-silk`.
- **SQL**: Prisma with one shared `PrismaClient` (`configs/prisma.js`), migrations with `prisma migrate dev` / `prisma migrate deploy`, `select`/`include` only what the response needs, `$transaction` for writes that belong together. Rules: `sql-silk`.
- Details for both: `references/database.md`.

## Running

- `npm run dev` (nodemon / `node --watch`), `npm start`, `npm test`. Windows: commands in CMD/PowerShell from the `server` folder.
- `.env` never committed: `.gitignore` exists from the first commit with `node_modules/`, `.env`, `logs/`.

## Reference files

| File | Read when |
|---|---|
| `references/project-setup.md` | Creating a project, copy map, package.json, build order, Express 5 differences |
| `references/routes-and-controllers.md` | Writing routes, controllers, validation, uploads, services for AI/storage, background jobs |
| `references/database.md` | Mongoose or Prisma: connection, models, queries, pagination, transactions, error codes |
| `references/testing.md` | Tests with node:test, supertest and mongodb-memory-server |

## Assets

`assets/server/` is a complete, tested starter: configs (env, db, logger), AppError, error/validate/auth middlewares, User and Expense models, auth/expense/health schemas (request + response), controllers and routes, health check, `app.js`/`server.js`, `.env.example`, `.gitignore`, `package.json` and `tests/app.test.js`. Copy the files the project needs; rename the example `expenses` domain.
