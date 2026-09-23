/* app.js - router + bootstrap for the tabbed console.
 * R. Patel 2018-06, extended by T. Osei through 2023. This is the file
 * that turned the 2016 single-page dashboard into a tabbed app without a
 * framework (there is no build step - MRD-181 - so no Backbone, no router
 * library, just a hashchange listener and a registry of view objects).
 *
 * Each view is a plain object { id, title, render($el), teardown() } hung
 * off window.Meridian.Views by its own file. This file wires the tab bar,
 * swaps views on hash change, loads the station roster once up front, and
 * keeps the header health badge current.
 *
 * The legacy single-page code (dashboard.js) is NOT loaded here anymore in
 * the tabbed layout; it is kept in the repo and served on the legacy URL
 * (index.html?legacy=1 -> a thin legacy shell). Both share MeridianApi.
 */
window.Meridian = window.Meridian || {};

(function ($) {

    var Dom = window.Meridian.Dom;
    var State = window.Meridian.State;

    /* tab order in the bar. IDs must match view.id. */
    var ORDER = ['stations', 'forecast', 'anomalies', 'compare', 'trends', 'quality', 'about'];

    var current = null;         /* currently-mounted view object */
    var $content = null;
    var $tabs = null;

    function viewFor(id) {
        var V = window.Meridian.Views || {};
        var names = ['Stations', 'Forecast', 'Anomalies', 'Compare', 'Trends', 'Quality', 'About'];
        for (var i = 0; i < names.length; i++) {
            if (V[names[i]] && V[names[i]].id === id) { return V[names[i]]; }
        }
        return null;
    }

    function buildTabBar() {
        var html = '';
        for (var i = 0; i < ORDER.length; i++) {
            var v = viewFor(ORDER[i]);
            if (!v) { continue; }
            html += '<a href="#' + v.id + '" class="tab" data-tab="' + v.id + '">' +
                    Dom.esc(v.title) + '</a>';
        }
        $tabs.html(html);
    }

    function currentHashId() {
        var h = (window.location.hash || '').replace(/^#/, '');
        /* strip any sub-params like #forecast/GT01 - we only use the head */
        h = h.split('/')[0];
        if (!h) { return ORDER[0]; }
        for (var i = 0; i < ORDER.length; i++) {
            if (ORDER[i] === h) { return h; }
        }
        return ORDER[0];
    }

    function go(id) {
        if (window.location.hash.replace(/^#/, '').split('/')[0] === id) {
            /* already there - force a mount anyway (e.g. programmatic go
             * from the Stations row click when we're on stations) */
            mount(id);
        } else {
            window.location.hash = '#' + id;   /* triggers hashchange -> mount */
        }
    }

    function mount(id) {
        var view = viewFor(id);
        if (!view) { view = viewFor(ORDER[0]); id = ORDER[0]; }

        if (current && current.teardown) {
            try { current.teardown(); } catch (e) {
                if (window.console) { console.error('teardown failed', e); }
            }
        }

        State.set('activeTab', id);
        $tabs.find('.tab').removeClass('active')
             .filter('[data-tab="' + id + '"]').addClass('active');

        /* fresh container each mount so a view never inherits stale nodes */
        $content.empty().append('<div class="view" id="view-' + id + '"></div>');
        current = view;
        try {
            view.render($('#view-' + id));
        } catch (e) {
            $('#view-' + id).html(Dom.banner('error',
                'This screen failed to load: ' + (e && e.message ? e.message : e)));
            if (window.console) { console.error('render failed for ' + id, e); }
        }
    }

    function onHashChange() { mount(currentHashId()); }

    /* --- header health badge ------------------------------------------ */
    function pollHealth() {
        MeridianApi.health(function (err, h) {
            var $b = $('#apiver');
            if (err) {
                $b.text('API offline').removeClass('ok').addClass('down');
                State.setHealth(null);
            } else {
                $b.text('API ' + (h.version || '?'))
                  .removeClass('down').addClass('ok');
                State.setHealth(h);
            }
        });
    }

    /* --- boot --------------------------------------------------------- */
    function boot() {
        $content = $('#content');
        $tabs = $('#tabs');

        if (!$content.length || !$tabs.length) {
            /* the legacy shell doesn't have these; if we're on it, do
             * nothing and let dashboard.js run. */
            return;
        }

        buildTabBar();

        $tabs.on('click', '.tab', function (ev) {
            /* let the hash change drive it, but on browsers where two tabs
             * resolve to the same hash head we still want a mount */
            var id = $(this).data('tab');
            if (currentHashId() === id) { ev.preventDefault(); mount(id); }
        });

        $(window).on('hashchange', onHashChange);

        /* load the station roster ONCE up front so every tab has it in
         * State before it renders. Then mount whatever the hash says. */
        MeridianApi.stations(function (err, rows) {
            if (!err) { State.setStations(rows); }
            mount(currentHashId());
        });

        pollHealth();
        setInterval(pollHealth, 15000);
    }

    /* expose a tiny router API for views (Stations row click uses go()) */
    window.Meridian.Router = { go: go, mount: mount, current: function () { return current; } };

    $(boot);

})(jQuery);
