# Azure OpenAI Migration

Replace the Anthropic Claude backend with Azure OpenAI, using the `NTangibleMarketingBrain` resource deployed in `eastus`.

## Decision Summary

- **Provider**: Azure OpenAI (replacing Anthropic Claude)
- **Default model**: `gpt-5.4-nano` (configurable via env var)
- **Approach**: Direct OpenAI SDK with Azure configuration
- **Scope**: Full replacement, no fallback to Claude

## Azure Resource Details

- **Resource name**: NTangibleMarketingBrain
- **Region**: eastus
- **Endpoint**: `https://ntangiblemarketingbrain.openai.azure.com/`
- **Deployed models**: gpt-5-chat, gpt-5.1-codex-mini, gpt-5.4-mini, gpt-5.4-nano

## Changes

### 1. Dependencies (`pyproject.toml`)

Replace `anthropic>=0.40.0` with `openai>=1.0.0`.

### 2. Configuration (`app/config.py`)

Remove `anthropic_api_key`. Add:

| Setting | Env Var | Default |
|---|---|---|
| `azure_openai_api_key` | `AZURE_OPENAI_API_KEY` | (required) |
| `azure_openai_endpoint` | `AZURE_OPENAI_ENDPOINT` | (required) |
| `azure_openai_api_version` | `AZURE_OPENAI_API_VERSION` | `2024-12-01-preview` |
| `azure_openai_model` | `AZURE_OPENAI_MODEL` | `gpt-5.4-nano` |

### 3. Agent Files

Four files change: `content_writer.py`, `linkedin_writer.py`, `instagram_writer.py`, `newsletter_writer.py`.

Each agent applies the same transformation:

**Import**: `import anthropic` -> `from openai import AzureOpenAI`

**Client init**:
```python
# Before
client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

# After
client = AzureOpenAI(
    api_key=settings.azure_openai_api_key,
    azure_endpoint=settings.azure_openai_endpoint,
    api_version=settings.azure_openai_api_version,
)
```

**API call**:
```python
# Before
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    system=prompt["system"],
    messages=[{"role": "user", "content": prompt["user"]}],
)

# After
response = client.chat.completions.create(
    model=settings.azure_openai_model,
    max_tokens=1024,
    messages=[
        {"role": "system", "content": prompt["system"]},
        {"role": "user", "content": prompt["user"]},
    ],
)
```

**Response parsing**:
```python
# Before
raw_text = response.content[0].text

# After
raw_text = response.choices[0].message.content
```

**Usage / cost logging**:
```python
# Before
"tokens_in": response.usage.input_tokens,
"tokens_out": response.usage.output_tokens,
"cost_estimate": (response.usage.input_tokens * 0.003 + response.usage.output_tokens * 0.015) / 1000,

# After
"tokens_in": response.usage.prompt_tokens,
"tokens_out": response.usage.completion_tokens,
"cost_estimate": (response.usage.prompt_tokens * 0.00005 + response.usage.completion_tokens * 0.0004) / 1000,
```

Model logged changes from hardcoded `"claude-sonnet-4-6"` to `settings.azure_openai_model`.

### 4. Environment Files

**`.env.example`**: Replace `ANTHROPIC_API_KEY=sk-ant-...` with:
```
AZURE_OPENAI_API_KEY=your-key-here
AZURE_OPENAI_ENDPOINT=https://ntangiblemarketingbrain.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-12-01-preview
AZURE_OPENAI_MODEL=gpt-5.4-nano
```

**`tests/conftest.py`**: Replace `ANTHROPIC_API_KEY` test default with:
```python
os.environ.setdefault("AZURE_OPENAI_API_KEY", "test-azure-key")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
os.environ.setdefault("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
os.environ.setdefault("AZURE_OPENAI_MODEL", "gpt-5.4-nano")
```

### 5. What Does NOT Change

- Prompt content (system prompts, user prompts) -- model-agnostic
- JSON response parsing logic and field validation
- `build_*_prompt()` functions
- Non-LLM agents (compliance, campaign_planner, competitor_scout, blog_writer, lead_nurture, video_writer)

## Cost Comparison

| Model | Input (per 1M tokens) | Output (per 1M tokens) |
|---|---|---|
| Claude Sonnet (before) | $3.00 | $15.00 |
| gpt-5.4-nano (after) | $0.05 | $0.40 |

~60x cheaper input, ~37x cheaper output.
