import { useEffect, useState } from 'react';
import { v4 as uuidv4 } from 'uuid';
import Header from './Header.jsx';
import Sidebar from './Sidebar.jsx';
import Editor from './Editor.jsx';
import OptionPanel from './OptionPanel.jsx';
import { logEvent } from './utils/logger.js';
import DebugPanel from './DebugPanel.jsx';
// HEAD의 실제 API 함수들과 Frontend의 Auth/Login 컴포넌트를 모두 가져옴
import { createDocument, postRecommend, postParaphrase, updateDocument } from './utils/api.js';
import { useAuth } from './auth/AuthContext.jsx';
import Login from './auth/Login.jsx';

const STORAGE_KEY = 'editor:docs:v1'; // Frontend의 키 사용

// 프론트 개발 모드에서 로그인 생략할지 여부
const DEV_BYPASS_LOGIN = true;

export default function App() {
  // AuthContext 사용 (Frontend)
  const { user, logout } = useAuth();

  const effectiveUser = DEV_BYPASS_LOGIN
    ? { id: 'dev-user-001', name: 'Dev User' }
    : user;
  const userId = effectiveUser?.id ?? null;

  // 문서 상태 관리 (Frontend 구조 채택 - 다중 문서 지원)
  const [docs, setDocs] = useState([]);
  const [currentId, setCurrentId] = useState(null);

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

  // 교정 후보 리스트
  const [candidates, setCandidates] = useState([]);

  // Backend Phase 식별자
  const [docId, setDocId] = useState(null);
  const [recommendId, setRecommendId] = useState(null);
  const [recommendInsertId, setRecommendInsertId] = useState(null);
  const [recoOptions, setRecoOptions] = useState([]);
  const [contextHash, setContextHash] = useState(null);
  const INITIAL_SCORING_INFO = {
    P_vec: {},
    P_doc: {},
    P_rule: {},
    doc_maturity_score: 0,
    applied_weight_doc: 0,
  };
  const [scoringInfo, setScoringInfo] = useState({ ...INITIAL_SCORING_INFO });

  // 제목 생성 헬퍼 (Frontend)
  const makeTitle = (t) => {
    const trimmed = (t || '').trim();
    if (!trimmed) return '새 문서';
    if (trimmed.length <= 20) return trimmed;
    return trimmed.slice(0, 20) + '…';
  };

  // 초기 로드 (Frontend LocalStorage 로직 유지)
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        const loadedDocs = parsed.docs || [];
        let loadedCurrentId = parsed.currentId;

        if (!loadedCurrentId && loadedDocs.length > 0) {
          loadedCurrentId = loadedDocs[0].id;
        }

        if (loadedDocs.length === 0) {
          const id = uuidv4();
          const initialDocs = [{ id, title: '새 문서', text: '', updatedAt: new Date().toISOString() }];
          setDocs(initialDocs);
          setCurrentId(id);
          setDocId(id);
          setText('');
        } else {
          setDocs(loadedDocs);
          setCurrentId(loadedCurrentId);
          setDocId(loadedCurrentId);
          const currentDoc = loadedDocs.find((d) => d.id === loadedCurrentId);
          setText(currentDoc?.text || '');
        }
      } else {
        const id = uuidv4();
        const initialDocs = [{ id, title: '새 문서', text: '', updatedAt: new Date().toISOString() }];
        setDocs(initialDocs);
        setCurrentId(id);
        setDocId(id);
        setText('');
      }
    } catch (e) {
      console.error('Failed to load docs', e);
    }
  }, []);

  // 문서 저장 및 LocalStorage 동기화 (Frontend 로직)
  // *추후 Phase 1.5에서 updateDocument API와 연동 예정*
  useEffect(() => {
    if (!currentId) return;

    setDocs((prev) => {
      const now = new Date().toISOString();
      const idx = prev.findIndex((d) => d.id === currentId);
      let next;

      if (idx === -1) {
        next = [{ id: currentId, title: makeTitle(text), text, updatedAt: now }, ...prev];
      } else {
        next = prev.map((d) =>
          d.id === currentId
            ? { ...d, text, title: makeTitle(text), updatedAt: now }
            : d
        );
      }

      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify({ docs: next, currentId }));
      } catch {}

      return next;
    });
  }, [text, currentId]);

  // useEffect(() => {
  //   if (!docId || !userId) return;

  //   const handler = setTimeout(async () => {
  //     try {
  //       await updateDocument(docId, {
  //         latest_full_text: text,
  //         user_id: userId,
  //       });
  //     } catch (err) {
  //       console.warn('자동 저장(updateDocument) 실패', err);
  //     }
  //   }, 1200);

  //   return () => clearTimeout(handler);
  // }, [text, docId, userId]);
  

  // 새 문서 (Frontend)
  const handleNewDraft = async () => {
    if (!userId) {
      alert('사용자 정보를 확인할 수 없어 새 문서를 만들 수 없습니다.');
      return;
    }

    try {
      const res = await createDocument({ user_id: userId });
      const id = res?.doc_id;
      if (!id) {
        throw new Error('서버에서 doc_id를 받지 못했습니다.');
      }
      const newDoc = { id, title: '새 문서', text: '', updatedAt: new Date().toISOString() };
      setDocs((prev) => [newDoc, ...prev]);
      setCurrentId(id);
      setDocId(id);
      setText('');
      resetSelectionState();
    } catch (err) {
      console.error('서버 문서 생성 실패', err);
      alert('새 문서를 생성하지 못했습니다. 잠시 후 다시 시도해 주세요.');
    }
  };

  // 문서 선택 (Frontend)
  const handleSelectDraft = (id) => {
    const doc = docs.find((d) => d.id === id);
    if (!doc) return;
    setCurrentId(id);
    setDocId(id);
    setText(doc.text || '');
    resetSelectionState();
  };

  // 문서 삭제 (Frontend)
  const handleDeleteDraft = (id) => {
    if (!window.confirm('이 문서를 삭제하시겠습니까?')) return;
    let nextDocs = docs.filter((d) => d.id !== id);
    let nextCurrentId = currentId;
    let nextText = text;

    if (id === currentId) {
      if (nextDocs.length > 0) {
        nextCurrentId = nextDocs[0].id;
        nextText = nextDocs[0].text || '';
      } else {
        const newId = uuidv4();
        const blankDoc = { id: newId, title: '새 문서', text: '', updatedAt: new Date().toISOString() };
        nextDocs = [blankDoc];
        nextCurrentId = newId;
        nextText = '';
      }
    }
    setDocs(nextDocs);
    setCurrentId(nextCurrentId);
    setDocId(nextCurrentId);
    setText(nextText);
    resetSelectionState();
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ docs: nextDocs, currentId: nextCurrentId }));
    } catch {}
  };

  // 로그아웃
  const handleLogout = () => {
    logout(); // Frontend Auth
    try { localStorage.removeItem(STORAGE_KEY); } catch {}
    setDocs([]);
    setCurrentId(null);
    setDocId(null);
    setText('');
    resetSelectionState();
  };

  const resetSelectionState = () => {
    setSelection({ text: '', start: 0, end: 0 });
    setContext({ prev: '', next: '' });
    setRecommendId(null);
    setRecommendInsertId(null);
    setRecoOptions([]);
    setContextHash(null);
    setCandidates([]);
  };

  // 컨텍스트 계산
  const updateContext = (fullText, start) => {
    const sentences = fullText.split(/(?<=[.!?])\s+/);
    let prev = '', next = '';
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

  // 선택 변경 시 -> 추천 API 호출 (HEAD 로직 사용)
  const handleSelectionChange = async (sel) => {
    setSelection(sel);
    const ctx = updateContext(text, sel.start);

    if (!sel.text) {
      setRecommendId(null);
      setRecommendInsertId(null);
      setRecoOptions([]);
      setContextHash(null);
      setScoringInfo({ ...INITIAL_SCORING_INFO });
      return;
    }

    if (!docId || !userId) {
      console.warn('추천 API 호출 불가: docId 또는 userId 없음');
      alert('문서 또는 사용자 정보가 없어 추천을 실행할 수 없습니다.');
      return;
    }

    const intensityMap = ['weak', 'moderate', 'strong'];
    const intensityLabel = typeof strength === 'number' ? intensityMap[strength] || 'moderate' : 'moderate';

    const payload = {
      doc_id: docId,
      user_id: userId,
      selected_text: sel.text,
      context_prev: ctx.prev || null,
      context_next: ctx.next || null,
      field: optEnabled.category && category !== 'none' ? category : null,
      language: optEnabled.language ? language : null,
      intensity: optEnabled.strength ? intensityLabel : null,
      user_prompt: requestText || null,
    };

    try {
      // HEAD의 실제 API 호출
      const res = await postRecommend(payload);

      setRecommendId(res.recommend_session_id);
      setRecommendInsertId(res.insert_id);
      setRecoOptions(res.reco_options || []);
      setContextHash(res.context_hash || null);
      setScoringInfo({
        P_vec: res.P_vec || {},
        P_doc: res.P_doc || {},
        P_rule: res.P_rule || {},
        doc_maturity_score: res.doc_maturity_score ?? 0,
        applied_weight_doc: res.applied_weight_doc ?? 0,
      });

      const topOption = res.reco_options?.[0];
      if (topOption?.category && optEnabled.category) setCategory(topOption.category);
      if (topOption?.language && optEnabled.language) setLanguage(topOption.language);

      logEvent({
        event: 'editor_recommend_options',
        user_id: effectiveUser?.id,
        doc_id: docId,
        selected_text: sel.text,
        // ... 나머지 로그 필드
        recommend_session_id: res.recommend_session_id,
      });
    } catch (err) {
      console.error('Failed to call /recommend', err);
      alert('추천 API 호출에 실패했습니다. 잠시 후 다시 시도해 주세요.');
    }
  };

  // 교정 실행 -> Paraphrase API 호출 (HEAD 로직 + Frontend 파라미터 통합)
  const handleRunCorrection = async (isRerun = false) => {
    if (!selection.text) {
      alert('먼저 문장을 드래그하여 선택해 주세요.');
      return;
    }

    if (!docId || !userId) {
      console.warn('교정 API 호출 불가: docId 또는 userId 없음');
      alert('문서 또는 사용자 정보를 확인한 뒤 다시 시도해 주세요.');
      return;
    }

    const intensityMap = ['weak', 'moderate', 'strong'];
    const intensityLabel = intensityMap[strength] || 'moderate';
    const resolvedCategory =
      optEnabled.category && category !== 'none' ? category : 'general';
    const resolvedLanguage = optEnabled.language ? language : 'ko';
    const resolvedMaintenance = optEnabled.strength ? intensityLabel : 'moderate';

    const payload = {
      doc_id: docId,
      user_id: userId,
      selected_text: selection.text,
      context_prev: context.prev || null,
      context_next: context.next || null,
      category: resolvedCategory,
      language: resolvedLanguage,
      intensity: resolvedMaintenance,
      style_request: requestText || null,
      recommend_session_id: recommendId,
      source_recommend_event_id: recommendInsertId,
    };

    try {
      const started = performance.now();
      // HEAD의 실제 API 호출
      const result = await postParaphrase(payload);
      const elapsed = Math.round(performance.now() - started);

      const apiList = Array.isArray(result?.candidates) ? result.candidates : [];
      const list = apiList.length > 0 ? apiList : [selection.text, selection.text, selection.text];
      
      setCandidates(list);

      logEvent({
        event: 'editor_run_paraphrasing',
        doc_id: docId,
        user_id: effectiveUser?.id,
        recommend_session_id: recommendId,
        source_recommend_event_id: recommendInsertId,
        input_sentence_length: selection.text.length,
        maintenance: resolvedMaintenance,
        target_language: resolvedLanguage,
        field: resolvedCategory,
        tone: 'normal',
        platform: 'web',
        trigger: isRerun ? 'rerun_click' : 'button_click',
        llm_name: 'gemini-2.5-flash',
        llm_provider: 'google',
        response_time_ms: elapsed,
        candidate_count: list.length,
      });

    } catch (err) {
      console.error('Failed to call /paraphrase', err);
      alert('교정 후보를 가져오는 중 문제가 발생했습니다.');
    }
  };

  const handleApplyCandidate = (candidate, index) => {
    if (!selection.text) {
      alert('적용할 문장을 찾을 수 없습니다.');
      return;
    }

    const totalCandidates = candidates.length || 1;
    const intensityMap = ['weak', 'moderate', 'strong'];
    const resolvedMaintenance =
      optEnabled.strength ? intensityMap[strength] || 'moderate' : 'moderate';
    const resolvedCategory =
      optEnabled.category && category !== 'none' ? category : 'general';
    const resolvedLanguage = optEnabled.language ? language : 'ko';
    const selectedSentenceId = uuidv4();
    const originalText = selection.text;

    const before = text.slice(0, selection.start);
    const after = text.slice(selection.end);
    const newText = before + candidate + after;

    setText(newText);
    setSelection({ text: '', start: 0, end: 0 });
    setCandidates([]);

    logEvent({
      event: 'editor_selected_paraphrasing',
      doc_id: docId,
      user_id: effectiveUser?.id,
      recommend_session_id: recommendId,
      source_recommend_event_id: recommendInsertId,
      index: typeof index === 'number' ? index : 0,
      was_accepted: true,
      selected_sentence_id: selectedSentenceId,
      total_paraphrasing_sentence_count: totalCandidates,
      maintenance: resolvedMaintenance,
      field: resolvedCategory,
      target_language: resolvedLanguage,
      selected_candidate_text: candidate,
      final_category: category,
    });

    logEvent({
      event: 'correction_history',
      history_id: uuidv4(),
      user_id: effectiveUser?.id,
      doc_id: docId,
      original_text: originalText,
      selected_text: candidate,
      created_at: new Date().toISOString(),
    });
  };

  if (!effectiveUser) {
    return (
      <div className="h-screen flex">
        <Login />
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col">
      <Header onLogout={handleLogout} />
      <div className="grid grid-cols-[240px_1fr_320px] gap-0 h-[calc(100vh-4rem)]">
        <aside className="border-r p-4">
          <Sidebar
            docs={docs}
            currentId={currentId}
            onNew={handleNewDraft}
            onSelect={handleSelectDraft}
            onDelete={handleDeleteDraft}
          />
        </aside>
        <main className="p-4">
          <h1 className="text-xl font-semibold mb-3">에디터</h1>
          <Editor
            text={text}
            setText={setText}
            onSelectionChange={handleSelectionChange}
          />
          <DebugPanel
            text={text}
            selection={selection}
            context={context}
            options={{ category, language, strength, requestText, optEnabled, recoOptions, contextHash }}
            docId={docId}
            recommendId={recommendId}
            scoringInfo={scoringInfo}
          />
        </main>
        <aside className="border-l p-4">
          <h2 className="text-lg font-semibold mb-4">옵션 패널</h2>
          <OptionPanel
            selectedText={selection.text}
            category={category} setCategory={setCategory}
            language={language} setLanguage={setLanguage}
            strength={strength} setStrength={setStrength}
            requestText={requestText} setRequestText={setRequestText}
            optEnabled={optEnabled} setOptEnabled={setOptEnabled}
            onRun={() => handleRunCorrection(false)}
            candidates={candidates}
            onApplyCandidate={handleApplyCandidate}
          />
        </aside>
      </div>
    </div>
  );
}
