/**
 * 전체시세보기 — 경매차수 구간 + 트림/주행/사고 집계
 */
(function () {
  const t = (k) => (window.I18N && window.I18N[k]) || k;
  const g = (id) => document.getElementById(id);

  function esc(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
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
      maker: g("f-maker").value,
      model_name: g("f-model").value,
      mdetail_name: g("f-mdetail").value,
      grade_name: g("f-grade").value,
      gdetail_name: g("f-gdetail").value,
      car_year: g("f-year").value,
      fuel: g("f-fuel").value,
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

  async function search() {
    const body = g("fullGrid");
    const weekFrom = g("weekFrom").value;
    const weekTo = g("weekTo").value;
    if (!weekFrom || !weekTo) {
      body.innerHTML = `<tr><td colspan="11" class="text-center text-muted py-5">${esc(t("pick_weeks"))}</td></tr>`;
      return;
    }
    body.innerHTML = `<tr><td colspan="11" class="text-center text-muted py-5">${esc(t("searching"))}</td></tr>`;
    try {
      const r = await fetch(`/market/api/full-grid?${qs({
        week_from: weekFrom, week_to: weekTo, q: g("qWord").value, ...filters(),
      })}`);
      const data = await r.json();
      if (!data.ok) {
        body.innerHTML = `<tr><td colspan="11" class="text-center text-danger py-5">${esc(data.error || t("search_fail"))}</td></tr>`;
        return;
      }
      if (!data.rows || !data.rows.length) {
        body.innerHTML = `<tr><td colspan="11" class="text-center text-muted py-5">${esc(t("no_results"))}</td></tr>`;
        return;
      }
      body.innerHTML = data.rows.map((row) => `<tr>
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
      </tr>`).join("");
    } catch (e) {
      body.innerHTML = `<tr><td colspan="11" class="text-center text-danger py-5">${esc(t("search_fail"))}</td></tr>`;
    }
  }

  g("fullSearch").addEventListener("click", search);
  g("qWord").addEventListener("keydown", (e) => {
    if (e.key === "Enter") search();
  });
})();
