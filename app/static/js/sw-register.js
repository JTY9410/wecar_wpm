(() => {
  if (!("serviceWorker" in navigator)) return;

  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/service-worker.js").catch(() => {});
  });

  let deferredPrompt = null;
  const banner = document.getElementById("pwaInstallBanner");
  const installBtn = document.getElementById("pwaInstallBtn");
  const dismissBtn = document.getElementById("pwaInstallDismiss");

  const dismissed = localStorage.getItem("pwa_install_dismissed") === "1";

  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferredPrompt = e;
    if (!dismissed && banner) banner.classList.remove("d-none");
  });

  if (installBtn) {
    installBtn.addEventListener("click", async () => {
      if (!deferredPrompt) return;
      deferredPrompt.prompt();
      await deferredPrompt.userChoice;
      deferredPrompt = null;
      if (banner) banner.classList.add("d-none");
    });
  }

  if (dismissBtn) {
    dismissBtn.addEventListener("click", () => {
      localStorage.setItem("pwa_install_dismissed", "1");
      if (banner) banner.classList.add("d-none");
    });
  }
})();
