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
  setStatus(status, "Refreshing chart data...");

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
  drawPriceChart(root.querySelector("[data-chart-canvas]"), data);
  drawRsiChart(root.querySelector("[data-rsi-canvas]"), data);
  drawMacdChart(root.querySelector("[data-macd-canvas]"), data);
  renderMetadata(root.querySelector("[data-chart-meta]"), data);
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
    .map(function (gap) { return gap.description; })
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

function drawPriceChart(canvas, data) {
  if (!canvas) {
    return;
  }
  var ctx = canvas.getContext("2d");
  clearCanvas(ctx, canvas);

  var candles = normalizeCandles(data.candles);
  if (!candles.length) {
    drawEmpty(ctx, canvas, "No candles available");
    return;
  }

  var overlays = (data.analytics && data.analytics.overlays) || {};
  var volumeHeight = candles.some(function (candle) { return candle.volume !== null; }) ? 92 : 0;
  var margin = { left: 58, right: 22, top: 26, bottom: 42 + volumeHeight };
  var plot = plotRect(canvas, margin);
  var xDomain = [candles[0].time, candles[candles.length - 1].time];
  if (xDomain[0] === xDomain[1]) {
    xDomain[0] -= 3600000;
    xDomain[1] += 3600000;
  }

  var priceValues = candles.reduce(function (values, candle) {
    values.push(candle.high, candle.low, candle.close);
    return values;
  }, []);
  collectValues(overlays.sma20, priceValues);
  collectValues(overlays.sma50, priceValues);
  collectValues(overlays.ema12, priceValues);
  collectValues(overlays.ema26, priceValues);
  (overlays.bollinger20 || []).forEach(function (point) {
    priceValues.push(point.upper, point.lower);
  });

  var yDomain = paddedDomain(priceValues);
  drawGrid(ctx, plot, yDomain);
  drawAxes(ctx, plot, yDomain, candles);
  drawVolume(ctx, canvas, plot, candles, xDomain, volumeHeight);
  drawCandles(ctx, plot, candles, xDomain, yDomain);
  drawBand(ctx, plot, overlays.bollinger20 || [], xDomain, yDomain);
  drawLine(ctx, plot, overlays.sma20 || [], xDomain, yDomain, "#9a5b00", 1.5);
  drawLine(ctx, plot, overlays.sma50 || [], xDomain, yDomain, "#6d42b8", 1.5);
  drawLine(ctx, plot, overlays.ema12 || [], xDomain, yDomain, "#006d77", 1.3);
  drawLine(ctx, plot, overlays.ema26 || [], xDomain, yDomain, "#a23e48", 1.3);
  drawMarkers(ctx, plot, data.analytics && data.analytics.markers, xDomain, yDomain);
  drawLegend(ctx, plot, ["Close", "SMA20", "SMA50", "EMA12", "EMA26", "Bollinger"]);
}

function drawRsiChart(canvas, data) {
  drawIndicatorLine(
    canvas,
    "RSI14",
    ((data.analytics && data.analytics.panels && data.analytics.panels.rsi14) || []),
    [0, 100],
    "#006d77",
    [
      { value: 70, color: "#b45309" },
      { value: 30, color: "#1f7a4d" },
    ]
  );
}

function drawMacdChart(canvas, data) {
  if (!canvas) {
    return;
  }
  var ctx = canvas.getContext("2d");
  clearCanvas(ctx, canvas);
  var points = (data.analytics && data.analytics.panels && data.analytics.panels.macd) || [];
  if (!points.length) {
    drawEmpty(ctx, canvas, "MACD needs more candles");
    return;
  }

  var normalized = points.map(function (point) {
    return {
      time: Date.parse(point.time),
      macd: Number(point.macd),
      signal: Number(point.signal),
      histogram: Number(point.histogram),
    };
  }).filter(function (point) {
    return Number.isFinite(point.time) && Number.isFinite(point.macd);
  });
  var margin = { left: 58, right: 22, top: 20, bottom: 34 };
  var plot = plotRect(canvas, margin);
  var xDomain = [normalized[0].time, normalized[normalized.length - 1].time];
  var values = [];
  normalized.forEach(function (point) {
    values.push(point.macd, point.signal, point.histogram);
  });
  var yDomain = paddedDomain(values.concat([0]));
  drawPanelFrame(ctx, plot, "MACD 12/26/9");
  normalized.forEach(function (point, index) {
    var x = scale(point.time, xDomain, [plot.left, plot.right]);
    var zeroY = scale(0, yDomain, [plot.bottom, plot.top]);
    var y = scale(point.histogram, yDomain, [plot.bottom, plot.top]);
    var nextTime = normalized[Math.min(index + 1, normalized.length - 1)].time;
    var barWidth = Math.max(2, Math.abs(scale(nextTime, xDomain, [plot.left, plot.right]) - x) * 0.55);
    ctx.fillStyle = point.histogram >= 0 ? "rgba(31,122,77,0.46)" : "rgba(180,35,24,0.42)";
    ctx.fillRect(x - barWidth / 2, Math.min(y, zeroY), barWidth, Math.abs(zeroY - y) || 1);
  });
  drawLine(ctx, plot, normalized.map(function (point) { return { time: point.time, value: point.macd }; }), xDomain, yDomain, "#1d4ed8", 1.4);
  drawLine(ctx, plot, normalized.map(function (point) { return { time: point.time, value: point.signal }; }), xDomain, yDomain, "#b45309", 1.2);
}

function drawIndicatorLine(canvas, title, rawPoints, fixedDomain, color, levels) {
  if (!canvas) {
    return;
  }
  var ctx = canvas.getContext("2d");
  clearCanvas(ctx, canvas);
  var points = normalizeSeries(rawPoints);
  if (!points.length) {
    drawEmpty(ctx, canvas, title + " needs more candles");
    return;
  }
  var margin = { left: 58, right: 22, top: 20, bottom: 34 };
  var plot = plotRect(canvas, margin);
  var xDomain = [points[0].time, points[points.length - 1].time];
  var yDomain = fixedDomain || paddedDomain(points.map(function (point) { return point.value; }));
  drawPanelFrame(ctx, plot, title);
  (levels || []).forEach(function (level) {
    var y = scale(level.value, yDomain, [plot.bottom, plot.top]);
    ctx.strokeStyle = level.color;
    ctx.globalAlpha = 0.55;
    ctx.beginPath();
    ctx.moveTo(plot.left, y);
    ctx.lineTo(plot.right, y);
    ctx.stroke();
    ctx.globalAlpha = 1;
  });
  drawLine(ctx, plot, points, xDomain, yDomain, color, 1.6);
}

function normalizeCandles(candles) {
  return (candles || []).map(function (candle) {
    return {
      time: Date.parse(candle.time),
      open: Number(candle.open),
      high: Number(candle.high),
      low: Number(candle.low),
      close: Number(candle.close),
      volume: candle.volume === null || candle.volume === undefined ? null : Number(candle.volume),
    };
  }).filter(function (candle) {
    return Number.isFinite(candle.time) && Number.isFinite(candle.close);
  });
}

function normalizeSeries(points) {
  return (points || []).map(function (point) {
    return {
      time: typeof point.time === "number" ? point.time : Date.parse(point.time),
      value: Number(point.value),
    };
  }).filter(function (point) {
    return Number.isFinite(point.time) && Number.isFinite(point.value);
  });
}

function collectValues(points, values) {
  normalizeSeries(points).forEach(function (point) {
    values.push(point.value);
  });
}

function drawCandles(ctx, plot, candles, xDomain, yDomain) {
  var width = Math.max(3, (plot.width / Math.max(candles.length, 1)) * 0.62);
  candles.forEach(function (candle) {
    var x = scale(candle.time, xDomain, [plot.left, plot.right]);
    var openY = scale(candle.open, yDomain, [plot.bottom, plot.top]);
    var closeY = scale(candle.close, yDomain, [plot.bottom, plot.top]);
    var highY = scale(candle.high, yDomain, [plot.bottom, plot.top]);
    var lowY = scale(candle.low, yDomain, [plot.bottom, plot.top]);
    var up = candle.close >= candle.open;
    ctx.strokeStyle = up ? "#1f7a4d" : "#b42318";
    ctx.fillStyle = up ? "rgba(31,122,77,0.62)" : "rgba(180,35,24,0.58)";
    ctx.beginPath();
    ctx.moveTo(x, highY);
    ctx.lineTo(x, lowY);
    ctx.stroke();
    ctx.fillRect(x - width / 2, Math.min(openY, closeY), width, Math.max(1, Math.abs(closeY - openY)));
  });
}

function drawVolume(ctx, canvas, plot, candles, xDomain, volumeHeight) {
  if (!volumeHeight) {
    return;
  }
  var top = canvas.height - volumeHeight - 30;
  var bottom = canvas.height - 38;
  var maxVolume = Math.max.apply(null, candles.map(function (candle) { return candle.volume || 0; }));
  if (!maxVolume) {
    return;
  }
  ctx.fillStyle = "rgba(93,102,109,0.28)";
  candles.forEach(function (candle, index) {
    var x = scale(candle.time, xDomain, [plot.left, plot.right]);
    var nextTime = candles[Math.min(index + 1, candles.length - 1)].time;
    var barWidth = Math.max(2, Math.abs(scale(nextTime, xDomain, [plot.left, plot.right]) - x) * 0.55);
    var y = scale(candle.volume || 0, [0, maxVolume], [bottom, top]);
    ctx.fillRect(x - barWidth / 2, y, barWidth, bottom - y);
  });
}

function drawBand(ctx, plot, rawPoints, xDomain, yDomain) {
  var points = (rawPoints || []).map(function (point) {
    return {
      time: Date.parse(point.time),
      upper: Number(point.upper),
      lower: Number(point.lower),
      middle: Number(point.middle),
    };
  }).filter(function (point) {
    return Number.isFinite(point.time) && Number.isFinite(point.upper) && Number.isFinite(point.lower);
  });
  if (!points.length) {
    return;
  }
  ctx.fillStyle = "rgba(29,78,216,0.08)";
  ctx.beginPath();
  points.forEach(function (point, index) {
    var x = scale(point.time, xDomain, [plot.left, plot.right]);
    var y = scale(point.upper, yDomain, [plot.bottom, plot.top]);
    if (index === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  });
  points.slice().reverse().forEach(function (point) {
    ctx.lineTo(scale(point.time, xDomain, [plot.left, plot.right]), scale(point.lower, yDomain, [plot.bottom, plot.top]));
  });
  ctx.closePath();
  ctx.fill();
}

function drawLine(ctx, plot, rawPoints, xDomain, yDomain, color, width) {
  var points = normalizeSeries(rawPoints);
  if (!points.length) {
    return;
  }
  ctx.strokeStyle = color;
  ctx.lineWidth = width || 1.5;
  ctx.beginPath();
  points.forEach(function (point, index) {
    var x = scale(point.time, xDomain, [plot.left, plot.right]);
    var y = scale(point.value, yDomain, [plot.bottom, plot.top]);
    if (index === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  });
  ctx.stroke();
  ctx.lineWidth = 1;
}

function drawMarkers(ctx, plot, markers, xDomain, yDomain) {
  if (!markers) {
    return;
  }
  [
    { marker: markers.entry, color: "#1f7a4d" },
    { marker: markers.exit, color: "#b42318" },
  ].forEach(function (item) {
    if (!item.marker) {
      return;
    }
    var x = scale(Date.parse(item.marker.time), xDomain, [plot.left, plot.right]);
    var y = scale(Number(item.marker.close), yDomain, [plot.bottom, plot.top]);
    ctx.fillStyle = item.color;
    ctx.beginPath();
    ctx.arc(x, y, 5, 0, Math.PI * 2);
    ctx.fill();
  });
}

function drawGrid(ctx, plot, yDomain) {
  ctx.strokeStyle = "#d9dedb";
  ctx.fillStyle = "#5d666d";
  ctx.font = "12px Segoe UI, Arial, sans-serif";
  for (var index = 0; index <= 4; index += 1) {
    var ratio = index / 4;
    var y = plot.top + plot.height * ratio;
    var value = yDomain[1] - (yDomain[1] - yDomain[0]) * ratio;
    ctx.globalAlpha = 0.75;
    ctx.beginPath();
    ctx.moveTo(plot.left, y);
    ctx.lineTo(plot.right, y);
    ctx.stroke();
    ctx.globalAlpha = 1;
    ctx.fillText(formatPrice(value), 8, y + 4);
  }
}

function drawAxes(ctx, plot, yDomain, candles) {
  ctx.strokeStyle = "#9ca3af";
  ctx.strokeRect(plot.left, plot.top, plot.width, plot.height);
  ctx.fillStyle = "#5d666d";
  ctx.font = "12px Segoe UI, Arial, sans-serif";
  var ticks = 4;
  for (var index = 0; index <= ticks; index += 1) {
    var candle = candles[Math.round((candles.length - 1) * (index / ticks))];
    if (!candle) {
      continue;
    }
    var x = scale(candle.time, [candles[0].time, candles[candles.length - 1].time], [plot.left, plot.right]);
    ctx.fillText(formatDate(candle.time), Math.min(x, plot.right - 60), plot.bottom + 22);
  }
}

function drawPanelFrame(ctx, plot, title) {
  ctx.strokeStyle = "#d9dedb";
  ctx.strokeRect(plot.left, plot.top, plot.width, plot.height);
  ctx.fillStyle = "#171a1c";
  ctx.font = "13px Segoe UI, Arial, sans-serif";
  ctx.fillText(title, plot.left, 14);
}

function drawLegend(ctx, plot, labels) {
  ctx.fillStyle = "#5d666d";
  ctx.font = "12px Segoe UI, Arial, sans-serif";
  ctx.fillText(labels.join("  "), plot.left, plot.top - 9);
}

function plotRect(canvas, margin) {
  return {
    left: margin.left,
    right: canvas.width - margin.right,
    top: margin.top,
    bottom: canvas.height - margin.bottom,
    width: canvas.width - margin.left - margin.right,
    height: canvas.height - margin.top - margin.bottom,
  };
}

function paddedDomain(values) {
  var finite = values.filter(Number.isFinite);
  var min = Math.min.apply(null, finite);
  var max = Math.max.apply(null, finite);
  if (!Number.isFinite(min) || !Number.isFinite(max)) {
    return [0, 1];
  }
  if (min === max) {
    return [min - 1, max + 1];
  }
  var padding = (max - min) * 0.08;
  return [min - padding, max + padding];
}

function scale(value, domain, range) {
  if (domain[0] === domain[1]) {
    return (range[0] + range[1]) / 2;
  }
  return range[0] + ((value - domain[0]) / (domain[1] - domain[0])) * (range[1] - range[0]);
}

function clearCanvas(ctx, canvas) {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
}

function drawEmpty(ctx, canvas, text) {
  ctx.fillStyle = "#5d666d";
  ctx.font = "15px Segoe UI, Arial, sans-serif";
  ctx.fillText(text, 24, 40);
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
  var gaps = (data.data_gaps || []).map(function (gap) { return gap.description; }).filter(Boolean);
  var gapText = gaps.length ? " Data gaps: " + gaps.join("; ") : "";
  container.textContent = (data.disclaimer || "") + gapText;
}

function formatPrice(value) {
  return Number(value).toFixed(Math.abs(value) >= 100 ? 0 : 2);
}

function formatDate(value) {
  return new Date(value).toLocaleDateString(undefined, { month: "short", day: "2-digit" });
}

function formatDateTime(value) {
  return new Date(value).toLocaleString(undefined, {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function readableStatus(value) {
  return String(value || "unknown").replace(/_/g, " ");
}
