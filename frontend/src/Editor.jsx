import { useRef } from 'react';

// 숫자인지 체크
const isDigit = (ch) => ch >= '0' && ch <= '9';

// 주어진 인덱스의 문자가 "문장 경계"인지 판단
const isSentenceBoundaryAt = (value, idx) => {
  const ch = value[idx];
  if (!ch) return false;

  // 기본 문장 부호들
  if (ch === '.' || ch === '!' || ch === '?' || ch === '…') {
    const prev = value[idx - 1];
    const next = value[idx + 1];

    // ✅ 숫자.숫자 패턴이면 → 소수점으로 보고 경계가 아님
    if (isDigit(prev) && isDigit(next)) {
      return false;
    }
    return true;
  }

  // 줄바꿈도 문장 경계로 취급
  if (ch === '\n') return true;

  return false;
};

export default function Editor({ text, setText, onSelectionChange }) {
  const taRef = useRef(null);

  // 키보드(Shift+방향키 등)로 선택할 때용 – 기존 동작 유지
  const handleKeyUp = () => {
    const ta = taRef.current;
    if (!ta) return;

    const start = ta.selectionStart ?? 0;
    const end = ta.selectionEnd ?? 0;
    const value = ta.value;
    const selected = start !== end ? value.slice(start, end) : '';

    onSelectionChange({ text: selected, start, end });
  };

  // 마우스 클릭/드래그 종료 시
  const handleMouseUp = () => {
    const ta = taRef.current;
    if (!ta) return;

    const value = ta.value;
    let start = ta.selectionStart ?? 0;
    let end = ta.selectionEnd ?? 0;

    // 드래그로 범위를 선택한 경우
    if (start !== end) {
      const selected = value.slice(start, end);
      onSelectionChange({ text: selected, start, end });
      return;
    }

    // 왼쪽으로 문장 시작 찾기
    let sentStart = start;
    while (sentStart > 0 && !isSentenceBoundaryAt(value, sentStart - 1)) {
      sentStart--;
    }

    // 오른쪽으로 문장 끝 찾기
    let sentEnd = end;
    while (sentEnd < value.length && !isSentenceBoundaryAt(value, sentEnd)) {
      sentEnd++;
    }

    // 앞뒤 공백 제거
    while (sentStart < sentEnd && /\s/.test(value[sentStart])) {
      sentStart++;
    }
    while (sentEnd > sentStart && /\s/.test(value[sentEnd - 1])) {
      sentEnd--;
    }

    // 실제로 선택할 문장이 있으면 selection 설정 + 상위로 전달
    if (sentEnd > sentStart) {
      ta.setSelectionRange(sentStart, sentEnd);
      const selectedSentence = value.slice(sentStart, sentEnd);
      onSelectionChange({
        text: selectedSentence,
        start: sentStart,
        end: sentEnd,
      });
    } else {
      // 문장을 못 찾은 경우(맨 처음/끝 등) → selection 비우기
      onSelectionChange({ text: '', start, end });
    }
  };

  return (
    <textarea
      ref={taRef}
      className="border rounded p-3 outline-none w-full max-w-full h-[calc(100vh-7rem)]"
      placeholder="이 곳에 텍스트를 입력하고 일부를 드래그하거나, 단어를 클릭해 보세요."
      value={text}
      onChange={(e) => setText(e.target.value)}
      onKeyUp={handleKeyUp}     // 키보드 선택
      onMouseUp={handleMouseUp} // 마우스 클릭/드래그
    />
  );
}
