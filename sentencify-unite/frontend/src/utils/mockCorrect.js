export async function mockCorrect(payload) {
  console.log('[MockCorrect Input]', payload);

  // 네트워크 지연 유사 효과
  await new Promise((r) => setTimeout(r, 300 + Math.random() * 500));

  const { selected_text, strength, style_request } = payload;
  let result = selected_text ?? '';

  switch (strength) {
    case 0:
      result = result.trim() + ' (가벼운 교정)';
      break;
    case 1:
      result = `[중간 교정] ${result.replace(/\s+/g, ' ').trim()}`;
      break;
    case 2:
      result = `[강한 교정] ${result.toUpperCase()}`;
      break;
    default:
      result = result;
  }

  if (style_request && style_request.trim().length > 0) {
    result += ` [요청사항 반영: ${style_request}]`;
  }

  console.log('[MockCorrect Output]', result);
  return result;
}
