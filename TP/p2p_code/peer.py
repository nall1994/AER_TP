import socket
import struct
import sys
import json
import os
from time import sleep
from threading import Thread
from threading import Lock
import random
import string

class Peer:

    def __init__(self):
        self.MCAST_GROUP = '224.0.2.15' # Endereço do grupo multicast para onde são enviados e de onde são recebidos pedidos de conexão.
        self.MCAST_PORT = 10000 # Porta de escuta de pedidos de conexão.
        self.peers_connected = 0 # peers conetados com este peer atualmente.
        self.needed_peers = 3 # peers necessários/adequados para manter conexão na rede P2P.
        self.max_ttl = 3 # ttl máximo para envio da mensagem de conexão.
        self.out = False # Variável de indicação para saber se é para terminar ou não o funcionamento do peer.
        self.known_peers = [] # peers conhecidos/conetados.
        self.connections = dict() # known_peer -> connection info
        self.connection_maintainer = dict() # known_peer -> alive_messages_received
        self.files = dict() # file_name -> file_path
        self.temporary_updater = [] # Array que guarda atualizações de ficheiros que devem ficar definitivas na próxima iteração.
        self.updated_files = False # Variável que indica se é necessário mandar atualizações de ficheiros ou não.
        self.interests_table = dict() # file_name -> interested_peer
        self.routing_table = dict() # file_name -> peer_to_ask
        self.pending_transfers = dict() # peer_to_transfer -> message
    
    # Função que gere o funcionamento de um Peer
    def peer_manager(self):
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
        for i in range(1,self.max_ttl + 1):
            sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
            sock.setsockopt(socket.IPPROTO_IP,socket.IP_MULTICAST_TTL,i)
            sock.sendto("P2PConnectionMANET".encode('utf8'),(self.MCAST_GROUP,self.MCAST_PORT))
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

    # Função que verifica a conexão atual com os seus peers.
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
                known_peer = self.connections.get(kp)
                if known_peer == None:
                    pass
                elif self.connections[kp]['tries'] == 0 or self.connections[kp]['tries'] == 1:
                    peer_pending_transfers = self.pending_transfers.get(kp)
                    if not peer_pending_transfers == None:
                        sending_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
                        for transfer in peer_pending_transfers:
                            sending_socket.sendto(transfer,(kp,10004))

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
                self.connection_maintainer[address[0]].append(message[0])

    # Função que apaga um peer dos peers conectados
    def deleteKnownPeer(self,kp):
        for i in range(0,len(self.known_peers)):
            if self.known_peers[i] == kp:
                del self.known_peers[i]
                del self.connections[kp]
                del self.connection_maintainer[kp]
                break

    #Função que, periodicamente, troca mensagens com os seus known_peers com o objetivo de avaliar o estado da sua ligação
    def maintain_connection(self):
        while(True): 
            sleep(5)
            if len(self.known_peers) < self.needed_peers: self.connect()   
            sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
            lock = Lock()
            lock.acquire()
            try:
                for known_peer in self.known_peers:
                    self.connections[known_peer]["alive"] = False
                    sock.sendto("ALIVE".encode('utf8'),(known_peer,10003))
            finally:
                lock.release()

    # Função que escuta por pedidos de conexão na rede P2P
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

    # Função que verifica se um dado endereço já pertence aos peers conectados.
    def belongs(self,address):
        ok = False
        for kp in self.known_peers:
            if kp == address:
                ok = True
        if address == self.IP: ok = True
        return ok

    #Esta poderá ser a função de main_menu do peer.
    def mainmenu(self):
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
    
    # Função de extracção do conhecimento sobre os peers conectados
    def conn_peers(self):
        print("- KNOWN PEERS -")
        for i in range(0,len(self.known_peers)):
            print(str(i+1) + ": " + str(self.known_peers[i]))

    # Função de extracção do conhecimento de informação sobre as conexões
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
    
    # Função de extracção de conhecimento dos ficheiros conhecidos e impressão na consola.
    def known_files(self):
        print("CONTENT  -->  PEER")
        for key,value in self.routing_table.items():
            print(key + "  -->  " + value)
    
    # Função de atualização do conhecimento de ficheiros, localmente.
    def update_files(self,message,peer):
        update = message["content"]
        files_array = update.split(";")
        for file in files_array:
            temp = self.routing_table.get(file)
            if temp == None or temp != 'self':
                self.routing_table[file] = peer
    
    # Função de envio de atualizações de ficheiros
    def files_updater(self):
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


    # Pedir um ficheiro à rede P2P
    def file_request(self):
        nome_ficheiro = input("Introduza o nome do ficheiro que pretende:")
        message_id = self.random_id()
        message = {
            "type": "FILE_REQUEST",
            "file_name": nome_ficheiro,
            "mid": message_id,
            "flooding_counter" : "0"
        }
        message = json.dumps(message).encode('utf8')
        sending_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
        routing_info = self.routing_table.get(nome_ficheiro)
        self.add_interest(nome_ficheiro,'self')
        if routing_info != None:
            sending_socket.sendto(message,(routing_info,10004))
        else:
            for kp in self.known_peers:
                sending_socket.sendto(message,(kp,10004))
    
    # Enviar um ficheiro que foi pedido.
    def send_file(self,message,recv_socket):
        interest = self.get_first_interest(message["file_name"])
        if interest != None:
            self.delete_first_interest(message["file_name"])
            message = json.dumps(message).encode('utf8')
            sending_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
            sending_socket.sendto(message,(interest,10004))
            recv_socket.settimeout(0.5)
            try:
                confirmation_message,address = recv_socket.recvfrom(4096)
                confirmation_message = json.loads(confirmation_message.decode('utf8'))
                message = json.loads(message.decode('utf8'))
                mid = message["mid"]
                coming_mid = confirmation_message["mid"]
                if mid == coming_mid and confirmation_message["type"] == "CONFIRMATION":
                    recv_socket.settimeout(None)
            except socket.timeout:
                recv_socket.settimeout(None)
                self.add_pending_transfer(interest,message)
        else:
            print('File not sent! There is no longer an interest in that file!')    
    
    # Adicionar uma transferência pendente
    def add_pending_transfer(self,peer,message):
        peer_array = self.pending_transfers.get(peer)
        if peer_array == None:
            arr = []
            arr.append(message)
            self.pending_transfers[peer] = arr
        else:
            peer_array.append(message)
            self.pending_transfers[peer] = peer_array
    
    # Apagar uma transferência pendente.
    def delete_pending_transfer(self,peer,message_id):
        peer_transfers_array = self.pending_transfers.get(peer)
        if peer_transfers_array == None:
            pass
        else:
            for i in range(0,len(peer_transfers_array)):
                msg = json.loads(peer_transfers_array[i].decode('utf8'))
                if msg["mid"] == message_id:
                    del peer_transfers_array[i]
                    self.pending_transfers[peer] = peer_transfers_array

    # ouvir por pedidos, respostas, atualizações e informações de ficheiros.
    def listen_file_requests(self):
        # Escutar por pedidos e respostas de ficheiro na porta 10004
        confirmation_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
        recv_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
        recv_socket.bind(('',10004))
        while True:
            message,address = recv_socket.recvfrom(1000000)
            message = json.loads(message.decode('utf8'))
            message_id = message.get("mid")
            if message["type"] == "CONFIRMATION":
                peer = address[0]
                message_id = message["mid"]
                self.delete_pending_transfer(peer,message_id)
            else:
                confirmation = {
                    "type" : "CONFIRMATION",
                    "mid": message_id
                }
                confirmation = json.dumps(confirmation).encode('utf8')
                confirmation_socket.sendto(confirmation,(address[0],10004))
                if message["type"] == 'FILE_REQUEST':
                    requested_file = message["file_name"]
                    routing_info = self.routing_table.get(requested_file)
                    if routing_info == 'self':
                        if os.path.isfile(self.files[requested_file]):
                            content_file = open(self.files[requested_file],"r")
                            content = content_file.read()
                            message = {
                                "type": "FILE_RESPONSE",
                                "file_name": requested_file,
                                "mid": message_id,
                                "content": content
                            }
                            content_file.close()
                            self.add_interest(requested_file,address[0])
                            self.send_file(message,recv_socket)
                        else:
                            # Enviar mensagem INFORM a dizer que este peer já não possui o ficheiro
                            # Ou secalhar pedir o ficheiro aos outros known_peers.
                            # Atualizar as routing tables de todos os peers quando isto acontece.
                            # A mensagem é do tipo FILE_INFORM
                            # Mas se tiver uma mensagem do tipo = "FILE_NON_EXISTENT" devem ser informados os peers para retirarem da routing table a associação.
                            message_to_send = {
                                "type" : "FILE_INFORM",
                                "mid" : message_id,
                                "file_name" : requested_file,
                                "message" : "FILE_NON_EXISTENT"
                            }
                            message_to_send = json.dumps(message_to_send).encode('utf8')
                            sending_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
                            sending_socket.sendto(message_to_send,(address[0],10004))
                    elif routing_info == None :
                        flooding_counter = int(message["flooding_counter"])
                        if flooding_counter < 5:
                            self.add_interest(requested_file,address[0])
                            sending_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
                            flooding_counter += 1
                            message_to_send = {
                                "type": "FILE_REQUEST",
                                "mid": message_id,
                                "file_name": requested_file,
                                "flooding_counter": str(flooding_counter)
                            }
                            message_to_send = json.dumps(message_to_send).encode('utf8')
                            for kp in self.known_peers:
                                if not kp == address[0]:
                                    sending_socket.sendto(message_to_send,(kp,10004))
                        else:
                            message_to_send = {
                                "type" : "FILE_INFORM",
                                "mid" : message_id,
                                "file_name" : requested_file,
                                "message" : "File could not be found in the network!"
                            }
                            sending_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
                            message_to_send = json.dumps(message_to_send).encode('utf8')
                            sending_socket.sendto(message_to_send,(address[0],10004))

                    else:
                        sending_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
                        self.add_interest(requested_file,address[0])
                        message_to_send = {
                            "type": "FILE_REQUEST",
                            "mid": message_id,
                            "file_name": requested_file
                        }
                        message_to_send = json.dumps(message_to_send).encode('utf8')
                        sending_socket.sendto(message_to_send,(routing_info,10004))
                        recv_socket.settimeout(0.5)
                        try:
                            confirmation_message,address = recv_socket.recvfrom(4096)
                            confirmation_message = json.loads(confirmation_message.decode('utf8'))
                            if confirmation_message["mid"] == message_id and confirmation_message["type"] == "CONFIRMATION":
                                recv_socket.settimeout(None)
                        except socket.timeout:
                            recv_socket.settimeout(None)
                            self.add_pending_transfer(routing_info,message_to_send)
                elif message["type"] == 'FILE_RESPONSE':
                    requested_file = message["file_name"]
                    interest = self.get_first_interest(requested_file)
                    if interest == 'self':
                        if not(os.path.exists('downloaded_files')):
                            os.mkdir('downloaded_files')
                        file_path = "downloaded_files/" + requested_file
                        file = open(file_path, "w")
                        file.write(message["content"])
                        file.close()
                        print('Ficheiro guardado com sucesso em: ' + file_path)
                        self.delete_first_interest(requested_file)
                    elif interest != None:
                        sending_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
                        message = json.dumps(message).encode('utf8')
                        self.delete_first_interest(requested_file)
                        sending_socket.sendto(message,(interest,10004))
                        try:
                            recv_socket.settimeout(0.5)
                            confirmation_message,address = recv_socket.recvfrom(4096)
                            confirmation_message = json.loads(confirmation_message.decode('utf8'))
                            if confirmation_message["mid"] == message_id and confirmation_message["type"] == "CONFIRMATION":
                                recv_socket.settimeout(None)
                        except socket.timeout:
                            recv_socket.settimeout(None)
                            self.add_pending_transfer(interest,message)
                elif message["type"] == "FILE_UPDATE":
                    peer = address[0]
                    self.update_files(message,peer)
                elif message["type"] == "FILE_INFORM":
                    peer = self.interests_table["file_name"][0]
                    if peer == 'self':
                        if message["message"] == "FILE_NON_EXISTENT":
                            print('O ficheiro já não se encontra no mesmo peer que estava.')
                            del self.routing_table[message["file_name"]]
                            del self.interests_table[message["file_name"]][0]
                        else:
                            del self.interests_table[message["file_name"]][0]
                            print(message["message"])
                    else:
                        if message["message"] == "FILE_NON_EXISTENT":
                            del self.routing_table[message["file_name"]]
                        del self.interests_table["file_name"][0]
                        sending_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
                        message = json.dumps(message).encode('utf8')
                        sending_socket.send(message,(peer,10004))
                else:
                    pass

    # Submeter um ficheiro para a rede P2P
    def file_submit(self):
        try:
            file_path = input("Insira o caminho até ao ficheiro que pretende submeter para a rede P2P:")
            if os.path.isfile(file_path):
                self.temporary_updater.append(file_path)
                self.updated_files = True
                file_parts = file_path.split('/')
                file_name = file_parts[len(file_parts) - 1]
                self.routing_table[file_name] = 'self'
            else:
                print('O caminho que inseriu não indica um ficheiro!')
        except EOFError:
            pass
    
    # Geração da message_id
    def random_id(self):
        letters = string.ascii_letters
        return ''.join(random.choice(letters) for i in range(16))

    # Apagar o primeiro interesse da tabela.
    def delete_first_interest(self,file_name):
        assoc_array = self.interests_table.get(file_name)
        del assoc_array[0]
        if len(assoc_array) > 0:
            self.interests_table[file_name] = assoc_array
        else:
            del self.interests_table[file_name]
    
    # Coletar o interesse mais antigo existente na tabela
    def get_first_interest(self,file_name):
        assoc_array = self.interests_table.get(file_name)
        if assoc_array == None:
            return None
        else:
            return assoc_array[0]

    # Adicionar um interesse à tabela
    def add_interest(self,file_name,peer):
        assoc_array = self.interests_table.get(file_name)
        if assoc_array == None:
            arr = []
            arr.append(peer)
            self.interests_table[file_name] = arr
        else:
            assoc_array.append(peer)
            self.interests_table[file_name] = assoc_array

    # Sair da rede Peer to Peer.
    def p2p_exit(self):
        self.out = True
        raise SystemExit()