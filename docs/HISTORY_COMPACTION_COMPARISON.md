# History Compaction Implementation Comparison Report

## Executive Summary

This report provides a detailed comparison between the TypeScript (opencode) and Python (wolo) implementations of history compaction functionality. Both systems aim to manage long conversation histories by summarizing older messages when context limits are approached, but they differ significantly in architecture, triggering mechanisms, and implementation completeness.

---

## 1. Architecture Overview

### TypeScript Implementation (opencode)

**Location**: `packages/opencode/src/session/compaction.ts`

**Key Characteristics**:
- **Message-based compaction**: Creates a new assistant message with `summary: true` flag
- **Integrated with session loop**: Compaction is a first-class operation in the session processing loop
- **Plugin system integration**: Supports plugin hooks for customizing compaction behavior
- **Dual strategy**: Implements both full compaction (`process`) and selective pruning (`prune`)
- **Event-driven**: Publishes compaction events via event bus

**Architecture Pattern**: Stateful, message-oriented, integrated into session lifecycle

### Python Implementation (wolo)

**Location**: `wolo/compaction.py`

**Key Characteristics**:
- **Functional compaction**: Returns a new message list without modifying session state
- **In-memory operation**: Compaction happens in-memory during LLM call preparation
- **Simpler integration**: Called directly from agent loop when needed
- **Single strategy**: Only implements full message summarization
- **No event system**: No event publishing or plugin hooks

**Architecture Pattern**: Stateless, functional, called on-demand

---

## 2. Triggering Mechanisms

### TypeScript (opencode)

**Multiple Trigger Points**:

1. **Automatic overflow detection** (`isOverflow`):
   ```typescript
   // Checks: input + cache.read + output > usable context
   // usable = context - output (or input limit if set)
   ```
   - Triggered after each assistant message completion
   - Checks actual token usage from model response
   - Respects `config.compaction?.auto` flag
   - Considers cache tokens separately

2. **Manual compaction**:
   - Via API endpoint: `POST /:sessionID/summarize`
   - Can be triggered with `auto: false` for manual control

3. **Processor-initiated**:
   - Session processor can return `"compact"` signal
   - Integrated into decision flow

**Trigger Logic**:
```typescript
if (lastFinished && 
    lastFinished.summary !== true &&
    await SessionCompaction.isOverflow({ tokens: lastFinished.tokens, model })) {
  await SessionCompaction.create({ ... })
}
```

**Advantages**:
- ✅ Precise token counting from actual API responses
- ✅ Multiple trigger points for flexibility
- ✅ Respects model-specific limits (input caps, output limits)
- ✅ Configurable via config file

**Disadvantages**:
- ⚠️ More complex trigger logic
- ⚠️ Requires actual message completion to detect overflow

### Python (wolo)

**Single Trigger Point**:

1. **Periodic check during agent loop**:
   ```python
   if step > 0 and step % 5 == 0:
       token_estimate = estimate_session_tokens(messages)
       limit = config.max_tokens - 2000
       if token_estimate > limit:
           messages_to_use = await compact_messages(...)
   ```

**Trigger Logic**:
- Only checks every 5 steps
- Uses estimated tokens (not actual API response)
- Simple threshold comparison

**Advantages**:
- ✅ Simple and predictable
- ✅ No dependency on API response metadata
- ✅ Works with any LLM provider

**Disadvantages**:
- ⚠️ Less precise (estimation vs actual tokens)
- ⚠️ May miss overflow between checks
- ⚠️ Fixed interval (every 5 steps) may not be optimal
- ⚠️ No manual trigger mechanism
- ⚠️ No consideration of cache tokens

---

## 3. Token Estimation

### TypeScript (opencode)

**Method**: Uses actual token counts from API responses

**Source**: `MessageV2.Assistant["tokens"]` structure:
```typescript
{
  input: number,
  output: number,
  reasoning: number,
  cache: { read: number, write: number }
}
```

**Estimation Utility**: `Token.estimate()` for text-only estimation
```typescript
// Simple: 4 chars per token
export function estimate(input: string) {
  return Math.max(0, Math.round((input || "").length / CHARS_PER_TOKEN))
}
```

**Usage**:
- Primary: Actual API response tokens
- Secondary: Estimation for pruning tool outputs

**Advantages**:
- ✅ Accurate token counts
- ✅ Handles cache tokens correctly
- ✅ Model-specific limits respected

### Python (wolo)

**Method**: Character-based estimation

**Implementation**:
```python
TOKENS_PER_CHAR = 0.25  # 1 token ~= 4 characters
def estimate_tokens(text: str) -> int:
    return int(len(text) * TOKENS_PER_CHAR) + 1
```

**Message Token Estimation**:
- Text parts: Character-based estimation
- Tool calls: Fixed 20 token overhead + JSON size estimation
- Message overhead: Fixed 10 tokens

**Advantages**:
- ✅ Works without API metadata
- ✅ Provider-agnostic
- ✅ Fast computation

**Disadvantages**:
- ⚠️ Less accurate (especially for non-English, code, etc.)
- ⚠️ Doesn't account for actual tokenization differences
- ⚠️ May over/under-estimate significantly

---

## 4. Compaction Strategy

### TypeScript (opencode)

**Full Compaction Process**:

1. **Creates new assistant message**:
   - Role: `assistant`
   - Mode: `"compaction"`
   - Agent: `"compaction"` (dedicated agent)
   - Summary flag: `true`
   - Cost: 0 (marked as free)

2. **Uses SessionProcessor**:
   - Full processing pipeline
   - Streaming support
   - Error handling
   - Tool execution (but tools disabled for compaction)

3. **Prompt customization**:
   - Default prompt: Focus on continuing conversation, files, tasks
   - Plugin hooks: `experimental.session.compacting`
   - Can inject context or replace prompt entirely

4. **Continuation handling**:
   - If `auto: true` and result is `"continue"`, creates synthetic user message
   - Text: "Continue if you have next steps"

5. **Message preservation**:
   - All original messages remain in session
   - Compaction message added as new assistant message
   - Original history preserved for reference

**Pruning Strategy** (separate from compaction):

1. **Selective tool output removal**:
   - Goes backwards through messages
   - Finds completed tool calls
   - Protects recent 2 turns
   - Protects certain tools (`skill`)
   - Marks old tool outputs as compacted (sets `time.compacted`)
   - Removes output text but keeps tool call metadata

2. **Thresholds**:
   - `PRUNE_PROTECT = 40_000` tokens
   - `PRUNE_MINIMUM = 20_000` tokens
   - Only prunes if savings > minimum

**Advantages**:
- ✅ Preserves full history
- ✅ Compaction message is searchable/queryable
- ✅ Can continue conversation after compaction
- ✅ Two-tier strategy (full compaction + selective pruning)
- ✅ Extensible via plugins

**Disadvantages**:
- ⚠️ More complex implementation
- ⚠️ Creates additional messages (history grows)
- ⚠️ Requires dedicated compaction agent

### Python (wolo)

**Full Compaction Process**:

1. **Message selection**:
   - Keeps last 6 exchanges (user + assistant pairs)
   - Everything else goes to summary

2. **Summarization**:
   - Extracts text from messages
   - Formats as "User: ..." / "Assistant: ..."
   - Calls LLM with summarization prompt
   - Streams response
   - Limits summary to 500 characters

3. **Message replacement**:
   - Creates new user message with summary
   - Format: `"[Previous conversation summary: {summary}]"`
   - Replaces old messages with: `[summary_message] + recent_messages`
   - **Original messages are lost** (in-memory replacement)

4. **No continuation handling**:
   - Compaction is transparent to agent loop
   - Agent continues with compacted messages

**Advantages**:
- ✅ Simple and straightforward
- ✅ Reduces message count
- ✅ No additional messages created
- ✅ Fast execution

**Disadvantages**:
- ⚠️ **Loses original message history** (critical issue)
- ⚠️ No selective pruning strategy
- ⚠️ Fixed 6-exchange retention (not configurable)
- ⚠️ Summary length limit may truncate important info
- ⚠️ No plugin/extensibility mechanism

---

## 5. Summary Generation

### TypeScript (opencode)

**Prompt**:
```
"Provide a detailed prompt for continuing our conversation above. 
Focus on information that would be helpful for continuing the conversation, 
including what we did, what we're doing, which files we're working on, 
and what we're going to do next considering new session will not have 
access to our conversation."
```

**Features**:
- Uses dedicated "compaction" agent
- Can use different model than main conversation
- Plugin hooks can modify prompt
- Full message context passed to LLM
- No length limits (model-dependent)

**Output**:
- Full assistant message with parts
- Can include tool calls (though disabled)
- Streaming support
- Error handling with fallback

### Python (wolo)

**Prompt**:
```
"Summarize the following conversation concisely. 
Focus on key information, decisions, and context needed to continue the conversation.\n\n"
+ conversation_text
```

**Features**:
- Uses same LLM client as main conversation
- Simple text extraction
- Fixed 500-character limit on summary
- Fallback to simple count message on error

**Output**:
- Plain text summary string
- Truncated if > 500 chars
- No structured output

**Comparison**:
- **TS**: More detailed, context-aware, extensible
- **Python**: Simpler, but limited and may lose information

---

## 6. Integration Points

### TypeScript (opencode)

**Integration**:
1. **Session loop** (`SessionPrompt.loop`):
   - Checks overflow after each message
   - Handles compaction as first-class operation
   - Continues loop after compaction

2. **Session processor**:
   - Can signal compaction needed
   - Integrated into decision flow

3. **API endpoints**:
   - Manual compaction via REST API
   - Configurable auto/manual modes

4. **Event system**:
   - Publishes `Event.Compacted` after completion
   - Other components can react to compaction

5. **Pruning**:
   - Called at end of session loop
   - Separate from compaction

**Advantages**:
- ✅ Deep integration with session lifecycle
- ✅ Multiple integration points
- ✅ Event-driven architecture

### Python (wolo)

**Integration**:
1. **Agent loop** (`_call_llm`):
   - Periodic check (every 5 steps)
   - Inline compaction before LLM call
   - Transparent to rest of system

**Advantages**:
- ✅ Simple integration
- ✅ No additional infrastructure needed

**Disadvantages**:
- ⚠️ Limited integration points
- ⚠️ No event system
- ⚠️ No manual trigger
- ⚠️ No post-compaction hooks

---

## 7. Configuration

### TypeScript (opencode)

**Config Schema**:
```typescript
compaction: {
  auto: boolean,      // Enable automatic compaction (default: true)
  prune: boolean,     // Enable pruning (default: true)
}
```

**Features**:
- Can disable auto-compaction
- Can disable pruning separately
- Configurable per-instance

### Python (wolo)

**Configuration**:
- Uses `config.max_tokens` (no separate compaction config)
- Hardcoded values:
  - `RESERVED_TOKENS = 2000`
  - `recent_exchanges = 6`
  - Check interval: every 5 steps

**Limitations**:
- ⚠️ No way to disable compaction
- ⚠️ No way to configure retention count
- ⚠️ No way to configure check interval

---

## 8. Error Handling

### TypeScript (opencode)

**Error Handling**:
- Processor-level error handling
- Returns `"stop"` on error
- Error stored in message object
- Session loop can handle errors

**Robustness**: High - integrated error handling

### Python (wolo)

**Error Handling**:
```python
try:
    messages_to_use = await compact_messages(...)
except Exception as e:
    logger.warning(f"Compaction failed, using original messages: {e}")
    messages_to_use = messages
```

**Robustness**: Medium - falls back gracefully but may miss compaction

---

## 9. Completeness Analysis

### TypeScript (opencode) - Completeness Score: 9/10

**Strengths**:
- ✅ Full compaction with message preservation
- ✅ Selective pruning strategy
- ✅ Multiple trigger mechanisms
- ✅ Plugin extensibility
- ✅ Event system
- ✅ Configurable behavior
- ✅ Continuation support
- ✅ Accurate token counting
- ✅ Comprehensive tests

**Missing/Weak Areas**:
- ⚠️ Pruning could be more sophisticated (importance-based)
- ⚠️ No incremental compaction (always full)

### Python (wolo) - Completeness Score: 5/10

**Strengths**:
- ✅ Simple and functional
- ✅ Works for basic use cases
- ✅ Graceful error handling

**Missing/Weak Areas**:
- ❌ **Critical**: Loses original message history
- ❌ No pruning strategy
- ❌ No manual trigger
- ❌ No configuration options
- ❌ Fixed retention count
- ❌ Estimation-based (not accurate)
- ❌ No event system
- ❌ No plugin support
- ❌ Limited error recovery
- ❌ Summary length limit may truncate info

---

## 10. Functional Comparison

| Feature | TypeScript (opencode) | Python (wolo) | Winner |
|---------|----------------------|---------------|--------|
| **Token Accuracy** | Actual API tokens | Character estimation | TS ✅ |
| **History Preservation** | Full history kept | Messages replaced | TS ✅ |
| **Trigger Precision** | After each message | Every 5 steps | TS ✅ |
| **Configuration** | Full config support | Hardcoded values | TS ✅ |
| **Extensibility** | Plugin system | None | TS ✅ |
| **Pruning Strategy** | Selective tool pruning | None | TS ✅ |
| **Error Handling** | Comprehensive | Basic fallback | TS ✅ |
| **Simplicity** | Complex | Simple | Python ✅ |
| **Performance** | More overhead | Lightweight | Python ✅ |
| **Continuation** | Explicit continuation | Transparent | TS ✅ |
| **Manual Control** | API + auto modes | Auto only | TS ✅ |
| **Event System** | Full event bus | None | TS ✅ |

**Overall Winner**: TypeScript implementation is significantly more complete and robust.

---

## 11. Critical Issues in Python Implementation

### Issue 1: History Loss (CRITICAL)

**Problem**: Original messages are replaced, not preserved.

**Impact**:
- Cannot review original conversation
- Cannot debug compaction issues
- Loss of audit trail
- Cannot revert compaction

**Recommendation**: 
- Store original messages separately
- Or add compaction metadata to messages
- Or create compaction checkpoint

### Issue 2: Inaccurate Token Estimation

**Problem**: Character-based estimation is inaccurate.

**Impact**:
- May compact too early (wasteful)
- May compact too late (overflow)
- Doesn't account for model differences

**Recommendation**:
- Use actual tokenizer when available
- Or improve estimation algorithm
- Or use API token counts if available

### Issue 3: Fixed Retention Count

**Problem**: Always keeps exactly 6 exchanges.

**Impact**:
- May keep too much (wasteful)
- May keep too little (loses context)
- Not adaptive to conversation length

**Recommendation**:
- Make configurable
- Or adaptive based on token count
- Or based on conversation structure

### Issue 4: No Pruning Strategy

**Problem**: Only full compaction, no selective pruning.

**Impact**:
- Less efficient than selective pruning
- All-or-nothing approach
- Cannot preserve important old messages

**Recommendation**:
- Implement tool output pruning
- Or importance-based selection
- Or tiered compaction

---

## 12. Recommendations for Python (wolo) Implementation

### High Priority

1. **Preserve Original History**:
   ```python
   # Option A: Store separately
   session.compaction_history.append({
       "original_messages": messages,
       "compacted_at": time.time(),
       "summary": summary
   })
   
   # Option B: Add metadata
   summary_msg.metadata = {
       "compaction": True,
       "original_count": len(messages),
       "preserved_count": len(recent_messages)
   }
   ```

2. **Improve Token Estimation**:
   - Use tiktoken or similar when available
   - Fall back to improved character estimation
   - Consider model-specific tokenizers

3. **Add Configuration**:
   ```python
   class CompactionConfig:
       enabled: bool = True
       check_interval: int = 5  # steps
       recent_exchanges: int = 6
       reserved_tokens: int = 2000
       summary_max_length: int = 500
   ```

### Medium Priority

4. **Implement Pruning**:
   - Add tool output pruning similar to TS
   - Or implement importance-based selection
   - Preserve recent messages + important old ones

5. **Add Manual Trigger**:
   - CLI command: `wolo compact <session_id>`
   - API endpoint if applicable
   - Force compaction option

6. **Improve Summary Quality**:
   - Remove 500-char limit
   - Better prompt engineering
   - Structured output format

### Low Priority

7. **Add Event System**:
   - Publish compaction events
   - Allow hooks/plugins
   - Better observability

8. **Add Tests**:
   - Unit tests for compaction logic
   - Integration tests
   - Edge case handling

---

## 13. Conclusion

The TypeScript implementation in opencode is **significantly more complete and robust** than the Python implementation in wolo. It provides:

- ✅ Better architecture (preserves history, extensible)
- ✅ More accurate token handling
- ✅ Multiple strategies (compaction + pruning)
- ✅ Better integration and configurability
- ✅ Production-ready features

The Python implementation is **functional but incomplete**, with critical issues around history preservation and accuracy. It serves basic needs but needs significant improvements for production use.

**Recommendation**: Adopt key architectural patterns from TypeScript implementation while maintaining Python's simplicity where appropriate.

---

## Appendix: Code Snippets Comparison

### Token Estimation

**TypeScript**:
```typescript
// Simple estimation for text
Token.estimate(text) // 4 chars per token

// Actual tokens from API
message.tokens.input + message.tokens.cache.read
```

**Python**:
```python
# Character-based estimation
int(len(text) * 0.25) + 1  # 4 chars per token
```

### Compaction Trigger

**TypeScript**:
```typescript
if (await SessionCompaction.isOverflow({ 
    tokens: lastFinished.tokens, 
    model 
})) {
    await SessionCompaction.create({ ... })
}
```

**Python**:
```python
if step > 0 and step % 5 == 0:
    if estimate_session_tokens(messages) > limit:
        messages = await compact_messages(messages, config, limit)
```

### Summary Generation

**TypeScript**:
```typescript
// Full processor with plugins
const compacting = await Plugin.trigger(
    "experimental.session.compacting",
    { sessionID },
    { context: [], prompt: undefined }
)
const promptText = compacting.prompt ?? defaultPrompt
await processor.process({ messages, promptText, ... })
```

**Python**:
```python
# Simple LLM call
prompt = "Summarize..." + conversation_text
async for event in client.chat_completion([{"role": "user", "content": prompt}]):
    summary_parts.append(event["text"])
summary = "".join(summary_parts)[:500]  # Truncate
```

---

**Report Generated**: 2025-01-27
**Author**: Technical Analysis
**Version**: 1.0
