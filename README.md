# EvaliQA plugin for Claude Code

Send your Claude Code sessions to [EvaliQA](https://evaliqa.ai) for evaluation.

Claude Code can export OpenTelemetry traces of a session (structure, timings,
tokens, cost, and the output of Read, Edit, Write and Bash). What those traces
never carry is the text that matters most for judging quality: the agent's own
final answer, and the result of `Agent`, `AskUserQuestion` and MCP tool calls.
This plugin closes that gap. When a turn ends it reads the session transcript
Claude Code already writes to disk and posts it to EvaliQA, which folds the text
into the matching trace. The two halves join on ids both sides already carry, so
there is nothing to correlate by hand.

## What it sends, and when

- On the `Stop` and `SessionEnd` hooks, the plugin runs a small stdlib-only
  Python script that reads the session transcript (and any subagent transcripts)
  and `POST`s them to `EVALIQA_URL/api/traces/claude-code/session`.
- Nothing is sent unless you have supplied both config values below. On a
  machine that has not configured them, the hook does nothing and exits quietly.
- The script never fails your turn: any error is written to stderr and the exit
  code stays `0`.

## Install

Requires Claude Code and an EvaliQA workspace with a project API key
(`evx_…`), created on your project's Tracing tab.

```
/plugin install evaliqa --marketplace evaliqa/evaliqa-claude-plugin
```

(On Claude Code before 2.1.275, run `/plugin marketplace add evaliqa/evaliqa-claude-plugin`
then `/plugin install evaliqa`.)

When you install it, Claude Code opens the plugin's config dialog and asks for
two values:

- **EvaliQA URL** — the base URL of your EvaliQA host, e.g. `https://your-evaliqa-host`.
- **EvaliQA API key** — your project key (`evx_…`). It is marked sensitive, so
  Claude Code masks the input and stores it in your platform's secure credential
  storage — never in `settings.json` and never in the repository.

You can reopen the dialog any time with `/plugin configure evaliqa`. Leave either
field empty to turn sending off. Restart Claude Code so the hooks load, then work
as usual — your sessions appear on the EvaliQA Tracing feed.

### Traces as well as transcripts

This plugin ships the *text*. To also get the trace structure, point Claude
Code's OpenTelemetry trace exporter at the same EvaliQA host by adding to the
repository's `.claude/settings.json`:

```json
{
  "env": {
    "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
    "CLAUDE_CODE_ENHANCED_TELEMETRY_BETA": "1",
    "OTEL_TRACES_EXPORTER": "otlp",
    "OTEL_METRICS_EXPORTER": "none",
    "OTEL_LOGS_EXPORTER": "none",
    "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "https://your-evaliqa-host/api/traces/otlp/v1/traces",
    "OTEL_LOG_USER_PROMPTS": "1",
    "OTEL_LOG_TOOL_DETAILS": "1",
    "OTEL_LOG_TOOL_CONTENT": "1"
  }
}
```

and the exporter's api-key header to `.claude/settings.local.json`:

```json
{
  "env": {
    "OTEL_EXPORTER_OTLP_HEADERS": "x-api-key=evx_your_key"
  }
}
```

## Privacy

The transcript includes your prompts, the agent's answers, and tool inputs and
outputs (including file contents and shell output). It is sent only to the
EvaliQA URL you configure, over HTTPS, authenticated with your own API key. Set
it to your own EvaliQA host. Nothing is sent when either config value is empty.

## License

[Apache-2.0](./LICENSE).
