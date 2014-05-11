from autobahn.asyncio.websocket import WebSocketServerProtocol, \
                                       WebSocketServerFactory
import cobs
import threading
import argparse
import sys

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
        
class InterfaceC3Telemetry(threading.Thread):
	def __init__(self, _filename):
		threading.Thread.__init__(self)
		self.filename = _filename
		self.packetizer = CANPacketizer()
	def run(self):
		self.end_thread = False
		self.ser = serial.Serial(self.filename, 115200, timeout=1)
		while 1:
			if self.end_thread == True:
				break
			try:
				byte = None
				bytes = []
				while byte != '\x00':
					byte = self.ser.read(1)
					bytes.append(byte)
				stream = ''.join(bytes)
				packet = self.packetizer.decode(stream)
				packet.time = time.time()
				new_packet(packet)
			except DecodeError as e:
				print "malformed C3 packet at time",e, packet.time,''.join( [ "%02X " % ord( x ) for x in stream ] ).strip()
				continue
			except:
				continue
	def send(self, packet):
		encoded = self.packetizer.encode(packet)
		self.ser.write(encoded)
	def stop(self):
		self.end_thread = True

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
   
    argparser = argparse.ArgumentParser(description='''
	    can-websockets is a telemetry server that takes data from a serial
	    port or log file, and presents it va a HTTP and JSON API.
	    It also can log packets to disk.
	    ''')
    argparser.add_argument('-f', '--file', help='input log or serial port name')
    argparser.add_argument('-i', '--interface', help='''CAN interface type,
	    use `-i list` to get supported types''')
    argparser.add_argument('-b', '--browser', help='''Open web browser
	    with URL of this server''', action='store_true')
    argparser.add_argument('-l', '--log', help='Write to specified log file')
	
    args = argparser.parse_args()
    if args.interface == 'list':
	    print '''Supported interface types:
	    c3telem\tCentaurus 3 live telemetry'''
	    sys.exit()
	
    if args.log != None:
	    logger = Logger(args.log)

    print 'Type `can-websockets.py --help` for usage information.'


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
