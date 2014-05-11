from autobahn.asyncio.websocket import WebSocketServerProtocol, \
                                       WebSocketServerFactory
from pycrc.crc_algorithms import Crc
import cobs

class CANPacketizer:
    def __init__(self):
        self.crc = Crc(width = 16, poly = 0x8005,
            reflect_in = True, xor_in = 0x0000,
            reflect_out = True, xor_out = 0x0000)
        
    def checksum(self, txt):
        return self.crc.table_driven(txt)
    
    def decode(self, txt):
        if txt[-1] == '\x00':
            txt = txt[:-1]
        p = Packet()
        decoded = cobs.decode(txt)
        # print ''.join( [ "%02X " % ord( x ) for x in decoded ] ).strip()
        crc = self.checksum(decoded[0:-2])
        crc_check = uint16(decoded[-2:])
        if crc != crc_check:
            raise DecodeError("CRC mismatch")
        p.rtr = uint8(decoded[0]) & 0x40 != 0
        p.id = uint16(decoded[0:2]) & 0x7ff
        p.data = [uint8(x) for x in decoded[2:-2]]
        return p
        
    def encode(self, packet):
        out = []
        out.append((int(packet.rtr) << 6) | ((packet.id & 0x700) >> 8))
        out.append(packet.id & 0xff)
        out.extend(packet.data)
        out = [chr(x) for x in out]
        crc = self.checksum(out)
        out.append(chr( (crc & 0xff00)>>8 ))
        out.append(chr( crc & 0xff ))
        encoded = cobs.encode(''.join(out))
        encoded += '\x00'
        return encoded

class CANServer(WebSocketServerProtocol):

   def onConnect(self, request):
      print("Client connecting: {0}".format(request.peer))

   def onOpen(self):
      print("WebSocket connection open.")

   def onMessage(self, payload, isBinary):
      if isBinary:
         print("Binary message received: {0} bytes".format(len(payload)))
      else:
         print("Text message received: {0}".format(payload.decode('utf8')))

   def onClose(self, wasClean, code, reason):
      print("WebSocket connection closed: {0}".format(reason))



if __name__ == '__main__':

   import asyncio

   factory = WebSocketServerFactory("ws://localhost:9000", debug = False)
   factory.protocol = CANServer

   loop = asyncio.get_event_loop()
   coro = loop.create_server(factory, '127.0.0.1', 9000)
   server = loop.run_until_complete(coro)

   try:
      loop.run_forever()
   except KeyboardInterrupt:
      pass
   finally:
      server.close()
      loop.close()
