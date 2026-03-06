# Talk Screen — Conversation Sequence Diagram

User and AI conversation flow on the Talk screen.

## Overview

1. User records audio via the microphone button
2. Audio is sent to the backend as multipart/form-data
3. Backend processes STT → LLM → Correction + TTS in a single SSE stream
4. Frontend renders messages progressively as events arrive

## Sequence Diagram

```mermaid
sequenceDiagram
    participant User
    participant App
    participant Backend
    participant STT as STT (Whisper)
    participant LLM as LLM (OpenAI)
    participant TTS as TTS Service
    participant DB as Database

    Note over User, App: 1. Audio Recording
    User->>App: Long-press mic button
    App->>App: Start recording (expo-av)
    User->>App: Tap send button
    App->>App: Stop recording, build FormData
    App->>App: Show ProcessingBubble

    Note over App, Backend: 2. Start SSE Stream
    App->>Backend: POST /conversations/{id}/turns<br/>(multipart/form-data, Accept: text/event-stream)

    Note over Backend, DB: 3. Speech-to-Text
    Backend->>STT: transcribe(audio)
    STT-->>Backend: transcribed_text
    Backend->>DB: Save user turn (correction_status='pending')
    Backend-->>App: SSE: stt_result {text}
    App->>App: Show user bubble + AiTypingBubble

    Note over Backend, LLM: 4. AI Response (Streaming)
    Backend->>LLM: chat_completion(messages)
    loop Per chunk
        LLM-->>Backend: token chunk
        Backend-->>App: SSE: ai_response_chunk {text}
        App->>App: Buffer text (no UI update)
    end
    Backend-->>App: SSE: ai_response_done {text}
    App->>App: Store full AI text in buffer

    Note over Backend, TTS: 5. Correction & TTS (Parallel)
    par Correction Analysis
        Backend->>LLM: analyze(user_text)
        LLM-->>Backend: correction_result
        Backend-->>App: SSE: correction_result
        App->>App: Show correction annotation on user bubble
    and Text-to-Speech
        Backend->>TTS: synthesize(ai_text)
        TTS-->>Backend: audio_url
        Backend-->>App: SSE: tts_audio_url
        App->>App: Reveal AI bubble (buffered text)
        App->>User: Play AI voice
    end

    Note over Backend, App: 6. Turn Complete
    Backend-->>App: SSE: turn_complete
    App->>App: Enable mic button (ready for next turn)
```

## Key Behaviors

| Behavior | Detail |
|----------|--------|
| **AI text reveal timing** | Text is buffered during `ai_response_chunk`/`ai_response_done`. The AI bubble appears only when `tts_audio_url` arrives, so the user sees the text and hears the audio simultaneously. |
| **Correction & TTS parallelism** | The backend runs correction analysis and TTS synthesis concurrently after the LLM response completes. Each sends its event independently. |
| **Fallback on missing TTS** | If `tts_audio_url` never arrives and `turn_complete` fires, the buffered AI text is displayed without audio. |
| **Correction status lifecycle** | `pending` (while analyzing) → `has_corrections` (issues found) or `clean` (no issues). |

## SSE Event Types

| Event | Payload | Frontend Action |
|-------|---------|----------------|
| `stt_result` | `{text}` | Add user turn to store, show user bubble |
| `ai_response_chunk` | `{text}` | Buffer text (no UI update) |
| `ai_response_done` | `{text}` | Store full text in buffer |
| `tts_audio_url` | `{url}` | Reveal AI bubble, start audio playback |
| `correction_result` | `{correctedText, explanation, items}` | Update correction annotation on user bubble |
| `turn_complete` | `{}` | Reset to idle, enable mic button |
| `error` | `{code, message}` | Show error, reset state |

## Related Source Files

### Mobile (Frontend)
- `apps/mobile/src/features/talk/TalkScreen.tsx` — Main screen
- `apps/mobile/src/features/talk/hooks/useTurnStreaming.ts` — SSE event processing
- `apps/mobile/src/api/sse-client.ts` — SSE parser
- `apps/mobile/src/features/talk/hooks/useAudioRecording.ts` — Audio recording/playback
- `apps/mobile/src/features/talk/components/MessageBubble.tsx` — Message rendering
- `apps/mobile/src/features/talk/components/CorrectionCard.tsx` — Correction UI
- `apps/mobile/src/stores/conversation-store.ts` — Zustand state

### Backend (API)
- `apps/api/src/coto/routers/conversations.py` — API endpoints
- `apps/api/src/coto/services/turn_orchestrator.py` — SSE orchestration
- `apps/api/src/coto/services/correction.py` — Correction analysis
