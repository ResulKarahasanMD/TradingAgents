# Ollama Cloud Implementation Plan

> Implemented inline after design approval.

**Goal:** Add `ollama_cloud` provider using OpenAI-compatible API + `OLLAMA_API_KEY`.

**Architecture:** Extend `OpenAIClient` provider map. Wire CLI + macOS bridge. No new deps.

## Tasks

- [x] `openai_client` / `factory` / `validators` / `model_catalog`
- [x] `cli/macos_bridge.py` + `cli/utils.py` (stable id `ollama_cloud`)
- [x] `.env.example` + ensure `.env` has empty `OLLAMA_API_KEY=`
- [x] Tests updated

## Callers

Plan read by agents/humans only; not imported by runtime.
