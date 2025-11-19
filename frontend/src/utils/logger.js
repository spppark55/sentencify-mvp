export async function logEvent(eventData) {
  try {
    // 전역 버퍼에 적재 (페이지에서 즉시 확인용)
    if (!window.__eventLog) window.__eventLog = [];
    window.__eventLog.push({
      ts: new Date().toISOString(),
      ...eventData,
    });

    // 콘솔 확인
    console.log('[Event Log]', eventData);

    // 실제 서버 연동 (/log → Vite proxy → FastAPI /log)
    await fetch('/log', {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(eventData),
    });
  } catch (err) {
    console.error('Logging failed:', err);
  }
}
