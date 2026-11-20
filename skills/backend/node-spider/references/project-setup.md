# Project Setup

## Contents
1. Copy map
2. package.json
3. Build order
4. Commands (Windows)
5. Express 5 differences that break Express 4 habits
6. .env.example

## 1. Copy map

Everything comes from `node-spider/assets/server/`:

| Part | Files |
|---|---|
| Skeleton | `package.json`, `.env.example`, `.gitignore`, `configs/env.js`, `configs/logger.js`, `configs/db.js`, `utils/AppError.js`, `middlewares/errorMiddleware.js`, `middlewares/validateMiddleware.js`, `controllers/healthController.js`, `routes/healthRoutes.js`, `app.js`, `server.js` |
| Auth | `models/User.js`, `schemas/authSchema.js`, `controllers/authController.js`, `middlewares/authMiddleware.js`, `routes/authRoutes.js` |
| Each feature | Copy the `expense*` pattern: model, schema (request + response), controller, routes; mount the router in `app.js` |
| Tests | `tests/app.test.js` pattern |

`app.js` mounts only the routers that exist.

## 2. package.json

```json
{
  "type": "module",
  "scripts": {
    "start": "node server.js",
    "dev": "node --watch server.js",
    "test": "node --test \"tests/**/*.test.js\""
  }
}
```

- Dependencies (starter, pinned in `assets/server/package.json`): `express` 5, `mongoose` 9, `joi` 18, `jsonwebtoken`, `bcrypt`, `cors`, `dotenv`, `pino`, `pino-roll`. Dev: `supertest`, `mongodb-memory-server` (and `nodemon` only if the user prefers it over `node --watch`).
- The test script needs a glob: `node --test tests/` treats the folder as a file on Node 22 and fails.
- Install with `npm install <pkg>` so `package.json` and `package-lock.json` stay in sync; commit both. Remove packages the code doesn't import.
- SQL projects: `prisma` (dev) and `@prisma/client`; `postinstall: "prisma generate"`.

## 3. Build order (what depends on what)

1. **Skeleton**: config, logger, DB connection, error and validate middleware, health route, `app.js`, `server.js`. Expected: `GET /health` 200 with MongoDB running, 424 with it stopped.
2. **Auth**: User model, register/login/me. Expected: duplicate 409, weak password 400, wrong password and unknown email both 401 with the same message, missing/invalid token 401.
3. **Each feature**: routes decided first, then model (indexes), schemas (request + response), controller, routes, tests.
4. README with setup and run steps.

## 4. Commands (Windows)

```bat
cd server
npm install
copy .env.example .env
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
npm run dev
npm test
```

## 5. Express 5 differences that break Express 4 habits

| Express 4 habit | Express 5 |
|---|---|
| `wrapAsync` / `catchAsync` around every handler | Not needed: rejected promises go to the error middleware |
| `app.all("*", ...)` for the 404 | Path syntax changed; use a final `app.use(notFound)` without a path |
| Writing to `req.query` (e.g. after validation) | `req.query` is a getter; store validated values in `req.validated.query` |
| `body-parser` package | `express.json()` / `express.urlencoded()` built in |
| `res.send(status)` with a number, `res.json(obj, status)` | `res.status(code).json(obj)` |
| Regex characters in route strings (`/:id?`, `*`) | Named wildcards `/*splat`, optional `{/:id}` |

## 6. .env.example

The starter's `.env.example` lists every variable `configs/env.js` reads. Add a variable to both files in the same change. Keys for third-party services (OpenAI/Gemini, ImageKit, Cloudinary, Clerk, SMTP) go in with placeholder values and a comment on where to get them.
