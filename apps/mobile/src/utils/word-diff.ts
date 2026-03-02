/**
 * Word-level diff utilities using LCS (Longest Common Subsequence).
 *
 * Used by correction components to highlight only the actual differences
 * between original and corrected phrases, not entire phrases.
 */

export interface DiffSegment {
  text: string;
  isDiff: boolean;
}

/**
 * Compute word-level diff between original and corrected phrases using LCS.
 * Returns segments for each phrase indicating which parts are different.
 */
export function computeWordDiff(
  original: string,
  corrected: string,
): { originalSegments: DiffSegment[]; correctedSegments: DiffSegment[] } {
  const origWords = original.split(/\s+/).filter(Boolean);
  const corrWords = corrected.split(/\s+/).filter(Boolean);
  const m = origWords.length;
  const n = corrWords.length;

  const dp: number[][] = Array.from({ length: m + 1 }, () =>
    new Array<number>(n + 1).fill(0),
  );

  // Strip trailing punctuation for comparison so "favorite." matches "favorite"
  const normalize = (w: string) => w.replace(/[.,!?;:]+$/, '');

  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (normalize(origWords[i - 1]) === normalize(corrWords[j - 1])) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }

  const origIsDiff = new Array<boolean>(m).fill(true);
  const corrIsDiff = new Array<boolean>(n).fill(true);

  let i = m;
  let j = n;
  while (i > 0 && j > 0) {
    if (normalize(origWords[i - 1]) === normalize(corrWords[j - 1])) {
      origIsDiff[i - 1] = false;
      corrIsDiff[j - 1] = false;
      i--;
      j--;
    } else if (dp[i - 1][j] >= dp[i][j - 1]) {
      i--;
    } else {
      j--;
    }
  }

  return {
    originalSegments: groupWords(origWords, origIsDiff),
    correctedSegments: groupWords(corrWords, corrIsDiff),
  };
}

/**
 * Strip trailing punctuation from text for highlight purposes.
 * Returns [textWithoutPunct, punct] or [text, ''] if no trailing punctuation.
 */
export function splitTrailingPunct(text: string): [string, string] {
  const match = text.match(/^(.+?)([.,!?;:]+)$/);
  return match ? [match[1], match[2]] : [text, ''];
}

/**
 * Group consecutive words with the same diff status into segments.
 */
function groupWords(words: string[], isDiff: boolean[]): DiffSegment[] {
  if (words.length === 0) return [];

  const segments: DiffSegment[] = [];
  let currentWords: string[] = [words[0]];
  let currentIsDiff = isDiff[0];

  for (let k = 1; k < words.length; k++) {
    if (isDiff[k] === currentIsDiff) {
      currentWords.push(words[k]);
    } else {
      segments.push({ text: currentWords.join(' '), isDiff: currentIsDiff });
      currentWords = [words[k]];
      currentIsDiff = isDiff[k];
    }
  }
  segments.push({ text: currentWords.join(' '), isDiff: currentIsDiff });

  return segments;
}
