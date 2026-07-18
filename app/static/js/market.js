/**
 * 도매시세분석 — 캐스케이드 · 그리드 · 매트릭스 · 세부내역 · i18n
 */
(function () {
  const t = (k, vars) => {
    let s = (window.I18N && window.I18N[k]) || k;
    if (vars) Object.keys(vars).forEach((key) => {
      s = s.replace(`{${key}}`, vars[key]);
    });
    return s;
  };
  const g = (id) => document.getElementById(id);
  const unit = () => t("unit_man");

  function resetSelect(sel, label) {
    sel.innerHTML = `<option value="">${label || "—"}</option>`;
    sel.disabled = true;
  }

  async function fill(sel, url) {
    sel.disabled = true;
    sel.innerHTML = `<option value="">…</option>`;
    try {
      const r = await fetch(url);
      if (!r.ok) throw new Error("load failed");
      const data = await r.json();
      sel.innerHTML = `<option value="">—</option>` + data.map((v) => `<option>${v}</option>`).join("");
      sel.disabled = false;
    } catch (e) {
      sel.innerHTML = `<option value="">—</option>`;
      if (window.toast) toast("filter error", "warning");
    }
  }

  function filters() {
    return {
      maker: g("f-maker").value,
      model_name: g("f-model").value,
      mdetail_name: g("f-mdetail").value,
      grade_name: g("f-grade").value,
      gdetail_name: g("f-gdetail").value,
      car_year: g("f-year").value,
      fuel: g("f-fuel").value,
      awd: g("f-awd").value,
    };
  }

  function qs(obj) {
    const p = new URLSearchParams();
    Object.entries(obj).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") p.set(k, v);
    });
    if (window.LANG) p.set("lang", window.LANG);
    return p.toString();
  }

  g("f-maker").onchange = () => {
    resetSelect(g("f-model"));
    resetSelect(g("f-mdetail"));
    resetSelect(g("f-grade"));
    resetSelect(g("f-gdetail"));
    resetSelect(g("f-year"));
    resetSelect(g("f-fuel"));
    if (g("f-maker").value) {
      fill(g("f-model"), `/api/cascade/models?maker=${encodeURIComponent(g("f-maker").value)}`);
      fill(g("f-fuel"), `/api/cascade/fuels?maker=${encodeURIComponent(g("f-maker").value)}`);
    }
  };
  g("f-model").onchange = () => {
    resetSelect(g("f-mdetail"));
    resetSelect(g("f-grade"));
    resetSelect(g("f-gdetail"));
    resetSelect(g("f-year"));
    if (g("f-model").value) {
      const m = encodeURIComponent(g("f-maker").value);
      const mo = encodeURIComponent(g("f-model").value);
      fill(g("f-mdetail"), `/api/cascade/car_names?maker=${m}&model_name=${mo}`);
    }
  };
  g("f-mdetail").onchange = () => {
    resetSelect(g("f-grade"));
    resetSelect(g("f-gdetail"));
    resetSelect(g("f-year"));
    if (g("f-mdetail").value) {
      const f = filters();
      fill(g("f-grade"), `/api/cascade/grades?${qs({ maker: f.maker, model_name: f.model_name, mdetail_name: f.mdetail_name })}`);
      fill(g("f-year"), `/api/cascade/years?${qs({ maker: f.maker, model_name: f.model_name, mdetail_name: f.mdetail_name })}`);
    }
  };
  g("f-grade").onchange = () => {
    resetSelect(g("f-gdetail"));
    if (g("f-grade").value) {
      const f = filters();
      fill(g("f-gdetail"), `/api/cascade/gdetails?${qs({
        maker: f.maker, model_name: f.model_name,
        mdetail_name: f.mdetail_name, grade_name: f.grade_name,
      })}`);
    }
  };

  function rowActions(x) {
    const data = encodeURIComponent(JSON.stringify({
      maker: x.maker, model_name: x.model_name, mdetail_name: x.mdetail_name,
      grade_name: x.grade_name, gdetail_name: x.gdetail_name,
      car_year: x.car_year, km_bin: x.km_bin, fuel: x.fuel, awd: x.awd,
      accident_free: x.is_accident_free_flag ? "1" : "0",
      title: [x.maker, x.model_name, x.gdetail_name, x.car_year, x.km_bin].filter(Boolean).join(" · "),
    }));
    return `<div class="btn-group btn-group-sm">
      <button type="button" class="btn btn-outline-primary sample-btn" data-payload="${data}">${t("samples")}</button>
      <button type="button" class="btn btn-outline-secondary matrix-row-btn" data-payload="${data}">${t("matrix")}</button>
    </div>`;
  }

  g("f-search").onclick = async () => {
    const f = filters();
    if (!f.maker) return toast(t("select_maker"), "warning");
    g("grid").innerHTML = `<tr><td colspan="15" class="text-center py-4 text-muted">${t("searching")}</td></tr>`;
    try {
      const r = await fetch("/api/grid?" + qs(f));
      const rows = await r.json();
      if (!rows.length) {
        g("grid").innerHTML = `<tr><td colspan="15" class="text-center text-muted py-4">${t("no_results")}</td></tr>`;
        return;
      }
      g("grid").innerHTML = rows.map((x) => `<tr>
        <td>${x.maker || ""}</td>
        <td>${x.model_name || ""}</td>
        <td>${x.mdetail_name || ""}</td>
        <td>${x.grade_name || ""}</td>
        <td class="small">${x.gdetail_name || ""}</td>
        <td>${x.fuel || ""}</td>
        <td>${x.awd || ""}</td>
        <td>${x.is_accident_free || ""}</td>
        <td>${x.car_year || ""}</td>
        <td>${x.km_bin || ""}</td>
        <td>${x.start_avg?.toFixed?.(0) ?? "-"}</td>
        <td class="fw-semibold">${x.hammer_avg?.toFixed?.(0) ?? "-"}</td>
        <td>${x.mom_pct == null ? "-" : x.mom_pct + "%"}</td>
        <td>${x.sample_count || 0}</td>
        <td class="text-nowrap">${rowActions(x)}</td>
      </tr>`).join("");
    } catch (e) {
      g("grid").innerHTML = `<tr><td colspan="15" class="text-center text-danger py-4">${t("search_fail")}</td></tr>`;
      toast(t("search_fail"), "danger");
    }
  };

  async function renderMatrix(params) {
    const panel = g("matrixPanel");
    panel.classList.remove("d-none");
    g("matrixSub").textContent = [
      params.maker, params.model_name, params.mdetail_name,
      params.grade_name, params.gdetail_name, params.fuel, params.awd,
    ].filter(Boolean).join(" · ");
    g("matrixHead").innerHTML = "";
    g("matrixBody").innerHTML = `<tr><td class="text-muted py-3">${t("searching")}</td></tr>`;
    try {
      const r = await fetch("/api/matrix?" + qs(params));
      const data = await r.json();
      if (!data.years?.length) {
        g("matrixBody").innerHTML = `<tr><td class="text-muted py-3">${t("no_results")}</td></tr>`;
        return;
      }
      g("matrixHead").innerHTML = `<tr><th class="year-col">${t("year")}</th>${
        data.buckets.map((b) => `<th>${b}</th>`).join("")
      }</tr>`;
      g("matrixBody").innerHTML = data.years.map((y) => `<tr>
        <td class="year-col">${y}</td>
        ${data.buckets.map((b) => {
          const v = data.matrix[y]?.[b];
          const c = data.counts[y]?.[b] || 0;
          const payload = encodeURIComponent(JSON.stringify({
            ...params, car_year: y, km_bin: b,
            title: [params.maker, params.gdetail_name || params.mdetail_name, y, b].filter(Boolean).join(" · "),
          }));
          if (v == null) return "<td>-</td>";
          return `<td title="${t("sample_count")} ${c}">
            <button type="button" class="btn btn-link p-0 sample-btn fw-semibold" data-payload="${payload}">
              ${Number(v).toLocaleString()} ${unit()}
            </button>
          </td>`;
        }).join("")}
      </tr>`).join("");
      g("matrixSub").textContent += ` · ${t("sample_count")} ${data.total_samples}`;
      panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } catch (e) {
      g("matrixBody").innerHTML = `<tr><td class="text-danger py-3">${t("search_fail")}</td></tr>`;
    }
  }

  g("f-matrix").onclick = () => {
    const f = filters();
    if (!f.maker) return toast(t("select_maker"), "warning");
    renderMatrix(f);
  };

  // samples modal
  const modalEl = g("bpSamplesModal");
  const modal = modalEl ? bootstrap.Modal.getOrCreateInstance(modalEl) : null;

  async function openSamples(payload) {
    g("bpSamplesModalLabel").textContent = t("samples_title");
    g("bpSamplesSubtitle").textContent = payload.title || "";
    g("bpSamplesLoading").classList.remove("d-none");
    g("bpSamplesEmpty").classList.add("d-none");
    g("bpSamplesContent").classList.add("d-none");
    modal.show();
    try {
      const r = await fetch("/api/samples?" + qs(payload));
      const data = await r.json();
      g("bpSamplesLoading").classList.add("d-none");
      if (!data.ok || !data.items?.length) {
        g("bpSamplesEmpty").classList.remove("d-none");
        return;
      }
      g("bpSamplesCount").textContent = t("samples_count", { n: data.count });
      g("bpSamplesTableBody").innerHTML = data.items.map((item) => `
        <tr>
          <td>
            <button type="button" class="btn btn-link p-0 text-start bp-sample-name">${item.car_name || "-"}</button>
            <div class="small text-muted d-none sample-extra">${item.auction_date || ""} · ${item.accident_detail || ""} · ${item.hope_price ?? "-"}</div>
          </td>
          <td>${item.car_year ?? "-"}</td>
          <td>${item.fuel || "-"}</td>
          <td>${item.awd || "-"}</td>
          <td>${item.car_km?.toLocaleString?.() || item.km_bin || "-"}</td>
          <td class="text-end">${item.start_price ?? "-"}</td>
          <td class="text-end fw-semibold">${item.hammer_price ?? "-"}</td>
          <td>${item.accident_status || "-"}</td>
          <td>${item.imported || "-"}</td>
        </tr>`).join("");
      g("bpSamplesContent").classList.remove("d-none");
      g("bpSamplesTableBody").querySelectorAll(".bp-sample-name").forEach((btn) => {
        btn.addEventListener("click", () => {
          const extra = btn.parentElement.querySelector(".sample-extra");
          if (extra) extra.classList.toggle("d-none");
        });
      });
    } catch (e) {
      g("bpSamplesLoading").classList.add("d-none");
      g("bpSamplesEmpty").classList.remove("d-none");
    }
  }

  document.addEventListener("click", (e) => {
    const sampleBtn = e.target.closest(".sample-btn");
    if (sampleBtn) {
      try {
        openSamples(JSON.parse(decodeURIComponent(sampleBtn.dataset.payload)));
      } catch (_) {}
      return;
    }
    const matrixBtn = e.target.closest(".matrix-row-btn");
    if (matrixBtn) {
      try {
        const p = JSON.parse(decodeURIComponent(matrixBtn.dataset.payload));
        renderMatrix(p);
      } catch (_) {}
    }
  });
})();
