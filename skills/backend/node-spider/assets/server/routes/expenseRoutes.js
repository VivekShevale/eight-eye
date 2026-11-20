import express from "express";

import { createExpense, deleteExpense, getExpense, listExpenses, updateExpense } from "../controllers/expenseController.js";
import { protect } from "../middlewares/authMiddleware.js";
import { validate } from "../middlewares/validateMiddleware.js";
import { createExpenseSchema, listExpensesSchema, updateExpenseSchema } from "../schemas/expenseSchema.js";

const expenseRouter = express.Router();

// Every expense route needs a logged-in user.
expenseRouter.use(protect);

expenseRouter.route("/")
  .get(validate(listExpensesSchema, "query"), listExpenses)
  .post(validate(createExpenseSchema), createExpense);

expenseRouter.route("/:id")
  .get(getExpense)
  .patch(validate(updateExpenseSchema), updateExpense)
  .delete(deleteExpense);

export default expenseRouter;
