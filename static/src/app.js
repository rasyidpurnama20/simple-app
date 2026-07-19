(() => {
  const instances = new WeakMap();

  function renderChart(element) {
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
  }

  function boot(root = document) { root.querySelectorAll("[data-chart]").forEach(renderChart); }
  document.addEventListener("DOMContentLoaded", () => boot());
  document.body.addEventListener("htmx:beforeCleanupElement", event => {
    const chart = instances.get(event.target);
    if (chart) { chart.dispose(); instances.delete(event.target); }
  });
  document.body.addEventListener("htmx:afterSwap", event => boot(event.target));
})();

