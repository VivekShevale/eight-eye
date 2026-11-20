# Routes, Controllers and Services

## Contents
1. REST routes
2. Controller pattern
3. Validation
4. Shared checks (team lead, roles)
5. File uploads
6. Services for external systems (AI, storage, email)
7. Background jobs
8. Server-rendered apps (EJS)

## 1. REST routes

Resources, not verbs:

| Instead of | Use |
|---|---|
| `POST /api/resumes/create` | `POST /api/v1/resumes` |
| `PUT /api/resumes/update` with `resumeId` in the body | `PATCH /api/v1/resumes/:id` |
| `DELETE /api/resumes/delete/:id` | `DELETE /api/v1/resumes/:id` |
| `GET /api/resumes/get/:id` | `GET /api/v1/resumes/:id` |
| `POST /api/tasks/delete` with ids in the body | `DELETE /api/v1/tasks/:id` (or `POST /api/v1/tasks/bulk-delete` only when bulk is a real requirement) |
| `GET /allHoldings` | `GET /api/v1/holdings` |

```js
const resumeRouter = express.Router();
resumeRouter.use(protect);
resumeRouter.route("/").get(validate(listResumesSchema, "query"), listResumes).post(validate(createResumeSchema), createResume);
resumeRouter.route("/:id").get(getResume).patch(validate(updateResumeSchema), updateResume).delete(deleteResume);
```

Child resources: `express.Router({ mergeParams: true })` mounted at `/api/v1/listings/:listingId/reviews`.

## 2. Controller pattern

```js
// PATCH /api/v1/resumes/:id
export const updateResume = async (req, res) => {
  const resume = await findOwnedResume(req.params.id, req.user.id);
  resume.set(req.validated.body);
  await resume.save();
  logger.info({ resumeId: resume.id, userId: req.user.id }, "Resume updated");
  res.status(200).json(toResumeResponse(resume));
};
```

- Input only from `req.validated.*`, `req.params`, `req.user`.
- Load with the owner in the filter (`{ _id: id, user: userId }`); missing or foreign → `throw new AppError(404, "Resume not found.")`.
- Helper functions used by several handlers in the same file (`findOwnedResume`, `buildResumeFilter`) are module-level functions above the handlers, not exported unless another file needs them.
- One response per request, with an explicit status and a response function from `schemas/`. Never `res.json(document)`, never `res.json({ message: "Saved successfully" })`, never a different shape per route.

## 3. Validation

- `schemas/<domain>Schema.js` holds both sides of the contract:
  - request: one Joi schema per operation, `createXSchema`, `updateXSchema` (`.min(1)` so an empty PATCH is 400), `listXSchema` for query parameters (page, pageSize ≤ 100, search, filters, date ranges with `Joi.ref`);
  - response: `toXResponse(doc)` returning exactly the public fields, and `toXListResponse(items, page, pageSize, total)` returning `{ items, page, pageSize, total, totalPages }`; action results get their own function (`toTokenResponse`).
- `validate(schema, source)` rejects unknown fields, converts types and puts the result in `req.validated[source]`.
- Nested data sent as JSON strings in multipart forms (`resumeData`): parse it in a small middleware or in the Joi schema with a custom rule, then validate the parsed object; never save it unvalidated.
- Database rules (duplicate email, ownership, state transitions) belong in the controller, not in Joi.

## 4. Shared checks (team lead, roles)

A permission check used by several routes becomes one function or middleware:

```js
// middlewares/projectMiddleware.js
export const requireTeamLead = async (req, res, next) => {
  const project = await prisma.project.findUnique({ where: { id: req.params.projectId }, select: { id: true, team_lead: true } });
  if (!project) throw new AppError(404, "Project not found.");
  if (project.team_lead !== req.user.id) throw new AppError(403, "Only the team lead can do this.");
  req.project = project;
  next();
};
```

403 is for "you can see it but your role can't do this"; 404 for records the user can't see at all.

## 5. File uploads

- `middlewares/uploadMiddleware.js` configures multer once: `limits: { fileSize: config.maxUploadBytes }`, `fileFilter` on MIME type and extension; memory storage for files forwarded to a cloud service, disk storage under a configured temp folder otherwise.
- Check magic bytes for files that matter (PDF `%PDF-`, PNG, JPEG) before processing.
- Multer `LIMIT_FILE_SIZE` → 413 in the error middleware.
- Temporary files are removed in a `finally` with `fs.promises.rm(path, { force: true })`, also when the upload to the cloud fails.

## 6. Services for external systems

```js
// services/aiService.js
import ai from "../configs/ai.js";
import config from "../configs/env.js";
import { ENHANCE_SUMMARY_PROMPT } from "../prompts/resumePrompts.js";
import AppError from "../utils/AppError.js";

export const enhanceSummary = async (text) => {
  try {
    const response = await ai.chat.completions.create({ model: config.aiModel, messages: [{ role: "system", content: ENHANCE_SUMMARY_PROMPT }, { role: "user", content: text }] }, { timeout: config.aiTimeoutMs });
    return response.choices[0].message.content.trim();
  } catch (error) {
    throw mapAiError(error);
  }
};
```

- Clients (OpenAI-compatible, ImageKit, Cloudinary, Nodemailer transporter) are created once in `configs/` and imported by services.
- Every outbound call has a timeout. Map provider errors: rate limit → 429, timeout → 504, unreachable → 503, other provider error → 502 (see `backend-silk/references/cross-repo-communication.md`).
- Prompts live in `prompts/` as exported constants, short, written once (not duplicated across handlers).
- AI output that will be stored (e.g. parsed resume JSON) is validated with a Joi schema before saving; invalid output → 502 "The AI service returned invalid data.", never the raw output to the client.
- Model name, temperature, base URL and keys come from `.env`.

## 7. Background jobs

- Work that shouldn't block the response (emails, webhook syncs, reminders) goes to a job runner the project already uses (Inngest functions in `jobs/`, or a queue). Each job function is short, idempotent where possible, and logs its outcome.
- Webhook handlers (Clerk, payment providers) verify the signature before trusting the payload.
- Sending a job event never fails the user's request silently: log failures with the event name and ids.

## 8. Server-rendered apps (EJS)

When the requirement is a server-rendered site:

- Same layers; controllers end with `res.render(...)` or `res.redirect(...)` instead of `res.json(...)`.
- Sessions with `express-session` and a store (e.g. `connect-mongo`), secret from `.env`, `cookie: { httpOnly: true, secure: production, maxAge }`; Passport local strategy for login; `connect-flash` for messages.
- The error middleware renders `error.ejs` with the same status mapping; HTML forms use `method-override` for PUT/DELETE.
- `views/` (with `layouts/`, `includes/`) and `public/` at the server root.
