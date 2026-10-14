# Ollama Chat

A small local chatbot that streams answers from Ollama. It defaults to the
`qwen2.5:3b` model when that model is installed and otherwise lets you choose
from the models Ollama reports.

## Run it

1. Start Ollama and make sure your model is available with `ollama list`.
2. From this project folder, run `py server.py`.
3. Open [http://localhost:3000](http://localhost:3000).

The app uses `http://localhost:11434` as its Ollama host by default. To connect
to an Ollama server on a different host, set `OLLAMA_HOST` before starting the
app, for example in PowerShell:

```powershell
$env:OLLAMA_HOST = "http://192.168.1.20:11434"
py server.py
```

The chatbot UI and Ollama connection run locally; no API key or cloud account is
needed.
