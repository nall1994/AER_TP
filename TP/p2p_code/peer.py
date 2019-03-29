import socket
import struct
from time import sleep
from threading import Thread
from threading import Lock

class Peer:

    def __init__(self):
        self.MCAST_GROUP = '224.0.2.15'
        self.MCAST_PORT = 10000
        self.peers_connected = 0
        self.needed_peers = 3
        self.max_ttl = 5
        self.known_peers = []
    
    # Função que gere o funcionamento de um Peer
    def peer_manager(self):
        #Gerenciar as tarefas do peer
        self.IP = socket.gethostbyname(socket.gethostname())
        self.connect()
        cml_thread = Thread(target=self.connection_maintainer_listener)
        lc_thread = Thread(target=self.listen_connections)
        mc_thread = Thread(target=self.maintain_connection)
        lc_thread.start()
        cml_thread.start()
        mc_thread.start()

    # Função de conexão de um peer a 3 known_peers
    def connect(self):
        for i in range(1,self.max_ttl + 1):
            # Criar uma socket e enviar pedido de conexão para os vizinhos a distância i
            sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
            sock.setsockopt(socket.IPPROTO_IP,socket.IP_MULTICAST_TTL,i)
            sock.sendto("P2PConnectionMANET".encode('utf8'),(self.MCAST_GROUP,self.MCAST_PORT))
            out_ttl = False
            all = False
            # Iniciar o ciclo para escuta de respostas
            while self.peers_connected < self.needed_peers:
                receiving_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)   
                receiving_socket.settimeout(0.1*i) #timeout de 100ms multiplicado pelo ttl atual
                receiving_socket.bind(('',10002))

                while(True):
                    try:
                        message, address = receiving_socket.recvfrom(4096)
                        msg = message.decode('utf8')
                        parts = msg.split(';')
                        print(parts[0])
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
                all = True
                break
        self.connections = {}
        sock.close()
        receiving_socket.close()
        for kp in self.known_peers:
            self.connections[kp] = True

    #Função que escuta por mensagens de avaliação de conexão e responde conforme.
    def connection_maintainer_listener(self):
        recv_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
        recv_socket.bind(('',10003))
        while(True):
            message,address = recv_socket.recvfrom(4096)
            if message.decode('utf8') == "ALIVE":
                send_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
                send_socket.sendto("YES".encode('utf8'),(address[0],10004))

    #Função que, periodicamente, troca mensagens com os seus known_peers com o objetivo de avaliar o estado da sua ligação
    def maintain_connection(self):
        while(True): 
            sleep(5)
            print(self.known_peers)
            if len(self.known_peers) < 3: self.connect()   
            sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
            receiving_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
            receiving_socket.settimeout(0.5)
            receiving_socket.bind(('',10004))
            lock = Lock()
            lock.acquire()
            try:
                for known_peer in self.known_peers:
                    self.connections[known_peer] = False
                    sock.sendto("ALIVE".encode('utf8'),(known_peer,10003))
            finally:
                lock.release()
    
            try:
                message, address = receiving_socket.recvfrom(4096)
                msg = message.decode('utf8')
                if msg == "YES":
                    lock.acquire()
                    try:
                        self.connections[address[0]] = True
                    finally:
                        lock.release()
            except socket.timeout:
                if(not(self.connection_checker())):
                    print('regain connection')
                    self.connect()

    #Função que verifica se a conexão está bem estabelecida
    def connection_checker(self):
        ok = True
        lock = Lock()
        lock.acquire()
        try:
            for key,value in self.connections.items():
                if not(value):
                    ok = False
                    self.peers_connected = self.peers_connected - 1
                    del self.connections[key]
        finally:
            lock.release()
        if(not(ok)):
            print('not ok')
            return False
        else: return True

    #Função que escuta por pedidos de ficheiro
    def listen_requests(self):
        return ''

    def listen_connections(self):
        sending_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
        receiving_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
        receiving_socket.bind(('',self.MCAST_PORT))
        group = socket.inet_aton(self.MCAST_GROUP)
        mreq = struct.pack('4sL',group,socket.INADDR_ANY)
        receiving_socket.setsockopt(socket.IPPROTO_IP,socket.IP_ADD_MEMBERSHIP,mreq)
        while(True):
            msg,address = receiving_socket.recvfrom(4096)

            if msg.decode('utf8') == 'P2PConnectionMANET':
                print('Received connection request from:')
                print(address)
                add_sp = address[0]
                if not self.belongs(add_sp):
                    sending_socket.sendto("ConnectionOK".encode('utf8'),(add_sp,10002))
                    self.known_peers.append(add_sp)

    def belongs(self,address):
        ok = False
        for kp in self.known_peers:
            if kp == address:
                ok = True
        if address == self.IP: ok = True
        return ok
    #Função que deverá pedir um ficheiro para download ao peer respetivo
    def request_files(self):
        return ''