# 🤖 Adjnt: Local AI WhatsApp Assistant

Adjnt is a privacy-first, local AI assistant that turns your WhatsApp into a powerful productivity hub. It uses **Llama 3.2** via Ollama for brainpower, **FastAPI** for processing, and **WAHA** (WhatsApp HTTP API) to communicate.



## 🚀 Features
- **Privacy First**: Everything runs locally. Your messages never leave your machine.
- **Task Vault**: Automatically detects tasks and saves them to a local SQLite database.
- **AI Chat**: General assistance powered by local LLMs (Ollama).
- **Dockerized**: One-command setup using Docker Compose.

---

## 🛠️ Prerequisites
Before starting, ensure you have the following installed and running:
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [Ollama](https://ollama.com/) (Run `ollama run llama3.2` once to download the model)

---

## 📦 Installation & Setup

1. **Clone the repository** and open it in VS Code.
2. **Permissions**: In your VS Code terminal (Git Bash or Zsh), give the scripts permission to run:
   ```bash
   chmod +x *.sh
   ```
## Launch: Run the setup script:
```
./setup.sh
```