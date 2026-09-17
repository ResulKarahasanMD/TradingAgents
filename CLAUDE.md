# CLAUDE.md — tradingagents

## Ne bu
`TauricResearch/TradingAgents` klonu — çok-ajanlı LLM finansal-analiz **araştırma çerçevesi**. Python, uv (`uv.lock`), CLI (`cli/`, `main.py`), `tradingagents/` paketi, Docker. macOS kabuğu `TradingAgentsMac/`. Dal `main`.

## Komutlar
```bash
uv venv --python 3.12 && uv pip install -e .
python main.py
python -m cli.main
```

## ⚠️ Önemli sınır — finansal işlem yok
Bu bir **analiz/araştırma** aracı. Global güvenlik kuralı gereği:
- **Hiçbir alım-satım, transfer veya para hareketi yürütme.** Çıktı hipotez/analizdir.
- **Kişiselleştirilmiş yatırım tavsiyesi verme** — lisanslı danışman değilsin. Sorulursa bunu belirt.
- Broker/borsa API'sine emir gönderen bir kodu kullanıcı onayı olmadan çalıştırma.

## Dikkat
- `.env` API anahtarları (LLM, finans veri) — okuma/dışarı verme/commit etme.
- `data_cache/`, `results/`, `output/` üretilmiş; kaynak sanma.
- Upstream klon; push hedefin yok.
