# 🤖 Adjnt: Local AI WhatsApp Assistant

Adjnt is a privacy-first, local AI assistant that turns your WhatsApp into a powerful productivity hub. It uses **Llama 3.2** for brainpower, **FastAPI** for processing, and **WAHA** (WhatsApp HTTP API) to communicate.

## 🚀 Features
- **Privacy First**: Everything runs locally. Your messages never leave your machine to train big models.
- **Task Vault**: Automatically detects tasks in conversation and saves them to a local SQLite database.
- **AI Chat**: General assistance powered by local LLMs via Ollama.
- **LID Support**: Fully compatible with modern WhatsApp LID (Link ID) masking.

---

## 🛠️ Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (For the WhatsApp engine)
- [Ollama](https://ollama.com/) (For the AI model)
- [Python 3.10+](https://www.python.org/downloads/)

---

## 📦 Installation & Setup

This project requires **three terminal windows** to run simultaneously.

### 1. Start the WhatsApp Engine (Terminal 1)
Run the WAHA Docker container. This bridge allows your Python code to talk to WhatsApp.

```bash
docker run -d --name waha -p 3001:3000 \
  --add-host=host.docker.internal:host-gateway \
  -e "WAHA_SECURITY_MODE=DISABLED" \
  -e "WAHA_NO_API_KEY=True" \
  -e "WAHA_DASHBOARD_NO_PASSWORD=True" \
  -e "WHATSAPP_DEFAULT_ENGINE=NOWEB" \
  -e "WHATSAPP_HOOK_URL=[http://host.docker.internal:8000/webhook](http://host.docker.internal:8000/webhook)" \
  -e "WHATSAPP_HOOK_EVENTS=message,message.any" \
  -v waha_sessions:/app/.sessions \
  devlikeapro/waha
  ```

### 2. Start the FastAPI Brain (Terminal 2)
  # Activate virtual environment
  ```bash
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the server (Must be host 0.0.0.0 for Docker to find it)
uvicorn main:app --reload --host 0.0.0.0 --port 8000
  ```
### 3. Initialize Session (Terminal 3)
Wake up the WhatsApp session (one-time command per restart):
```bash
curl -X POST [http://127.0.0.1:3001/api/sessions/start](http://127.0.0.1:3001/api/sessions/start) -H "Content-Type: application/json" -d '{"name": "default"}'
```

### 4.⚙️ Configuration
WAHA Dashboard: http://127.0.0.1:3001/dashboard/

QR Code (if scan needed): http://127.0.0.1:3001/api/screenshot?session=default

AI Model: Ensure you have run ollama run llama3.2 at least once.

### 5.📝 Usage
Chat: Just text the bot anything.

Tasks: Send "Remind me to..." or "Add to my list..." to save to the vault.

Privacy: Send "What is your privacy policy?" for local storage info.