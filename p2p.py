import socket

known_peers = []

def connect():
    MCAST_GROUP = '224.0.0.1'
    MCAST_PORT = 10000
    sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP,socket.IP_MULTICAST_TTL,2)
    sock.sendto("P2PConnectionMANET".encode('utf8'),(MCAST_GROUP,MCAST_PORT))
    sock2 = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
    sock2.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    sock2.bind((MCAST_GROUP,MCAST_PORT))
    message, address = sock2.recvfrom(4000)
    msg = message.decode('utf8')
    parts = msg.split(';')
    if(parts[0] == "ConnectionOK"):
       known_peers.append(address[0])
       for x in range(1,len(parts)):
           known_peers.append(parts[x])

    # Quando finalizada a conexão, este já é peer e tem que iniciar uma thread de escuta por pedidos de conexao.

connect()
for x in known_peers:
    print(x)