import mongoose from "mongoose";

const expenseSchema = new mongoose.Schema(
  {
    user: { type: mongoose.Schema.Types.ObjectId, ref: "User", required: true },
    title: { type: String, required: true, trim: true, maxlength: 200 },
    amount: { type: Number, required: true, min: 0.01 },
    category: { type: String, required: true, trim: true, maxlength: 50 },
    expenseDate: { type: Date, required: true },
  },
  // createdAt / updatedAt maintained by Mongoose (never Date.now() as a fixed default).
  { timestamps: true },
);

// Matches the list query: every query is scoped by user, newest first.
expenseSchema.index({ user: 1, expenseDate: -1, _id: -1 }, { name: "user_expense_date_idx" });
expenseSchema.index({ user: 1, category: 1 }, { name: "user_category_idx" });

const Expense = mongoose.model("Expense", expenseSchema);

export default Expense;
