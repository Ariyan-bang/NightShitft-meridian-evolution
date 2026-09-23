/* views/trends.js - fleet-wide seasonal yield trends.
 * 2026-02. A single table across every station: run count, min / max /
 * current forecast yield, and a yield-history sparkline, with a biomass
 * chart for whichever station you click. It answers "how is the whole
 * network trending this season" without adding each station to the Compare
 * set by hand.
 *
 * This re-implements the roll-up the ui-next Compare screen does in
 * ui-next/src/api/forecastClient.ts (yieldSpread + the yield table). It is a
 * second copy in ES5 - the two consoles ship separately and neither imports
 * the other - so if the roll-up changes it has to change in both places.
 *
 * DRIFT (matches the rest of this console, differs from ui-next):
 *   - "Current" run is the LAST row the service returns for a station, the
 *     same rule views/forecast.js and views/compare.js use. The ui-next
 *     forecast client instead takes the greatest-numeric-year run, so the two
 *     consoles can name a different current yield for the same station when the
 *     service returns runs out of ascending-year order (cf. MRD-238, MRD-241).
 *   - Yields are formatted with Fmt.yield_t (three decimals). ui-next's
 *     Compare prints two.
 *
 * No build step (MRD-181): bare <script>, ES5 only, no arrow/template syntax.
 */
window.Meridian = window.Meridian || {};
window.Meridian.Views = window.Meridian.Views || {};

window.Meridian.Views.Trends = (function ($) {

    var Dom = window.Meridian.Dom;
    var Fmt = window.Meridian.Fmt;
    var State = window.Meridian.State;
    var BarChart = window.Meridian.Charts.BarChart;
    var Spark = window.Meridian.Charts.Sparkline;

    var $root = null;
    var fleet = {};            /* stnid -> forecast rows */
    var detailStn = null;      /* station whose series is charted */

    function render($container) {
        $root = $container;
        $container.html(
            '<div class="view-head">' +
            '  <h2>Trends <span class="subtitle">fleet seasonal yield</span></h2>' +
            '  <div class="view-actions">' +
            '    <button id="tr-refresh" class="btn">Refresh</button>' +
            '  </div>' +
            '</div>' +
            '<div id="tr-table">' + Dom.spinner('loading forecasts…') + '</div>' +
            '<div class="chart-head"><h3>Current-season biomass ' +
            '  <span id="tr-detail-lbl" class="subtitle"></span></h3></div>' +
            '<div id="tr-chart" class="chart tall"></div>'
        );

        wireEvents();
        loadFleet();
    }

    function loadFleet() {
        var all = State.get('stations') || [];
        if (!all.length) {
            $('#tr-table').html(Dom.emptyState('No stations loaded.'));
            return;
        }
        fleet = {};
        var pending = all.length;
        $.each(all, function (i, s) {
            MeridianApi.forecast(s.stnid, function (err, rows) {
                pending -= 1;
                fleet[s.stnid] = err ? [] : (rows || []);
                if (pending === 0) { renderTable(all); }
            });
        });
    }

    /* currentRun(): the run "in force" for a station. LEGACY rule - the last
     * row the service returns. Kept identical to views/forecast.js and
     * views/compare.js so this console stays internally consistent (see the
     * DRIFT note at the top for how this differs from ui-next). */
    function currentRun(rows) {
        if (!rows || !rows.length) { return null; }
        return rows[rows.length - 1];
    }

    /* spread(): min / max / current yield + a year-ordered history, the ES5
     * twin of forecastClient.yieldSpread(). */
    function spread(rows) {
        if (!rows || !rows.length) {
            return { runs: 0, min: null, max: null, current: null, year: null, history: [] };
        }
        var byYear = rows.slice().sort(function (a, b) { return a.year - b.year; });
        var min = null, max = null, history = [], i, y;
        for (i = 0; i < byYear.length; i++) {
            y = Number(byYear[i].yield_t);
            history.push(y);
            if (min === null || y < min) { min = y; }
            if (max === null || y > max) { max = y; }
        }
        var cur = currentRun(rows);
        return {
            runs: rows.length,
            min: min, max: max,
            current: cur ? Number(cur.yield_t) : null,
            year: cur ? cur.year : null,
            history: history
        };
    }

    function renderTable(all) {
        var rows = [];
        for (var i = 0; i < all.length; i++) {
            var stn = all[i].stnid;
            var s = spread(fleet[stn]);
            rows.push({ stn: stn, s: s });
        }
        var html = Dom.buildTable({
            tableClass: 'cmp-yield-tbl trends-tbl',
            rows: rows,
            empty: 'no forecasts',
            cols: [
                { label: 'Station', cls: '', get: function (r) { return r.stn; } },
                { label: 'Runs', cls: 'right num', get: function (r) { return r.s.runs; } },
                { label: 'Min', cls: 'right num', get: function (r) { return Fmt.yield_t(r.s.min); } },
                { label: 'Max', cls: 'right num', get: function (r) { return Fmt.yield_t(r.s.max); } },
                { label: 'Current', cls: 'right num', get: function (r) {
                    return Fmt.yield_t(r.s.current); } },
                { label: 'Yr', cls: 'right num muted', get: function (r) {
                    return r.s.year || '—'; } },
                { label: 'Trend', cls: 'spark-cell', raw: true, get: function (r) {
                    return Spark.render(r.s.history, { width: 110, height: 20 }); } }
            ],
            rowAttrs: function (r) {
                var a = { 'data-stn': r.stn, 'class': 'tr-row clickable' };
                if (r.stn === detailStn) { a['class'] += ' sel'; }
                return a;
            }
        });
        $('#tr-table').html(html);

        /* default the detail chart to the first station if none chosen yet */
        if (!detailStn && all.length) { openDetail(all[0].stnid); }
        else if (detailStn) { markSelected(detailStn); }
    }

    function markSelected(stn) {
        $('#tr-table .tr-row').removeClass('sel')
            .filter('[data-stn="' + stn + '"]').addClass('sel');
    }

    function openDetail(stn) {
        detailStn = stn;
        markSelected(stn);
        var run = currentRun(fleet[stn]);
        if (!run) {
            $('#tr-detail-lbl').text('');
            $('#tr-chart').html('<div class="chart-empty">no forecast runs for ' +
                                Dom.esc(stn) + '</div>');
            return;
        }
        $('#tr-detail-lbl').text('– ' + stn + ' ' + run.year);
        $('#tr-chart').html(Dom.spinner('loading series…'));
        MeridianApi.series(stn, run.year, function (err, rows) {
            if (err) {
                $('#tr-chart').html(Dom.banner('error', 'Series unreachable (' + err + ')'));
                return;
            }
            var $chart = $('#tr-chart');
            Dom.onceWidth($chart, function () {
                BarChart.draw($chart, rows || [], {
                    value: function (r) { return Number(r.biom); },
                    height: 180,
                    gridlines: true,
                    colorFor: function () { return 'v-biom'; },
                    label: function (r) {
                        return Fmt.doyToDate(r.doy, run.year) + ' (DOY ' + r.doy + '): biomass ' +
                               Fmt.int(r.biom);
                    }
                });
            });
        });
    }

    function wireEvents() {
        $root.off('.tr');
        $root.on('click.tr', '.tr-row', function () {
            openDetail($(this).data('stn'));
        });
        $root.on('click.tr', '#tr-refresh', function () {
            $('#tr-table').html(Dom.spinner('loading forecasts…'));
            loadFleet();
        });
    }

    function teardown() {
        if ($root) { $root.off('.tr'); }
        fleet = {};
    }

    return {
        id: 'trends',
        title: 'Trends',
        render: render,
        teardown: teardown
    };
})(jQuery);
