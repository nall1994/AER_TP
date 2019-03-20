import socket

def receive_connections():
    MCAST_GROUP = '224.0.2.15'
    MCAST_PORT = 10000
    sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    sock.bind((MCAST_GROUP,MCAST_PORT))

    while True:
        message = sock.recv(1024).decode('utf8')
        if(message == "P2PConnectionMANET"):
            print(message)
            # Antes de enviar teria que consultar para ver se podia mandar mais IPS de Peers conhecidos para ficar em cache
            sock.sendto(("ConnectionOK;").encode('utf8'),(MCAST_GROUP,MCAST_PORT))

receive_connections()