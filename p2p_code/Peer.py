import threading
import socket
import struct

class Peer:

    def __init__(self):
        self.MCAST_GROUP = '224.0.2.15'
        self.MCAST_PORT = 10000
        self.peers_connected = 0
        self.needed_peers = 3
        self.max_ttl = 5
        self.known_peers = []
    
    def peer_manager(self):
        #Gerenciar as tarefas do peer
        self.connect()

    
    def connect(self):
        for i in range(1,self.max_ttl + 1):
            # Criar uma socket e enviar pedido de conexão para os vizinhos a distância i
            sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
            sock.setsockopt(socket.IPPROTO_IP,socket.IP_MULTICAST_TTL,i)
            sock.sendto("P2PConnectionMANET".encode('utf8'),(self.MCAST_GROUP,self.MCAST_PORT))
            out_ttl = False
            # Iniciar o ciclo para escuta de respostas
            while self.peers_connected < self.needed_peers:
                receiving_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)   
                receiving_socket.settimeout(0.1*i) #timeout de 100ms multiplicado pelo ttl atual
                receiving_socket.bind(('',self.MCAST_PORT))
                group = socket.inet_aton(self.MCAST_GROUP)
                mreq = struct.pack('4sL',group,socket.INADDR_ANY)
                receiving_socket.setsockopt(socket.IPPROTO_IP,socket.IP_ADD_MEMBERSHIP,mreq)

                while(True):
                    try:
                        message, address = receiving_socket.recvfrom(4096)
                        msg = message.decode('utf8')
                        parts = msg.split(';')
                        if(parts[0] == 'ConnectionOK'):
                            self.peers_connected = self.peers_connected + 1
                            self.known_peers.append(address[0]) #coletar o IP de quem enviou a resposta
                            #Esta parte de coleta de ips conhecidos de quem enviou será necessária??
                            for x in range(1,len(parts)):
                                self.known_peers.append(parts[x]) #coletar IPS de outros peers conhecidos
                            if self.peers_connected == self.needed_peers:
                                out_ttl = True
                                break
                    except socket.timeout:
                        out_ttl = True
                        break
                if out_ttl: break
            if self.peers_connected == self.needed_peers:
                break
        self.connections = {}
        for kp in self.known_peers:
            self.connections[kp] = True


    def connection_maintainer_listener(self):
        recv_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
        recv_socket.bind('',10002)
        while(True):
            message,address = recv_socket.recvfrom(4096)
            if message.decode('utf8') == "ALIVE":
                send_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
                send_socket.sendto("YES".encode('utf8'),(address[0],10001))

    def maintain_connection(self):

        # Esta parte de envio de ALIVEs só deve ser feita de x em x segundos
        # Possivelmente terá que ser a sua própria thread??    
        sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
        for known_peer in self.known_peers:
            self.connections[known_peer] = False
            sock.sendto("ALIVE".encode('utf8'),(known_peer,10001))

        #Isto deve estar sempre ativo!
        #Mas quando verificámos se a conexão está correta?
        receiving_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
        receiving_socket.settimeout(0.5)
        receiving_socket.bind(('',10001))
        
        while(True):
            try:
                message, address = receiving_socket.recvfrom(4096)
                msg = message.decode('utf8')
                if msg == "YES":
                    self.connections[address[0]] = True
            except socket.timeout:
                print('verify')
                #chamar função que verifica.
        return ''

    def connection_checker(self):
        ok = True
        for key,value in self.connections.items():
            if not(value):
                ok = False
                # Get peer not connected and regain connection
        if(not(ok)):
            print('not ok')
            #regain connection

    def listen_requests(self):
        return ''

    def listen_connections(self):
        return ''

    def request_files(self):
        return ''

p = Peer()
p.peer_manager()