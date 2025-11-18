export default function DebugPanel({
  text,
  selection,
  context,
  options,
  docId,
  recommendId,
}) {
  const events = window.__eventLog || [];

  return (
    <div className="mt-4 border rounded p-3 text-xs bg-gray-50 max-w-full">
      <div className="flex items-center justify-between">
        <strong className="text-gray-700">Debug Panel</strong>
        <div className="flex gap-2">
          <button
            className="px-2 py-1 rounded bg-gray-800 text-white"
            onClick={() => {
              window.__eventLog = [];
              alert('이벤트 로그 초기화');
            }}
          >
            로그 초기화
          </button>
          <button
            className="px-2 py-1 rounded bg-gray-800 text-white"
            onClick={() => {
              try {
                const dump = {
                  textLen: text.length,
                  selection,
                  context,
                  options,
                  docId,
                  recommendId,
                  events,
                };
                console.log('[DUMP]', dump);
                alert('콘솔에 DUMP 출력됨');
              } catch {}
            }}
          >
            콘솔로 덤프
          </button>
        </div>
      </div>

      {/* 상단 상태 요약 */}
      <div className="grid grid-cols-2 gap-3 mt-3">
        <div className="border rounded p-2">
          <div className="font-semibold text-gray-700 mb-1">현재 상태</div>
          <div>
            문서 ID: <code>{docId}</code>
          </div>
          <div>
            추천 ID: <code>{recommendId || '-'}</code>
          </div>
          <div>본문 길이: {text.length}</div>
          <div>선택 길이: {selection?.text?.length || 0}</div>
          <div>
            선택 구간: [{selection?.start},{selection?.end}]
          </div>
        </div>

        <div className="border rounded p-2">
          <div className="font-semibold text-gray-700 mb-1">문맥(Context)</div>
          <div className="truncate">Prev: {context?.prev || '-'}</div>
          <div className="truncate">Next: {context?.next || '-'}</div>
        </div>

        <div className="border rounded p-2 col-span-2 max-w-full">
          <div className="font-semibold text-gray-700 mb-1">옵션</div>
          <pre className="whitespace-pre-wrap break-all text-[11px] leading-relaxed">
            {JSON.stringify(options, null, 2)}
          </pre>
        </div>
      </div>

      {/* 이벤트 로그 */}
      <div className="mt-3">
        <div className="font-semibold text-gray-700 mb-1">
          이벤트 로그 ({events.length})
        </div>
        <div className="max-h-64 overflow-y-auto overflow-x-auto border rounded max-w-full">
          <table className="w-full text-left">
            <thead className="sticky top-0 bg-white border-b">
              <tr>
                <th className="p-2">#</th>
                <th className="p-2">시간</th>
                <th className="p-2">event</th>
                <th className="p-2">요약</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e, idx) => (
                <tr key={idx} className="border-b hover:bg-gray-100">
                  <td className="p-2">{idx + 1}</td>
                  <td className="p-2">{e.ts?.split('T')[1]?.slice(0, 8)}</td>
                  <td className="p-2">
                    <code>{e.event}</code>
                  </td>
                  <td className="p-2">
                    <div className="truncate text-gray-600">
                      {e.event === 'editor_recommend_options' &&
                        `reco=${e.reco_category} conf=${e.confidence}`}

                      {e.event === 'editor_run_paraphrasing' &&
                        `phase=${e.recommend_phase} cat=${e.reco_category}`}

                      {e.event === 'editor_selected_paraphrasing' &&
                        `final=${e.final_category}/${e.final_language} s=${e.final_strength} t=${e.response_time_ms}ms`}

                      {e.event === 'correction_history' &&
                        `origLen=${e.original_text?.length} -> selLen=${e.selected_text?.length}`}
                      
                      {e.event === 'editor_paraphrasing_candidates' &&
                        `candidates=${e.candidate_count} time=${e.response_time_ms}ms len=${e.selected_text?.length}`}

                      {![
                          'editor_recommend_options',
                          'editor_run_paraphrasing',
                          'editor_selected_paraphrasing',
                          'correction_history',
                          'editor_paraphrasing_candidates',
                        ].includes(e.event) && '기타 이벤트'}
                    </div>
                  </td>
                </tr>
              ))}
              {events.length === 0 && (
                <tr>
                  <td className="p-2 text-gray-400" colSpan={4}>
                    로그가 없습니다. 에디터에서 드래그/실행을 해보세요.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <details className="mt-2 max-w-full">
          <summary className="cursor-pointer text-gray-600">
            원본 JSON 보기
          </summary>
          <pre className="p-2 bg-white border rounded overflow-auto max-h-64 max-w-full whitespace-pre break-all text-[11px] leading-relaxed">
            {JSON.stringify(events, null, 2)}
          </pre>
        </details>
      </div>
    </div>
  );
}
