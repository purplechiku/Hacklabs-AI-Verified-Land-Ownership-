import { useEffect, useRef, useState } from "react";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

function App() {
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [result, setResult] = useState(null);
  const [records, setRecords] = useState([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState(null);
  const [error, setError] = useState("");
  const [health, setHealth] = useState(null);

  const fileInputRef = useRef(null);

  useEffect(() => {
    loadLedger();
    loadHealth();
  }, []);

  async function loadLedger() {
    try {
      const response = await fetch(`${API_BASE}/api/ledger/recent`);

      if (!response.ok) {
        throw new Error("Could not load ledger.");
      }

      const data = await response.json();
      setRecords(data.records || []);
    } catch {
      setError("Could not connect to the backend.");
    }
  }

  async function loadHealth() {
    try {
      const response = await fetch(`${API_BASE}/api/health`);

      if (!response.ok) {
        throw new Error();
      }

      const data = await response.json();
      setHealth(data);
    } catch {
      setHealth(null);
    }
  }

  function selectFile(selectedFile) {
    setError("");
    setResult(null);

    if (!selectedFile) {
      return;
    }

    const allowedTypes = [
      "application/pdf",
      "image/jpeg",
      "image/png",
      "image/webp",
      "image/bmp",
      "image/tiff",
    ];

    const allowedExtensions = [
      "pdf",
      "jpg",
      "jpeg",
      "png",
      "webp",
      "bmp",
      "tif",
      "tiff",
    ];

    const extension = selectedFile.name
      .split(".")
      .pop()
      ?.toLowerCase();

    if (
      !allowedTypes.includes(selectedFile.type) &&
      !allowedExtensions.includes(extension)
    ) {
      setError(
        "Please upload a PDF, JPG, JPEG, PNG, WEBP, BMP, or TIFF file.",
      );
      return;
    }

    setFile(selectedFile);
  }

  function handleFileChange(event) {
    selectFile(event.target.files?.[0]);
  }

  function handleDrop(event) {
    event.preventDefault();
    setDragging(false);
    selectFile(event.dataTransfer.files?.[0]);
  }

  async function verifyDocument() {
    if (!file) {
      setError("Choose a document first.");
      return;
    }

    setVerifying(true);
    setError("");
    setResult(null);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(`${API_BASE}/api/verify`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Verification failed.");
      }

      setResult(data);

      if (data.ledger?.written) {
        await loadLedger();
      }
    } catch (err) {
      setError(err.message || "Could not verify document.");
    } finally {
      setVerifying(false);
    }
  }

  async function searchLedger(event) {
    event.preventDefault();

    const query = searchQuery.trim();

    if (!query) {
      setSearchResults(null);
      return;
    }

    try {
      const response = await fetch(
        `${API_BASE}/api/search?q=${encodeURIComponent(query)}`,
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Search failed.");
      }

      setSearchResults(data.results || []);
      setError("");
    } catch (err) {
      setError(err.message || "Search failed.");
    }
  }

  function clearSearch() {
    setSearchQuery("");
    setSearchResults(null);
  }

  function formatDate(value) {
    if (!value) {
      return "—";
    }

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
      return value;
    }

    return date.toLocaleString();
  }

  function formatScore(value) {
    if (typeof value !== "number") {
      return "—";
    }

    return `${Math.round(value * 100)}%`;
  }

  function getResultType() {
    if (!result) {
      return null;
    }

    if (result.verified === true) {
      return "verified";
    }

    if (result.status === "Conflict") {
      return "conflict";
    }

    if (
      result.status === "Rejected" ||
      result.document_type === "Non-land document"
    ) {
      return "rejected";
    }

    if (
      result.duplicate_flag ||
      (result.duplicate_matches &&
        result.duplicate_matches.length > 0)
    ) {
      return "conflict";
    }

    return "rejected";
  }

  const resultType = getResultType();

  const displayedRecords =
    searchResults !== null ? searchResults : records;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">अ</div>

          <div>
            <div className="brand-name">
              अधिकारAdhikar
            </div>

            <div className="brand-subtitle">
              Digital Land Registry · Verification Pilot
            </div>
          </div>
        </div>

        <div className="nav-status">
          <span
            className={`status-dot ${
              health?.status === "ok" ? "online" : ""
            }`}
          />

          {health?.status === "ok"
            ? "Service online"
            : "Connecting..."}
        </div>
      </header>

      <main className="container">
        <section className="hero">
          <div>
            <span className="eyebrow">
              DIGITAL LAND VERIFICATION
            </span>

            <h1>
              Every deed read,
              <br />
              checked &amp; recorded.
            </h1>

            <p>
              Upload a property document. Adhikar extracts its
              details, checks them against the existing registry,
              and records clean submissions in the verification
              ledger.
            </p>
          </div>

          <div className="hero-card">
            <div className="hero-card-label">
              LEDGER RECORDS
            </div>

            <div className="hero-card-number">
              {health?.records_stored ?? records.length}
            </div>

            <div className="hero-card-text">
              verified records stored locally
            </div>
          </div>
        </section>

        <section className="workspace">
          <div className="upload-panel">
            <div className="section-heading">
              <div>
                <span className="section-kicker">
                  01 · DOCUMENT
                </span>

                <h2>Submit a property document</h2>
              </div>
            </div>

            <div
              className={`dropzone ${
                dragging ? "dragging" : ""
              } ${file ? "has-file" : ""}`}
              onDragOver={(event) => {
                event.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
              onClick={() =>
                fileInputRef.current?.click()
              }
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.jpg,.jpeg,.png,.webp,.bmp,.tif,.tiff"
                onChange={handleFileChange}
                hidden
              />

              {file ? (
                <>
                  <div className="file-icon">
                    {file.name
                      .split(".")
                      .pop()
                      ?.toUpperCase() || "FILE"}
                  </div>

                  <div className="file-info">
                    <strong>{file.name}</strong>

                    <span>
                      {(file.size / 1024 / 1024).toFixed(2)} MB
                    </span>
                  </div>

                  <button
                    className="change-button"
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation();
                      fileInputRef.current?.click();
                    }}
                  >
                    Change
                  </button>
                </>
              ) : (
                <>
                  <div className="upload-icon">↑</div>

                  <div>
                    <strong>
                      Drag a document here
                    </strong>

                    <span>
                      or click to choose · PDF, JPG, PNG,
                      WEBP
                    </span>
                  </div>
                </>
              )}
            </div>

            <button
              className="verify-button"
              type="button"
              disabled={!file || verifying}
              onClick={verifyDocument}
            >
              {verifying
                ? "Reading & verifying..."
                : "Verify document"}

              {!verifying && <span>→</span>}
            </button>

            <div className="upload-note">
              Images are converted to PDF before OCR
              processing.
            </div>
          </div>

          <div className="result-panel">
            <div className="section-heading">
              <div>
                <span className="section-kicker">
                  02 · RESULT
                </span>

                <h2>Verification result</h2>
              </div>

              {result && (
                <span
                  className={`result-pill ${
                    resultType === "verified"
                      ? "verified"
                      : resultType === "conflict"
                        ? "conflict"
                        : "rejected"
                  }`}
                >
                  {resultType === "verified"
                    ? "Verified"
                    : resultType === "conflict"
                      ? "Conflict"
                      : "Rejected"}
                </span>
              )}
            </div>

            {!result && !verifying && (
              <div className="empty-result">
                <div className="empty-symbol">✓</div>

                <strong>Awaiting document</strong>

                <p>
                  Upload a deed and run verification to see
                  the extracted property information here.
                </p>
              </div>
            )}

            {verifying && (
              <div className="empty-result">
                <div className="spinner" />

                <strong>Analyzing document</strong>

                <p>
                  Reading the document, identifying its type,
                  extracting property details, and checking
                  the registry.
                </p>
              </div>
            )}

            {result && (
              <div className="result-content">
                {resultType === "verified" && (
                  <div className="result-banner">
                    <div className="result-icon success">
                      ✓
                    </div>

                    <div>
                      <strong>
                        Document verified
                      </strong>

                      <span>
                        No matching registry record was
                        found.
                      </span>
                    </div>
                  </div>
                )}

                {resultType === "conflict" && (
                  <div className="result-banner">
                    <div className="result-icon danger">
                      !
                    </div>

                    <div>
                      <strong>
                        Potential registry conflict
                      </strong>

                      <span>
                        This property appears to match an
                        existing registry record.
                      </span>
                    </div>
                  </div>
                )}

                {resultType === "rejected" && (
                  <div className="result-banner">
                    <div className="result-icon danger">
                      !
                    </div>

                    <div>
                      <strong>
                        Document rejected
                      </strong>

                      <span>
                        {result.reason ||
                          "The uploaded document does not appear to be a land or property document."}
                      </span>
                    </div>
                  </div>
                )}

                {resultType === "rejected" &&
                  result.document_type && (
                    <div className="document-type">
                      <span>Detected document type</span>
                      <strong>
                        {result.document_type}
                      </strong>
                    </div>
                  )}

                <div className="fields-grid">
                  <Field
                    label="Owner name"
                    value={result.record?.owner_name}
                  />

                  <Field
                    label="Plot number"
                    value={result.record?.plot_number}
                  />

                  <Field
                    label="Survey number"
                    value={result.record?.survey_number}
                  />

                  <Field
                    label="Area"
                    value={
                      result.record?.area_sqft
                        ? `${result.record.area_sqft} sq ft`
                        : null
                    }
                  />

                  <Field
                    label="Registration date"
                    value={
                      result.record?.registration_date
                    }
                  />

                  <Field
                    label="Confidence"
                    value={formatScore(
                      result.record?.confidence_score,
                    )}
                  />

                  <div className="field full">
                    <span>Address</span>

                    <strong>
                      {result.record?.address || "—"}
                    </strong>
                  </div>
                </div>

                {result.document_analysis && (
                  <div className="document-analysis">
                    <div className="matches-title">
                      Document analysis
                    </div>

                    <div className="analysis-row">
                      <span>Extraction method</span>

                      <strong>
                        {result.document_analysis
                          .extraction_method || "—"}
                      </strong>
                    </div>

                    {result.document_analysis
                      .land_keyword_hits?.length > 0 && (
                      <div className="analysis-row">
                        <span>Land indicators</span>

                        <strong>
                          {result.document_analysis.land_keyword_hits.join(
                            ", ",
                          )}
                        </strong>
                      </div>
                    )}

                    {result.document_analysis
                      .non_land_keyword_hits?.length > 0 && (
                      <div className="analysis-row">
                        <span>Non-land indicators</span>

                        <strong>
                          {result.document_analysis.non_land_keyword_hits.join(
                            ", ",
                          )}
                        </strong>
                      </div>
                    )}
                  </div>
                )}

                {result.duplicate_matches?.length > 0 && (
                  <div className="matches">
                    <div className="matches-title">
                      Matching registry records
                    </div>

                    {result.duplicate_matches.map(
                      (match) => (
                        <div
                          className="match-row"
                          key={`${match.record_id}-${match.plot_number}`}
                        >
                          <div>
                            <strong>
                              {match.plot_number ||
                                "Unknown plot"}
                            </strong>

                            {match.owner_name && (
                              <span>
                                {match.owner_name}
                              </span>
                            )}
                          </div>

                          <strong>
                            {formatScore(
                              match.similarity_score,
                            )}
                          </strong>
                        </div>
                      ),
                    )}
                  </div>
                )}

                <div className="ledger-result">
                  <span>
                    {result.ledger?.written
                      ? "✓ Written to verification ledger"
                      : "⚠ Not written to ledger"}
                  </span>

                  {result.ledger?.record_id && (
                    <code>
                      {result.ledger.record_id}
                    </code>
                  )}
                </div>
              </div>
            )}
          </div>
        </section>

        {error && (
          <div className="error-banner">
            <strong>Error</strong>

            <span>{error}</span>

            <button
              type="button"
              onClick={() => setError("")}
            >
              ×
            </button>
          </div>
        )}

        <section className="ledger-section">
          <div className="ledger-header">
            <div>
              <span className="section-kicker">
                03 · LEDGER
              </span>

              <h2>
                {searchResults !== null
                  ? "Search results"
                  : "Recently written to ledger"}
              </h2>
            </div>

            <form
              className="search"
              onSubmit={searchLedger}
            >
              <input
                value={searchQuery}
                onChange={(event) =>
                  setSearchQuery(event.target.value)
                }
                placeholder="Search owner, plot, survey..."
              />

              <button type="submit">
                Search
              </button>

              {searchResults !== null && (
                <button
                  type="button"
                  className="clear-button"
                  onClick={clearSearch}
                >
                  Clear
                </button>
              )}
            </form>
          </div>

          {displayedRecords.length === 0 ? (
            <div className="ledger-empty">
              {searchResults !== null
                ? "No matching records found."
                : "No verified records have been written yet."}
            </div>
          ) : (
            <div className="ledger-list">
              {displayedRecords.map((record) => (
                <div
                  className="ledger-row"
                  key={record.record_id}
                >
                  <div className="ledger-id">
                    {record.plot_number || "—"}
                  </div>

                  <div className="ledger-owner">
                    <strong>
                      {record.owner_name ||
                        "Unknown owner"}
                    </strong>

                    <span>
                      {record.address ||
                        "No address available"}
                    </span>
                  </div>

                  <div className="ledger-date">
                    <span>Verified</span>

                    <strong>
                      {formatDate(
                        record.verified_at,
                      )}
                    </strong>
                  </div>

                  <div className="ledger-confidence">
                    {formatScore(
                      record.confidence_score,
                    )}
                  </div>

                  <div className="ledger-status">
                    Verified
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>

      <footer>
        <span>
          अधिकारAdhikar · Digital Land Registry
        </span>

        <span>Verification Pilot</span>
      </footer>
    </div>
  );
}

function Field({ label, value, full = false }) {
  return (
    <div className={`field ${full ? "full" : ""}`}>
      <span>{label}</span>

      <strong>{value || "—"}</strong>
    </div>
  );
}

export default App;

