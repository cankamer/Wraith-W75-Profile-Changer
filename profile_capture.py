"""wraith.software'te bir profile tıklanınca klavyeye giden paketleri yakalar.

Ayarlar penceresindeki "Tanımla" sihirbazı kullanır. Sitenin konsoluna yapıştırılan kısa bir kod,
sendReport çağrılarını 127.0.0.1'deki bu dinleyiciye iletir. Dinleyici yalnızca oturuma özel anahtarı
bilen ve Origin'i wraith.software olan istekleri kabul eder; böylece başka bir web sitesi sahte paket
yazdıramaz.
"""
import json
import re
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8765
SITE_ORIGIN = "https://wraith.software"
MIN_BURST = 20  # bundan az paket, profil yüklemesi sayılmaz (ör. tek bir ışık değişikliği)
MAX_EVENTS = 5000
PACKET_RE = re.compile(r"^[0-9a-f]{126}$")  # 63 bayt veri = 126 hex karakter (reportId ayrı, hep 1)

SNIPPET = """(()=>{window.__wraithUrl='%(url)s';const P=HIDDevice.prototype;if(P.__w)return;P.__w=1;
const post=o=>fetch(window.__wraithUrl,{method:'POST',mode:'no-cors',body:JSON.stringify(o)});
for(const m of ['sendReport']){const orig=P[m];P[m]=function(id,data){
const u=data instanceof ArrayBuffer?new Uint8Array(data):new Uint8Array(data.buffer,data.byteOffset,data.byteLength);
post({id,hex:[...u].map(b=>b.toString(16).padStart(2,'0')).join('')});return orig.call(this,id,data)}}
document.getElementById('profiles').addEventListener('click',e=>{const id=e.target.id;
const l=id&&document.querySelector('label[for="'+id+'"]');
post({mark:((l?l.textContent:e.target.textContent)||id||'').trim().slice(0,30)})},true);
console.log('Wraith yakalama hazır')})()"""


class _Server(ThreadingHTTPServer):
    allow_reuse_address = False  # Windows'ta SO_REUSEADDR başka sürecin aynı porta bağlanmasına izin verir


class CaptureSession:
    def __init__(self):
        self.token = secrets.token_urlsafe(16)
        self.events = []
        self._lock = threading.Lock()
        session = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(min(int(self.headers.get("Content-Length", 0)), 4096))
                ok = self.path == f"/{session.token}" and self.headers.get("Origin") == SITE_ORIGIN
                if ok:
                    session._add(body)
                self.send_response(204 if ok else 403)
                self.end_headers()

            def log_message(self, *args):
                pass

        self._server = _Server(("127.0.0.1", PORT), Handler)  # port doluysa OSError
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def snippet(self):
        return SNIPPET % {"url": f"http://127.0.0.1:{PORT}/{self.token}"}

    def _add(self, body):
        try:
            obj = json.loads(body)
        except ValueError:
            return
        if isinstance(obj.get("mark"), str):
            event = {"mark": obj["mark"][:30]}
        elif obj.get("id") == 1 and isinstance(obj.get("hex"), str) and PACKET_RE.match(obj["hex"]):
            event = {"hex": obj["hex"]}
        else:
            return
        with self._lock:
            if len(self.events) < MAX_EVENTS:
                self.events.append(event)

    def last_burst(self):
        """Son profil yüklemesi: (site profil adı, paket listesi) ya da None."""
        with self._lock:
            events = list(self.events)
        segments, current = [], None
        for e in events:
            if "mark" in e:
                current = [e["mark"], []]
                segments.append(current)
            elif current is not None:
                current[1].append(e["hex"])
        for name, packets in reversed(segments):
            if len(packets) >= MIN_BURST:
                return name, packets
        return None

    def close(self):
        self._server.shutdown()
        self._server.server_close()
