# Local LLM Models

PC Fixer's Assistant tab loads a GGUF model from this folder at runtime. Model files are not committed to git (see `.gitignore`).

## Recommended model

- **Model:** Llama-3.2-3B-Instruct
- **Format:** GGUF
- **Quantization:** Q4_K_M (~2 GB)
- **Filename:** `llama-3.2-3b-instruct-q4_k_m.gguf`

## Download

1. Open the Hugging Face model page, for example:
   - [bartowski/Llama-3.2-3B-Instruct-GGUF](https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF)
2. Download the `Q4_K_M` variant (`.gguf` file).
3. Place the file in this directory as:

```
models/llama-3.2-3b-instruct-q4_k_m.gguf
```

Exact Hugging Face filenames vary by uploader. Rename the downloaded file to match the name above, or update `DEFAULT_MODEL_FILENAME` in `app/ai_engine.py`.

## Requirements

- ~4 GB free RAM recommended for inference with this model
- The chat template in `app/ai_engine.py` is configured for Llama-3.2-Instruct; use a matching model or update the template

## GPU acceleration (optional)

For NVIDIA GPUs, reinstall `llama-cpp-python` with CUDA support:

```powershell
$env:CMAKE_ARGS="-DGGML_CUDA=on"
.\venv\Scripts\python.exe -m pip install llama-cpp-python --force-reinstall --no-cache-dir
```

## Packaging (PyInstaller)

When building a standalone executable, include the model as data:

```powershell
pyinstaller --add-data "models\llama-3.2-3b-instruct-q4_k_m.gguf;models" main.py
```
