
import http.server
import socketserver
import socket
import select
import sys
import logging
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Proxy")

# Default whitelist (will be overridden by args or env vars in real usage)
DEFAULT_WHITELIST = [
    "pypi.org",
    "files.pythonhosted.org",
    "huggingface.co",
    "cdn-lfs.huggingface.co",
    "github.com",
    "raw.githubusercontent.com",
    "s3.amazonaws.com", # Often needed for specialized downloads
    "download.pytorch.org",
]

class WhitelistProxy(http.server.SimpleHTTPRequestHandler):
    whitelist = DEFAULT_WHITELIST

    def log_message(self, format, *args):
        logger.info(format % args)

    def is_whitelisted(self, host: str) -> bool:
        if not host:
            return False
            
        # Strip port
        if ':' in host:
            host = host.split(':')[0]
            
        # Check exact match or subdomain
        for domain in self.whitelist:
            if host == domain or host.endswith('.' + domain):
                return True
        
        return False

    def do_CONNECT(self):
        """Handle HTTPS CONNECT requests"""
        host = self.path
        if self.is_whitelisted(host):
            self.wfile.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
            self.proxy_data(host)
        else:
            logger.warning(f"BLOCKED CONNECT to {host}")
            self.send_error(403, f"Access to {host} is blocked by whitelist policy")

    def do_GET(self):
        """Handle HTTP GET requests"""
        parsed = urlparse(self.path)
        host = parsed.netloc
        
        if self.is_whitelisted(host):
            # For a real HTTP proxy, we'd need to fetch and return.
            # But most tools (pip, curl) will use CONNECT for everything or simple HTTP
            # For simplicity in this lightweight version, we'll suggest using HTTPS which uses CONNECT
            self.send_error(501, "Please use HTTPS for secure whitelisted access")
        else:
            logger.warning(f"BLOCKED GET to {host}")
            self.send_error(403, f"Access to {host} is blocked by whitelist policy")

    def proxy_data(self, host):
        """Tunnel data between client and target"""
        port = 443
        if ':' in host:
            host, port_str = host.split(':')
            port = int(port_str)
            
        try:
            # Connect to destination
            remote = socket.create_connection((host, port))
            
            # Tunnel data
            self.socket_attributes = (self.connection, remote)
            
            while True:
                # Wait for data from either side
                r, w, e = select.select([self.connection, remote], [], [], 60)
                
                if self.connection in r:
                    data = self.connection.recv(8192)
                    if not data: break
                    remote.sendall(data)
                    
                if remote in r:
                    data = remote.recv(8192)
                    if not data: break
                    self.connection.sendall(data)
                    
            remote.close()
            
        except Exception as e:
            logger.error(f"Tunnel error to {host}: {e}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8888)
    parser.add_argument("--whitelist", type=str, help="Comma-separated whitelist")
    args = parser.parse_args()
    
    if args.whitelist:
        WhitelistProxy.whitelist = [d.strip() for d in args.whitelist.split(',')]
        
    logger.info(f"Starting Whitelist Proxy on port {args.port}")
    logger.info(f"Allowed domains: {WhitelistProxy.whitelist}")
    
    with socketserver.TCPServer(("", args.port), WhitelistProxy) as httpd:
        httpd.serve_forever()
