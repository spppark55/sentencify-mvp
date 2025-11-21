import { useEffect, useState } from 'react';
import { v4 as uuidv4 } from 'uuid';
import Header from './Header.jsx';
import Sidebar from './Sidebar.jsx';
import Editor from './Editor.jsx';
import OptionPanel from './OptionPanel.jsx';
import { logEvent } from './utils/logger.js';
import DebugPanel from './DebugPanel.jsx';
import api, { postRecommend, postParaphrase, updateDocument } from './utils/api.js';

const STORAGE_KEY = 'editor:draft:v1';

export default function App() {
  // 임시 사용자 (로그인 붙기 전)
  const user = { id: 'mock_user_001', email: 'mock@example.com' };

  // 본문/선택/컨텍스트
  const [text, setText] = useState('');
  const [selection, setSelection] = useState({ text: '', start: 0, end: 0 });
  const [context, setContext] = useState({ prev: '', next: '' });

  // 옵션 상태
  const [category, setCategory] = useState('none');
  const [language, setLanguage] = useState('ko');
  const [strength, setStrength] = useState(1);
  const [requestText, setRequestText] = useState('');
  const [optEnabled, setOptEnabled] = useState({
    category: true,
    language: true,
    strength: true,
  });

  // 교정 후보 리스트 상태
  const [candidates, setCandidates] = useState([]);

  // Phase 식별자
  const [docId, setDocId] = useState(() => uuidv4());
  const [recommendId, setRecommendId] = useState(null); // recommend_session_id
  const [recommendInsertId, setRecommendInsertId] = useState(null); // A.insert_id
  const [recoOptions, setRecoOptions] = useState([]);
  const [contextHash, setContextHash] = useState(null);
  const [lastSnapshotTime, setLastSnapshotTime] = useState(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [isSaving, setIsSaving] = useState(false);
  const [lastSnapshotText, setLastSnapshotText] = useState('');

  // 자동 저장
  useEffect(() => {
    if (!docId || !user?.id) return;
    setIsSaving(true);
    const t = setTimeout(() => {
      (async () => {
        try {
          localStorage.setItem(STORAGE_KEY, text);
          const now = Date.now();
          setLastSnapshotTime(now);
          await updateDocument(docId, {
            user_id: user.id,
            latest_full_text: text,
          });
          console.log('Saved to DB.');
        } catch (err) {
          console.error('Auto-save failed', err);
        } finally {
          setIsSaving(false);
        }
      })();
    }, 400);
    return () => clearTimeout(t);
  }, [text, docId, user?.id]);

  // 초기 복원
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) setText(saved);
    } catch {}
  }, []);

  // 새 글 시작(좌측 사이드바에서 호출)
  const handleNewDraft = async () => {
    try {
      const res = await api.post('/documents', { user_id: user.id });
      const newDocId = res.data?.doc_id || uuidv4();

      setDocId(newDocId);
      setText('');
      setSelection({ text: '', start: 0, end: 0 });
      setContext({ prev: '', next: '' });
      setRecommendId(null);
      setRecommendInsertId(null);
      setRecoOptions([]);
      setContextHash(null);
      setCandidates([]);
      setLastSnapshotTime(null);
      setRefreshTrigger((v) => v + 1);

      try {
        localStorage.removeItem(STORAGE_KEY);
      } catch {}
    } catch (err) {
      console.error('Failed to create new document', err);
      // fallback: 로컬에서만 새 문서 시작
      const fallbackId = uuidv4();
      setDocId(fallbackId);
      setText('');
      setSelection({ text: '', start: 0, end: 0 });
      setContext({ prev: '', next: '' });
      setRecommendId(null);
      setRecommendInsertId(null);
      setRecoOptions([]);
      setContextHash(null);
      setCandidates([]);
      setLastSnapshotTime(null);
      setRefreshTrigger((v) => v + 1);
      try {
        localStorage.removeItem(STORAGE_KEY);
      } catch {}
    }
  };

  // 좌측 사이드바에서 문서 선택 시 호출
  const handleSelectDocument = async (doc) => {
    if (!doc || !doc.doc_id) return;
    try {
      const res = await api.get(`/documents/${doc.doc_id}`, {
        params: { user_id: user.id },
      });
      const fullText = res.data?.latest_full_text ?? '';

      setDocId(doc.doc_id);
      setText(fullText);
      setSelection({ text: '', start: 0, end: 0 });
      setContext({ prev: '', next: '' });
      setRecommendId(null);
      setRecommendInsertId(null);
      setRecoOptions([]);
      setContextHash(null);
      setLastSnapshotTime(null);
      setLastSnapshotText(fullText);
    } catch (err) {
      console.error('Failed to load document', err);
    }
  };

  // 로그아웃(헤더에서 호출) — 현재는 로컬 상태/스토리지 초기화
  const handleLogout = () => {
    try {
      localStorage.clear();
    } catch {}
    setText('');
    setSelection({ text: '', start: 0, end: 0 });
    setContext({ prev: '', next: '' });
    setCategory('none');
    setLanguage('ko');
    setStrength(1);
    setRequestText('');
    setOptEnabled({ category: true, language: true, strength: true });
    setDocId(uuidv4());
    setRecommendId(null);
    setCandidates([]);
    alert('로그아웃 (mock): 로컬 데이터가 초기화되었습니다.');
  };

  // 문맥(prev/next) 계산
  const updateContext = (fullText, start) => {
    const sentences = fullText.split(/(?<=[.!?])\s+/);
    let prev = '',
        next = '';
    let cumulative = 0;
    for (let i = 0; i < sentences.length; i++) {
      const s = sentences[i];
      const sStart = cumulative;
      const sEnd = cumulative + s.length;
      if (start >= sStart && start <= sEnd) {
        prev = sentences[i - 1] || '';
        next = sentences[i + 1] || '';
        break;
      }
      cumulative += s.length + 1;
    }
    const ctx = { prev, next };
    setContext(ctx);
    return ctx;
  };

  // 에디터에서 선택 변경되면 호출
  const handleSelectionChange = async (sel) => {
    setSelection(sel);
    const ctx = updateContext(text, sel.start);

    if (!sel.text) {
      setRecommendId(null);
      setRecommendInsertId(null);
      setRecoOptions([]);
      setContextHash(null);
      return;
    }

    const intensityMap = ['weak', 'moderate', 'strong'];
    const intensityLabel =
      typeof strength === 'number'
        ? intensityMap[strength] || 'moderate'
        : 'moderate';

    const payload = {
      doc_id: docId,
      user_id: user?.id ?? 'anonymous',
      selected_text: sel.text,
      context_prev: ctx.prev || null,
      context_next: ctx.next || null,
      field: optEnabled.category && category !== 'none' ? category : null,
      language: optEnabled.language ? language : null,
      intensity: optEnabled.strength ? intensityLabel : null,
      user_prompt: requestText || null,
    };

    try {
      const res = await postRecommend(payload);

      setRecommendId(res.recommend_session_id);
      setRecommendInsertId(res.insert_id);
      const recoList = res.reco_options || [];
      setRecoOptions(recoList);
      setContextHash(res.context_hash || null);

      const topOption = recoList[0];
      if (topOption?.category) {
        setCategory(topOption.category);
      }
      if (topOption?.language && optEnabled.language) {
        setLanguage(topOption.language);
      }

      logEvent({
        event: 'editor_recommend_options',
        user_id: user?.id,
        doc_id: docId,
        selected_text: sel.text,
        selection_start: sel.start,
        selection_end: sel.end,
        context_prev: ctx.prev || '',
        context_next: ctx.next || '',
        recommend_session_id: res.recommend_session_id,
        source_recommend_event_id: res.insert_id,
        reco_options: res.reco_options,
        P_rule: res.P_rule,
        P_vec: res.P_vec,
        context_hash: res.context_hash,
        model_version: res.model_version,
        api_version: res.api_version,
        schema_version: res.schema_version,
        embedding_version: res.embedding_version,
      });
    } catch (err) {
      console.error('Failed to call /recommend', err);
    }
  };

  // 교정 실행
  const handleRunCorrection = async () => {
    if (!selection.text) {
      alert('?? ??? ????? ??? ???.');
      return;
    }

    const intensityMap = ['weak', 'moderate', 'strong'];
    const intensityLabel = intensityMap[strength] || 'moderate';

    const payload = {
      doc_id: docId,
      user_id: user?.id ?? 'anonymous',
      selected_text: selection.text,
      context_prev: context.prev || null,
      context_next: context.next || null,
      category: optEnabled.category && category !== 'none' ? category : 'general',
      language: optEnabled.language ? language : 'ko',
      intensity: optEnabled.strength ? intensityLabel : 'moderate',
      style_request: requestText || null,
      recommend_session_id: recommendId,
      source_recommend_event_id: recommendInsertId,
    };

    try {
      const started = performance.now();
      const result = await postParaphrase(payload);
      const elapsed = Math.round(performance.now() - started);

      const apiList = Array.isArray(result?.candidates) ? result.candidates : [];
      const list = apiList.length > 0
        ? apiList
        : [selection.text, selection.text, selection.text];
      setCandidates(list);

    } catch (err) {
      console.error('Failed to call /paraphrase', err);
      alert('?? ?? ? ??? ??????.');
    }
  };

  // ?? ?? ? ?? ???? ???

  const handleApplyCandidate = (candidate, index) => {
    if (!selection.text) {
      // 이론상 실행 직후에는 selection이 살아있어야 하지만,
      // 방어적으로 체크
      alert('적용할 문장을 찾을 수 없습니다. 다시 문장을 선택하고 실행해 주세요.');
      return;
    }

    const before = text.slice(0, selection.start);
    const after = text.slice(selection.end);
    const newText = before + candidate + after;

    setText(newText);
    // ✅ 선택 해제 & 후보 리스트 비우기
    setSelection({ text: '', start: 0, end: 0 });
    // ✅ 적용 후 후보 지우기
    setCandidates([]);

    // ✅ 최종 채택 로그
    logEvent({
      event: 'editor_selected_paraphrasing',
      recommend_session_id: recommendId,
      source_recommend_event_id: recommendInsertId,
      was_recommended: true,
      was_accepted: true,
      selected_candidate_index: index,
      selected_candidate_text: candidate,
      final_category: category,
      final_language: language,
      final_strength: strength,
      style_request: requestText,
      original_selected_text: selection.text,
      selection_start: selection.start,
      selection_end: selection.end,
      recommend_confidence: 0.87,
      macro_weight: 0.25,
      response_time_ms: 0,
    });

    // ✅ 히스토리 로그
    logEvent({
      event: 'correction_history',
      history_id: uuidv4(),
      user_id: user?.id,
      doc_id: docId,
      original_text: selection.text,
      selected_text: candidate,
      recommended_category: category,
      final_category: category,
      context_ref: `ctx_${Date.now()}`,
      created_at: new Date().toISOString(),
    });
};


  return (
    <div className="h-screen flex flex-col">
      {/* 상단 헤더 */}
      <Header onLogout={handleLogout} />

      {/* 본문 3열 레이아웃: Sidebar | Editor | OptionPanel */}
      <div className="
              grid 
              grid-cols-[240px_1fr_320px] 
              gap-0 
              h-[calc(100vh-4rem)] 
            "
      >
        <aside className="border-r p-4">
          <Sidebar
            userId={user?.id}
            selectedDocId={docId}
            refreshTrigger={refreshTrigger}
            onNew={handleNewDraft}
            onSelectDoc={handleSelectDocument}
          />
        </aside>

        <main className="p-4">
          <div className="flex items-center justify-between mb-3">
            <h1 className="text-xl font-semibold">에디터</h1>
            <span className="text-xs text-gray-500">
              {isSaving
                ? '저장 중...'
                : lastSnapshotTime
                  ? '저장됨'
                  : ''}
            </span>
          </div>
          <Editor
            text={text}
            setText={setText}
            onSelectionChange={handleSelectionChange}
          />

          {/* 디버그 패널 */}
          <DebugPanel
            text={text}
            selection={selection}
            context={context}
            options={{
              category,
              language,
              strength,
              requestText,
              optEnabled,
              recoOptions,
              contextHash,
            }}
            docId={docId}
            recommendId={recommendId}
          />
        </main>

        {/* 옵션 패널 */}
        <aside className="border-l p-4">
          <h2 className="text-lg font-semibold mb-4">옵션 패널</h2>
          <OptionPanel
            selectedText={selection.text}
            category={category}
            setCategory={setCategory}
            language={language}
            setLanguage={setLanguage}
            strength={strength}
            setStrength={setStrength}
            requestText={requestText}
            setRequestText={setRequestText}
            optEnabled={optEnabled}
            setOptEnabled={setOptEnabled}
            onRun={handleRunCorrection}
            candidates={candidates}
            onApplyCandidate={handleApplyCandidate}
          />
        </aside>
      </div>
    </div>
  );
}
