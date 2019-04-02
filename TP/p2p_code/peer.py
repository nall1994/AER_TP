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
        self.max_ttl = 3
        self.known_peers = []
    
    # Função que gere o funcionamento de um Peer
    def peer_manager(self):
        #Gerenciar as tarefas do peer
        self.IP = socket.gethostbyname(socket.gethostname())
        print(self.IP)
        self.connect()
        cml_thread = Thread(target=self.connection_maintainer_listener)
        lc_thread = Thread(target=self.listen_connections)
        mc_thread = Thread(target=self.maintain_connection)
        lc_thread.start()
        mc_thread.start()
        cml_thread.start()

    # Função de conexão de um peer a 3 known_peers
    def connect(self):
        # NÃO ESTÁ A FAZER OS TTLS TODOS. SÓ FAZ PARA OS VIZINHOS
        for i in range(1,self.max_ttl + 1):
            # Criar uma socket e enviar pedido de conexão para os vizinhos a distância i
            sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
            sock.setsockopt(socket.IPPROTO_IP,socket.IP_MULTICAST_TTL,i)
            sock.sendto("P2PConnectionMANET".encode('utf8'),(self.MCAST_GROUP,self.MCAST_PORT))
            # Iniciar o ciclo para escuta de respostas
            receiving_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
            receiving_socket.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)   
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
                        if not self.belongs(address[0]):
                            self.known_peers.append(address[0])
                        for x in range(1,len(parts)):
                            self.known_peers.append(parts[x]) #coletar IPS de outros peers conhecidos
                        if self.peers_connected == self.needed_peers:
                            break
                except socket.timeout:
                    break
            if self.peers_connected == self.needed_peers:
                break
        self.connections = {}
        sock.close()
        receiving_socket.close()
        for kp in self.known_peers:
            self.connections[kp] = {'alive':True, 'tries': 0}

    #Função que escuta por mensagens de avaliação de conexão e responde conforme.
    def connection_maintainer_listener(self):
        recv_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
        recv_socket.settimeout(0.5)
        recv_socket.bind(('',10003))
        checked = dict()
        while(True):
            sleep(5)
            try:
                for kp in self.known_peers:
                    checked[kp] = False
                message,address = recv_socket.recvfrom(4096)
                if message.decode('utf8') == "ALIVE":
                    print('ALIVE message received from: ' + str(address[0]))
                    checked[address[0]] = True
                    self.connections[address[0]]["alive"] = True
                    self.connections[address[0]]["tries"] = 0

            except socket.timeout:
                for kp in self.known_peers:
                    if not checked[kp]:
                        self.connections[kp]["tries"] += 1
                        if self.connections[kp]["tries"] == 3:
                            print ("Disconnecting peer: " + str(kp))
                            del self.connections[kp]
                            del self.known_peers[kp]
                            del checked[kp]
        
                if len(self.known_peers) < self.needed_peers:
                    self.connect()
                

    #Função que, periodicamente, troca mensagens com os seus known_peers com o objetivo de avaliar o estado da sua ligação
    def maintain_connection(self):
        # Alterar a forma de manutenção da conexão:
        # Nesta fase, cada peer também deve enviar informação atualizada dos ficheiros que tem e conhece.
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
                    self.connections[known_peer]["alive"] = False
                    sock.sendto("ALIVE".encode('utf8'),(known_peer,10003))
            finally:
                lock.release()
            '''
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
            '''

    #Função que verifica se a conexão está bem estabelecida
    def connection_checker(self):
        ok = True
        lock = Lock()
        lock.acquire()
        try:
            i = self.connections.items()
            for key,value in i:
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
        # Os ficheiros devem ser inseridos na rede pelo peer. Nesta fase podemos inserir manualmente os nomes.
        # escutar por pedidos de ficheiro e enviá-los se os tiver. responder com o endereço que o tem se conhecer.
        # Responder que não conhece caso não tenha conhecimento (ou não responder de todo).
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
                    self.connections[add_sp] = {'alive':True, 'tries':0}

    def belongs(self,address):
        ok = False
        for kp in self.known_peers:
            if kp == address:
                ok = True
        if address == self.IP: ok = True
        return ok
    #Função que deverá pedir um ficheiro para download ao peer respetivo
    def request_files(self):
        # Pedir um conteúdo por nome. Consultar a tabela que é mantida para verificar se este peer sabe quem possui esse ficheiro.
        # Se não conhecer , enviar mensagem multicast com pedido de endereço para o ficheiro
        return ''