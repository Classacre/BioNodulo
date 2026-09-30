# Assistant harness

The assistant uses an explicit asynchronous turn driver, replacing the former
two-node LangGraph loop. BioNodulo retains its Python tool registry, editor
isolation rules, provider adapters, and user-approved workflow proposals.

## Design references

Reviewed on 2026-09-30:

- [Pi agent core](https://github.com/earendil-works/pi/blob/main/packages/agent/README.md):
  distinct model and tool lifecycle events, cancellation, context projection,
  and sequential execution for stateful tools. The former `badlogic/pi-mono`
  repository URL redirects here.
- [DeepSeek Harness architecture](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/architecture.md):
  separate model adapters, tools, session state, loop, and presentation events;
  settled messages are distinct from live updates. It remains a developer preview.
- [AWS response streaming](https://docs.aws.amazon.com/lambda/latest/dg/configuration-response-streaming.html)
  and [Lambda Web Adapter](https://github.com/aws/aws-lambda-web-adapter): Python
  ASGI events require a streaming runtime and Function URL configuration, not
  just a StreamingResponse in application code.

These are design references, not runtime dependencies or claims that either
framework has been embedded. The Python driver avoids an additional Node
service and retains BioNodulo's tested domain tools and deployment boundaries.

## Components

| Component | Responsibility |
| --- | --- |
| `bionodulo/ai/runtime.py` | Typed events, sequential tool loop, budgets, repeated-failure guard, proposals |
| `bionodulo/ai/assistant.py` | Prompt/context construction, attachment support, LiteLLM adapter, streamed response assembly |
| `bionodulo/ai/tools.py` | Tool schemas, execution, availability and shared-editor restrictions |
| `bionodulo/api/ai_routes.py` | Authentication, SSE delivery, heartbeats, disconnect cleanup, safe errors |
| `web/src/api/aiChat.ts` | Authenticated streaming transport, incremental framing, idle/total deadlines |
| `web/src/components/modals/AIWorkflowModal.tsx` | Visible activity, tool inputs/results, answer text, errors, retry and Stop |

## Turn lifecycle

1. Resolve the user's provider or authenticated free hosted access.
2. Publish a model-wait status before making the model request.
3. Stream visible answer text as `reply_delta`; retain full tool arguments
   until the model stream completes. Do not expose or manufacture private reasoning.
4. Validate each tool name and argument object; publish `tool_call` before
   execution and `tool_result` afterward using the same ID.
5. Feed settled tool results back to the model. Workflow-edit tools operate
   on a draft, which is presented for explicit Apply confirmation.
6. Finish with `reply` or `error`, followed by the transport's `[DONE]` marker.

`commentary` is model-provided visible text accompanying tool calls. Heartbeat
comments indicate an open connection, not completed model or tool work.
`propose_changes` is a reviewable draft, not evidence the canvas changed.

## Bounded execution and failure handling

- Default 12 tool rounds; orchestrators may request up to 40.
- Model request: 90 seconds; individual tool: 45 seconds; entire turn: 240 seconds.
- Three identical failing calls stop the turn rather than loop indefinitely.
- Malformed arguments, unavailable tools, nested domain errors, empty replies,
  incomplete streams and truncated model output cannot become silent success.
- UI inactivity and total deadlines are separate from backend deadlines.
- Local ASGI disconnects cancel the task. Hosted disconnect propagation also
  depends on the reverse proxy and Lambda adapter. Already-started external
  operations cannot be assumed reversible or stopped by closing a connection.
- Conversation context retains the latest 12 non-system messages; individual
  tool results sent to the model are bounded. This is bounded history, not
  semantic compaction or a durable background-job system.

## Hosted deployment contract

The website holds upstream credentials. The app uses the neutral hosted model
label with an explicit OpenAI protocol; model-name inference previously failed
before any network request. The website editor proxy obtains a Clerk session
token valid for the bounded turn so later model requests do not reuse a
60-second browser token. That credential stays on the server side.

The cloud editor uses Lambda Web Adapter with `AWS_LWA_INVOKE_MODE=response_stream`
and an IAM-authenticated Function URL in `RESPONSE_STREAM` mode. Lambda and
website route budgets are 300 seconds. The website forwards cancellation and
streams the body without buffering it. The legacy Mangum entrypoint remains
available for buffered integrations; it does not supply live SSE delivery.

The free-provider proxy has an 85-second total budget and bounded individual
attempts. Provider-specific authentication/model failures may fall through to
another configured provider. It only reports global quota exhaustion when all
providers report quota failure. A stream cannot fail over after bytes have
been delivered; a partial failure must be visible instead.

## Verification and remaining scope

Regression suites cover model routing, live event ordering, tool failures,
malformed arguments, cancellation, deadlines, stream framing and truncation,
editor isolation, provider failover and UI failure states. Real provider and
production checks remain separate from mocked regression tests.

This change does not implement durable server-side session replay, continuation
after process restart, autonomous background jobs, semantic history compaction,
or a scientific-quality benchmark of every assistant capability. Those need
their own storage, authorization and evaluation design. Browser chat history
is not a durable execution journal.
