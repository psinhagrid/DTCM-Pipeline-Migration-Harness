# RLM Migration Agent

Replaces the supervisor + subagent hierarchy with a single fast-rlm agent.

## Start LiteLLM proxy (bridges Anthropic key to OpenAI-compatible API)

```bash
source venv/bin/activate
litellm --config rlm/litellm_config.yaml --port 4000
```

## Set environment variables

```bash
export RLM_MODEL_API_KEY=anything        # LiteLLM doesn't need real key here
export RLM_MODEL_BASE_URL=http://localhost:4000/v1
```

Or add to .env:
```
RLM_MODEL_API_KEY=local
RLM_MODEL_BASE_URL=http://localhost:4000/v1
RLM_PRIMARY_MODEL=claude-sonnet-4-6
```

## Run

```python
from rlm.agent import run_migration
result = await run_migration("silver_orders")
```
