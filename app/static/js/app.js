/**
 * 인앱 브라우저(카카오톡/네이버/인스타 등) 감지 및 외부 브라우저 탈출.
 * Android: intent:// → Chrome, iOS: 안내 오버레이 + 링크 복사.
 */
(function () {
  const ua = navigator.userAgent || "";
  const isInApp =
    /KAKAOTALK|NAVER|Instagram|FBAN|FBAV|Line\//i.test(ua) ||
    (/wv/i.test(ua) && /Android/i.test(ua));

  if (!isInApp) return;

  const targetUrl = window.location.href;
  const overlay = document.getElementById("inappEscapeOverlay");
  if (overlay) overlay.classList.remove("d-none");

  const isAndroid = /Android/i.test(ua);
  const isIOS = /iPhone|iPad|iPod/i.test(ua);

  function openExternal() {
    if (isAndroid) {
      const hostPath = targetUrl.replace(/^https?:\/\//, "");
      const intent = `intent://${hostPath}#Intent;scheme=https;package=com.android.chrome;end`;
      window.location.href = intent;
      return;
    }
    // iOS: Safari로 직접 강제 불가 → 안내 + 복사
    copyLink();
  }

  function copyLink() {
    const input = document.getElementById("inappCopyUrl");
    if (input) input.value = targetUrl;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(targetUrl).then(() => {
        const tip = document.getElementById("inappCopyTip");
        if (tip) tip.textContent = "링크가 복사되었습니다. Safari에서 붙여넣기 하세요.";
      });
    }
  }

  const openBtn = document.getElementById("inappOpenBtn");
  const copyBtn = document.getElementById("inappCopyBtn");
  if (openBtn) openBtn.addEventListener("click", openExternal);
  if (copyBtn) copyBtn.addEventListener("click", copyLink);

  if (isAndroid) {
    // 자동 유도 1회 시도
    setTimeout(openExternal, 400);
  }
})();
