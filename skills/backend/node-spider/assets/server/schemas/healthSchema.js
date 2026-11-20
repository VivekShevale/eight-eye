// ---- Response schemas ----

export const toHealthResponse = (databaseStatus) => ({
  status: "ok",
  database: databaseStatus,
});
