const BASE_ENDPOINT = 'http://dev.getsentry.net:8000/api/0';

export async function fetchData(request, url, options = undefined) {
  const res = await fetch(BASE_ENDPOINT + url, {
    headers: {
      cookie: request.headers.get('cookie') || '',
    },
    ...(options || {}),
  });
  if (!res.ok) {
    throw new Error(res.statusText);
  }
  return res.json();
}
