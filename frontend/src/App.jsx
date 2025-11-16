import { useEffect, useState } from 'react';
import { v4 as uuidv4 } from 'uuid';
import Header from './Header.jsx';
import Sidebar from './Sidebar.jsx';
import Editor from './Editor.jsx';
import OptionPanel from './OptionPanel.jsx';
import { logEvent } from './utils/logger.js';
import { mockCorrect } from './utils/mockCorrect.js';
import DebugPanel from './DebugPanel.jsx';

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
  const [recommendId, setRecommendId] = useState(null);


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
    setContext({ prev, next });
  };

  // 에디터에서 선택 변경되면 호출
  const handleSelectionChange = (sel) => {
    setSelection(sel);
    updateContext(text, sel.start);

    // Phase 1: 실시간 추천 이벤트 (mock)
    const recoEventId = uuidv4();
    setRecommendId(recoEventId);

    logEvent({
      event: 'editor_recommend_options', // 이벤트 내용
      user_id: user?.id, // 사용자 ID
      doc_id: docId, // 현재 문서 ID(uuid 형식)
      selected_text: selection.text, // 드래그한 실제 텍스트
      selection_start: selection.start, // 드래그 시작 인덱스
      selection_end: selection.end, // 드래그 끝 인덱스
      context_prev: context.prev || '', // 앞 문맥
      context_next: context.next || '', // 뒤 문맥
      reco_category: 'thesis', //
      rule_hit: true,
      vec_hit: false,
      P_rule: 0.62,
      P_vec: 0.74,
      P_doc: 0.7,
      macro_weight: 0.25,
      confidence: 0.85,
      auto_applied: false,
      recommend_checkbox_status: true,
      latency_ms: 250 + Math.floor(Math.random() * 200),
      cache_hit: false,
      model_version: 'phase1_v1',
    });
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
      source_recommend_event_id: recommendId,
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
      source_recommend_event_id: recommendId,
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
