(() => {
  "use strict";

  const dataNode = document.getElementById("security-dashboard-data");
  const filterForm = document.getElementById("security-filter-form");
  if (!dataNode || !filterForm || typeof Chart === "undefined") return;

  const dashboard = JSON.parse(dataNode.textContent || "{}");
  const styles = getComputedStyle(document.body);
  const accent = styles.getPropertyValue("--admin-accent").trim() || "#EC0000";
  const ink = styles.getPropertyValue("--admin-ink").trim() || "#242424";
  const muted = styles.getPropertyValue("--admin-muted").trim() || "#6F7779";
  const grid = styles.getPropertyValue("--admin-line").trim() || "#E1E4E5";
  const palette = [accent, "#8B1E37", "#0E5F78", "#4E2A97", "#6F7779", "#C1080F", "#732645"];

  const chart = (canvasId, type, labels, values, title, onSelect) => {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const colors = labels.map((_, index) => palette[index % palette.length]);
    new Chart(canvas, {
      type,
      data: {
        labels,
        datasets: [{
          label: title,
          data: values,
          backgroundColor: type === "line" ? "rgb(236 0 0 / 14%)" : colors,
          borderColor: type === "line" ? accent : colors,
          borderWidth: type === "line" ? 2 : 0,
          borderRadius: type === "bar" ? 4 : 0,
          fill: type === "line",
          tension: 0.28,
          pointRadius: type === "line" ? 3 : undefined,
          pointHoverRadius: type === "line" ? 5 : undefined,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: type === "pie" || type === "doughnut", position: "bottom", labels: { color: muted, usePointStyle: true, padding: 18 } },
          title: { display: false, text: title },
          tooltip: { backgroundColor: "#242424", titleColor: "#fff", bodyColor: "#fff", padding: 10, cornerRadius: 6 },
        },
        scales: type === "line" || type === "bar" ? {
          x: { ticks: { color: muted }, grid: { display: false }, border: { display: false } },
          y: { beginAtZero: true, ticks: { precision: 0, color: muted }, grid: { color: grid }, border: { display: false } },
        } : {},
        color: ink,
        onClick: (_event, elements) => {
          if (!elements.length || typeof onSelect !== "function") return;
          const selected = labels[elements[0].index];
          onSelect(selected);
        },
      },
    });
  };

  const applyFilter = (name, value) => {
    const field = filterForm.elements.namedItem(name);
    if (!field) return;
    field.value = value;
    const page = filterForm.elements.namedItem("page");
    if (page) page.value = "1";
    filterForm.requestSubmit();
  };

  chart(
    "audit-timeseries-chart",
    "line",
    dashboard.timeseries.map((item) => item.date),
    dashboard.timeseries.map((item) => item.count),
    "Eventos por dia (UTC)",
    (day) => {
      const start = filterForm.elements.namedItem("date_from");
      const end = filterForm.elements.namedItem("date_to");
      start.value = day;
      end.value = day;
      const page = filterForm.elements.namedItem("page");
      if (page) page.value = "1";
      filterForm.requestSubmit();
    },
  );
  chart(
    "audit-event-types-chart",
    "bar",
    dashboard.breakdowns.event_types.map((item) => item.value),
    dashboard.breakdowns.event_types.map((item) => item.count),
    "Eventos por tipo",
    (value) => applyFilter("event_type", value),
  );
  chart(
    "audit-sources-chart",
    "bar",
    dashboard.breakdowns.source_components.map((item) => item.value),
    dashboard.breakdowns.source_components.map((item) => item.count),
    "Eventos por componente",
    (value) => applyFilter("source_component", value),
  );
  chart(
    "audit-users-chart",
    "bar",
    dashboard.breakdowns.users.map((item) => item.value),
    dashboard.breakdowns.users.map((item) => item.count),
    "Eventos por usuário identificado",
    (value) => applyFilter("user_identifier", value),
  );
})();
