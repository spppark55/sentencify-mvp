import { useEffect, useState } from 'react';
import { api } from './utils/api.js';

export default function Sidebar({
  userId,
  selectedDocId,
  refreshTrigger,
  onNew,
  onSelectDoc,
}) {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(false);

  const fetchDocuments = async () => {
    if (!userId) return;
    setLoading(true);
    try {
      const res = await api.get('/documents', { params: { user_id: userId } });
      const items = res.data?.items ?? [];
      setDocuments(items);
    } catch (err) {
      console.error('Failed to fetch documents', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId, refreshTrigger]);

  const handleDelete = async (docId) => {
    if (!userId) return;
    try {
      await api.delete(`/documents/${docId}`, { params: { user_id: userId } });
      await fetchDocuments();
    } catch (err) {
      console.error('Failed to delete document', err);
    }
  };

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

      <ul className="text-sm text-gray-600 space-y-2">
        {loading && (
          <li className="text-xs text-gray-400">문서 목록을 불러오는 중...</li>
        )}
        {!loading && documents.length === 0 && (
          <li className="text-xs text-gray-400">저장된 문서가 없습니다.</li>
        )}
        {!loading &&
          documents.map((doc) => {
            const label =
              (doc.preview_text && doc.preview_text.trim()) || '새 문서';
            const isActive = selectedDocId === doc.doc_id;
            return (
              <li
                key={doc.doc_id}
                className={`flex items-center justify-between gap-2 rounded px-1 py-1 ${
                  isActive ? 'bg-purple-50' : ''
                }`}
              >
                <button
                  type="button"
                  className="flex-1 text-left truncate hover:underline"
                  onClick={() =>
                    onSelectDoc?.({
                      doc_id: doc.doc_id,
                      text: doc.latest_full_text ?? '',
                    })
                  }
                >
                  {label}
                </button>
                <button
                  type="button"
                  className="text-xs text-red-500 hover:text-red-700"
                  onClick={() => handleDelete(doc.doc_id)}
                >
                  삭제
                </button>
              </li>
            );
          })}
      </ul>
    </div>
  );
}
