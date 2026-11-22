const fetchOriginal = globalThis.fetch;
globalThis.fetch = async function(input, options) {
  const url = new URL(typeof input === 'string' || input instanceof URL ? input : input.url);
  const category = url.pathname.replace(/\/u\/[a-f0-9]+/, '/u/key').replace(/[a-f0-9]{32,}/g, 'hash').replace(/\/d\/[^/]+/, '/d/id');
  const start = performance.now();
  const result = await fetchOriginal(input, options);
  console.log('HTTP', options?.method || 'GET', category, result.status, Math.round(performance.now()-start));
  return result;
};
