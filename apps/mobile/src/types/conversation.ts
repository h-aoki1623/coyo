/**
 * Conversation domain types derived from OpenAPI-generated schemas.
 *
 * These re-export and narrow the auto-generated types so the rest of
 * the codebase can import from a stable module rather than reaching
 * into the generated file directly.
 */
import type { components } from './generated/api';

// -- Direct re-exports from OpenAPI schemas --------------------------------

export type ConversationResponse = components['schemas']['ConversationResponse'];
export type HistoryListItem = components['schemas']['HistoryListItem'];
export type HistoryListResponse = components['schemas']['HistoryListResponse'];
export type HistoryDetailResponse = components['schemas']['HistoryDetailResponse'];
export type FeedbackResponse = components['schemas']['FeedbackResponse'];

// -- Narrowed types (OpenAPI uses plain `string`; we add union literals) ----

type TurnResponseRaw = components['schemas']['TurnResponse'];

export interface Turn extends Omit<TurnResponseRaw, 'role' | 'correctionStatus'> {
  role: 'user' | 'ai';
  correctionStatus: 'none' | 'pending' | 'clean' | 'has_corrections';
}

type CorrectionItemRaw = components['schemas']['CorrectionItemResponse'];

export interface CorrectionItem extends Omit<CorrectionItemRaw, 'type'> {
  type: 'grammar' | 'expression' | 'vocabulary';
}

type TurnCorrectionRaw = components['schemas']['TurnCorrectionResponse'];

export interface TurnCorrection extends Omit<TurnCorrectionRaw, 'items'> {
  items: CorrectionItem[];
}

// -- Sentence-level grouping (used by Feedback / History screens) -----------

export interface SentenceCorrection {
  readonly key: string;
  readonly originalSentence: string;
  readonly correctedSentence: string;
  readonly items: readonly CorrectionItem[];
}
