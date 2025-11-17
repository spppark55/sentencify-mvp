import { useEffect, useState } from 'react';
import { v4 as uuidv4 } from 'uuid';
import Header from './Header.jsx';
import Sidebar from './Sidebar.jsx';
import Editor from './Editor.jsx';
import OptionPanel from './OptionPanel.jsx';
import { logEvent } from './utils/logger.js';
import { mockCorrect } from './utils/mockCorrect.js';
import DebugPanel from './DebugPanel.jsx';
import { postRecommend } from './utils/api.js';

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

  // Phase 식별자
  const [docId, setDocId] = useState(() => uuidv4());
  const [recommendId, setRecommendId] = useState(null); // recommend_session_id
  const [recommendInsertId, setRecommendInsertId] = useState(null); // A.insert_id
  const [recoOptions, setRecoOptions] = useState([]);
  const [contextHash, setContextHash] = useState(null);


  // 자동 저장
  useEffect(() => {
    const t = setTimeout(() => {
      try {
        localStorage.setItem(STORAGE_KEY, text);
      } catch {}
    }, 400);
    return () => clearTimeout(t);
  }, [text]);

  // 초기 복원
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) setText(saved);
    } catch {}
  }, []);

  // 새 글 시작(좌측 사이드바에서 호출)
  const handleNewDraft = () => {
    setText('');
    setSelection({ text: '', start: 0, end: 0 });
    setContext({ prev: '', next: '' });
    setDocId(uuidv4());
    setRecommendId(null);
    setRecommendInsertId(null);
    setRecoOptions([]);
    setContextHash(null);
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {}
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
      setRecoOptions(res.reco_options || []);
      setContextHash(res.context_hash || null);

      const topOption = res.reco_options?.[0];
      if (topOption?.category && optEnabled.category) {
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
      alert('먼저 문장을 드래그하여 선택해 주세요.');
      return;
    }

    // 교정 직후
    logEvent({
      event: 'editor_run_paraphrasing',
      recommend_session_id: recommendId,
      source_recommend_event_id: recommendInsertId,
      reco_category: category,
      recommend_phase: 'phase1.5',
      cache_hit: false,
      response_time_ms: 0,
      llm_name: 'mock-gpt',
      selected_text: selection.text,
      selection_start: selection.start,
      selection_end: selection.end,
    });

    const payload = {
      user_id: user?.id,
      doc_id: docId,
      selected_text: selection.text,
      context,
      category: optEnabled.category ? category : undefined,
      language: optEnabled.language ? language : undefined,
      strength: optEnabled.strength ? strength : undefined,
      style_request: requestText,
    };

    const started = performance.now();
    const corrected = await mockCorrect(payload);
    const elapsed = Math.round(performance.now() - started);

    // 사용자 최종 채택 로그
    logEvent({
      event: 'editor_selected_paraphrasing',
      recommend_session_id: recommendId,
      source_recommend_event_id: recommendInsertId,
      was_recommended: true,
      was_accepted: true,
      final_category: category,
      final_language: language,
      final_strength: strength,
      style_request: requestText,
      selected_text: selection.text,
      selection_start: selection.start,
      selection_end: selection.end,
      recommend_confidence: 0.87,
      macro_weight: 0.25,
      response_time_ms: elapsed,
    });

    logEvent({
      event: 'correction_history',
      history_id: uuidv4(),
      user_id: user?.id,
      doc_id: docId,
      original_text: selection.text,
      selected_text: corrected,
      recommended_category: category,
      final_category: category,
      context_ref: `ctx_${Date.now()}`,
      created_at: new Date().toISOString(),
    });

    const before = text.slice(0, selection.start);
    const after = text.slice(selection.end);
    setText(before + corrected + after);
    setSelection({ text: '', start: 0, end: 0 });
  };

  // 서술형 요청 제출
  const handleSubmitRequest = (e) => {
    e.preventDefault();
    logEvent({
      event: 'style_request_submit',
      user_id: user?.id,
      doc_id: docId,
      payload: {
        requestText,
        category: optEnabled.category ? category : undefined,
        language: optEnabled.language ? language : undefined,
        strength: optEnabled.strength ? strength : undefined,
        selection: selection.text,
        context,
      },
    });
    alert('요청사항이 제출되었습니다. (mock)');
    setRequestText('');
  };

  return (
    <div className="h-screen flex flex-col">
      {/* 상단 헤더 */}
      <Header onLogout={handleLogout} />

      {/* 본문 3열 레이아웃: Sidebar | Editor | OptionPanel */}
      <div className="grid grid-cols-[240px_1fr_320px] gap-0 h-[calc(100vh-4rem)]">
        <aside className="border-r p-4">
          <Sidebar onNew={handleNewDraft} />
        </aside>

        <main className="p-4">
          <h1 className="text-xl font-semibold mb-3">에디터</h1>
          <Editor
            text={text}
            setText={setText}
            onSelectionChange={handleSelectionChange}
          />

          {/* ✅ 디버그 패널 */}
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
            onSubmitRequest={handleSubmitRequest}
          />
        </aside>
      </div>
    </div>
  );
}
