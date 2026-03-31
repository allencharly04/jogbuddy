"""
JogBuddy — works both locally (HTTPS) and on cloud (HTTP, HTTPS handled by platform).
"""
import http.server, ssl, os, sys, socket, pathlib, urllib.request, urllib.parse, threading, signal

PORT = int(os.environ.get("PORT", sys.argv[1] if len(sys.argv) > 1 else 8501))
BASE = pathlib.Path(__file__).parent
os.chdir(BASE)

CERT = BASE / "cert.pem"
KEY  = BASE / "key.pem"
IS_LOCAL = not os.environ.get("RENDER") and not os.environ.get("RAILWAY_ENVIRONMENT")

# ── Generate self-signed cert for local use only ───────────────────────────────
if IS_LOCAL and (not CERT.exists() or not KEY.exists()):
    print("Generating self-signed certificate for local HTTPS...")
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import datetime, ipaddress

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, u"JogBuddy")])
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject).issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.utcnow())
            .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
            .add_extension(x509.SubjectAlternativeName([
                x509.DNSName(u"localhost"),
                x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
            ]), critical=False)
            .sign(key, hashes.SHA256())
        )
        with open("cert.pem","wb") as f: f.write(cert.public_bytes(serialization.Encoding.PEM))
        with open("key.pem","wb") as f:
            f.write(key.private_bytes(serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption()))
        print("Certificate created.")
    except Exception as e:
        print(f"Warning: could not create certificate ({e}) — running HTTP")

class Handler(http.server.SimpleHTTPRequestHandler):

    def do_GET(self):
        if self.path in ("/", ""):
            self.path = "/static/index.html"
            return super().do_GET()

        # ── LibriVox / archive.org search proxy ───────────────────────────────
        if self.path.startswith("/search?"):
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            term = params.get("q", [""])[0]
            page = params.get("page", ["1"])[0]
            rows = 12
            api = (f"https://archive.org/advancedsearch.php?"
                   f"q=title:({urllib.parse.quote(term)})+collection:librivoxaudio"
                   f"&output=json&fl[]=identifier,title,creator,description"
                   f"&rows={rows}&page={page}&sort[]=downloads+desc")
            try:
                req = urllib.request.Request(api, headers={"User-Agent":"Mozilla/5.0"})
                resp = urllib.request.urlopen(req, timeout=15)
                data = resp.read()
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.send_header("Access-Control-Allow-Origin","*")
                self.end_headers()
                self.wfile.write(data)
            except Exception as e:
                self.send_error(502, str(e))
            return

        # ── Book metadata proxy (chapters list) ───────────────────────────────
        if self.path.startswith("/metadata?"):
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            identifier = params.get("id", [""])[0]
            if not identifier:
                self.send_error(400, "Missing id"); return
            api = f"https://archive.org/metadata/{identifier}"
            try:
                req = urllib.request.Request(api, headers={"User-Agent":"Mozilla/5.0"})
                resp = urllib.request.urlopen(req, timeout=15)
                data = resp.read()
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.send_header("Access-Control-Allow-Origin","*")
                self.end_headers()
                self.wfile.write(data)
            except Exception as e:
                self.send_error(502, str(e))
            return

        # ── Audio proxy (streams MP3 from archive.org to phone) ───────────────
        if self.path.startswith("/proxy?"):
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            target = params.get("url", [None])[0]
            if not target:
                self.send_error(400, "Missing url parameter"); return
            allowed = ["archive.org", "librivox.org", "loyalbooks.com"]
            if not any(d in target for d in allowed):
                self.send_error(403, "Domain not allowed"); return
            print(f"Streaming: {target[:80]}...")
            try:
                req = urllib.request.Request(target, headers={
                    "User-Agent": "Mozilla/5.0",
                    "Range": self.headers.get("Range", ""),
                })
                resp = urllib.request.urlopen(req, timeout=15)
                self.send_response(200)
                for h in ["Content-Type","Content-Length","Content-Range","Accept-Ranges"]:
                    v = resp.headers.get(h)
                    if v: self.send_header(h, v)
                self.send_header("Access-Control-Allow-Origin","*")
                self.end_headers()
                while True:
                    chunk = resp.read(65536)
                    if not chunk: break
                    try: self.wfile.write(chunk)
                    except (BrokenPipeError, ConnectionResetError): break
            except Exception as e:
                print(f"Stream error: {e}")
            return

        return super().do_GET()

    def log_message(self, fmt, *args):
        pass

def local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]; s.close(); return ip
    except: return "YOUR_PC_IP"

class ReusableTCPServer(http.server.HTTPServer):
    allow_reuse_address = True

# Bind to all interfaces (required for cloud deployment)
httpd = ReusableTCPServer(("0.0.0.0", PORT), Handler)

# Wrap with SSL only when running locally and cert exists
proto = "http"
if IS_LOCAL and CERT.exists() and KEY.exists():
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(str(CERT), str(KEY))
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    proto = "https"

ip = local_ip()
if IS_LOCAL:
    print(f"\n🏃 JogBuddy is running!")
    print(f"   On this PC:    {proto}://localhost:{PORT}")
    print(f"   On your phone: {proto}://{ip}:{PORT}")
    if proto == "https":
        print(f"\n   ⚠️  First time: tap Advanced → Proceed to {ip} (unsafe)")
    print(f"   Press Ctrl+C to stop.\n")
else:
    print(f"🏃 JogBuddy running on port {PORT}")

def shutdown():
    print("\n\nStopping JogBuddy... bye! 👋")
    threading.Thread(target=httpd.shutdown, daemon=True).start()
    sys.exit(0)

def sig_handler(sig, frame): shutdown()

signal.signal(signal.SIGINT, sig_handler)
signal.signal(signal.SIGTERM, sig_handler)
if hasattr(signal, 'SIGBREAK'):
    signal.signal(signal.SIGBREAK, sig_handler)

try:
    httpd.serve_forever()
except KeyboardInterrupt:
    shutdown()
