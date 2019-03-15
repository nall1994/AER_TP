import socket

def connect():
    MCAST_GROUP = '224.0.2.15'
    MCAST_PORT = 10000
    peers_connected = 0
    for i in range(1,max_ttl+1):
        sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
        sock.setsockopt(socket.IPPROTO_IP,socket.IP_MULTICAST_TTL,i)
        sock.sendto("P2PConnectionMANET".encode('utf8'),(MCAST_GROUP,MCAST_PORT))
        out = False
        while peers_connected < peers_to_stay:
            try:
                sock2 = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
                sock2.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
                sock2.settimeout(0.1*i)
                sock2.bind((MCAST_GROUP,MCAST_PORT))
                message, address = sock2.recvfrom(4000)
                msg = message.decode('utf8')
                parts = msg.split(';')
                if(parts[0] == "ConnectionOK"):
                    peers_connected += 1
                    known_peers.append(address[0])
                    for x in range(1,len(parts)):
                        known_peers.append(parts[x])
                    if peers_connected == peers_to_stay:
                        out = True
            except socket.timeout:
                break
        if out: break

    # Quando finalizada a conexão, este já é peer e tem que iniciar uma thread de escuta por pedidos de conexao.
known_peers = []
peers_to_stay = 3
max_ttl = 5
connect()
for x in known_peers:
    print(x)