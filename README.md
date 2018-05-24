# Simple-FTP-Server-and-Client

A small exercise for protocol design and sockets programming.

Language used: Python 2

Server execution:

    python serv.py <port_number>
    python serv.py -t 1 <port_number>     for threaded version
    python serv.py -t 2 <port_number>     for forking version
    
Client execution:

    python cli.py <server_address> <port_number>

Supported commands:

    'get <file name>' downloads file <file name> from the server

    'put <file name>' uploads file <file name> to the server

    'ls' lists files on the server

    'quit' disconnects from the server and exits

    'lls' lists files on the client

    'help' prints the help string
