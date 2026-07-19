(() => {
  const instances = new WeakMap();

  async function renderChart(element) {
    if (!window.echarts || instances.has(element)) return;
    const chart = window.echarts.init(element, null, { renderer: "svg" });
    instances.set(element, chart);
    chart.setOption({
      animation: !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
      tooltip: { trigger: "item" },
      radar: { indicator: ["CPL01", "CPL02", "CPL03", "CPL04", "CPL05", "CPL06"].map(name => ({ name, max: 100 })) },
      series: [{ type: "radar", data: [{ name: "Aktual", value: [0, 0, 0, 0, 0, 0] }, { name: "Target", value: [75, 75, 75, 75, 75, 75] }] }],
      color: ["#4f46e5", "#d97706"]
    });
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(element);
    const endpoint = element.dataset.endpoint;
    if (!endpoint) return;
    const container = element.closest("article");
    const status = container?.querySelector("[data-attainment-status]");
    const table = container?.querySelector("[data-attainment-table]");
    try {
      const response = await fetch(endpoint, { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json();
      const rows = payload.data || [];
      if (!rows.length) throw new Error("Data capaian belum tersedia");
      chart.setOption({
        radar: { indicator: rows.map(row => ({ name: row.outcome, max: 100 })) },
        series: [{ type: "radar", data: payload.series }]
      });
      element.setAttribute("aria-label", `Grafik radar ${rows.length} capaian CPL program`);
      if (status) {
        status.textContent = `${rows.length} CPL terverifikasi`;
        status.className = "rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-800";
      }
      if (table) {
        table.replaceChildren(...rows.map(row => {
          const tr = document.createElement("tr");
          [row.outcome, row.actual?.toFixed(2) ?? "—", row.target.toFixed(2), row.status].forEach((value, index) => {
            const cell = document.createElement("td");
            cell.textContent = value;
            cell.className = index === 0 ? "py-2 font-medium" : "py-2";
            tr.appendChild(cell);
          });
          return tr;
        }));
      }
    } catch (error) {
      if (status) {
        status.textContent = "Data belum tersedia";
        status.className = "rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-amber-800";
      }
      if (table) table.innerHTML = '<tr><td class="py-2" colspan="4">Data capaian belum tersedia.</td></tr>';
    }
  }

  function boot(root = document) { root.querySelectorAll("[data-chart]").forEach(renderChart); }
  document.addEventListener("DOMContentLoaded", () => boot());
  document.body.addEventListener("htmx:beforeCleanupElement", event => {
    const chart = instances.get(event.target);
    if (chart) { chart.dispose(); instances.delete(event.target); }
  });
  document.body.addEventListener("htmx:afterSwap", event => boot(event.target));
})();
