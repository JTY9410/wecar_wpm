/**
 * 도매시세분석 — 낙찰가 기준 그리드/매트릭스/모수 세부내역
 */
(function () {
  const t = (k, vars) => {
    let s = (window.I18N && window.I18N[k]) || k;
    if (vars) Object.keys(vars).forEach((key) => { s = s.replace(`{${key}}`, vars[key]); });
    return s;
  };
  const g = (id) => document.getElementById(id);
  const unit = () => t("unit_man");

  function esc(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function resetSelect(sel) {
    sel.innerHTML = `<option value="">—</option>`;
    sel.disabled = true;
  }

  async function fill(sel, url) {
    sel.disabled = true;
    sel.innerHTML = `<option value="">…</option>`;
    try {
      const r = await fetch(url);
      if (!r.ok) throw new Error("fail");
      const data = await r.json();
      sel.innerHTML = `<option value="">—</option>` + data.map((v) => `<option>${esc(v)}</option>`).join("");
      sel.disabled = false;
    } catch (e) {
      sel.innerHTML = `<option value="">—</option>`;
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
    Object.entries(obj || {}).forEach(([k, v]) => {
      if (v !== undefined && v !== null && String(v) !== "") p.set(k, v);
    });
    if (window.LANG) p.set("lang", window.LANG);
    return p.toString();
  }

  /** data-* 속성으로 안전하게 전달 (JSON-in-attr 깨짐 방지) */
  function dataAttrs(obj) {
    const map = {
      maker: "maker",
      model_name: "model-name",
      mdetail_name: "mdetail-name",
      grade_name: "grade-name",
      gdetail_name: "gdetail-name",
      car_year: "car-year",
      km_bin: "km-bin",
      fuel: "fuel",
      awd: "awd",
      accident_free: "accident-free",
      title: "sample-title",
    };
    return Object.entries(map)
      .filter(([k]) => obj[k] !== undefined && obj[k] !== null && obj[k] !== "")
      .map(([k, attr]) => `data-${attr}="${esc(obj[k])}"`)
      .join(" ");
  }

  function readPayload(el) {
    const d = el.dataset;
    return {
      maker: d.maker || "",
      model_name: d.modelName || "",
      mdetail_name: d.mdetailName || "",
      grade_name: d.gradeName || "",
      gdetail_name: d.gdetailName || "",
      car_year: d.carYear || "",
      km_bin: d.kmBin || "",
      fuel: d.fuel || "",
      awd: d.awd || "",
      accident_free: d.accidentFree || "",
      title: d.sampleTitle || "",
    };
  }

  g("f-maker").onchange = () => {
    resetSelect(g("f-model")); resetSelect(g("f-mdetail")); resetSelect(g("f-grade"));
    resetSelect(g("f-gdetail")); resetSelect(g("f-year")); resetSelect(g("f-fuel"));
    if (g("f-maker").value) {
      fill(g("f-model"), `/api/cascade/models?maker=${encodeURIComponent(g("f-maker").value)}`);
      fill(g("f-fuel"), `/api/cascade/fuels?maker=${encodeURIComponent(g("f-maker").value)}`);
    }
  };
  g("f-model").onchange = () => {
    resetSelect(g("f-mdetail")); resetSelect(g("f-grade")); resetSelect(g("f-gdetail")); resetSelect(g("f-year"));
    if (g("f-model").value) {
      fill(g("f-mdetail"), `/api/cascade/car_names?${qs({ maker: g("f-maker").value, model_name: g("f-model").value })}`);
    }
  };
  g("f-mdetail").onchange = () => {
    resetSelect(g("f-grade")); resetSelect(g("f-gdetail")); resetSelect(g("f-year"));
    if (g("f-mdetail").value) {
      const f = filters();
      fill(g("f-grade"), `/api/cascade/grades?${qs(f)}`);
      fill(g("f-year"), `/api/cascade/years?${qs(f)}`);
    }
  };
  g("f-grade").onchange = () => {
    resetSelect(g("f-gdetail"));
    if (g("f-grade").value) fill(g("f-gdetail"), `/api/cascade/gdetails?${qs(filters())}`);
  };

  function rowActions(x) {
    const payload = {
      maker: x.maker, model_name: x.model_name, mdetail_name: x.mdetail_name,
      grade_name: x.grade_name, gdetail_name: x.gdetail_name,
      car_year: x.car_year, km_bin: x.km_bin, fuel: x.fuel, awd: x.awd,
      accident_free: x.is_accident_free_flag ? "1" : "0",
      title: [x.maker, x.model_name, x.gdetail_name, x.car_year, x.km_bin].filter(Boolean).join(" · "),
    };
    return `<div class="btn-group btn-group-sm">
      <button type="button" class="btn btn-outline-primary sample-btn" ${dataAttrs(payload)}>${esc(t("samples"))}</button>
      <button type="button" class="btn btn-outline-secondary matrix-row-btn" ${dataAttrs(payload)}>${esc(t("matrix"))}</button>
    </div>`;
  }

  g("f-search").onclick = async () => {
    const f = filters();
    if (!f.maker) return toast(t("select_maker"), "warning");
    g("grid").innerHTML = `<tr><td colspan="14" class="text-center py-4 text-muted">${esc(t("searching"))}</td></tr>`;
    try {
      const r = await fetch("/api/grid?" + qs(f));
      const rows = await r.json();
      if (!rows.length) {
        g("grid").innerHTML = `<tr><td colspan="14" class="text-center text-muted py-4">${esc(t("no_results"))}</td></tr>`;
        return;
      }
      g("grid").innerHTML = rows.map((x) => `<tr>
        <td>${esc(x.maker)}</td>
        <td>${esc(x.model_name)}</td>
        <td>${esc(x.mdetail_name)}</td>
        <td>${esc(x.grade_name)}</td>
        <td class="small">${esc(x.gdetail_name)}</td>
        <td>${esc(x.fuel)}</td>
        <td>${esc(x.awd)}</td>
        <td>${esc(x.is_accident_free)}</td>
        <td>${esc(x.car_year)}</td>
        <td>${esc(x.km_bin)}</td>
        <td class="fw-semibold text-end">${x.hammer_avg != null ? Number(x.hammer_avg).toLocaleString() : "-"}</td>
        <td>${x.mom_pct == null ? "-" : x.mom_pct + "%"}</td>
        <td>${x.sample_count || 0}</td>
        <td class="text-nowrap">${rowActions(x)}</td>
      </tr>`).join("");
    } catch (e) {
      g("grid").innerHTML = `<tr><td colspan="14" class="text-center text-danger py-4">${esc(t("search_fail"))}</td></tr>`;
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
    g("matrixBody").innerHTML = `<tr><td class="text-muted py-3">${esc(t("searching"))}</td></tr>`;
    try {
      const r = await fetch("/api/matrix?" + qs(params));
      const data = await r.json();
      if (!data.years?.length) {
        g("matrixBody").innerHTML = `<tr><td class="text-muted py-3">${esc(t("no_results"))}</td></tr>`;
        return;
      }
      g("matrixHead").innerHTML = `<tr><th class="year-col">${esc(t("year"))}</th>${
        data.buckets.map((b) => `<th>${esc(b)}</th>`).join("")
      }</tr>`;
      g("matrixBody").innerHTML = data.years.map((y) => `<tr>
        <td class="year-col">${y}</td>
        ${data.buckets.map((b) => {
          const v = data.matrix[y]?.[b];
          const c = data.counts[y]?.[b] || 0;
          if (v == null) return "<td>-</td>";
          const cell = {
            ...params, car_year: y, km_bin: b,
            title: [params.maker, params.gdetail_name || params.mdetail_name, y, b].filter(Boolean).join(" · "),
          };
          return `<td title="${esc(t("sample_count"))} ${c}">
            <button type="button" class="btn btn-link p-0 sample-btn fw-semibold" ${dataAttrs(cell)}>
              ${Number(v).toLocaleString()} ${esc(unit())}
            </button>
          </td>`;
        }).join("")}
      </tr>`).join("");
      g("matrixSub").textContent += ` · ${t("sample_count")} ${data.total_samples} · ${t("hammer_avg")}`;
      panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } catch (e) {
      g("matrixBody").innerHTML = `<tr><td class="text-danger py-3">${esc(t("search_fail"))}</td></tr>`;
    }
  }

  g("f-matrix").onclick = () => {
    const f = filters();
    if (!f.maker) return toast(t("select_maker"), "warning");
    renderMatrix(f);
  };

  const modalEl = g("bpSamplesModal");
  let modal = null;
  if (modalEl && window.bootstrap) {
    // body 직속으로 옮겨 side-rail/overflow 영향 제거
    document.body.appendChild(modalEl);
    modal = bootstrap.Modal.getOrCreateInstance(modalEl);
  }

  async function openSamples(payload) {
    if (!modal) return toast(t("samples_empty"), "warning");
    g("bpSamplesModalLabel").textContent = t("samples_title");
    g("bpSamplesSubtitle").textContent = payload.title || "";
    g("bpSamplesLoading").classList.remove("d-none");
    g("bpSamplesEmpty").classList.add("d-none");
    g("bpSamplesContent").classList.add("d-none");
    g("bpSamplesTableBody").innerHTML = "";
    modal.show();

    try {
      const r = await fetch("/api/samples?" + qs(payload), {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      });
      const data = await r.json();
      g("bpSamplesLoading").classList.add("d-none");
      if (!r.ok || !data.ok || !data.items?.length) {
        g("bpSamplesEmpty").classList.remove("d-none");
        return;
      }
      g("bpSamplesCount").textContent = t("samples_count", { n: data.count });
      g("bpSamplesTableBody").innerHTML = data.items.map((item) => {
        const detail = [
          item.grade_name, item.gdetail_name, item.accident_detail, item.hope_price != null ? `희망 ${item.hope_price}` : "",
        ].filter(Boolean).join(" · ");
        return `<tr>
          <td>
            <div class="fw-semibold">${esc(item.car_name || "-")}</div>
            <div class="small text-muted">${esc(detail)}</div>
          </td>
          <td>${esc(item.car_year)}</td>
          <td>${esc(item.fuel || "-")}</td>
          <td>${esc(item.awd || "-")}</td>
          <td>${item.car_km != null ? Number(item.car_km).toLocaleString() + "km" : esc(item.km_bin || "-")}</td>
          <td class="text-end fw-bold">${item.hammer_price != null ? Number(item.hammer_price).toLocaleString() : "-"}</td>
          <td>${esc(item.accident_status || "-")}</td>
          <td>${esc(item.imported || "-")}</td>
          <td class="small">${esc(item.auction_date || "-")}</td>
        </tr>`;
      }).join("");
      g("bpSamplesContent").classList.remove("d-none");
    } catch (e) {
      g("bpSamplesLoading").classList.add("d-none");
      g("bpSamplesEmpty").classList.remove("d-none");
      toast(t("search_fail"), "danger");
    }
  }

  document.addEventListener("click", (e) => {
    const sampleBtn = e.target.closest(".sample-btn");
    if (sampleBtn) {
      e.preventDefault();
      openSamples(readPayload(sampleBtn));
      return;
    }
    const matrixBtn = e.target.closest(".matrix-row-btn");
    if (matrixBtn) {
      e.preventDefault();
      renderMatrix(readPayload(matrixBtn));
    }
  });
})();
