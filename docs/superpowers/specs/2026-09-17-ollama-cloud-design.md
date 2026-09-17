# Ollama Cloud provider

## Goal

Add a separate LLM provider `ollama_cloud` that calls Ollama Cloud (`https://ollama.com/v1`) with `OLLAMA_API_KEY` from `.env`. Local `ollama` stays unchanged.

## Decisions

- Separate provider value: `ollama_cloud` (not merged into local `ollama`)
- Auth: `.env` only → `OLLAMA_API_KEY` (no macOS key field)
- Client: reuse `OpenAIClient` / OpenAI-compatible Chat Completions (same pattern as OpenRouter/xAI)
- Base URL: `https://ollama.com/v1`
- Model IDs: API names (e.g. `gemma4:31b`), not `:cloud` CLI aliases
- Any model ID accepted by validator (same as local ollama / openrouter)

## Surfaces

- `tradingagents/llm_clients/openai_client.py` — provider config
- `tradingagents/llm_clients/factory.py` — route to OpenAIClient
- `tradingagents/llm_clients/validators.py` — accept any model
- `tradingagents/llm_clients/model_catalog.py` — cloud model presets
- `cli/utils.py` — CLI provider list (return stable id `ollama_cloud`)
- `cli/macos_bridge.py` — PROVIDERS entry for macOS UI catalog
- `.env.example` — `OLLAMA_API_KEY=`
- Tests: bridge catalog + validation for `ollama_cloud`

## Out of scope

- macOS API key UI
- Changing local Ollama / docker-compose ollama profile
- Official `ollama` Python SDK client

## Callers

Not imported by runtime code. Read by agents/humans during planning (`docs/superpowers/plans/2026-09-17-ollama-cloud.md` and implementers). No prior file in `docs/superpowers/specs/`.
