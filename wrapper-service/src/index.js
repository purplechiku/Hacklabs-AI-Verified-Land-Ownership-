const express = require("express");
const config = require("./config");
const registerRoute = require("./routes/register");
const ownershipRoute = require("./routes/ownership");

const app = express();
app.use(express.json());

// Simple request log — helpful during integration with the Backend team.
app.use((req, res, next) => {
  console.log(`${new Date().toISOString()} ${req.method} ${req.path}`);
  next();
});

app.get("/health", (req, res) => res.json({ status: "ok", service: "landregistry-wrapper" }));

app.use(registerRoute);
app.use(ownershipRoute);

app.use((req, res) => res.status(404).json({ error: "Not found" }));

// Central error handler — anything thrown synchronously in a route lands here.
app.use((err, req, res, next) => {
  console.error("Unhandled error:", err);
  res.status(500).json({ error: "Internal server error" });
});

app.listen(config.port, () => {
  console.log(`LandRegistry wrapper service listening on port ${config.port}`);
  console.log(`Health check: http://localhost:${config.port}/health`);
});
