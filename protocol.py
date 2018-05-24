"""protocol.py
NOT FOR USE AS A STANDALONE FILE. ASSUMES SOCKET MODULE HAS BEEN IMPORTED
DESCRIPTION:
    Defines the FTP protocol for transferring files between the server
    and client. Implements methods shared between the server and client.

    First MESSAGE_SIZE_PADDING bytes of each message contains the message 
    size and the rest contain the data.
    
    Support commands are:
        'get <file name>' downloads file <file name> from the server
        'put <file name>' uploads file <file name> to the server
        'ls' lists files on the server
        'quit' disconnects from the server
    Additionally on the client side:
        'lls' lists files on the client
        'help' prints the help string

    By default, MESSAGE_SIZE_PADDING = 10.
"""
from os.path import isfile

MESSAGE_SIZE_PADDING = 10
HELP_STRING = """The FTP client accepts the following commands:
\tget <file name> - downloads file <file name> from the server
\tput <file name> - uploads file <file name> to the server
\tls - lists files on the server
\tlls - lists files on the client
\tquit - disconnects and exits"""

def sendAll(sock, data):
    """Send all data through a socket
    @param sock: socket to send through
    @param data: string data to send
    @return (numBytes, error)
        numBytes: number of bytes transferred
        error: None if all data transferred, error message string otherwise
    """
    sizeStr = str(len(data))
    while len(sizeStr) < MESSAGE_SIZE_PADDING:
        sizeStr = '0' + sizeStr

    data = sizeStr + data
    numSent = 0
    while len(data) > numSent:
        sent = sock.send(data[numSent:])
        if sent == 0:
            return (numSent - MESSAGE_SIZE_PADDING, 'socket connection broken')
        numSent += sent

    return (numSent - MESSAGE_SIZE_PADDING, None)

def sendFile(sock, filename):
    """Sends a file through a socket
    @param sock: socket to send through
    @param filename: name of the file to send
    @return (numBytes, error)
        numBytes: number of bytes transferred
        error: None if all data transferred, error message string otherwise
    """
    if not isfile(filename):
        return (0, '{} is not a file'.format(filename))

    try:
        f = open(filename, 'r')
    except IOError:
        return (0, 'Can not read {}'.format(filename))

    data = f.read()
    f.close()
    return sendAll(sock, data)

def recvAll(sock):
    """Receive all data from a socket
    @param sock: socket to receive from
    @return (data, error)
        data: data received
        error: None if all data received, error message string otherwise
    """
    buff = ''
    size = 0

    sizeStr, err = _recvAll(sock, MESSAGE_SIZE_PADDING)
    if err:
        return ('', err)

    try:
        size = int(sizeStr)
    except ValueError:
        return ('', 'FTP protocol does not match, unable to receive data')

    return _recvAll(sock, size)

def _recvAll(sock, num):
    """Receive a specified number of bytes from a socket
    @param sock: socket to receive from
    @param num: number of bytes to receive
    @return (data, error)
        data: data transferred
        error: None if all data received, error message string otherwise
    """
    recvBuff = ''
    tmpBuff = ''

    while len(recvBuff) < num:
        tmpBuff = sock.recv(num)
        if not tmpBuff:
            return (recvBuff, 'socket connection broken')
        recvBuff += tmpBuff

    return (recvBuff, None)

def recvFile(filename, sock):
    """Writes all received data from a socket into a file
    @param filename: name of filen to store the data
    @param sock: socket to receive from
    @return (recievedBytes, expectedBytes, error)
        receivedBytes: number of bytes received
        expectedBytes: file size in bytes
        error: None if all data received, error message string otherwise
    """
    sizeStr, err = _recvAll(sock, MESSAGE_SIZE_PADDING)
    if err:
        return (0, 0, err)

    try:
        size = int(sizeStr)
    except ValueError:
        return (0, 0,'FTP protocol does not match, unable to receive data')

    try:
        f = open(filename, 'w')
    except IOError:
        return (0, 0, 'Can not write to {}'.format(filename))

    recvBytes = 0
    while recvBytes < size:
        tmpBuff = sock.recv(size)
        if not tmpBuff:
            f.close()
            return (recvBytes, size, 'socket connection broken')
        f.write(tmpBuff)
        recvBytes += len(tmpBuff)

    f.close()
    return (recvBytes, size, None)

