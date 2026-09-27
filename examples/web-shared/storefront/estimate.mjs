const LINE_TERMINATOR = /[\n\r\u2028\u2029]/;

/**
 * Split the legacy `date (note)` format without a backtracking regular
 * expression. This preserves the prior greedy delimiter semantics.
 *
 * @param {string} raw
 * @returns {{ date: string, note: string } | null}
 */
export function splitEstimate(raw) {
  if (!raw || /^\s/.test(raw)) return null;
  const trimmed = raw.trimEnd();
  if (!trimmed.endsWith(")")) return null;

  const close = trimmed.length - 1;
  const firstWhitespace = raw.search(/\s/);
  let noteStart = -1;

  if (firstWhitespace >= 0 && firstWhitespace < close) {
    let afterWhitespace = firstWhitespace;
    while (afterWhitespace < close && /\s/.test(raw[afterWhitespace])) afterWhitespace += 1;
    if (raw[afterWhitespace] === "(") noteStart = afterWhitespace;
  }

  if (noteStart < 0) {
    const searchEnd = firstWhitespace >= 0 && firstWhitespace < close ? firstWhitespace : close;
    noteStart = raw.lastIndexOf("(", searchEnd - 1);
  }
  if (noteStart < 1) return null;

  const date = raw.slice(0, noteStart).trimEnd();
  const note = raw.slice(noteStart + 1, close);
  if (!date || /\s/.test(date) || LINE_TERMINATOR.test(note)) return null;
  return { date, note };
}
