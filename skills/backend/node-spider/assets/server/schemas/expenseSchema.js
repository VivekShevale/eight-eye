import Joi from "joi";

// ---- Request schemas ----
// Server-owned fields (user, createdAt, updatedAt, id) are not in any request schema, so clients can't set them.

export const createExpenseSchema = Joi.object({
  title: Joi.string().trim().min(1).max(200).required(),
  amount: Joi.number().positive().precision(2).required(),
  category: Joi.string().trim().min(1).max(50).required(),
  expenseDate: Joi.date().iso().required(),
});

// PATCH: every field optional, at least one required, no explicit nulls.
export const updateExpenseSchema = Joi.object({
  title: Joi.string().trim().min(1).max(200),
  amount: Joi.number().positive().precision(2),
  category: Joi.string().trim().min(1).max(50),
  expenseDate: Joi.date().iso(),
})
  .min(1)
  .messages({ "object.min": "Provide at least one field to update." });

export const listExpensesSchema = Joi.object({
  page: Joi.number().integer().min(1).default(1),
  pageSize: Joi.number().integer().min(1).max(100).default(10),
  search: Joi.string().trim().max(100),
  category: Joi.string().trim().max(50),
  startDate: Joi.date().iso(),
  endDate: Joi.date().iso().min(Joi.ref("startDate")).messages({ "date.min": "endDate must not be before startDate." }),
});

// ---- Response schemas ----
// The only shapes the API returns for expenses; controllers never send a document or an object literal directly.

export const toExpenseResponse = (expense) => ({
  id: expense.id ?? expense._id.toString(),
  title: expense.title,
  amount: expense.amount,
  category: expense.category,
  expenseDate: expense.expenseDate,
  createdAt: expense.createdAt,
  updatedAt: expense.updatedAt,
});

export const toExpenseListResponse = (expenses, page, pageSize, total) => ({
  items: expenses.map(toExpenseResponse),
  page,
  pageSize,
  total,
  totalPages: Math.ceil(total / pageSize),
});
