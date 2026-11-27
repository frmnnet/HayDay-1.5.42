from Utils.Logging import logger, setup_logging
import socket
import traceback
from threading import *
from Packets.MessageFactory import *
from Logic.Device import Device
from Logic.GameState import GameState
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from Utils.Storage import load_config, save_config
from Utils.PacketCapture import record as capture_packet


class ServerThread():
    def __init__(self, ip, port):
        self.address = str(ip)
        self.port = int(port)
        self.client = socket.socket()

    def start(self):
        self.client.bind((self.address, self.port))

        logger.info(f"[*] Server is listening on {self.address}:{self.port}\nLet's play HayDay!".format(self.address, self.port))

        while True:
            self.client.listen(5)
            client, address = self.client.accept()

            logger.info("[*] New connection from {}".format(address[0]))
            clientThread = ClientThread(client).start()


class ClientThread(Thread):
    def __init__(self, client):
        Thread.__init__(self)

        self.client = client
        self.device = Device(self.client)

    def recvall(self, size, timeout=5.0):
        data = []
        while size > 0:
            self.client.settimeout(timeout)
            s = self.client.recv(size)
            self.client.settimeout(None)
            if not s:
                raise EOFError
            data.append(s)
            size -= len(s)
        return b''.join(data)

    def run(self):
        try:
            self.loop()
        except (EOFError, OSError):
            pass
        finally:
            # Anything still marked dirty on this connection gets persisted.
            try:
                GameState.flush_device(self.device)
            except Exception:
                logger.exception("[DB] final flush failed")
            self.device.unregister_online()
            self.client.close()
            logger.info('[*] Client disconnected')

    def loop(self):
        while True:
            header   = self.recvall(7, None)
            packetid = int.from_bytes(header[:2], 'big')
            length   = int.from_bytes(header[2:5], 'big')
            version  = int.from_bytes(header[5:], 'big')
            data     = self.recvall(length)

            if len(header) >= 7:
                if length == len(data):
                    logger.info("[*] {} received".format(packetid))

                    try:
                        decrypted = self.device.decrypt(data)
                        capture_packet("C2S", packetid, decrypted, version)
                        if packetid in availablePackets:

                            Message = availablePackets[packetid](decrypted, self.device)

                            Message.decode()
                            Message.process()

                        else:
                            logger.warning("[*] {} not handled, payload: {}".format(packetid, decrypted.hex()))  # hex for reversing

                    except Exception:
                            logger.error('Error while decrypting / handling {}'.format(packetid))
                            logger.exception('Traceback for packet {}'.format(packetid))
                    finally:
                        # One write per packet instead of one per command:
                        # state.save() only marks the state dirty.
                        try:
                            GameState.flush_device(self.device)
                        except Exception:
                            logger.exception("[DB] flush failed for packet {}".format(packetid))
                else:
                    logger.warning('Incorrect Length for packet {} (header length: {}, data length: {})'.format(packetid, length, len(data)))
            else:
                logger.warning('Received an invalid packet from client')
                return
            
class EnvHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        c = load_config()
        body = json.dumps({
            "environment": "maintenance" if c["Maintenance"] else c["Environment"],
            "serverHost": c["Host"],
            "assetUrl": "http://{}:{}/assets/".format(c["Host"], c["HttpPort"]),
            "updateUrl": "",
            "status": "ok",
        }).encode()
        logger.info('[HTTP] GET {}'.format(self.path))

        if self.path == "/status":
            body = json.dumps({
                "status": "ok",
                "host": c["Host"],
                "port": c["Port"],
                "name": c.get("Name"),
                "diamonds": c.get("Diamonds"),
                "cash": c.get("Cash"),
                "expLevel": c.get("ExpLevel"),
            }).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


if __name__ == '__main__':
    setup_logging()
    logger.info('Starting Hay Day server (log level from config.json)')
    conf = load_config()
    Thread(target=ThreadingHTTPServer(("0.0.0.0", conf["HttpPort"]), EnvHandler).serve_forever, daemon=True).start()
    server = ServerThread("0.0.0.0", conf["Port"])
    server.start()
