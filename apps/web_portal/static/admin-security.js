(() => {
  "use strict";

  const dataNode = document.getElementById("security-dashboard-data");
  const filterForm = document.getElementById("security-filter-form");
  if (!dataNode || !filterForm || typeof Chart === "undefined") return;

  const dashboard = JSON.parse(dataNode.textContent || "{}");
  const palette = ["#9b1220", "#246b57", "#315e8a", "#a35d17", "#6d5a90", "#477d82", "#8b6c32"];

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
          backgroundColor: type === "line" ? "rgb(155 18 32 / 16%)" : colors,
          borderColor: type === "line" ? "#9b1220" : colors,
          borderWidth: type === "line" ? 2 : 1,
          fill: type === "line",
          tension: 0.22,
          pointRadius: type === "line" ? 3 : undefined,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: type !== "bar", position: "bottom" },
          title: { display: false, text: title },
        },
        scales: type === "line" || type === "bar" ? {
          y: { beginAtZero: true, ticks: { precision: 0 } },
        } : {},
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
