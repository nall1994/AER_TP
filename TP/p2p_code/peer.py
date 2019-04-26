import socket
import struct
import sys
import json
import os
from time import sleep
from threading import Thread
from threading import Lock
#from pathlib import Path

class Peer:

    def __init__(self):
        self.MCAST_GROUP = '224.0.2.15'
        self.MCAST_PORT = 10000
        self.peers_connected = 0
        self.needed_peers = 3
        self.max_ttl = 3
        self.out = False
        self.known_peers = []
        self.connections = {}
        self.connection_maintainer = dict()
        self.files = dict() # file_name -> file_path
        self.temporary_updater = []
        self.updated_files = False
        self.interests_table = dict()
        self.routing_table = dict()
    
    # Função que gere o funcionamento de um Peer
    def peer_manager(self):
        #Gerenciar as tarefas do peer
        self.IP = socket.gethostbyname(socket.gethostname())
        self.connect()
        mainmenu_thread = Thread(target=self.mainmenu)
        cml_thread = Thread(target=self.connection_maintainer_listener)
        lc_thread = Thread(target=self.listen_connections)
        mc_thread = Thread(target=self.maintain_connection)
        cchecker_thread = Thread(target=self.connection_checker)
        files_thread = Thread(target=self.files_updater)
        listen_files_thread = Thread(target=self.listen_file_requests)
        lc_thread.start()
        mc_thread.start()
        cml_thread.start()
        cchecker_thread.start()
        files_thread.start()
        listen_files_thread.start()
        try:
            mainmenu_thread.start()
            while(True):
                if self.out:
                    raise SystemExit()
        except SystemExit:
            lc_thread._stop()
            mc_thread._stop()
            cml_thread._stop()
            cchecker_thread._stop()
            files_thread._stop()
            listen_files_thread._stop()
            mainmenu_thread._stop()
            sys.exit("Manually exiting P2P network.")

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
                    if(parts[0] == 'ConnectionOK'):
                        self.peers_connected = self.peers_connected + 1
                        if not self.belongs(address[0]):
                            self.known_peers.append(address[0])
                            self.connection_maintainer[address[0]] = []
                            self.connections[address[0]] = {'alive':True, 'tries': 0}
                        if self.peers_connected == self.needed_peers:
                            break
                except socket.timeout:
                    break
            if self.peers_connected == self.needed_peers:
                break
        sock.close()
        receiving_socket.close()

    def connection_checker(self):
        while True:
            sleep(5)
            for kp in self.known_peers:
                messages = self.connection_maintainer[kp]
                if len(messages) > 0:
                    if messages[0] == 'ALIVE':
                        del messages[0]
                        self.connection_maintainer[kp] = messages
                        self.connections[kp]['tries'] = 0
                else:
                    self.connections[kp]['tries'] += 1
                    if self.connections[kp]['tries'] == 3:
                        self.deleteKnownPeer(kp)
            if len(self.known_peers) < self.needed_peers:
                self.connect()
    #Função que escuta por mensagens de avaliação de conexão e responde conforme.
    def connection_maintainer_listener(self):
        recv_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
        recv_socket.bind(('',10003))
        while(True):
            message,address = recv_socket.recvfrom(4096)
            message = message.decode('utf8')
            message = message.split(';')
            if message[0] == "ALIVE":
            # As restantes componentes recebidas na mensagem alive serão atualizações de ficheiros.
                self.connection_maintainer[address[0]].append(message[0])

    def deleteKnownPeer(self,kp):
        for i in range(0,len(self.known_peers)):
            if self.known_peers[i] == kp:
                del self.known_peers[i]
                del self.connections[kp]
                del self.connection_maintainer[kp]
                break

    #Função que, periodicamente, troca mensagens com os seus known_peers com o objetivo de avaliar o estado da sua ligação
    def maintain_connection(self):
        # Alterar a forma de manutenção da conexão:
        # Nesta fase, cada peer também deve enviar informação atualizada dos ficheiros que tem e conhece.
        while(True): 
            sleep(5)
            if len(self.known_peers) < 3: self.connect()   
            sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
            lock = Lock()
            lock.acquire()
            try:
                for known_peer in self.known_peers:
                    self.connections[known_peer]["alive"] = False
                    sock.sendto("ALIVE".encode('utf8'),(known_peer,10003))
            finally:
                lock.release()

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
                add_sp = address[0]
                if not self.belongs(add_sp):
                    sending_socket.sendto("ConnectionOK".encode('utf8'),(add_sp,10002))
                    self.known_peers.append(add_sp)
                    self.connection_maintainer[add_sp] = []
                    self.connections[add_sp] = {'alive':True, 'tries':0}

    def belongs(self,address):
        ok = False
        for kp in self.known_peers:
            if kp == address:
                ok = True
        if address == self.IP: ok = True
        return ok

    #Esta poderá ser a função de main_menu do peer.
    def mainmenu(self):
        # Deverá poder ver os peers a que está conectado.
        # Informação alive e tries.
        # Ficheiros que pode pedir.
        # Ficheiros que pode enviar.
        switcher = {
            1: self.conn_peers,
            2: self.conn_info,
            3: self.known_files,
            4: self.file_request,
            5: self.file_submit,
            6: self.p2p_exit
        }
        while(True):
            print("\n")
            print("----- MENU -----\n")
            print("1 --- Check connected peers.")
            print("2 --- Check connections information.")
            print("3 --- Check known files.")
            print("4 --- Request for file.")
            print("5 --- Submit file to network.")
            print("6 --- Disconnect from P2P network.\n")
            escolha = input("Choose your option: ")
            try:
                escolha = int(escolha)
                if escolha < 1 or escolha > 6:
                    print("\n")
                    print("The choice has to be a number from 1 to 6.")
                else:
                    print("\n")
                    function_to_execute = switcher.get(escolha,None)
                    function_to_execute()
            except ValueError:
                print("\n")
                print("The choice has to be a number from 1 to 6.")
            except SystemExit:
                break
    
    def conn_peers(self):
        print("- KNOWN PEERS -")
        for i in range(0,len(self.known_peers)):
            print(str(i+1) + ": " + str(self.known_peers[i]))

    
    def conn_info(self):
        print("- CONNECTIONS INFORMATION -")
        for i in range(0,len(self.known_peers)):
            print("PEER " + str(self.known_peers[i]) + ":")
            if self.connections[self.known_peers[i]]["tries"] < 3:
                print("\t Alive -> YES;")
            else:
                print("\t Alive -> NO. DISCONNECTING.;")
            print("\t Alive Messages Failed -> " + str(self.connections[self.known_peers[i]]["tries"]) + ".")
            print("\n")
    
    def known_files(self):
        # Esta função apenas apresenta os ficheiros conhecidos na consola.
        print("CONTENT  -->  PEER")
        for key,value in self.routing_table.items():
            print(key + "  -->  " + value)
    
    def update_files(self,message,peer):
        update = message["content"]
        files_array = update.split(";")
        for file in files_array:
            temp = self.routing_table.get(file)
            if temp == None or temp != 'self':
                self.routing_table[file] = peer
    
    def files_updater(self):
        # Função que verifica de 5 em 5 segundos se existem atualizacoes de ficheiros a enviar aos known_peers.
        while(True):
            sleep(5)
            if self.updated_files :
                sending_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
                update = ""
                for i in range(0,len(self.temporary_updater)):
                    file_path = self.temporary_updater[i]
                    file_parts = file_path.split("/")
                    file_name = file_parts[len(file_parts) - 1]
                    self.files[file_name] = file_path
                    if i == len(self.temporary_updater) - 1:
                        update += file_name
                    else:
                        update += file_name + ";"
                self.temporary_updater = []
                message = {
                    "type" : "FILE_UPDATE",
                    "content": update
                }
                message = json.dumps(message).encode('utf8')
                for kp in self.known_peers:
                    sending_socket.sendto(message,(kp,10004))
                self.updated_files = False



    def file_request(self):
        nome_ficheiro = input("Introduza o nome do ficheiro que pretende:")
        message = {
            "type": "FILE_REQUEST",
            "file_name": nome_ficheiro
        }
        message = json.dumps(message).encode('utf8')
        sending_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
        routing_info = self.routing_table.get(nome_ficheiro)
        self.interests_table[nome_ficheiro] = 'self'
        if routing_info != None:
            sending_socket.sendto(message,(routing_info,10004))
        else:
            for kp in self.known_peers:
                sending_socket.sendto(message,(kp,10004))
    
    def send_file(self,message):
        # Alterar a interests_table para permitir mais que um peer com interesse no ficheiro (array ligado À chave)
        # O peer na posição 0 do array é o mais antigo e , logo, o primeiro a responder.
        interest = self.interests_table.get(message["file_name"])
        if interest != None:
            del self.interests_table[message["file_name"]]
            message = json.dumps(message).encode('utf8')
            sending_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
            sending_socket.sendto(message,(interest,10004))
        else:
            print('File not sent! There is no longer an interest in that file!')    
    
    def listen_file_requests(self):
        # Escutar por pedidos e respostas de ficheiro na porta 10004
        recv_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
        recv_socket.bind(('',10004))
        while True:
            message,address = recv_socket.recvfrom(1000000)
            message = json.loads(message.decode('utf8'))
            if message["type"] == 'FILE_REQUEST':
                requested_file = message["file_name"]
                routing_info = self.routing_table.get(requested_file)
                if routing_info == 'self':
                    # ler dados do ficheiro : self.files[requested_file] é o path para o ficheiro
                    content_file = open(self.files[requested_file],"r")
                    content = content_file.read()
                    message = {
                        "type": "FILE_RESPONSE",
                        "file_name": requested_file,
                        "content": content
                    }
                    content_file.close()
                    self.interests_table[requested_file] = address[0]
                    self.send_file(message)
                elif routing_info == None :
                    self.interests_table[message["file_name"]] = address[0]
                    sending_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
                    message_to_send = {
                        "type": "FILE_REQUEST",
                        "file_name": requested_file
                    }
                    message_to_send = json.dumps(message_to_send).encode('utf8')
                    for kp in self.known_peers:
                        if not kp == address[0]:
                            sending_socket.sendto(message_to_send,(kp,10004))
                else:
                    sending_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
                    self.interests_table[message["file_name"]] = address[0]
                    message_to_send = {
                        "type": "FILE_REQUEST",
                        "file_name": requested_file
                    }
                    message_to_send = json.dumps(message_to_send).encode('utf8')
                    sending_socket.sendto(message_to_send,(routing_info,10004))
            elif message["type"] == 'FILE_RESPONSE':
                interest = self.interests_table.get(message["file_name"])
                if interest == 'self':
                    if not(os.path.exists('downloaded_files')):
                        os.mkdir('downloaded_files')
                    file_path = "downloaded_files/" + message["file_name"]
                    file = open(file_path, "w")
                    file.write(message["content"])
                    file.close()
                    print('Ficheiro guardado com sucesso em: ' + file_path)
                    del self.interests_table[message["file_name"]]
                elif interest != None:
                    sending_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
                    message = json.dumps(message).encode('utf8')
                    del self.interests_table[requested_file]
                    sending_socket.sendto(message,(interest,10004))
            elif message["type"] == "FILE_UPDATE":
                peer = address[0]
                self.update_files(message,peer)
            else:
                pass

    def file_submit(self):
        try:
            file_path = input("Insira o caminho até ao ficheiro que pretende submeter para a rede P2P:")
            #file = Path(file_path)
            #if file.is_file():
            self.temporary_updater.append(file_path)
            self.updated_files = True
            file_parts = file_path.split('/')
            file_name = file_parts[len(file_parts) - 1]
            self.routing_table[file_name] = 'self'
            #else:
            #    print('O caminho que inseriu não indica um ficheiro!')
        except EOFError:
            pass
        # Ao submeter o ficheiro, deve ser acrescentado ao array files, que são os ficheiros deste peer.
        # A flag updated_files deve ser posta a True para que a thread files_updater envie essa info aos known_peers.

    def p2p_exit(self):
        self.out = True
        raise SystemExit()