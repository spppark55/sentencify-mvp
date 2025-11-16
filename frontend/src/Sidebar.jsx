export default function Sidebar({ onNew }) {
  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold">문서</h3>
        <button
          onClick={onNew}
          className="text-xs h-7 px-2 rounded bg-purple-600 text-white hover:bg-purple-700"
        >
          새 글
        </button>
      </div>

      {/* 간단한 목업 목록 (추후 히스토리/문서 목록 연동) */}
      <ul className="text-sm text-gray-600 space-y-2">
        <li className="flex items-center justify-between">
          <span className="truncate">Draft A</span>
          <span className="text-xs text-gray-400">오늘</span>
        </li>
        <li className="flex items-center justify-between">
          <span className="truncate">Draft B</span>
          <span className="text-xs text-gray-400">어제</span>
        </li>
        <li className="flex items-center justify-between">
          <span className="truncate">Draft C</span>
          <span className="text-xs text-gray-400">3일 전</span>
        </li>
      </ul>
    </div>
  );
}
