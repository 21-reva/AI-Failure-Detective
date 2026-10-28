# 🔍 AI Failure Detective & Log Anomaly Engine

### 🤖 AI-Powered Log Analysis • Error Detection • Root Cause Analysis

An AI-powered log analysis tool that automatically identifies errors in application logs and uses **Google Gemini AI** to analyze them, explain potential causes, and suggest possible solutions.

Built with **Python, FastAPI, Pandas, and Google Gemini**, this project demonstrates how AI can help developers understand application failures and troubleshoot issues more efficiently. 🚀

---

## ✨ Features

🔎 **Automated Error Detection**
Extracts `ERROR` and `CRITICAL` entries from application logs.

🧠 **AI-Powered Root Cause Analysis**
Uses Google Gemini to analyze detected errors and generate explanations, potential causes, and suggested solutions.

📂 **Log File Upload**
Upload `.log` or `.txt` files for automated analysis.

⚡ **REST API**
Provides API endpoints through FastAPI for submitting logs and retrieving analysis results.

📊 **Structured Error Processing**
Uses Pandas to process extracted log entries into structured data.

📄 **JSON Reports**
Stores extracted errors and analysis results in JSON format for easier inspection and further processing.

🩺 **Health Check Endpoint**
Includes an endpoint to check whether the API service is running.

---

## 🛠️ Tech Stack

| Technology       | Purpose                                            |
| ---------------- | -------------------------------------------------- |
| 🐍 Python        | Core application logic                             |
| ⚡ FastAPI        | Building REST API endpoints                        |
| 🧠 Google Gemini | AI-powered error analysis                          |
| 🐼 Pandas        | Processing and structuring log data                |
| 📦 JSON          | Storing structured errors and analysis results     |
| 🔐 python-dotenv | Loading API credentials from environment variables |
| 🧪 Pytest        | Python testing framework                           |

---

## ⚙️ How It Works

```text
        📂 Application Logs
                 |
                 ▼
       🔍 Log Parsing & Processing
                 |
                 ▼
        🚨 Error Extraction
                 |
                 ▼
       🧠 Google Gemini Analysis
                 |
                 ▼
      📋 Root Cause Analysis Results
                 |
                 ▼
          📄 JSON Output
```

### 🔄 Workflow

1. **Input:** Provide application logs through a file upload or text input.
2. **Parsing:** The log parser processes the input and identifies error entries.
3. **Extraction:** Relevant `ERROR` and `CRITICAL` entries are extracted.
4. **AI Analysis:** Google Gemini analyzes the extracted errors.
5. **Results:** The API returns structured findings, including the original error information and AI-generated analysis.

> 💡 The AI provides potential explanations and troubleshooting suggestions; its conclusions should be verified against the actual application and environment.

---

## 🌐 API Endpoints

The application exposes the following endpoints:

| Method | Endpoint        | Description                                |
| ------ | --------------- | ------------------------------------------ |
| `GET`  | `/`             | Welcome endpoint                           |
| `GET`  | `/health`       | Checks API availability                    |
| `POST` | `/analyze-text` | Analyzes log text                          |
| `POST` | `/analyze-file` | Analyzes an uploaded `.log` or `.txt` file |

### 📖 Interactive API Documentation

FastAPI automatically provides interactive API documentation when the application is running.

Open:

`http://127.0.0.1:8000/docs`

Use this page to explore endpoints, submit requests, and inspect responses.

---

## 🚀 Getting Started

Follow these steps to run the project locally.

### 1️⃣ Clone the Repository

```bash
git clone https://github.com/21-reva/AI-Failure-Detective.git
```

Navigate into the project directory:

```bash
cd AI-Failure-Detective
```

### 2️⃣ Create a Virtual Environment

```bash
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 3️⃣ Install Dependencies

```bash
python -m pip install -r requirements.txt
```

### 4️⃣ Configure Your Gemini API Key 🔐

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_gemini_api_key
```

Replace `your_gemini_api_key` with your own API key.

⚠️ **Security reminder:** Never upload your `.env` file or expose your API key publicly. The repository's `.gitignore` should exclude `.env`.

### 5️⃣ Start the API Server

From the project root, run:

```bash
python -m uvicorn src.main:app --reload
```

The server should start locally at:

`http://127.0.0.1:8000`

### 6️⃣ Explore the API 🎯

Open the interactive documentation:

`http://127.0.0.1:8000/docs`

Select an endpoint, click **Try it out**, provide the required input, and execute the request.

---

## 📁 Project Structure

```text
AI-Failure-Detective/
│
├── logs/
│   ├── sample_log.log
│   ├── extracted_errors.json
│   ├── analysis_results.json
│   └── rca_report.json
│
├── src/
│   ├── __init__.py
│   ├── log_parser.py
│   ├── ai_analyzer.py
│   └── main.py
│
├── .gitignore
├── requirements.txt
├── README.md
└── .env                 # Local configuration; not committed
```

### 📌 Core Modules

* **`log_parser.py`** — Parses log text, extracts error entries, and produces structured error data.
* **`ai_analyzer.py`** — Sends extracted errors to Google Gemini for analysis and supports saving analysis results to JSON.
* **`main.py`** — Defines the FastAPI application and exposes endpoints for text-based and file-based log analysis.

---

## 🎯 Project Goals

This project explores how AI can support software debugging by:

* Automating repetitive log inspection.
* Converting unstructured error messages into structured data.
* Generating explanations for application failures.
* Providing API-based access to AI-assisted troubleshooting.

---

## 🔮 Future Improvements

🚧 Potential enhancements include:

* 📈 Log anomaly detection using statistical or machine-learning methods.
* 🔗 Correlating related errors across multiple log entries.
* 📊 A dashboard for exploring errors and analysis results.
* 🧪 Automated tests for log parsing and API endpoints.
* 🔔 Alerts for critical errors.
* 📚 Historical analysis to identify recurring failures.

*These are planned enhancements, not claims about existing functionality.*

---

## 👩‍💻 Author

**Reva**

🔗 GitHub: [@21-reva](https://github.com/21-reva)

---

### ⭐ If you find this project interesting, consider giving the repository a star!

💡 *Built to explore the intersection of Artificial Intelligence and Software Reliability.*
