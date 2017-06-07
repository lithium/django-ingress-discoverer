// ==UserScript==
// @id             iitc-plugin-portal-discoverer@noobdy889
// @name           IITC plugin: Portal Discoverer
// @category       Cache
// @version        0.0.2
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
// ==/UserScript==


function wrapper(plugin_info) {
// ensure plugin framework is there, even if iitc is not yet loaded
if(typeof window.plugin !== 'function') window.plugin = function() {};


// PLUGIN START ////////////////////////////////////////////////////////


// util functions
var _xhr = function(method, url, cb, data, async) {
  if (async === undefined) async = true;

  var req = new window.XMLHttpRequest();
  req.withCredentials = true;
  req.open(method, url, async);
  req.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
  req.onreadystatechange = function() {
    if (req.readyState != 4) return;
    if(req.status == 200) {
      cb(JSON.parse(req.responseText));
    }
  };

  req.send(data);

};
var _llstring = function(latlng) {
  return latlng[0]+","+latlng[1];
};
var _latlng_in_bounds = function(latlng, bounds) {
    return ((latlng[0] <= bounds[0][0] && latlng[0] >= bounds[1][0]) &&
            (latlng[1] >= bounds[0][1] && latlng[1] <= bounds[1][1]));
}


// use own namespace for plugin
window.plugin.portalDiscoverer = function() {};
window.plugin.portalDiscoverer.portalQueue = [];
window.plugin.portalDiscoverer.portalIndex = {};
window.plugin.portalDiscoverer.foundPortalIndex = {};
window.plugin.portalDiscoverer.newPortals = {};

window.plugin.portalDiscoverer.base_url = undefined;
window.plugin.portalDiscoverer.how_many_new_portals = 1;


window.plugin.portalDiscoverer.filter_bounds = [
  [46.325171, -124.799138],
  [41.991194, -117.023564]
];

window.plugin.portalDiscoverer.setup  = function() {

  var portal_cache = localStorage.getItem("known_portal_index");
  var base_url = localStorage.getItem("base_url")
  if (base_url) {
    window.plugin.portalDiscoverer.base_url = base_url;
  }

  if (portal_cache) {
    window.plugin.portalDiscoverer.portalIndex = JSON.parse(portal_cache);
    window.plugin.portalDiscoverer.fetchSpi();
  } else {
    window.plugin.portalDiscoverer.fetchIndex();
  }

  addHook('portalAdded', window.plugin.portalDiscoverer.handlePortalAdded);

  $('head').append('<style>'+
  'iframe { width: 675px; background: white; border: none; }'+
  '</style>')

  $('#toolbox').append('<a onclick="window.plugin.portalDiscoverer.displayLoginDialog()">Discoverer</a>');

  window.addPortalHighlighter('Discovered Portals', window.plugin.portalDiscoverer.highlight)
};

window.plugin.portalDiscoverer.highlight = function(data) {
  var ll = data.portal._latlng.lat+","+data.portal._latlng.lng

  if (ll in window.plugin.portalDiscoverer.foundPortalIndex) {
    data.portal.setStyle({
      fillColor: "magenta",
      fillOpacity: 1.0
    })
  }
  else if (!(ll in window.plugin.portalDiscoverer.portalIndex)) {
    data.portal.setStyle({
      fillColor: "red",
      fillOpacity: 1.0
    })
  }

};

window.plugin.portalDiscoverer.fetchIndex = function() {
    if (window.plugin.portalDiscoverer.base_url) {
        _xhr('GET', window.plugin.portalDiscoverer.base_url+"pidx", window.plugin.portalDiscoverer.handleKnownIndex);
    } else {
    }
};

window.plugin.portalDiscoverer.displayLoginDialog = function() {
  var html = $('<div/>');
  if (window.plugin.portalDiscoverer.base_url) {
    html.append('<iframe style="width: 670px" src="'+window.plugin.portalDiscoverer.base_url+'"></iframe>');
    html.append($('<button>Clear Server</button>').click(function() {
        window.plugin.portalDiscoverer.base_url = undefined;
        localStorage.removeItem("base_url")
    }))
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
        window.plugin.portalDiscoverer.fetchIndex();
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
    width: 700
  });
};


window.plugin.portalDiscoverer.handlePortalAdded = function(data) {

  var latlng = [data.portal._latlng.lat, data.portal._latlng.lng];
  var name = data.portal.options.data.title;
  var idx = {
    latlng: latlng,
    name: name
  };
  var llstring = _llstring(latlng);

  if (!name) {
    return; // skip unless we know the name
  }

  if (window.plugin.portalDiscoverer.portalIndex) {
    window.plugin.portalDiscoverer.checkInPortal(llstring, idx);
  } else {
    window.plugin.portalDiscoverer.portalQueue.push([llstring,idx]);
  }

};


window.plugin.portalDiscoverer.checkInPortal = function(llstring, idx) {
  if (!window.plugin.portalDiscoverer.portalIndex) {
    return;
  }

  if (!_latlng_in_bounds(idx.latlng, window.plugin.portalDiscoverer.filter_bounds)) {
      return;
  }

  if (!(llstring in window.plugin.portalDiscoverer.portalIndex) && !(llstring in window.plugin.portalDiscoverer.foundPortalIndex)) {
    if (!(llstring in window.plugin.portalDiscoverer.newPortals)) {
      window.plugin.portalDiscoverer.newPortals[llstring] = idx;
    } else {
      window.plugin.portalDiscoverer.newPortals[llstring].name = idx.name;
    }
  }

  window.plugin.portalDiscoverer.sendNewPortals();
};

window.plugin.portalDiscoverer.sendNewPortals = function() {
  if (!window.plugin.portalDiscoverer.base_url)
      return;

  if ((Object.keys(window.plugin.portalDiscoverer.newPortals).length) >= window.plugin.portalDiscoverer.how_many_new_portals) {
    var portalsToSend = Object.values(window.plugin.portalDiscoverer.newPortals);
    window.plugin.portalDiscoverer.newPortals = {};
    _xhr('POST', window.plugin.portalDiscoverer.base_url+"spi", window.plugin.portalDiscoverer.handleSubmit, JSON.stringify(portalsToSend));
  }
};


window.plugin.portalDiscoverer.addIndex = function(data, index) {
  var index = index || window.plugin.portalDiscoverer.portalIndex;
  for (var i=0; i < data.k.length; i++) {
    var ll = [data.k[i][1], data.k[i][0]];
    var key = _llstring(ll);
    index[key] = true;
  }
}

window.plugin.portalDiscoverer.handleKnownIndex = function(data) {
    window.plugin.portalDiscoverer.addIndex(data);

    localStorage.setItem("known_portal_index", JSON.stringify(window.plugin.portalDiscoverer.portalIndex));

    window.plugin.portalDiscoverer.fetchSpi();

};
window.plugin.portalDiscoverer.fetchSpi = function() {
  _xhr('GET', window.plugin.portalDiscoverer.base_url+"spi", function(data) {
      window.plugin.portalDiscoverer.addIndex(data, window.plugin.portalDiscoverer.foundPortalIndex);
      window.plugin.portalDiscoverer.processPortalQueue();
  });
}


window.plugin.portalDiscoverer.processPortalQueue = function() {
  for (i=0; i < window.plugin.portalDiscoverer.portalQueue.length; i++) {
    var llstring = window.plugin.portalDiscoverer.portalQueue[i][0];
    var idx = window.plugin.portalDiscoverer.portalQueue[i][1];
    window.plugin.portalDiscoverer.checkInPortal(llstring, idx);
  }
};







var setup = window.plugin.portalDiscoverer.setup;
// PLUGIN END //////////////////////////////////////////////////////////

setup.info = plugin_info; //add the script info data to the function as a property
if(!window.bootPlugins) window.bootPlugins = [];
window.bootPlugins.push(setup);
// if IITC has already booted, immediately run the 'setup' function
if(window.iitcLoaded && typeof setup === 'function') setup();
} // wrapper end
// inject code into site context
var script = document.createElement('script');
var info = {};
if (typeof GM_info !== 'undefined' && GM_info && GM_info.script) info.script = { version: GM_info.script.version, name: GM_info.script.name, description: GM_info.script.description };
script.appendChild(document.createTextNode('('+ wrapper +')('+JSON.stringify(info)+');'));
(document.body || document.head || document.documentElement).appendChild(script);


