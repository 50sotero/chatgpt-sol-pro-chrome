# ChatGPT Chrome state machine

Use this reference for picker interaction, submission, monitoring, extraction, and recovery. Treat every UI label below as a current breadcrumb that must be rediscovered in a fresh snapshot.

Before this state machine reaches model selection, complete:

`DISCOVER_LOCAL -> RESOLVE_PROJECT -> PROJECT_READY -> CONVERSATION_READY`

Follow [project-routing.md](project-routing.md). Do not upload or submit until the local identity, exact ChatGPT Project, and conversation are separately proven.

## Historical UI observations

Observed on `chatgpt.com` in a signed-in Pro account on 2026-07-25:

- The banner exposed a `Select chat surface` group with `Chat` and `Work` radios.
- The Chat composer exposed a `Chat with ChatGPT` textbox and a model/intelligence button whose selected label was `Pro`.
- Opening that composer-scoped button exposed a `Pro` menu with `menuitemradio` choices `Instant 5.5`, `Medium`, `High`, `Extra High`, and `Pro`. The target `Pro` item was checked.
- The same menu exposed a nested `GPT-5.6 Sol` menu. Its submenu contained a checked `menuitemradio` named `GPT-5.6 Sol`.
- The profile area also displayed an account-plan `Pro` badge. That badge proved entitlement only; it did not prove selected intelligence mode.
- Completed conversation turns used `section` elements with `data-testid="conversation-turn-N"`. A completed assistant turn exposed a `Response actions` group and a `Copy response` button with `data-testid="copy-turn-action-button"`. The response body used a scoped Markdown/prose container and a stable `data-message-id`.

## Current target

Target `GPT-6 Astra` with `Pro` intelligence. The observations above describe the earlier Sol UI, not a verified Astra picker. Rediscover the current controls and verify the exact Astra model and Pro mode independently before submission. An account-plan badge does not establish either selection.

Recheck current official guidance if the product labels or picker structure change:

- https://learn.chatgpt.com/docs/models
- https://learn.chatgpt.com/docs/web
- https://developers.openai.com/api/docs/models/gpt-6-astra

## Establish the target

1. Take a fresh DOM snapshot after the resolved ChatGPT Project and conversation finish hydrating.
2. Verify signed-in state, intended account/workspace, exact Project URL/ID/name, memory mode, and private/shared state.
3. Select the `Chat` surface when it is not already checked.
4. Scope the model/intelligence control to the composer or `main`.
5. Open the control and inspect the current accessible roles and names.
6. Open the model submenu and select `GPT-6 Astra` only when its checked state is absent.
7. Reopen the intelligence menu if selection closed it.
8. Select `Pro` only when its checked state is absent.
9. Reopen the menu and independently verify both checked states after all changes.
10. Record the verification in the task receipt.

Select the model first and Pro second because a model change may reset the intelligence choice. Verification after both selections is mandatory.

If a target is absent, allow one hydration/re-snapshot/reopen cycle. Then stop. Do not guess renamed options, use the profile badge, or substitute Extra High.

## Locator discipline

- Derive every locator from the latest relevant snapshot.
- Prefer stable test IDs, stable attributes, scoped roles and exact accessible names, then scoped text.
- Count a locator before acting unless uniqueness is self-evident.
- Scope generic `Pro`, `Chat`, `Menu`, and `Copy` labels to the relevant composer, menu, or turn.
- Never use source order, `nth-child`, or a whole-page text match to choose the latest turn.
- After a timeout, strict-mode error, or selector error, re-snapshot and change the locator strategy.
- Observe the cheapest authoritative state after every action. Do not click twice because a transition is slow.

## Pre-submit checkpoint

Record:

- canonical tab and current URL;
- local project fingerprint and exact ChatGPT Project URL/ID/name;
- project memory mode, private/shared state, chat title, and account/workspace;
- checked model and mode;
- current conversation-turn count and last message ID;
- prompt SHA-256 and byte count;
- attachment filenames, byte counts, hashes, and approved context inventory fingerprint;
- one unique enabled send control.

Fill once, verify once, send once.

## Submission acknowledgement

Accept any one authoritative acknowledgement:

- exactly one new user conversation turn appears;
- the URL changes from the project composer to a concrete stable conversation URL;
- a new assistant turn or active-generation control appears.

Record the new URL immediately. If no acknowledgement is visible, inspect the current turn list and composer before deciding. Never resubmit on ambiguity.

## Monitoring loop

A real project GPT-5.6 Pro review took 10 minutes 51 seconds. Use semantic polling rather than a short fixed timeout:

1. Poll in bounded intervals that still allow a user update at least every minute.
2. Reuse targeted locators until state changes; avoid repeated full snapshots.
3. Track the expected new assistant turn by turn index and message ID.
4. Classify:
   - `RUNNING`: stop/streaming control visible, response content changing, or new assistant turn lacks response actions.
   - `WAITING_INPUT`: ChatGPT visibly asks a question or exposes a continuation decision.
   - `COMPLETED`: expected assistant turn exists, streaming is absent, composer is ready, terminal response actions/artifacts exist, and scoped content is stable across two observations.
   - `UNCERTAIN`: send/reconnect/interruption state cannot be reconciled without risking duplication.
   - `BLOCKED`: sign-in, CAPTCHA, unavailable target, rate limit, explicit refusal, or unrecoverable page error.
5. Treat safeguard pauses and temporarily stable text as still running while terminal signals are absent.

For a visible `Continue generating` control, continue only when the user's requested output is incomplete and the continuation remains within the original scope. Record the action and never loop without a bounded stopping condition.

## Extract the response

1. Count conversation-turn sections and identify the expected post-submit assistant turn by its new identity, not merely by position.
2. Scope to that turn.
3. Verify the `Response actions` group or equivalent terminal signal.
4. Extract the Markdown/prose container, links, code blocks, tables, and artifacts from that turn only.
5. Use plain scoped DOM extraction when rendered text is sufficient.
6. Use `Copy response` only when exact Markdown fidelity matters. Preserve the clipboard, read the copied response, then restore the prior clipboard without logging or returning its previous contents.
7. Hash the extracted response and record its character/byte count.

## Recover without duplication

- Reacquire a stale tab from the existing Chrome binding; do not reinitialize the browser unless it is actually disconnected.
- Navigate to the exact recorded conversation URL when the task tab disappeared.
- Inspect turn count, last user message, last assistant message, and generation state before any retry.
- Retry only after a visible terminal failure proves that the original prompt did not produce a usable assistant turn. Keep retries bounded and in the same conversation.
- Treat user/extension interruption naturally and preserve the canonical tab for handoff.
- Never reload the same URL merely to probe state when doing so could lose unsent or in-progress content.

## Finalize

- Keep exactly one canonical tab for nonterminal work.
- Close automation-created duplicates and intermediate tabs.
- Leave user-owned unrelated tabs untouched.
- Call Chrome finalization exactly once as the final browser action.
