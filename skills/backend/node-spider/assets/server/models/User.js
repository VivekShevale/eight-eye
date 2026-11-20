import mongoose from "mongoose";

const userSchema = new mongoose.Schema(
  {
    email: { type: String, required: true, unique: true, lowercase: true, trim: true },
    // select: false keeps the hash out of every query unless a login explicitly asks for it.
    password: { type: String, required: true, select: false },
  },
  { timestamps: true },
);

const User = mongoose.model("User", userSchema);

export default User;
