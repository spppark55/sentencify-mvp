// App.jsx
import { useEffect, useState } from 'react';
import { v4 as uuidv4 } from 'uuid';
import Header from './Header.jsx';
import Sidebar from './Sidebar.jsx';
import Editor from './Editor.jsx';
import OptionPanel from './OptionPanel.jsx';
import { logEvent } from './utils/logger.js';
import DebugPanel from './DebugPanel.jsx';
import { postRecommend } from './utils/api.js';

// ✅ 추가: AuthContext & Login 불러오기
import { useAuth } from './auth/AuthContext.jsx';
import Login from './auth/Login.jsx';

const STORAGE_KEY = 'editor:docs:v1'; // 🔹 여러 문서를 한 번에 저장하는 키

export default function App() {
  // ✅ 임시 유저 제거하고, AuthContext에서 user / logout 사용
  const { user, logout } = useAuth();

  // 🔹 문서 리스트 & 현재 문서 id
  const [docs, setDocs] = useState([]); // [{ id, title, text, updatedAt }, ...]
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

  // 교정 후보 리스트 상태
  const [candidates, setCandidates] = useState([]);

  // Phase 식별자 (문서 id와 동일하게 가져가자)
  const [docId, setDocId] = useState(null);
  const [recommendId, setRecommendId] = useState(null); // recommend_session_id
  const [recommendInsertId, setRecommendInsertId] = useState(null); // A.insert_id
  const [recoOptions, setRecoOptions] = useState([]);
  const [contextHash, setContextHash] = useState(null);

  // 🔹 제목 만들어주는 헬퍼 (처음 20자)
  const makeTitle = (t) => {
    const trimmed = (t || '').trim();
    if (!trimmed) return '새 문서';
    if (trimmed.length <= 20) return trimmed;
    return trimmed.slice(0, 20) + '…';
  };

  // 🔹 초기 로드: localStorage에서 문서 리스트 읽기
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

        // 문서가 하나도 없다면 기본 문서 생성
        if (loadedDocs.length === 0) {
          const id = uuidv4();
          const initialDocs = [
            {
              id,
              title: '새 문서',
              text: '',
              updatedAt: new Date().toISOString(),
            },
          ];
          setDocs(initialDocs);
          setCurrentId(id);
          setDocId(id);
          setText('');
          localStorage.setItem(
            STORAGE_KEY,
            JSON.stringify({ docs: initialDocs, currentId: id }),
          );
        } else {
          setDocs(loadedDocs);
          setCurrentId(loadedCurrentId);
          setDocId(loadedCurrentId);
          const currentDoc = loadedDocs.find((d) => d.id === loadedCurrentId);
          setText(currentDoc?.text || '');
        }
      } else {
        // 저장된 게 전혀 없으면 기본 문서 하나 생성
        const id = uuidv4();
        const initialDocs = [
          {
            id,
            title: '새 문서',
            text: '',
            updatedAt: new Date().toISOString(),
          },
        ];
        setDocs(initialDocs);
        setCurrentId(id);
        setDocId(id);
        setText('');
        localStorage.setItem(
          STORAGE_KEY,
          JSON.stringify({ docs: initialDocs, currentId: id }),
        );
      }
    } catch (e) {
      console.error('Failed to load docs from localStorage', e);
    }
  }, []);

  // 🔹 현재 문서(text)가 바뀔 때마다 docs 배열 & localStorage에 저장
  useEffect(() => {
    if (!currentId) return;

    setDocs((prev) => {
      const now = new Date().toISOString();
      const idx = prev.findIndex((d) => d.id === currentId);
      let next;

      if (idx === -1) {
        // 현재 id에 해당하는 문서가 없으면 새로 추가
        next = [
          {
            id: currentId,
            title: makeTitle(text),
            text,
            updatedAt: now,
          },
          ...prev,
        ];
      } else {
        next = prev.map((d) =>
          d.id === currentId
            ? {
                ...d,
                text,
                title: makeTitle(text),
                updatedAt: now,
              }
            : d,
        );
      }

      try {
        localStorage.setItem(
          STORAGE_KEY,
          JSON.stringify({ docs: next, currentId }),
        );
      } catch {}

      return next;
    });
  }, [text, currentId]);

  // 새 글 시작(좌측 사이드바에서 호출)
  const handleNewDraft = () => {
    const id = uuidv4();
    const newDoc = {
      id,
      title: '새 문서',
      text: '',
      updatedAt: new Date().toISOString(),
    };

    setDocs((prev) => [newDoc, ...prev]);
    setCurrentId(id);
    setDocId(id);
    setText('');
    setSelection({ text: '', start: 0, end: 0 });
    setContext({ prev: '', next: '' });
    setRecommendId(null);
    setRecommendInsertId(null);
    setRecoOptions([]);
    setContextHash(null);
    setCandidates([]);
  };

  // 🔹 사이드바에서 문서 클릭 시
  const handleSelectDraft = (id) => {
    const doc = docs.find((d) => d.id === id);
    if (!doc) return;

    setCurrentId(id);
    setDocId(id);
    setText(doc.text || '');
    setSelection({ text: '', start: 0, end: 0 });
    setContext({ prev: '', next: '' });
    setRecommendId(null);
    setRecommendInsertId(null);
    setRecoOptions([]);
    setContextHash(null);
    setCandidates([]);
  };

  // 🔹 사이드바에서 문서 삭제
  const handleDeleteDraft = (id) => {
    const ok = window.confirm('이 문서를 삭제하시겠습니까?');
    if (!ok) return;

    let nextDocs = docs.filter((d) => d.id !== id);

    // 현재 보고 있던 문서를 삭제한 경우
    let nextCurrentId = currentId;
    let nextText = text;

    if (id === currentId) {
      if (nextDocs.length > 0) {
        // 남은 문서 중 첫 번째로 이동
        nextCurrentId = nextDocs[0].id;
        nextText = nextDocs[0].text || '';
      } else {
        // 하나도 안 남으면 새 문서 하나 생성
        const newId = uuidv4();
        const blankDoc = {
          id: newId,
          title: '새 문서',
          text: '',
          updatedAt: new Date().toISOString(),
        };
        nextDocs = [blankDoc];
        nextCurrentId = newId;
        nextText = '';
      }
    }

    setDocs(nextDocs);
    setCurrentId(nextCurrentId);
    setDocId(nextCurrentId);
    setText(nextText);

    // 선택/후보/추천 상태 초기화
    setSelection({ text: '', start: 0, end: 0 });
    setContext({ prev: '', next: '' });
    setRecommendId(null);
    setRecommendInsertId(null);
    setRecoOptions([]);
    setContextHash(null);
    setCandidates([]);

    // localStorage 동기화
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ docs: nextDocs, currentId: nextCurrentId }),
      );
    } catch {}
  };

  // ✅ 로그아웃(헤더에서 호출)
  //    - auth.logout() 호출 → user=null → App이 Login 화면으로 전환
  //    - 에디터 관련 로컬 상태 & localStorage도 초기화
  const handleLogout = () => {
    // 인증 정보 초기화 (AuthContext)
    logout();

    // 에디터 상태 초기화
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {}
    setDocs([]);
    setCurrentId(null);
    setDocId(null);
    setText('');
    setSelection({ text: '', start: 0, end: 0 });
    setContext({ prev: '', next: '' });
    setCategory('none');
    setLanguage('ko');
    setStrength(1);
    setRequestText('');
    setOptEnabled({ category: true, language: true, strength: true });
    setRecommendId(null);
    setRecommendInsertId(null);
    setRecoOptions([]);
    setContextHash(null);
    setCandidates([]);

    // 필요하면 alert 유지하거나 제거
    // alert('로그아웃되었습니다.');
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
      user_id: user?.id ?? 'anonymous', // ✅ AuthContext에서 받은 user
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
      llm_name: 'gemini-2.5-flash',
      selected_text: selection.text,
      selection_start: selection.start,
      selection_end: selection.end,
    });

    // intensity 매핑
    const intensityMap = ['weak', 'moderate', 'strong'];
    const intensityLabel = intensityMap[strength] || 'moderate';

    const payload = {
      source_recommend_event_id: recommendInsertId,
      recommend_session_id: recommendId,
      doc_id: docId,
      user_id: user?.id ?? 'anonymous',
      context_hash: contextHash,
      selected_text: selection.text,
      target_category: category !== 'none' ? category : '이메일',
      target_language: language || 'ko',
      target_intensity: intensityLabel,
    };

    const started = performance.now();
    try {
      const result = await postParaphrase(payload);
      const list = result.candidates;
      const elapsed = Math.round(performance.now() - started);

      const safeList = Array.isArray(list) ? list : list ? [list] : [];

    // 후보 리스트 상태에 저장 → OptionPanel에서 버튼으로 보여줌
    setCandidates(safeList);

    // 후보가 생성된 것에 대한 별도 로그
    logEvent({
      event: 'editor_paraphrasing_candidates',
      recommend_session_id: recommendId,
      source_recommend_event_id: recommendInsertId,
      candidate_count: list.length,
      response_time_ms: elapsed,
      selected_text: selection.text,
      selection_start: selection.start,
      selection_end: selection.end,
      style_request: requestText,
      category,
      language,
      strength,
    });
  };

  // 후보 클릭 시 본문 반영하는 핸들러
  const handleApplyCandidate = (candidate, index) => {
    if (!selection.text) {
      alert('적용할 문장을 찾을 수 없습니다. 다시 문장을 선택하고 실행해 주세요.');
      return;
    }

    const before = text.slice(0, selection.start);
    const after = text.slice(selection.end);
    const newText = before + candidate + after;

    setText(newText);
    setSelection({ text: '', start: 0, end: 0 });
    setCandidates([]);

    // 최종 채택 로그
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

    // 히스토리 로그
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

  // ✅ 여기서 "로그인 여부"에 따라 다른 화면 렌더링
  if (!user) {
    // 로그인 안 된 상태 → 로그인 페이지부터 시작
    return (
      <div className="h-screen flex">
        <Login />
      </div>
    );
  }

  // ✅ user가 있을 때만 원래 에디터 3열 레이아웃 보여주기
  return (
    <div className="h-screen flex flex-col">
      {/* 상단 헤더 */}
      <Header onLogout={handleLogout} />

      {/* 본문 3열 레이아웃: Sidebar | Editor | OptionPanel */}
      <div
        className="
          grid 
          grid-cols-[240px_1fr_320px] 
          gap-0 
          h-[calc(100vh-4rem)] 
        "
      >
        {/* 사이드바 */}
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
