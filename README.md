# Dynamic LangChain Chat CLI

A simple, interactive command-line interface built with Python and LangChain. It allows you to dynamically switch between **Google Gemini** and **OpenRouter** LLMs (with active free models) using dynamic API keys.

## Features
- **Dynamic Providers**: Supports Google Gemini and OpenRouter.
- **Dynamic API Keys**: Prompts for your API key if it's not set in the environment.
- **Active Free Models**: Configured to use working, active free models on OpenRouter (e.g. Gemini-2.5-Flash, Llama-3.3-70B, DeepSeek R1).
- **Session Switching**: Type `menu` during a chat to change providers, models, or keys without terminating the application.
- **Token Efficiency**: Configured with a `max_tokens` limit (`512`) to prevent credit-check errors on OpenRouter.

## Setup Instructions

### 1. Requirements
Ensure you have Python 3.10+ installed.

### 2. Install Dependencies
Set up the virtual environment and install the required libraries:

```bash
# Initialize virtual environment
python -m venv .venv

# Activate virtual environment
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 3. Environment Configuration (Optional)
Copy `.env.example` to `.env` and configure your API keys:
```bash
cp .env.example .env
```
Inside `.env`:
```ini
GEMINI_API_KEY=your_gemini_api_key
OPENROUTER_API_KEY=your_openrouter_api_key
```
*If environment keys are not configured, the CLI will prompt you to type them at startup.*

## Usage

Start the CLI application:
```bash
python app.py
```

### Navigation Commands
While chatting, type:
- `menu` - Go back to model/provider selection.
- `exit` or `quit` - Terminate the script.
