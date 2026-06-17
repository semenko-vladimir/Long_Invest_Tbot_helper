document.addEventListener("input", function (event) {
  var input = event.target.closest("[data-confirm-source]");
  if (!input) {
    return;
  }

  var form = input.closest("form");
  if (!form) {
    return;
  }

  var button = form.querySelector("[data-confirm-button]");
  if (!button) {
    return;
  }

  button.disabled = input.value.trim().toUpperCase() !== input.dataset.confirmTicker;
});

document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll("[data-chart-url]").forEach(initLiveChart);
});

function initLiveChart(root) {
  var refreshMs = Number(root.dataset.refreshMs || "60000");

  function refresh() {
    loadChart(root);
  }

  refresh();
  if (refreshMs > 0) {
    window.setInterval(refresh, refreshMs);
  }
}

function loadChart(root) {
  var status = root.querySelector("[data-chart-status]");
  setStatus(status, "Refreshing market data...");

  fetch(root.dataset.chartUrl, { headers: { Accept: "application/json" } })
    .then(function (response) {
      return response.json().then(function (data) {
        return { ok: response.ok, data: data };
      });
    })
    .then(function (result) {
      renderChart(root, result.data);
      var errors = Array.isArray(result.data.errors) ? result.data.errors.filter(Boolean) : [];
      if (!result.ok) {
        setStatus(status, errors.join("; ") || "Chart data is incomplete.");
        return;
      }
      setStatus(status, chartStatusText(result.data));
    })
    .catch(function (error) {
      setStatus(status, "Chart data request failed: " + error.message);
    });
}

function renderChart(root, data) {
  renderDataStatus(root.querySelector("[data-chart-data-status]"), data);
  renderSummary(root.querySelector("[data-chart-summary]"), data.analytics && data.analytics.metrics);
  renderInteractiveChart(root, data);
  renderMetadata(root.querySelector("[data-chart-meta]"), data);
}

function renderInteractiveChart(root, data) {
  var host = root.querySelector("[data-chart-host]");
  var headline = root.querySelector("[data-chart-headline]");
  var tooltip = root.querySelector("[data-chart-tooltip]");
  if (!host) {
    return;
  }

  destroyExistingChart(root);
  host.textContent = "";

  if (!window.LightweightCharts || typeof window.LightweightCharts.createChart !== "function") {
    drawChartUnavailable(host, "Chart library is unavailable. Use the PNG fallback.");
    return;
  }

  var candles = normalizeCandlesForLibrary(data.candles);
  if (!candles.length) {
    drawChartUnavailable(host, "No candles available");
    return;
  }

  var dimensions = chartDimensions(host);
  var chart = window.LightweightCharts.createChart(host, {
    width: dimensions.width,
    height: dimensions.height,
    layout: {
      background: { color: "#05070a" },
      textColor: "#d8f3dc",
      fontFamily: "Inter, Segoe UI, Arial, sans-serif",
      fontSize: 12,
    },
    grid: {
      vertLines: { color: "rgba(46, 255, 161, 0.08)" },
      horzLines: { color: "rgba(46, 255, 161, 0.08)" },
    },
    crosshair: {
      mode: 0,
      vertLine: {
        color: "rgba(45, 212, 191, 0.72)",
        width: 1,
        style: 3,
        labelBackgroundColor: "#0f1720",
      },
      horzLine: {
        color: "rgba(45, 212, 191, 0.72)",
        width: 1,
        style: 3,
        labelBackgroundColor: "#0f1720",
      },
    },
    rightPriceScale: {
      borderColor: "rgba(46, 255, 161, 0.18)",
      scaleMargins: { top: 0.08, bottom: 0.24 },
    },
    timeScale: {
      borderColor: "rgba(46, 255, 161, 0.18)",
      timeVisible: true,
      secondsVisible: false,
    },
    handleScroll: true,
    handleScale: true,
  });

  var candleSeries = addChartSeries(
    chart,
    window.LightweightCharts.CandlestickSeries,
    {
      upColor: "#17f287",
      downColor: "#ff4d5f",
      borderUpColor: "#17f287",
      borderDownColor: "#ff4d5f",
      wickUpColor: "#8fffc1",
      wickDownColor: "#ff9aa6",
      priceLineColor: "#2dd4bf",
      lastValueVisible: true,
    },
    "addCandlestickSeries",
  );
  candleSeries.setData(candles);

  var volumeSeries = addChartSeries(
    chart,
    window.LightweightCharts.HistogramSeries,
    {
      priceFormat: { type: "volume" },
      priceScaleId: "",
      lastValueVisible: false,
      priceLineVisible: false,
    },
    "addHistogramSeries",
  );
  volumeSeries.setData(volumeData(candles));
  if (typeof volumeSeries.priceScale === "function") {
    volumeSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.78, bottom: 0 },
    });
  }

  chart.timeScale().fitContent();
  root._chartInstance = chart;
  root._chartResizeObserver = attachChartResize(host, chart);

  renderChartHeadline(headline, data, candles[candles.length - 1]);
  attachCrosshairTooltip(chart, candleSeries, volumeSeries, host, tooltip, data);
}

function addChartSeries(chart, seriesType, options, fallbackMethod) {
  if (typeof chart.addSeries === "function" && seriesType) {
    return chart.addSeries(seriesType, options);
  }
  if (typeof chart[fallbackMethod] === "function") {
    return chart[fallbackMethod](options);
  }
  throw new Error("Unsupported chart library build.");
}

function attachChartResize(host, chart) {
  if (!window.ResizeObserver) {
    window.addEventListener("resize", function () {
      var dimensions = chartDimensions(host);
      chart.resize(dimensions.width, dimensions.height);
    });
    return null;
  }

  var observer = new ResizeObserver(function () {
    var dimensions = chartDimensions(host);
    chart.resize(dimensions.width, dimensions.height);
  });
  observer.observe(host);
  return observer;
}

function destroyExistingChart(root) {
  if (root._chartResizeObserver) {
    root._chartResizeObserver.disconnect();
    root._chartResizeObserver = null;
  }
  if (root._chartInstance && typeof root._chartInstance.remove === "function") {
    root._chartInstance.remove();
  }
  root._chartInstance = null;
}

function chartDimensions(host) {
  return {
    width: Math.max(320, Math.round(host.clientWidth || host.getBoundingClientRect().width || 960)),
    height: Math.max(420, Math.round(host.clientHeight || 540)),
  };
}

function renderChartHeadline(container, data, latest) {
  if (!container) {
    return;
  }
  var status = data.data_status || {};
  var parts = [
    data.ticker || "Chart",
    data.range ? readableStatus(data.range) : "",
    status.source || data.source || "",
    status.freshness ? readableStatus(status.freshness) : "",
  ].filter(Boolean);
  container.innerHTML = "";

  var title = document.createElement("strong");
  title.textContent = parts.join(" / ");
  container.appendChild(title);

  var latestNode = document.createElement("span");
  latestNode.textContent = latest
    ? "Last " + formatPrice(latest.close) + " | " + formatDateTimeFromSeconds(latest.time)
    : "No latest candle";
  container.appendChild(latestNode);
}

function attachCrosshairTooltip(chart, candleSeries, volumeSeries, host, tooltip, data) {
  if (!tooltip || typeof chart.subscribeCrosshairMove !== "function") {
    return;
  }

  chart.subscribeCrosshairMove(function (param) {
    if (
      !param ||
      !param.time ||
      !param.point ||
      param.point.x < 0 ||
      param.point.y < 0 ||
      param.point.x > host.clientWidth ||
      param.point.y > host.clientHeight
    ) {
      tooltip.hidden = true;
      return;
    }

    var candle = param.seriesData && param.seriesData.get(candleSeries);
    var volume = param.seriesData && param.seriesData.get(volumeSeries);
    if (!candle) {
      tooltip.hidden = true;
      return;
    }

    tooltip.hidden = false;
    tooltip.innerHTML = "";
    [
      [data.ticker || "Ticker", formatDateTimeFromSeconds(candle.time || param.time)],
      ["O", formatPrice(candle.open)],
      ["H", formatPrice(candle.high)],
      ["L", formatPrice(candle.low)],
      ["C", formatPrice(candle.close)],
      ["Vol", volume && volume.value !== undefined ? formatVolume(volume.value) : "n/a"],
    ].forEach(function (item) {
      var row = document.createElement("div");
      var label = document.createElement("span");
      var value = document.createElement("strong");
      label.textContent = item[0];
      value.textContent = item[1];
      row.appendChild(label);
      row.appendChild(value);
      tooltip.appendChild(row);
    });

    var left = Math.min(param.point.x + 16, host.clientWidth - tooltip.offsetWidth - 12);
    var top = Math.min(param.point.y + 16, host.clientHeight - tooltip.offsetHeight - 12);
    tooltip.style.left = Math.max(12, left) + "px";
    tooltip.style.top = Math.max(12, top) + "px";
  });
}

function drawChartUnavailable(host, text) {
  var node = document.createElement("div");
  node.className = "chart-empty";
  node.textContent = text;
  host.appendChild(node);
}

function normalizeCandlesForLibrary(candles) {
  return (candles || [])
    .map(function (candle) {
      return {
        time: Math.floor(Date.parse(candle.time) / 1000),
        open: Number(candle.open),
        high: Number(candle.high),
        low: Number(candle.low),
        close: Number(candle.close),
        volume: candle.volume === null || candle.volume === undefined ? null : Number(candle.volume),
      };
    })
    .filter(function (candle) {
      return (
        Number.isFinite(candle.time) &&
        Number.isFinite(candle.open) &&
        Number.isFinite(candle.high) &&
        Number.isFinite(candle.low) &&
        Number.isFinite(candle.close)
      );
    })
    .sort(function (a, b) {
      return a.time - b.time;
    });
}

function volumeData(candles) {
  return candles
    .filter(function (candle) {
      return Number.isFinite(candle.volume);
    })
    .map(function (candle) {
      return {
        time: candle.time,
        value: candle.volume,
        color: candle.close >= candle.open ? "rgba(23, 242, 135, 0.28)" : "rgba(255, 77, 95, 0.30)",
      };
    });
}

function renderDataStatus(container, data) {
  if (!container) {
    return;
  }
  container.textContent = "";
  var status = data.data_status || {};
  var items = [
    ["Source", status.source || data.source || "unknown"],
    ["Freshness", readableStatus(status.freshness || data.freshness)],
    ["Delay", readableStatus(status.delay_status || data.delay_status)],
    ["Fetched", status.fetched_at ? formatDateTime(Date.parse(status.fetched_at)) : "unknown"],
    ["As of", status.as_of_date || data.as_of_date || "unknown"],
    ["Candles", String(status.candle_count || (data.candles || []).length || 0)],
  ];

  items.forEach(function (item) {
    var node = document.createElement("div");
    var label = document.createElement("span");
    var value = document.createElement("strong");
    label.textContent = item[0];
    value.textContent = item[1];
    node.appendChild(label);
    node.appendChild(value);
    container.appendChild(node);
  });

  var warnings = (status.data_gaps || data.data_gaps || [])
    .map(function (gap) {
      return gap.description;
    })
    .filter(Boolean);
  if (warnings.length) {
    var warning = document.createElement("p");
    warning.textContent = warnings.join("; ");
    container.appendChild(warning);
  }
}

function renderSummary(container, metrics) {
  if (!container) {
    return;
  }
  container.textContent = "";
  (metrics || [])
    .filter(function (metric) {
      return [
        "range_return_pct",
        "latest_change_pct",
        "max_drawdown_pct",
        "annualized_volatility_pct",
        "volume_vs_average_pct",
      ].indexOf(metric.key) !== -1;
    })
    .forEach(function (metric) {
      var item = document.createElement("div");
      var label = document.createElement("span");
      var value = document.createElement("strong");
      label.textContent = metric.label;
      value.textContent = metric.display || "n/a";
      if (typeof metric.value === "number") {
        value.className = metric.value > 0 ? "positive" : metric.value < 0 ? "negative" : "";
      }
      item.appendChild(label);
      item.appendChild(value);
      container.appendChild(item);
    });
}

function setStatus(status, text) {
  if (status) {
    status.textContent = text;
  }
}

function chartStatusText(data) {
  var status = data.data_status || {};
  var parts = [];
  if (status.source || data.source) {
    parts.push("Source: " + (status.source || data.source));
  }
  if (status.freshness || data.freshness) {
    parts.push("Freshness: " + readableStatus(status.freshness || data.freshness));
  }
  if (status.delay_status || data.delay_status) {
    parts.push("Delay: " + readableStatus(status.delay_status || data.delay_status));
  }
  if (status.fetched_at || data.fetched_at) {
    parts.push("Fetched: " + formatDateTime(Date.parse(status.fetched_at || data.fetched_at)));
  }
  if (status.as_of_date || data.as_of_date) {
    parts.push("As of: " + (status.as_of_date || data.as_of_date));
  }
  if (data.cache && data.cache.refreshed) {
    parts.push("auto-refresh on");
  }
  return parts.join(" | ") || "Chart data loaded.";
}

function renderMetadata(container, data) {
  if (!container) {
    return;
  }
  var gaps = (data.data_gaps || [])
    .map(function (gap) {
      return gap.description;
    })
    .filter(Boolean);
  var gapText = gaps.length ? " Data gaps: " + gaps.join("; ") : "";
  container.textContent = (data.disclaimer || "") + gapText;
}

function formatPrice(value) {
  var number = Number(value);
  if (!Number.isFinite(number)) {
    return "n/a";
  }
  return number.toFixed(Math.abs(number) >= 100 ? 2 : 4).replace(/\.?0+$/, "");
}

function formatVolume(value) {
  var number = Number(value);
  if (!Number.isFinite(number)) {
    return "n/a";
  }
  return number.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function formatDateTime(value) {
  return new Date(value).toLocaleString(undefined, {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDateTimeFromSeconds(value) {
  return formatDateTime(Number(value) * 1000);
}

function readableStatus(value) {
  return String(value || "unknown").replace(/_/g, " ");
}
