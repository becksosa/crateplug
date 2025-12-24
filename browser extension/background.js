chrome.action.onClicked.addListener(async (tab) => {
  if (!tab.url) return;

  fetch("http://127.0.0.1:48721/download", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: tab.url })
  }).catch(() => {
    // GUI not running — silently fail
  });
});
