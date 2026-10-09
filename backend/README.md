# JobHunt AI Backend

Python FastAPI + LangGraph backend for the JobHunt AI personal career copilot.

See the repository root [README.md](../README.md) for the full product requirements
document, setup instructions, and usage guide.

## Layout

```
app/
  config.py       # environment-based settings (pydantic-settings)
  database.py     # async SQLAlchemy engine + LangGraph checkpoint saver
  ...
tests/           # pytest suite
```