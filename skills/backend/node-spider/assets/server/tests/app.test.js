import assert from "node:assert/strict";
import { after, before, describe, test } from "node:test";

import { MongoMemoryServer } from "mongodb-memory-server";
import mongoose from "mongoose";
import request from "supertest";

// Env must be set before the app (and configs/env.js) is imported.
const mongo = await MongoMemoryServer.create();
process.env.MONGODB_URI = mongo.getUri("test_db");
process.env.JWT_SECRET = "test-secret-key-with-at-least-32-characters";
process.env.LOG_LEVEL = "silent";

const { default: app } = await import("../app.js");
const { connectDB, disconnectDB } = await import("../configs/db.js");

const PASSWORD = "Str0ng!Pass";

const registerAndLogin = async (email) => {
  await request(app).post("/api/v1/auth/register").send({ email, password: PASSWORD });
  const response = await request(app).post("/api/v1/auth/login").send({ email, password: PASSWORD });
  return { Authorization: `Bearer ${response.body.accessToken}` };
};

before(async () => {
  await connectDB();
});

after(async () => {
  await disconnectDB();
  await mongo.stop();
});

describe("auth", () => {
  test("register, duplicate, weak password and login", async () => {
    let response = await request(app).post("/api/v1/auth/register").send({ email: "Owner@Example.com", password: PASSWORD });
    assert.equal(response.status, 201);
    assert.equal(response.body.email, "owner@example.com");
    assert.deepEqual(Object.keys(response.body).sort(), ["createdAt", "email", "id"]);

    response = await request(app).post("/api/v1/auth/register").send({ email: "owner@example.com", password: PASSWORD });
    assert.deepEqual([response.status, response.body.message], [409, "Email is already registered."]);

    response = await request(app).post("/api/v1/auth/register").send({ email: "weak@example.com", password: "weakpw" });
    assert.equal(response.status, 400);
    assert.equal(response.body.details[0].field, "body.password");
    assert.ok(!JSON.stringify(response.body).includes("weakpw"));

    response = await request(app).post("/api/v1/auth/register").send({ email: "x@example.com", password: PASSWORD, role: "admin" });
    assert.equal(response.status, 400);
  });

  test("login messages and token checks", async () => {
    for (const email of ["owner@example.com", "nobody@example.com"]) {
      const response = await request(app).post("/api/v1/auth/login").send({ email, password: "Wrong!Pass1" });
      assert.deepEqual([response.status, response.body.message], [401, "Invalid email or password."]);
    }
    const headers = await registerAndLogin("me@example.com");
    let response = await request(app).get("/api/v1/auth/me").set(headers);
    assert.deepEqual(Object.keys(response.body).sort(), ["email", "id"]);
    assert.equal(response.body.email, "me@example.com");
    response = await request(app).get("/api/v1/auth/me");
    assert.equal(response.status, 401);
    response = await request(app).get("/api/v1/auth/me").set({ Authorization: "Bearer abc" });
    assert.equal(response.status, 401);
    response = await request(app).get("/api/v1/auth/me").set({ Authorization: headers.Authorization.replace("Bearer ", "") });
    assert.equal(response.status, 401);
  });
});

describe("expenses", () => {
  test("create, list with filters, ownership, update, delete", async () => {
    const owner = await registerAndLogin("spender@example.com");
    const other = await registerAndLogin("other@example.com");
    const ids = [];
    let response;
    for (const [index, category, date] of [[0, "food", "2026-01-05"], [1, "travel", "2026-01-10"], [2, "food", "2026-02-01"]]) {
      response = await request(app).post("/api/v1/expenses").set(owner).send({ title: `  Lunch ${index} `, amount: 12.5, category, expenseDate: date });
      assert.equal(response.status, 201);
      ids.push(response.body.id);
    }
    response = await request(app).get(`/api/v1/expenses/${ids[2]}`).set(owner);
    assert.equal(response.body.title, "Lunch 2");
    assert.deepEqual(Object.keys(response.body).sort(), ["amount", "category", "createdAt", "expenseDate", "id", "title", "updatedAt"]);

    response = await request(app).post("/api/v1/expenses").set(owner).send({ title: "x", amount: -1, category: "food", expenseDate: "2026-01-01" });
    assert.equal(response.status, 400);
    response = await request(app).post("/api/v1/expenses").set(owner).send({ title: "x", amount: 1, category: "food", expenseDate: "2026-01-01", user: "someone" });
    assert.equal(response.status, 400);

    response = await request(app).get("/api/v1/expenses?category=food&pageSize=1").set(owner);
    assert.deepEqual([response.body.total, response.body.items.length, response.body.totalPages, response.body.pageSize], [2, 1, 2, 1]);
    assert.deepEqual(Object.keys(response.body.items[0]).sort(), ["amount", "category", "createdAt", "expenseDate", "id", "title", "updatedAt"]);
    assert.equal(response.body.items[0].title, "Lunch 2");
    assert.equal((await request(app).get("/api/v1/expenses?search=lunch 1").set(owner)).body.total, 1);
    assert.equal((await request(app).get("/api/v1/expenses?search=.*").set(owner)).body.total, 0);
    assert.equal((await request(app).get("/api/v1/expenses?startDate=2026-01-06&endDate=2026-01-31").set(owner)).body.total, 1);
    assert.equal((await request(app).get("/api/v1/expenses?startDate=2026-02-01&endDate=2026-01-01").set(owner)).status, 400);
    assert.equal((await request(app).get("/api/v1/expenses?pageSize=101").set(owner)).status, 400);
    assert.deepEqual((await request(app).get("/api/v1/expenses?category=none").set(owner)).body.items, []);

    assert.equal((await request(app).get(`/api/v1/expenses/${ids[0]}`).set(other)).status, 404);
    assert.equal((await request(app).get("/api/v1/expenses").set(other)).body.total, 0);
    assert.equal((await request(app).get("/api/v1/expenses/not-an-id").set(owner)).status, 404);

    assert.equal((await request(app).patch(`/api/v1/expenses/${ids[0]}`).set(owner).send({})).status, 400);
    assert.equal((await request(app).patch(`/api/v1/expenses/${ids[0]}`).set(owner).send({ title: null })).status, 400);
    assert.equal((await request(app).patch(`/api/v1/expenses/${ids[0]}`).set(other).send({ amount: 99.99 })).status, 404);
    response = await request(app).patch(`/api/v1/expenses/${ids[0]}`).set(owner).send({ amount: 99.99 });
    assert.deepEqual([response.status, response.body.amount, response.body.title], [200, 99.99, "Lunch 0"]);

    assert.equal((await request(app).delete(`/api/v1/expenses/${ids[0]}`).set(other)).status, 404);
    response = await request(app).delete(`/api/v1/expenses/${ids[0]}`).set(owner);
    assert.deepEqual([response.status, response.text], [204, ""]);
    assert.equal((await request(app).get(`/api/v1/expenses/${ids[0]}`).set(owner)).status, 404);
  });
});

describe("errors", () => {
  test("shared error shape for unknown routes and bad JSON", async () => {
    let response = await request(app).get("/api/v1/nope");
    assert.deepEqual(response.body, { status: "error", message: "Route not found." });
    response = await request(app).post("/api/v1/auth/login").set("Content-Type", "application/json").send("{bad json");
    assert.equal(response.status, 400);
  });

  test("health is 200 with the database and 424 without it", async () => {
    assert.equal((await request(app).get("/health")).status, 200);
    const headers = await registerAndLogin("down@example.com");
    await disconnectDB();
    let response = await request(app).get("/health");
    assert.deepEqual([response.status, response.body.message], [424, "Database dependency is unavailable."]);
    response = await request(app).get("/api/v1/expenses").set(headers);
    assert.equal(response.status, 424);
    assert.ok(!JSON.stringify(response.body).includes("mongodb://"));
    await connectDB();
  });
});
