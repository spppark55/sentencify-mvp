import { useRef } from 'react';

export default function Editor({ text, setText, onSelectionChange }) {
  const taRef = useRef(null);

  // 입력창 드래그 구간 수집
  const reportSelection = () => {
    const ta = taRef.current;
    if (!ta) return;
    const start = ta.selectionStart ?? 0;
    const end = ta.selectionEnd ?? 0;
    const selected = start !== end ? ta.value.slice(start, end) : '';

    // 드래그 구간 상위(App)로 전달
    onSelectionChange({ text: selected, start, end });
  };

  return (
    <textarea
      ref={taRef}
      className="border rounded p-3 outline-none w-full h-[calc(100vh-7rem)]"
      placeholder="이 곳에 텍스트를 입력하고 일부를 드래그해 보세요."
      value={text}
      // 본문 텍스트를 상위(App)로 반영
      onChange={(e) => setText(e.target.value)}
      onSelect={reportSelection}
      onKeyUp={reportSelection}
      onMouseUp={reportSelection}
    />
  );
}
