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
            'iframe { width: 675px; background: white; border: none; }' +
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
            var refreshidxbtn = $('<button style="margin-left: 1em">Refresh Index</button>')
            refreshidxbtn.click(function() {
                window.plugin.portalDiscoverer.portalIndex = undefined;
                window.plugin.portalDiscoverer.fetchIndex();
            })
            html.append($('<p>Known Index: ' + Object.keys(window.plugin.portalDiscoverer.portalIndex).length + '</p>').append(refreshidxbtn))
            html.append('<iframe style="width: 670px" src="' + window.plugin.portalDiscoverer.base_url + '"></iframe>');
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

                html.empty()
                html.append('<iframe style="width: 670px" src="' + window.plugin.portalDiscoverer.base_url + '"></iframe>');
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
        var ll = [data.portal._latlng.lat, data.portal._latlng.lng];

        if (!_latlng_in_bounds(ll, window.plugin.portalDiscoverer.filter_bounds)) {
            return;
        }

        if (!window.plugin.portalDiscoverer.portalIndex) {
            window.plugin.portalDiscoverer.portalQueue.push(data);
            return;
        }

        var name = data.portal.options.data.title;
        var guid = data.portal.options.guid
        var latE6 = data.portal.options.data.latE6;
        var lngE6 = data.portal.options.data.lngE6;

        if (!(latE6 && lngE6 && name && guid)) {
            return;
        }

        var doc = {
            latE6: latE6,
            lngE6: lngE6,
            name: name,
            guid: guid
        };
        doc._ref = _portal_ref(doc)

        window.plugin.portalDiscoverer.checkInPortal(doc);
    };


    window.plugin.portalDiscoverer.checkInPortal = function(doc) {
        if (doc.guid in window.plugin.portalDiscoverer.newPortals) {
            console.log("discoverer checkInPortal already in newPortals")
            return;
        }

        if (!(doc.guid in window.plugin.portalDiscoverer.portalIndex)) {
            console.log("discoverer checkInPortal new portal");
            window.plugin.portalDiscoverer.newPortals[doc.guid] = doc
        }
        else if (doc._ref != window.plugin.portalDiscoverer.portalIndex[doc.guid]) {
            console.log("discoverer checkInPortal ref mismatch!", doc, window.plugin.portalDiscoverer.portalIndex[doc.guid])
            window.plugin.portalDiscoverer.newPortals[doc.guid] = doc
        } else {
            console.log("discoverer checkInPortal skipping portal");
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



    /*! rusha 2017-05-05 */
    (function(){var a={getDataType:function(a){if(typeof a==="string"){return"string"}if(a instanceof Array){return"array"}if(typeof global!=="undefined"&&global.Buffer&&global.Buffer.isBuffer(a)){return"buffer"}if(a instanceof ArrayBuffer){return"arraybuffer"}if(a.buffer instanceof ArrayBuffer){return"view"}if(a instanceof Blob){return"blob"}throw new Error("Unsupported data type.")}};function b(d){"use strict";var e={fill:0};var f=function(a){for(a+=9;a%64>0;a+=1);return a};var g=function(a,b){var c=new Uint8Array(a.buffer);var d=b%4,e=b-d;switch(d){case 0:c[e+3]=0;case 1:c[e+2]=0;case 2:c[e+1]=0;case 3:c[e+0]=0}for(var f=(b>>2)+1;f<a.length;f++)a[f]=0};var h=function(a,b,c){a[b>>2]|=128<<24-(b%4<<3);a[((b>>2)+2&~15)+14]=c/(1<<29)|0;a[((b>>2)+2&~15)+15]=c<<3};var i=function(a,b,c,d,e){var f=this,g,h=e%4,i=(d+h)%4,j=d-i;switch(h){case 0:a[e]=f.charCodeAt(c+3);case 1:a[e+1-(h<<1)|0]=f.charCodeAt(c+2);case 2:a[e+2-(h<<1)|0]=f.charCodeAt(c+1);case 3:a[e+3-(h<<1)|0]=f.charCodeAt(c)}if(d<i+h){return}for(g=4-h;g<j;g=g+4|0){b[e+g>>2]=f.charCodeAt(c+g)<<24|f.charCodeAt(c+g+1)<<16|f.charCodeAt(c+g+2)<<8|f.charCodeAt(c+g+3)}switch(i){case 3:a[e+j+1|0]=f.charCodeAt(c+j+2);case 2:a[e+j+2|0]=f.charCodeAt(c+j+1);case 1:a[e+j+3|0]=f.charCodeAt(c+j)}};var j=function(a,b,c,d,e){var f=this,g,h=e%4,i=(d+h)%4,j=d-i;switch(h){case 0:a[e]=f[c+3];case 1:a[e+1-(h<<1)|0]=f[c+2];case 2:a[e+2-(h<<1)|0]=f[c+1];case 3:a[e+3-(h<<1)|0]=f[c]}if(d<i+h){return}for(g=4-h;g<j;g=g+4|0){b[e+g>>2|0]=f[c+g]<<24|f[c+g+1]<<16|f[c+g+2]<<8|f[c+g+3]}switch(i){case 3:a[e+j+1|0]=f[c+j+2];case 2:a[e+j+2|0]=f[c+j+1];case 1:a[e+j+3|0]=f[c+j]}};var k=function(a,b,d,e,f){var g=this,h,i=f%4,j=(e+i)%4,k=e-j;var l=new Uint8Array(c.readAsArrayBuffer(g.slice(d,d+e)));switch(i){case 0:a[f]=l[3];case 1:a[f+1-(i<<1)|0]=l[2];case 2:a[f+2-(i<<1)|0]=l[1];case 3:a[f+3-(i<<1)|0]=l[0]}if(e<j+i){return}for(h=4-i;h<k;h=h+4|0){b[f+h>>2|0]=l[h]<<24|l[h+1]<<16|l[h+2]<<8|l[h+3]}switch(j){case 3:a[f+k+1|0]=l[k+2];case 2:a[f+k+2|0]=l[k+1];case 1:a[f+k+3|0]=l[k]}};var l=function(b){switch(a.getDataType(b)){case"string":return i.bind(b);case"array":return j.bind(b);case"buffer":return j.bind(b);case"arraybuffer":return j.bind(new Uint8Array(b));case"view":return j.bind(new Uint8Array(b.buffer,b.byteOffset,b.byteLength));case"blob":return k.bind(b)}};var m=function(b,c){switch(a.getDataType(b)){case"string":return b.slice(c);case"array":return b.slice(c);case"buffer":return b.slice(c);case"arraybuffer":return b.slice(c);case"view":return b.buffer.slice(c)}};var n=new Array(256);for(var o=0;o<256;o++){n[o]=(o<16?"0":"")+o.toString(16)}var p=function(a){var b=new Uint8Array(a);var c=new Array(a.byteLength);for(var d=0;d<c.length;d++){c[d]=n[b[d]]}return c.join("")};var q=function(a){var b;if(a<=65536)return 65536;if(a<16777216){for(b=1;b<a;b=b<<1);}else{for(b=16777216;b<a;b+=16777216);}return b};var r=function(a){if(a%64>0){throw new Error("Chunk size must be a multiple of 128 bit")}e.offset=0;e.maxChunkLen=a;e.padMaxChunkLen=f(a);e.heap=new ArrayBuffer(q(e.padMaxChunkLen+320+20));e.h32=new Int32Array(e.heap);e.h8=new Int8Array(e.heap);e.core=new b._core({Int32Array:Int32Array,DataView:DataView},{},e.heap);e.buffer=null};r(d||64*1024);var s=function(a,b){e.offset=0;var c=new Int32Array(a,b+320,5);c[0]=1732584193;c[1]=-271733879;c[2]=-1732584194;c[3]=271733878;c[4]=-1009589776};var t=function(a,b){var c=f(a);var d=new Int32Array(e.heap,0,c>>2);g(d,a);h(d,a,b);return c};var u=function(a,b,c,d){l(a)(e.h8,e.h32,b,c,d||0)};var v=function(a,b,c,d,f){var g=c;u(a,b,c);if(f){g=t(c,d)}e.core.hash(g,e.padMaxChunkLen)};var w=function(a,b){var c=new Int32Array(a,b+320,5);var d=new Int32Array(5);var e=new DataView(d.buffer);e.setInt32(0,c[0],false);e.setInt32(4,c[1],false);e.setInt32(8,c[2],false);e.setInt32(12,c[3],false);e.setInt32(16,c[4],false);return d};var x=this.rawDigest=function(a){var b=a.byteLength||a.length||a.size||0;s(e.heap,e.padMaxChunkLen);var c=0,d=e.maxChunkLen;for(c=0;b>c+d;c+=d){v(a,c,d,b,false)}v(a,c,b-c,b,true);return w(e.heap,e.padMaxChunkLen)};this.digest=this.digestFromString=this.digestFromBuffer=this.digestFromArrayBuffer=function(a){return p(x(a).buffer)};this.resetState=function(){s(e.heap,e.padMaxChunkLen);return this};this.append=function(a){var b=0;var c=a.byteLength||a.length||a.size||0;var d=e.offset%e.maxChunkLen;var f;e.offset+=c;while(b<c){f=Math.min(c-b,e.maxChunkLen-d);u(a,b,f,d);d+=f;b+=f;if(d===e.maxChunkLen){e.core.hash(e.maxChunkLen,e.padMaxChunkLen);d=0}}return this};this.getState=function(){var a=e.offset%e.maxChunkLen;var b;if(!a){var c=new Int32Array(e.heap,e.padMaxChunkLen+320,5);b=c.buffer.slice(c.byteOffset,c.byteOffset+c.byteLength)}else{b=e.heap.slice(0)}return{offset:e.offset,heap:b}};this.setState=function(a){e.offset=a.offset;if(a.heap.byteLength===20){var b=new Int32Array(e.heap,e.padMaxChunkLen+320,5);b.set(new Int32Array(a.heap))}else{e.h32.set(new Int32Array(a.heap))}return this};var y=this.rawEnd=function(){var a=e.offset;var b=a%e.maxChunkLen;var c=t(b,a);e.core.hash(c,e.padMaxChunkLen);var d=w(e.heap,e.padMaxChunkLen);s(e.heap,e.padMaxChunkLen);return d};this.end=function(){return p(y().buffer)}}b._core=function a(b,c,d){"use asm";var e=new b.Int32Array(d);function f(a,b){a=a|0;b=b|0;var c=0,d=0,f=0,g=0,h=0,i=0,j=0,k=0,l=0,m=0,n=0,o=0,p=0,q=0;f=e[b+320>>2]|0;h=e[b+324>>2]|0;j=e[b+328>>2]|0;l=e[b+332>>2]|0;n=e[b+336>>2]|0;for(c=0;(c|0)<(a|0);c=c+64|0){g=f;i=h;k=j;m=l;o=n;for(d=0;(d|0)<64;d=d+4|0){q=e[c+d>>2]|0;p=((f<<5|f>>>27)+(h&j|~h&l)|0)+((q+n|0)+1518500249|0)|0;n=l;l=j;j=h<<30|h>>>2;h=f;f=p;e[a+d>>2]=q}for(d=a+64|0;(d|0)<(a+80|0);d=d+4|0){q=(e[d-12>>2]^e[d-32>>2]^e[d-56>>2]^e[d-64>>2])<<1|(e[d-12>>2]^e[d-32>>2]^e[d-56>>2]^e[d-64>>2])>>>31;p=((f<<5|f>>>27)+(h&j|~h&l)|0)+((q+n|0)+1518500249|0)|0;n=l;l=j;j=h<<30|h>>>2;h=f;f=p;e[d>>2]=q}for(d=a+80|0;(d|0)<(a+160|0);d=d+4|0){q=(e[d-12>>2]^e[d-32>>2]^e[d-56>>2]^e[d-64>>2])<<1|(e[d-12>>2]^e[d-32>>2]^e[d-56>>2]^e[d-64>>2])>>>31;p=((f<<5|f>>>27)+(h^j^l)|0)+((q+n|0)+1859775393|0)|0;n=l;l=j;j=h<<30|h>>>2;h=f;f=p;e[d>>2]=q}for(d=a+160|0;(d|0)<(a+240|0);d=d+4|0){q=(e[d-12>>2]^e[d-32>>2]^e[d-56>>2]^e[d-64>>2])<<1|(e[d-12>>2]^e[d-32>>2]^e[d-56>>2]^e[d-64>>2])>>>31;p=((f<<5|f>>>27)+(h&j|h&l|j&l)|0)+((q+n|0)-1894007588|0)|0;n=l;l=j;j=h<<30|h>>>2;h=f;f=p;e[d>>2]=q}for(d=a+240|0;(d|0)<(a+320|0);d=d+4|0){q=(e[d-12>>2]^e[d-32>>2]^e[d-56>>2]^e[d-64>>2])<<1|(e[d-12>>2]^e[d-32>>2]^e[d-56>>2]^e[d-64>>2])>>>31;p=((f<<5|f>>>27)+(h^j^l)|0)+((q+n|0)-899497514|0)|0;n=l;l=j;j=h<<30|h>>>2;h=f;f=p;e[d>>2]=q}f=f+g|0;h=h+i|0;j=j+k|0;l=l+m|0;n=n+o|0}e[b+320>>2]=f;e[b+324>>2]=h;e[b+328>>2]=j;e[b+332>>2]=l;e[b+336>>2]=n}return{hash:f}};if(typeof module!=="undefined"){module.exports=b}else if(typeof window!=="undefined"){window.Rusha=b}if(typeof FileReaderSync!=="undefined"){var c=new FileReaderSync;var d=function a(b,c,d){try{return d(null,b.digest(c))}catch(a){return d(a)}};var e=function a(b,c,d,f,g){var h=new self.FileReader;h.onloadend=function a(){var i=h.result;c+=h.result.byteLength;try{b.append(i)}catch(a){g(a);return}if(c<f.size){e(b,c,d,f,g)}else{g(null,b.end())}};h.readAsArrayBuffer(f.slice(c,c+d))};self.onmessage=function a(c){var f=c.data.data,g=c.data.file,h=c.data.id;if(typeof h==="undefined")return;if(!g&&!f)return;var i=c.data.blockSize||4*1024*1024;var j=new b(i);j.resetState();var k=function a(b,c){if(!b){self.postMessage({id:h,hash:c})}else{self.postMessage({id:h,error:b.name})}};if(f)d(j,f,k);if(g)e(j,0,i,g,k)}}})();

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