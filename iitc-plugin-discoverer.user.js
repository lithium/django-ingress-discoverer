// ==UserScript==
// @id             iitc-plugin-portal-discoverer@nobody889
// @name           IITC plugin: Portal Discoverer
// @category       Cache
// @version        2.0.0
// @namespace      https://github.com/jonatkins/ingress-intel-total-conversion
// @description    [iitc-2017-01-08-021732] discover portals
// @include        https://*.ingress.com/intel*
// @include        http://*.ingress.com/intel*
// @match          https://*.ingress.com/intel*
// @match          http://*.ingress.com/intel*
// @include        https://*.ingress.com/mission/*
// @include        http://*.ingress.com/mission/*
// @match          https://*.ingress.com/mission/*
// @match          http://*.ingress.com/mission/*
// @grant          none
// @require        https://cdnjs.cloudflare.com/ajax/libs/rusha/0.8.6/rusha.min.js
// ==/UserScript==
function wrapper(plugin_info) {
    // ensure plugin framework is there, even if iitc is not yet loaded
    if (typeof window.plugin !== 'function') window.plugin = function() {};


    // PLUGIN START ////////////////////////////////////////////////////////

    window.plugin.portalDiscoverer = function() {};
    window.plugin.portalDiscoverer.portalQueue = []; // portals found before we got index
    window.plugin.portalDiscoverer.portalIndex = undefined; // portals we get back from server
    window.plugin.portalDiscoverer.newPortals = {}; // portals we've seen that dont match index

    window.plugin.portalDiscoverer.base_url = undefined;
    window.plugin.portalDiscoverer.how_many_new_portals = 1;
    window.plugin.portalDiscoverer.sending_portal_lock = false;
    window.plugin.portalDiscoverer.discovered_count = 0;

    window.plugin.portalDiscoverer.filter_bounds = [
        [46.887566, -125.208619],
        [40.258825, -115.094343],
    ];

    window.plugin.portalDiscoverer.setup = function() {

        var base_url = localStorage.getItem("base_url")
        if (base_url) {
            window.plugin.portalDiscoverer.base_url = base_url;
            window.plugin.portalDiscoverer.fetchIndex();
        }

        addHook('portalAdded', window.plugin.portalDiscoverer.handlePortalAdded);

        $('head').append('<style>' +
            'iframe { width: 475px; background: white; border: none; }' +
            'p.stats span { padding: 0 0.5em; }' +
            '</style>')

        $('#toolbox').append('<a onclick="window.plugin.portalDiscoverer.displayLoginDialog()">Discoverer</a>');

        window.addPortalHighlighter('Discovered Portals', window.plugin.portalDiscoverer.highlight)
    };

    window.plugin.portalDiscoverer.highlight = function(data) {
        var ll = _llstring([data.portal._latlng.lat, data.portal._latlng.lng]);
        var guid = data.portal.options.guid;

        if (!_latlng_in_bounds([data.portal._latlng.lat, data.portal._latlng.lng], window.plugin.portalDiscoverer.filter_bounds)) {
            return;
        }
//        console.log("discoverer highlight", guid, window.plugin.portalDiscoverer.portalIndex[guid])

        if (window.plugin.portalDiscoverer.portalIndex && !(guid in window.plugin.portalDiscoverer.portalIndex)) {
            data.portal.setStyle({
                fillColor: "red",
                fillOpacity: 1.0
            })
        }

    };

    window.plugin.portalDiscoverer.displayLoginDialog = function() {
        var html = $('<div/>');
        if (window.plugin.portalDiscoverer.base_url) {
            var stats = $('<p class="stats"></p>')
            stats.append($('<span>Index size: ' + Object.keys(window.plugin.portalDiscoverer.portalIndex).length + '</span>'));
            stats.append($('<span>Discovered this session: ' + window.plugin.portalDiscoverer.discovered_count + '</span>'));
            stats.append($('<span>Queued to send: ' + Object.keys(window.plugin.portalDiscoverer.newPortals).length + '</span>'));

            html.append(stats)
            html.append('<iframe style="width: 470px" src="' + window.plugin.portalDiscoverer.base_url + '"></iframe>');

            html.append($('<button>Clear Server</button>').click(function() {
                window.plugin.portalDiscoverer.base_url = undefined;
                localStorage.removeItem("base_url")
            }));
            html.append($('<button style="margin-left: 1em">Refresh Index</button>').click(function() {
                window.plugin.portalDiscoverer.portalIndex = undefined;
                window.plugin.portalDiscoverer.fetchIndex();
            }));
        } else {
            var server_input = $('<input id="discoverer_server_url" type="text"/>');
            var sbut = $('<button>Save</button>');
            sbut.click(function() {
                var url = server_input.val();
                if (!url.endsWith('/')) {
                    url += '/'
                }
                window.plugin.portalDiscoverer.base_url = url;
                localStorage.setItem("base_url", window.plugin.portalDiscoverer.base_url);

                html.empty()
                html.append('<iframe style="width: 470px" src="' + window.plugin.portalDiscoverer.base_url + '"></iframe>');
            })
            html = $('<div/>')
            html.append(server_input)
            html.append(sbut)
        }

        dialog({
            'html': html,
            'dialogClass': "ui-dialog-discoverer",
            title: "Discoverer",
            id: "discoverer",
            width: 500
        });
    };



    window.plugin.portalDiscoverer.handlePortalAdded = function(data) {
        var ll = [data.portal._latlng.lat, data.portal._latlng.lng];

        if (!_latlng_in_bounds(ll, window.plugin.portalDiscoverer.filter_bounds)) {
//            console.log("discoverer addPortal out of bounds")
            return;
        }

        if (!window.plugin.portalDiscoverer.portalIndex) {
            window.plugin.portalDiscoverer.portalQueue.push(data);
//            console.log("discoverer addPortal pushing to queue")
            return;
        }

        var name = data.portal.options.data.title;
        var guid = data.portal.options.guid
        var latE6 = data.portal.options.data.latE6;
        var lngE6 = data.portal.options.data.lngE6;
        var region = window.plugin.regions.regionName(S2.S2Cell.FromLatLng(data.portal._latlng, 6))

//        console.log("discoverer addPortal ", latE6, lngE6, name, guid, region);

        if (!(latE6 && lngE6 && name && guid)) {
            return;
        }

        var doc = {
            latE6: latE6,
            lngE6: lngE6,
            name: name,
            guid: guid,
            region: region
        };
        doc._ref = _portal_ref(doc)

        window.plugin.portalDiscoverer.checkInPortal(doc);
    };


    window.plugin.portalDiscoverer.checkInPortal = function(doc) {
        if (doc.guid in window.plugin.portalDiscoverer.newPortals) {
//            console.log("discoverer checkInPortal already in newPortals")
            return;
        }

        if (!(doc.guid in window.plugin.portalDiscoverer.portalIndex)) {
//            console.log("discoverer checkInPortal new portal");
            window.plugin.portalDiscoverer.newPortals[doc.guid] = doc
        }
        else if (doc._ref != window.plugin.portalDiscoverer.portalIndex[doc.guid]) {
//            console.log("discoverer checkInPortal ref mismatch!", doc, window.plugin.portalDiscoverer.portalIndex[doc.guid])
            window.plugin.portalDiscoverer.newPortals[doc.guid] = doc
        } else {
//            console.log("discoverer checkInPortal skipping portal");
        }

        window.plugin.portalDiscoverer.sendNewPortals();
    };

    window.plugin.portalDiscoverer.sendNewPortals = function() {
        if (!window.plugin.portalDiscoverer.base_url) {
            return;
        }

        if (window.plugin.portalDiscoverer.sending_portal_lock) {
            return;
        }

        if ((Object.keys(window.plugin.portalDiscoverer.newPortals).length) >= window.plugin.portalDiscoverer.how_many_new_portals) {
            window.plugin.portalDiscoverer.sending_portal_lock = true;

            var portalsToSend = Object.values(window.plugin.portalDiscoverer.newPortals);

            window.plugin.portalDiscoverer.discovered_count += portalsToSend.length;

            window.plugin.portalDiscoverer.newPortals = {};
            _xhr('POST', window.plugin.portalDiscoverer.base_url + "spi", function() {
                window.plugin.portalDiscoverer.sending_portal_lock = false;
                if (Object.keys(window.plugin.portalDiscoverer.newPortals).length > 0) {
                    window.plugin.portalDiscoverer.sendNewPortals();
                }
            }, JSON.stringify(portalsToSend));
        }
    };



    window.plugin.portalDiscoverer.fetchIndex = function() {
        if (window.plugin.portalDiscoverer.base_url) {
            _xhr('GET', window.plugin.portalDiscoverer.base_url + "pidx", window.plugin.portalDiscoverer.handleKnownIndex);
        }
    };

    window.plugin.portalDiscoverer.handleKnownIndex = function(data) {
        if (!window.plugin.portalDiscoverer.portalIndex) {
            window.plugin.portalDiscoverer.portalIndex = {}
        }
        var n = Object.keys(data).length;
        for (var guid in data) {
            if (!data.hasOwnProperty(guid)) continue;
            window.plugin.portalDiscoverer.portalIndex[guid] = data[guid];
        }

        window.plugin.portalDiscoverer.processPortalQueue();
    };

    window.plugin.portalDiscoverer.processPortalQueue = function() {
        for (i = 0; i < window.plugin.portalDiscoverer.portalQueue.length; i++) {
            window.plugin.portalDiscoverer.handlePortalAdded(window.plugin.portalDiscoverer.portalQueue[i]);
        }
        window.plugin.portalDiscoverer.portalQueue = [];
    };


    // util functions
    var _xhr = function(method, url, cb, data, async) {
        if (async === undefined) async = true;

        var req = new window.XMLHttpRequest();
        req.withCredentials = true;
        req.open(method, url, async);
        req.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
        req.onreadystatechange = function() {
            if (req.readyState != 4) return;
            if (req.status == 200) {
                if (this.getResponseHeader('Content-Type') == "application/json") {
                    cb(JSON.parse(req.responseText));
                } else {
                    cb(req.response)
                }
            } else {
            }
        };

        req.send(data);

    };
    var _llstring = function(latlng) {
        return Number(latlng[0]).toFixed(6) + "," + Number(latlng[1]).toFixed(6);
    };
    var _latlng_in_bounds = function(latlng, bounds) {
        return ((latlng[0] <= bounds[0][0] && latlng[0] >= bounds[1][0]) &&
            (latlng[1] >= bounds[0][1] && latlng[1] <= bounds[1][1]));
    };


    var _rusha = new Rusha();
    var _portal_ref = function(doc) {
        return _rusha.digest(doc.latE6+"|"+doc.lngE6+"|"+doc.name+"|"+doc.guid)
    }


    var setup = window.plugin.portalDiscoverer.setup;
    // PLUGIN END //////////////////////////////////////////////////////////

    setup.info = plugin_info; //add the script info data to the function as a property
    if (!window.bootPlugins) window.bootPlugins = [];
    window.bootPlugins.push(setup);
    // if IITC has already booted, immediately run the 'setup' function
    if (window.iitcLoaded && typeof setup === 'function') setup();
} // wrapper end


// inject code into site context
var script = document.createElement('script');
var info = {};
if (typeof GM_info !== 'undefined' && GM_info && GM_info.script) info.script = {
    version: GM_info.script.version,
    name: GM_info.script.name,
    description: GM_info.script.description
};
script.appendChild(document.createTextNode('(' + wrapper + ')(' + JSON.stringify(info) + ');'));
(document.body || document.head || document.documentElement).appendChild(script);