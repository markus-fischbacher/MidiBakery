/*
 * MidiBakery Reference Analyzer device, view: the reference's sections as coloured blocks over its bars,
 * with lanes for the kick, lows, mids and highs below and a header line.
 *
 *   show <json>     the analysis (midibakery-reference.js)
 *   status <text>   the header line while there is no analysis or something happens
 */

mgraphics.init();
mgraphics.relative_coords = 0;
mgraphics.autofill = 0;

var data = null;
var message = "Drop the reference song on this track's Arrangement, then press Analyze";

var COLORS = {
  intro: [0.45, 0.47, 0.5],
  groove: [0.36, 0.62, 0.42],
  build: [0.9, 0.6, 0.25],
  drop: [0.86, 0.33, 0.3],
  break: [0.33, 0.52, 0.8],
  outro: [0.45, 0.47, 0.5],
};
var GENRE_TITLES = { house: "House", melodic_techno: "Melodic Techno", peak_time_techno: "Peak Time Techno", drum_and_bass: "Drum & Bass", trap: "Trap" };
var BG = [0.12, 0.12, 0.12, 1];
var TEXT = [0.85, 0.85, 0.85, 1];
var DIM = [0.55, 0.55, 0.55, 1];
var LANES = [
  ["Kick", "kick", 0, 1],
  ["Lows", "low", -30, 0],
  ["Mids", "mid", -30, 0],
  ["Hats", "high", -30, 0],
];
var HEADER = 16;
var BLOCKS = 32;
var LANE = 22;
var LABEL = 30;

function show(json) {
  try {
    data = JSON.parse(json);
    message = null; // the status line goes; tempo and key stay in the header
  } catch (e) {
    message = "Unreadable analysis";
  }
  mgraphics.redraw();
}

function status() {
  message = arrayfromargs(arguments).join(" ");
  mgraphics.redraw();
}

/** The analysis at a glance: tempo and key, large. */
function facts() {
  var parts = [];
  if (data.tempo) parts.push(data.tempo + " BPM");
  if (data.key) parts.push(data.key);
  return parts.join("   ");
}

/** The rest, small: song, genre, bars. */
function details() {
  var parts = [data.name];
  if (!data.warped) parts.push("tempo detected");
  if (data.genre && GENRE_TITLES[data.genre]) parts.push(GENRE_TITLES[data.genre]);
  parts.push((data.bar_grid === "song" ? "song bars " : "bars ") + data.first_bar + "-" + (data.first_bar + data.bars - 1));
  return parts.join("  ·  ");
}

function measure(value, size, font) {
  mgraphics.select_font_face(font || "Arial");
  mgraphics.set_font_size(size);
  return mgraphics.text_measure(value)[0];
}

/** `value` cut to `width` with an ellipsis. */
function fit(value, width, size) {
  if (measure(value, size) <= width) return value;
  for (var n = value.length - 1; n > 0; n--) if (measure(value.slice(0, n) + "…", size) <= width) return value.slice(0, n) + "…";
  return "";
}

/** A section name that fits: "Breakdown 2", "Breakd. 2", ... "B. 2", "B2". */
function shortName(name, width, size) {
  if (measure(name, size) <= width) return name;
  var m = /^(.*?)( \d+)?$/.exec(name);
  var word = m[1];
  var number = m[2] || "";
  for (var n = word.length - 1; n > 0; n--) {
    var short = word.slice(0, n) + "." + number;
    if (measure(short, size) <= width) return short;
  }
  var tiny = word.charAt(0) + number.replace(" ", "");
  return measure(tiny, size) <= width ? tiny : "";
}

function text(x, y, value, color, size) {
  mgraphics.select_font_face("Arial");
  mgraphics.set_font_size(size || 9);
  mgraphics.set_source_rgba(color);
  mgraphics.move_to(x, y);
  mgraphics.show_text(value);
}

function paint() {
  var w = mgraphics.size[0];
  var h = mgraphics.size[1];
  mgraphics.set_source_rgba(BG);
  mgraphics.rectangle(0, 0, w, h);
  mgraphics.fill();
  if (!data) {
    text(4, 11, message || "", DIM, 9);
    return;
  }
  var big = facts();
  var bigWidth = measure(big, 12, "Arial Bold");
  mgraphics.set_source_rgba(TEXT);
  mgraphics.move_to(4, 13);
  mgraphics.show_text(big);
  var right = w - 4;
  if (message) {
    var status = fit(message, w / 2, 9);
    right -= measure(status, 9) + 12;
    text(w - measure(status, 9) - 4, 12, status, DIM, 9);
  }
  text(bigWidth + 14, 12, fit(details(), right - bigWidth - 14, 9), DIM, 9);

  var left = LABEL;
  var width = w - LABEL - 2;
  var bars = data.bars;
  var x = function (bar) {
    return left + (bar / bars) * width;
  };

  // sections
  var top = HEADER + 2;
  for (var i = 0; i < data.sections.length; i++) {
    var s = data.sections[i];
    var x0 = x(s.start_bar - data.first_bar);
    var x1 = x(s.start_bar - data.first_bar + s.bars);
    var c = COLORS[s.kind] || COLORS.groove;
    mgraphics.set_source_rgba(c[0], c[1], c[2], 1);
    mgraphics.rectangle(x0 + 0.5, top, Math.max(1, x1 - x0 - 1), BLOCKS);
    mgraphics.fill();
    var label = shortName(s.name, x1 - x0 - 6, 9);
    if (label) text(x0 + 3, top + 12, label, [1, 1, 1, 0.95], 9);
    if (measure(String(s.start_bar), 8) <= x1 - x0 - 6) text(x0 + 3, top + 24, String(s.start_bar), [1, 1, 1, 0.7], 8);
  }

  // lanes: one column per bar, height by value
  var y = top + BLOCKS + 4;
  for (var l = 0; l < LANES.length; l++) {
    var lane = LANES[l];
    var values = data.lanes[lane[1]] || [];
    text(2, y + LANE - 6, lane[0], DIM, 8);
    mgraphics.set_source_rgba(0.2, 0.2, 0.2, 1);
    mgraphics.rectangle(left, y, width, LANE - 2);
    mgraphics.fill();
    mgraphics.set_source_rgba(0.75, 0.78, 0.8, 0.85);
    for (var b = 0; b < values.length; b++) {
      var v = (values[b] - lane[2]) / (lane[3] - lane[2]);
      v = Math.max(0, Math.min(1, v));
      if (v <= 0) continue;
      var bh = (LANE - 2) * v;
      mgraphics.rectangle(x(b), y + LANE - 2 - bh, Math.max(1, x(b + 1) - x(b) - 0.3), bh);
    }
    mgraphics.fill();
    y += LANE;
  }

  // bar ruler every 16 bars
  for (var bar = 0; bar <= bars; bar += 16) {
    mgraphics.set_source_rgba(1, 1, 1, 0.12);
    mgraphics.rectangle(x(bar), top + BLOCKS + 2, 0.5, y - top - BLOCKS - 2);
    mgraphics.fill();
    if (bar < bars) text(x(bar) + 1, h - 2, String(data.first_bar + bar), DIM, 7);
  }
}

function onresize() {
  mgraphics.redraw();
}
