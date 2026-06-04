# MindAI: Mental Health Platform

MindAI is a Streamlit-based mental health support and research application powered by local LLMs through Ollama.

Repository: [Aanshi22/mental-health-ai](https://github.com/Aanshi22/mental-health-ai)

## Features

- Home dashboard with platform overview
- Chat Q&A for mental health-related conversations
- 40-question self-assessment across 8 mental wellness domains
- PDF analysis and question answering from uploaded documents
- Image analysis using a vision model (via Ollama)
- AI prediction module with severity/urgency-style output

## Tech Stack

- Python 3.10+
- Streamlit
- Ollama (local model serving)
- PyPDF2
- Pillow
- python-dotenv

## Project Structure

```text
mental-health-ai/
|- app.py
|- requirements.txt
|- README.md
```

## Prerequisites

1. Install Python 3.10 or newer.
2. Install Ollama and make sure it is running locally.
3. Pull required Ollama models.

Example:

```powershell
ollama pull codellama:latest
ollama pull llava
```

You can use other compatible models if preferred.

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the project root:

```env
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=codellama:latest
OLLAMA_VISION_MODEL=llava
```

Notes:

- `OLLAMA_HOST` defaults to `http://localhost:11434` if not set.
- `OLLAMA_MODEL` is used for text features.
- `OLLAMA_VISION_MODEL` is required for Image Analysis.

## Run the App

```powershell
python -m streamlit run app.py
```

Then open the local URL shown in terminal (usually `http://localhost:8501` or next available port).

## Troubleshooting

- Ollama server not reachable:
	- Ensure Ollama is installed and running.
	- Check `OLLAMA_HOST` in `.env`.
- Vision model errors:
	- Confirm the model exists locally:
		```powershell
		ollama list
		```
	- Pull missing model:
		```powershell
		ollama pull llava
		```
- Dependency issues:
	- Reinstall dependencies in active environment:
		```powershell
		pip install -r requirements.txt
		```

## Security

- Do not commit `.env` or secrets to Git.
- Rotate any keys that were accidentally exposed.

## Disclaimer

This project is for research and informational purposes only. It is not a medical diagnosis tool and does not replace professional mental health care.

try: https://mental-health-ai-r24azkuj4m5bt2zoqme6wb.streamlit.app/
