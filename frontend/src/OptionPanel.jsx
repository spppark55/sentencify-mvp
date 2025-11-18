export default function OptionPanel({
  selectedText,
  category,
  setCategory,
  language,
  setLanguage,
  strength,
  setStrength,
  requestText,
  setRequestText,
  optEnabled,
  setOptEnabled,
  onRun,
  candidates,
  onApplyCandidate,
}) {
  const toggleOption = (key) => {
    setOptEnabled({ ...optEnabled, [key]: !optEnabled[key] });
  };

  return (
    <aside className="h-full flex flex-col gap-4">
      {/* 교정 대상 문장 미리보기 영역 */}
      <div className="border rounded-md mt-4 p-3 text-sm text-gray-700 bg-gray-50">
        <div className="font-semibold mb-1 text-gray-600">선택된 문장</div>
        <div className="max-h-24 overflow-auto whitespace-pre-wrap">
          {selectedText ? (
            selectedText
          ) : (
            <span className="text-gray-400">
              드래그한 문장이 여기에 표시됩니다.
            </span>
          )}
        </div>
      </div>

      {/* 카테고리 */}
      <div className="option-group">
        <div className="flex items-center justify-between">
          <label className="font-medium">카테고리</label>
          <label className="flex items-center gap-2 text-sm">
            <span>ON/OFF</span>
            <input
              type="checkbox"
              checked={optEnabled.category}
              onChange={() => toggleOption('category')}
            />
          </label>
        </div>
        {optEnabled.category && (
          <select
            className="mt-2 border rounded p-2 w-full"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            <option value="none">없음</option>
            <option value="email">이메일</option>
            <option value="thesis">논문</option>
            <option value="report">보고서</option>
            <option value="article">기사</option>
            <option value="marketing">마케팅</option>
            <option value="customer">고객상담</option>
          </select>
        )}
      </div>

      {/* 언어 */}
      <div className="option-group">
        <div className="flex items-center justify-between">
          <label className="font-medium">언어</label>
          <label className="flex items-center gap-2 text-sm">
            <span>ON/OFF</span>
            <input
              type="checkbox"
              checked={optEnabled.language}
              onChange={() => toggleOption('language')}
            />
          </label>
        </div>
        {optEnabled.language && (
          <select
            className="mt-2 border rounded p-2 w-full"
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
          >
            <option value="ko">한국어</option>
            <option value="en">영어</option>
            <option value="ja">일본어</option>
            <option value="zh">중국어</option>
          </select>
        )}
      </div>

      {/* 교정 강도 */}
      <div className="option-group">
        <div className="flex items-center justify-between">
          <label className="font-medium">교정 강도</label>
          <label className="flex items-center gap-2 text-sm">
            <span>ON/OFF</span>
            <input
              type="checkbox"
              checked={optEnabled.strength}
              onChange={() => toggleOption('strength')}
            />
          </label>
        </div>
        {optEnabled.strength && (
          <input
            className="mt-2 w-full"
            type="range"
            min="0"
            max="2"
            step="1"
            value={strength}
            onChange={(e) => setStrength(parseInt(e.target.value))}
          />
        )}
      </div>

      {/* 서술형 요청 */}
      <div className="request-form mt-2">
        <label className="font-medium">서술형 요청사항</label>
        <textarea
          className="flex w-full mt-2 border rounded p-2 text-sm"
          placeholder="예) 더 간결하고 자연스럽게 바꿔줘"
          value={requestText}
          onChange={(e) => setRequestText(e.target.value)}
        />
      </div>

      {/* 실행 버튼 */}
      <button
        onClick={onRun}
        className="h-10 rounded-md bg-purple-600 text-white hover:bg-purple-700"
      >
        실행 (교정 후보 생성)
      </button>

      {/* 후보 리스트 */}
      {Array.isArray(candidates) && candidates.length > 0 && (
        <div className="mt-3 border rounded-md p-3 bg-purple-50 text-sm text-gray-800">
          <div className="font-semibold mb-2 text-gray-700">교정된 문장 후보</div>
          <ul className="space-y-2 max-h-40 overflow-auto">
            {candidates.map((c, idx) => (
              <li key={idx}>
                <button
                  type="button"
                  className="w-full text-left border rounded-md px-2 py-1 bg-white hover:bg-purple-100"
                  onClick={() => onApplyCandidate(c, idx)}
                >
                  {c}
                </button>
              </li>
            ))}
          </ul>
          <p className="mt-1 text-xs text-gray-500">
            원하는 문장을 클릭하면 본문에 반영됩니다.
          </p>
        </div>
      )}
      
      <div className="mt-auto text-xs text-gray-500 pt-3 border-t">
        히스토리 / 설정
      </div>
    </aside>
  );
}
