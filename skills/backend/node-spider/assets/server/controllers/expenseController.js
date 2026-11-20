import mongoose from "mongoose";

import logger from "../configs/logger.js";
import Expense from "../models/Expense.js";
import { toExpenseListResponse, toExpenseResponse } from "../schemas/expenseSchema.js";
import AppError from "../utils/AppError.js";

const escapeRegex = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

// Every lookup is scoped to the owner, so another user's expense is indistinguishable from a missing one.
const findOwnedExpense = async (expenseId, userId) => {
  const expense = mongoose.isValidObjectId(expenseId) ? await Expense.findOne({ _id: expenseId, user: userId }) : null;
  if (!expense) {
    throw new AppError(404, "Expense not found.");
  }
  return expense;
};

const buildExpenseFilter = (userId, query) => {
  const filter = { user: userId };
  if (query.category) filter.category = query.category;
  if (query.search) filter.title = { $regex: escapeRegex(query.search), $options: "i" };
  if (query.startDate || query.endDate) {
    filter.expenseDate = {};
    if (query.startDate) filter.expenseDate.$gte = query.startDate;
    if (query.endDate) filter.expenseDate.$lte = query.endDate;
  }
  return filter;
};

// POST /api/v1/expenses
export const createExpense = async (req, res) => {
  const expense = await Expense.create({ ...req.validated.body, user: req.user.id });
  logger.info({ expenseId: expense.id, userId: req.user.id }, "Expense created");
  res.status(201).json(toExpenseResponse(expense));
};

// GET /api/v1/expenses?page=&pageSize=&search=&category=&startDate=&endDate=
export const listExpenses = async (req, res) => {
  const query = req.validated.query;
  const filter = buildExpenseFilter(req.user.id, query);
  const [items, total] = await Promise.all([
    Expense.find(filter).sort({ expenseDate: -1, _id: -1 }).skip((query.page - 1) * query.pageSize).limit(query.pageSize).lean(),
    Expense.countDocuments(filter),
  ]);
  logger.debug({ userId: req.user.id, count: items.length, total }, "Expenses listed");
  res.status(200).json(toExpenseListResponse(items, query.page, query.pageSize, total));
};

// GET /api/v1/expenses/:id
export const getExpense = async (req, res) => {
  const expense = await findOwnedExpense(req.params.id, req.user.id);
  res.status(200).json(toExpenseResponse(expense));
};

// PATCH /api/v1/expenses/:id
export const updateExpense = async (req, res) => {
  const expense = await findOwnedExpense(req.params.id, req.user.id);
  expense.set(req.validated.body);
  await expense.save();
  logger.info({ expenseId: expense.id, userId: req.user.id, fields: Object.keys(req.validated.body) }, "Expense updated");
  res.status(200).json(toExpenseResponse(expense));
};

// DELETE /api/v1/expenses/:id
export const deleteExpense = async (req, res) => {
  const expense = await findOwnedExpense(req.params.id, req.user.id);
  await expense.deleteOne();
  logger.info({ expenseId: req.params.id, userId: req.user.id }, "Expense deleted");
  res.status(204).end();
};
