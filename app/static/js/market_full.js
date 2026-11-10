/**
 * 전체시세보기 — 경매차수 구간 + 트림/주행/사고 집계 + 매트릭스
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
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function toast(msg, type) {
    const el = document.getElementById("toastHost") || document.body;
    const div = document.createElement("div");
    div.className = `alert alert-${type || "info"} position-fixed top-0 end-0 m-3 shadow`;
    div.style.zIndex = 2000;
    div.textContent = msg;
    el.appendChild(div);
    setTimeout(() => div.remove(), 2800);
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
      const data = await r.json();
      sel.innerHTML = `<option value="">—</option>` + data.map((v) => {
        if (v && typeof v === "object") {
          return `<option value="${esc(v.value)}">${esc(v.label != null ? v.label : v.value)}</option>`;
        }
        return `<option value="${esc(v)}">${esc(v)}</option>`;
      }).join("");
      sel.disabled = false;
    } catch (e) {
      sel.innerHTML = `<option value="">—</option>`;
    }
  }

  function qs(obj) {
    const p = new URLSearchParams();
    Object.entries(obj || {}).forEach(([k, v]) => {
      if (v !== undefined && v !== null && String(v) !== "") p.set(k, v);
    });
    if (window.LANG) p.set("lang", window.LANG);
    return p.toString();
  }

  function filters() {
    return {
      week_from: g("weekFrom").value,
      week_to: g("weekTo").value,
      maker: g("f-maker").value,
      model_name: g("f-model").value,
      mdetail_name: g("f-mdetail").value,
      grade_name: g("f-grade").value,
      gdetail_name: g("f-gdetail").value,
      car_year: g("f-year").value,
      fuel: g("f-fuel").value,
      q: (g("qWord").value || "").trim(),
    };
  }

  function hasWeeks(f) {
    return !!(f.week_from && f.week_to);
  }

  function hasMatrixCriteria(f) {
    return !!(f.maker || f.model_name || f.q);
  }

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
      accident_free: "accident-free",
      week_from: "week-from",
      week_to: "week-to",
      title: "sample-title",
    };
    return Object.entries(map)
      .filter(([k]) => obj[k] !== undefined && obj[k] !== null && obj[k] !== "")
      .map(([k, attr]) => {
        const raw = String(obj[k]);
        const val = k === "title" ? encodeURIComponent(raw) : esc(raw);
        return `data-${attr}="${val}"`;
      })
      .join(" ");
  }

  function readPayload(el) {
    const d = el.dataset;
    let title = "";
    if (d.sampleTitle) {
      try { title = decodeURIComponent(d.sampleTitle); } catch (e) { title = d.sampleTitle; }
    }
    if (!title) {
      title = [d.maker, d.mdetailName || d.modelName, d.carYear, d.kmBin]
        .filter(Boolean).join(" · ");
    }
    return {
      maker: d.maker || "",
      model_name: d.modelName || "",
      mdetail_name: d.mdetailName || "",
      grade_name: d.gradeName || "",
      gdetail_name: d.gdetailName || "",
      car_year: d.carYear || "",
      km_bin: d.kmBin || "",
      fuel: d.fuel || "",
      accident_free: d.accidentFree || "",
      week_from: d.weekFrom || g("weekFrom").value || "",
      week_to: d.weekTo || g("weekTo").value || "",
      title,
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
    const f = filters();
    if (g("f-mdetail").value) {
      fill(g("f-grade"), `/api/cascade/grades?${qs(f)}`);
      fill(g("f-year"), `/api/cascade/years?${qs(f)}`);
    }
  };
  g("f-grade").onchange = () => {
    resetSelect(g("f-gdetail"));
    if (g("f-grade").value) fill(g("f-gdetail"), `/api/cascade/gdetails?${qs(filters())}`);
  };

  function lbl(row, key) {
    return row[`${key}_label`] != null && row[`${key}_label`] !== "" ? row[`${key}_label`] : (row[key] || "-");
  }

  function rowPayload(row) {
    const f = filters();
    return {
      maker: row.maker,
      model_name: row.model_name,
      mdetail_name: row.mdetail_name,
      grade_name: row.grade_name,
      gdetail_name: row.gdetail_name,
      car_year: row.car_year,
      km_bin: row.km_bin,
      fuel: row.fuel,
      accident_free: row.is_accident_free_flag ? "1" : "0",
      week_from: f.week_from,
      week_to: f.week_to,
      title: [
        lbl(row, "maker"), lbl(row, "mdetail_name") || lbl(row, "model_name"),
        row.car_year, row.km_bin, row.is_accident_free,
      ].filter((v) => v && v !== "-").join(" · "),
    };
  }

  async function search() {
    const body = g("fullGrid");
    const f = filters();
    if (!hasWeeks(f)) {
      body.innerHTML = `<tr><td colspan="12" class="text-center text-muted py-5">${esc(t("pick_weeks"))}</td></tr>`;
      return;
    }
    body.innerHTML = `<tr><td colspan="12" class="text-center text-muted py-5">${esc(t("searching"))}</td></tr>`;
    try {
      const r = await fetch(`/market/api/full-grid?${qs(f)}`);
      const data = await r.json();
      if (!data.ok) {
        body.innerHTML = `<tr><td colspan="12" class="text-center text-danger py-5">${esc(data.error || t("search_fail"))}</td></tr>`;
        return;
      }
      if (!data.rows || !data.rows.length) {
        body.innerHTML = `<tr><td colspan="12" class="text-center text-muted py-5">${esc(t("no_results"))}</td></tr>`;
        return;
      }
      body.innerHTML = data.rows.map((row) => {
        const p = rowPayload(row);
        return `<tr>
          <td>${esc(lbl(row, "maker"))}</td>
          <td>${esc(lbl(row, "model_name"))}</td>
          <td>${esc(lbl(row, "mdetail_name"))}</td>
          <td>${esc(lbl(row, "grade_name"))}</td>
          <td>${esc(lbl(row, "gdetail_name"))}</td>
          <td>${esc(row.car_year ?? "-")}</td>
          <td>${esc(lbl(row, "fuel"))}</td>
          <td>${esc(row.km_bin || "-")}</td>
          <td>${esc(row.is_accident_free || "-")}</td>
          <td class="fw-semibold">${row.hammer_avg != null ? Number(row.hammer_avg).toLocaleString() : "-"}</td>
          <td>${esc(row.sample_count ?? 0)}</td>
          <td>
            <div class="btn-group btn-group-sm flex-wrap">
              <button type="button" class="btn btn-outline-primary sample-btn" ${dataAttrs(p)}>${esc(t("samples"))}</button>
              <button type="button" class="btn btn-outline-secondary matrix-row-btn" ${dataAttrs(p)}>${esc(t("matrix"))}</button>
            </div>
          </td>
        </tr>`;
      }).join("");
    } catch (e) {
      body.innerHTML = `<tr><td colspan="12" class="text-center text-danger py-5">${esc(t("search_fail"))}</td></tr>`;
    }
  }

  async function renderMatrix(params) {
    const panel = g("matrixPanel");
    panel.classList.remove("d-none");
    g("matrixSub").textContent = [
      params.week_from && params.week_to ? `${params.week_from}~${params.week_to}` : "",
      params.maker, params.model_name, params.mdetail_name,
      params.grade_name, params.gdetail_name, params.fuel, params.q,
    ].filter(Boolean).join(" · ");
    g("matrixHead").innerHTML = "";
    g("matrixBody").innerHTML = `<tr><td class="text-muted py-3">${esc(t("searching"))}</td></tr>`;
    try {
      const q = { ...params };
      if (params.q && !params.car_name) q.car_name = params.q;
      const r = await fetch("/api/matrix?" + qs(q));
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
            title: [params.maker, params.gdetail_name || params.mdetail_name || params.model_name || params.q, y, b]
              .filter(Boolean).join(" · "),
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

  const modalEl = g("bpSamplesModal");
  let modal = null;
  if (modalEl && window.bootstrap) {
    document.body.appendChild(modalEl);
    modal = bootstrap.Modal.getOrCreateInstance(modalEl);
  }

  async function openSamples(payload) {
    if (!modal) return toast(t("samples_empty"), "warning");
    const heading = payload.title
      || [payload.maker, payload.mdetail_name || payload.model_name, payload.car_year, payload.km_bin]
        .filter(Boolean).join(" · ");
    g("bpSamplesModalLabel").textContent = heading || t("samples_title");
    g("bpSamplesSubtitle").textContent = heading ? t("samples_title") : "";
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
          item.grade_name, item.gdetail_name, item.accident_detail,
          item.hope_price != null ? `희망 ${item.hope_price}` : "",
        ].filter(Boolean).join(" · ");
        return `<tr>
          <td class="small text-nowrap">${esc(item.auction_date || "-")}</td>
          <td>
            <div class="fw-semibold">${esc(item.car_name || "-")}</div>
            <div class="small text-muted">${esc(detail)}</div>
          </td>
          <td>${esc(item.car_year)}</td>
          <td>${item.car_km != null ? Number(item.car_km).toLocaleString() + "km" : esc(item.km_bin || "-")}</td>
          <td>${esc(item.accident_grade || item.accident_status || "-")}</td>
          <td class="text-end fw-bold">${item.hammer_price != null ? Number(item.hammer_price).toLocaleString() : "-"}</td>
          <td class="small">${esc(item.imported || "-")}</td>
        </tr>`;
      }).join("");
      g("bpSamplesContent").classList.remove("d-none");
    } catch (e) {
      g("bpSamplesLoading").classList.add("d-none");
      g("bpSamplesEmpty").classList.remove("d-none");
      toast(t("search_fail"), "danger");
    }
  }

  g("fullSearch").addEventListener("click", search);
  g("fullMatrix").addEventListener("click", () => {
    const f = filters();
    if (!hasWeeks(f)) return toast(t("pick_weeks"), "warning");
    if (!hasMatrixCriteria(f)) return toast(t("matrix_need_criteria"), "warning");
    const params = { ...f };
    if (f.q) params.car_name = f.q;
    renderMatrix(params);
  });
  g("fullExport").addEventListener("click", () => {
    const f = filters();
    if (!hasWeeks(f)) {
      g("fullGrid").innerHTML =
        `<tr><td colspan="12" class="text-center text-muted py-5">${esc(t("pick_weeks"))}</td></tr>`;
      return;
    }
    window.location.href = `/market/api/export/full-grid?${qs(f)}`;
  });
  g("qWord").addEventListener("keydown", (e) => {
    if (e.key === "Enter") search();
  });

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
      const p = readPayload(matrixBtn);
      if (p.q) p.car_name = p.q;
      renderMatrix(p);
    }
  });
})();
