export function csrf() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.getAttribute("content") : "";
}

export async function getJSON(url) {
  const response = await fetch(url, {
    credentials: "same-origin",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error("HTTP " + response.status);
  return response.json();
}

export async function postJSON(url, body) {
  const response = await fetch(url, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      "X-CSRFToken": csrf(),
    },
    body: JSON.stringify(body || {}),
  });
  if (!response.ok) throw new Error("HTTP " + response.status);
  return response.json();
}
