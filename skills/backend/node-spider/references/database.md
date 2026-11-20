# Database

## Contents
1. Mongoose
2. Prisma (SQL)
3. Error mapping

## 1. Mongoose

**Connection** (`configs/db.js` in the starter):
- `mongoose.connect(uri, { maxPoolSize, serverSelectionTimeoutMS: 5000, socketTimeoutMS: 20000 })` once in `server.js` before `listen`; `mongoose.disconnect()` on shutdown.
- A failed connection is logged (`errorType` only, never the URI) and the server still starts; with `bufferCommands: false`, queries while disconnected fail at once and become 424.
- `await mongoose.syncIndexes()` after connecting makes declared indexes exist (fine for small apps; large production collections build indexes in a migration step instead).
- Never connect inside `app.listen`'s callback without awaiting it, and never log "DB connected" before it is.

**Models**:
- One file per model, schema and model together (`models/Resume.js`); no separate `schemas/` + `model/` file pairs.
- `{ timestamps: true }` for `createdAt`/`updatedAt`. A field default of `Date.now()` (with parentheses) is evaluated once at startup; use `timestamps` or `default: Date.now` without calling it.
- `required` (not `require`), `enum`, `min`/`max`, `maxlength`, `trim`, `lowercase` on the schema; Joi validates requests, the schema guards the data.
- Owner reference `user: { type: ObjectId, ref: "User", required: true }` and compound indexes starting with it (`{ user: 1, createdAt: -1 }`), named.
- `password: { select: false }`. Response shaping is not the model's job: controllers send `toXResponse(doc)` from `schemas/`, so `_id`, `__v`, `password` and internal fields never reach a response.
- Cascading deletes (listing → its reviews) in a `post("findOneAndDelete")` / `deleteOne` hook or explicitly in the controller, consistently.

**Queries**:
- Owner in every filter: `Model.findOne({ _id: id, user: req.user.id })`; `mongoose.isValidObjectId(id)` first, invalid → 404.
- Lists: filter + `sort({ createdAt: -1, _id: -1 })` + `skip/limit`, total from `countDocuments(filter)` in `Promise.all`; response through `toXListResponse` (`{ items, page, pageSize, total, totalPages }`).
- Search: `{ $regex: escapeRegex(term), $options: "i" }`; never `new RegExp(userInput)`.
- `.lean()` for read-only lists that don't need document methods; `.select()` to skip large fields.
- `populate` only what the response shows (`populate("owner", "email")`), never the whole user document.
- Updates: load-and-`save()` (runs validators and hooks) or `findOneAndUpdate(filter, { $set: validated }, { new: true, runValidators: true })`; never pass `req.body`.
- Multi-document transactions need a replica set (Atlas): `mongoose.startSession()` + `session.withTransaction(...)`; prefer designs that need one write.

## 2. Prisma (SQL)

**Client** (`configs/prisma.js`): one `PrismaClient` per process (reuse via `globalThis` in development to survive hot reload); with Neon serverless, the `@prisma/adapter-neon` pool. `await prisma.$disconnect()` on shutdown.

**Schema and migrations**:
- `prisma/schema.prisma` with `@id @default(uuid())` or `cuid()`, `@@unique`, `@@index` on filtered columns, `@relation(onDelete: Cascade)` for true children, enums for statuses and roles, `createdAt DateTime @default(now())`, `updatedAt DateTime @updatedAt`.
- `npx prisma migrate dev --name add_tasks` locally (creates and applies a migration; commit `prisma/migrations/`), `npx prisma migrate deploy` in production. `prisma db push` only for throwaway prototypes.
- `postinstall: "prisma generate"` so deploys have the client.

**Queries**:
- Owner/permission in the `where` (`where: { id, workspace: { members: { some: { userId } } } }`) or a shared permission middleware.
- `select`/`include` only the fields the response needs (never `include: { members: { include: { user: true } } }` just to check one id).
- Writes that belong together: `prisma.$transaction([...])` or the interactive form; never an outbound HTTP call inside an interactive transaction.
- Pagination: `skip`/`take` + `orderBy: [{ createdAt: "desc" }, { id: "desc" }]`, total from `prisma.x.count({ where })` in the same `$transaction`.
- `data` is built from validated fields only (`data: req.validated.body`), so clients can't change `projectId` or owners.
- Dates from requests are validated by Joi before `new Date(...)`; `new Date(undefined)` is an Invalid Date that Prisma rejects at runtime.

## 3. Error mapping

| Error | Status |
|---|---|
| Mongoose `CastError` (bad ObjectId reaching a query) | 404 |
| Mongoose `ValidationError` | 400 with field details |
| MongoDB duplicate key `code 11000` | 409 |
| `MongooseServerSelectionError`, `MongoNetworkError`, disconnected/buffering errors | 424 |
| Prisma `P2002` unique constraint | 409 |
| Prisma `P2025` record not found | 404 |
| Prisma `P2003` foreign key | 400 (or 409 when deleting something referenced) |
| Prisma `P1001` / `P1002` / `PrismaClientInitializationError` (can't reach database) | 424 |

Add the Prisma rows to `classifyError` in `errorMiddleware.js` in SQL projects (`error instanceof Prisma.PrismaClientKnownRequestError` and `error.code`).
