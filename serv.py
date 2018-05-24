"""serv.py
MUST IMPORT protocol.py
DESCRIPTION:
    Simplified FTP server, which can run as a normal, threading,
    or forking server by setting the -t flag to 0, 1, and 2, respectively.
    
    Supported commands are:
        'get <file name>' downloads file <file name> from the server
        'put <file name>' uploads file <file name> to the server
        'ls' lists files on the server
        'quit' disconnects from the server and closes the client

    Basic Usage:
        python serv.py <port_number>
"""
import argparse
import sys
import socket
import threading
import logging
import os
from os import listdir
from os.path import isfile
from os.path import basename
from os.path import splitext
from protocol import *

class FTPServer(object):
    """FTPServer
    @attribute address: (host, port) pair for the AF_INET family
    @attribute sType: server type; 0 for normal, 1 for threading, 2 for forking
    @attribute logger: Logger object for server messages
    @attribute connSock: socket for accepting client commands
    """
    def __init__(self, port=21, sType=0, logger=None):
        """Constructor
        @param port: port number for the server
        @param sType: server type
        @param logger: Logger object for server messages
        """
        self.address = ('', port)
        self.logger = logger or logging.getLogger(__name__)
        self.connSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sType = sType

        try:
            self.init_socket()
        except socket.error as e:
            self.logger.debug('Failed to connect server to port %s %s', port, e)

    def __del__(self):
        """Deconstructor
        Explicitly closes the connection socket
        """
        # TODO join all threads?
        self.connSock.close()
        self.logger.info('>>>>>>>> SERVER CLOSED <<<<<<<<')
        
    def init_socket(self):
        """Constructs and starts the FTP server
        @raise socket.error
        """
        server_type = {0: 'normal', 1: 'threading', 2: 'forking'}
        self.connSock.bind(self.address)
        self.connSock.listen(1)
        self.logger.info('>>>>> SERVER LISTENING ON PORT %s <<<<<',
                         self.address[1])
        self.logger.debug('Server starting in %s mode', server_type[self.sType])

        try:
            self.start()
        except socket.error as e:
            self.connSock.close()
            raise e

    def start(self):
        """Start running the FTP server
        """
        while True:
            # Begin listening for incoming connections
            clientSock, clientAddr = self.connSock.accept()
            self.logger.info('New client accepted HOST: %s PORT: %s',
                             clientAddr[0], clientAddr[1])

            if self.sType == 1:
                self.logger.debug('New thread created for %s:%s',
                                  clientAddr[0], clientAddr[1])
                threading.Thread(target=self.process_commands,
                                 args=(clientSock, clientAddr)).start()
            elif self.sType == 2:
                pid = os.fork()
                if pid != 0:
                    # Child process listens for new connections
                    # Parent process starts handling commands
                    self.logger.debug('Child process %d was created', pid)
                    self.process_commands(clientSock, clientAddr)
            else:
                self.process_commands(clientSock, clientAddr)

    def process_commands(self, clientSock, clientAddr):
        """Process the client commands
        @param clientSock: client socket
        @param clientAddr: client addr
        """
        while True:
            # Process FTP client commands
            userInput, err = recvAll(clientSock)
            if err:
                self.logger.debug('%s:%s %s', clientAddr[0], clientAddr[1], err)
                break
                
            if userInput != '':
                tokens = userInput.split()
                command = tokens[0].lower()
                msg = '%s:%s\t%s' % (clientAddr[0], clientAddr[1], userInput)
                self.logger.debug('EXECUTE %s', msg)

                if command == 'get' and len(tokens) == 2:
                    self.send_file(tokens[1], clientSock)
                elif command == 'put' and len(tokens) == 2:
                    self.retrieve_file(tokens[1], clientSock)
                elif command == 'ls' and len(tokens) == 1:
                    if self.list_files(clientSock):
                        self.logger.info('SUCCESS %s', msg)
                    else:
                        self.logger.info('FAILURE %s', msg)
                elif command == 'quit':
                    self.logger.info('SUCCESS %s', msg)
                    break
                else:
                    self.logger.info('Unknown command %s', msg)

        clientSock.close()
        if self.sType == 2:
            sys.exit()


    def send_file(self, filename, sock):
        """Send a file to the client in a separate thread
        @param filename: name of sent file from the client
        @param sock: client command socket
        """
        threading.Thread(target=self._send_file, args=(filename, sock, self.logger)).start()

    def _send_file(self, filename, commandSock, logger):
        """Send file over ephermal data socket
        @param filename: name of file sent to send to the client
        @param commandSock: client command socket
        @param logger: Logger object for server messages
        """

        if not isfile(filename):
            sendAll(commandSock, '-1')
            logger.info("FAILURE get failed. '%s' is not a file", filename)
        else:
            # set up the ephermal data socket
            dataSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            dataSock.bind(('', 0))
            dataSock.listen(1)

            cName = commandSock.getsockname()
            dName = dataSock.getsockname()
            sendAll(commandSock, str(dName[1]))
            logger.debug('Opened data socket %s for %s:%s', dName[1], cName[0], cName[1])

            conn, addr = dataSock.accept()
            logger.debug('Connected data socket %s for %s:%s through %s:%s',
                         dName[1], cName[0], cName[1], addr[0], addr[1])

            numSent, err = sendFile(conn, filename)
            if err:
                logger.info("FAILURE did not send all of '%s' to %s:%s",
                            filename, cName[0], dName[1])
            else:
                logger.info("SUCCESS sent '%s' to %s:%s", filename, cName[0], dName[1])

            conn.close()
            logger.debug('Closed data socket %s for %s:%s', dName[1], cName[0], cName[1])

    def retrieve_file(self, filename, sock):
        """Get a file from the client in a separate thread
        @param filename: name of sent file from the client
        @param sock: client command socket
        """
        threading.Thread(target=self._retrieve_file, args=(filename, sock, self.logger)).start()

    def _retrieve_file(self, filename, commandSock, logger):
        """Retrieve file over ephermal data socket
        @param filename: name of file sent from the client
        @param commandSock: client command socket
        @param logger: Logger object for server messages
        """
        # if a file named filename already exists in the current directory,
        # rename the transfer file
        root, ext = splitext(basename(filename))
        tmp = root + ext
        count = 0
        while isfile(tmp):
            count += 1
            tmp = "%s(%d)%s" % (root, count, ext)

        # set up the ephermal data socket
        dataSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        dataSock.bind(('', 0))
        dataSock.listen(1)

        cName = commandSock.getsockname()
        dName = dataSock.getsockname()
        sendAll(commandSock, str(dName[1]))
        logger.debug('Opened data socket %s for %s:%s', dName[1], cName[0], cName[1])

        conn, addr = dataSock.accept()
        logger.debug('Connected data socket %s for %s:%s through %s:%s',
                     dName[1], cName[0], cName[1], addr[0], addr[1])

        numRead, filesize, err = recvFile(tmp, conn)
        if err:
            logger.info("FAILURE did not retrieve all of '%s' from %s:%s",
                        filename, cName[0], dName[1])
        else:
            logger.info("SUCCESS retrieved '%s' from %s:%s and saved as '%s'",
                        filename, cName[0], dName[1], tmp)

        conn.close()
        logger.debug('Closed data socket %s for %s:%s', dName[1], cName[0], cName[1])

    def list_files(self, sock):
        """List the files in the current working directory
        @param sock: client command socket
        @return: True if file list completely sent to client, False otherwise
        """
        files = [f for f in listdir('.') if isfile(f) and f[0] != '.']
        _, err = sendAll(sock, '\n'.join(files))
        if err:
            sockName = sock.getsockname()
            self.logger.debug('%s:%s %s', sockName[0], sockName[1], err)
            return False
        return True

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('port_number', help='server port number', type=int)
    parser.add_argument('-t', help='server type: 0 for normal,  1 for threading, \
                        2 for forking', choices=xrange(0,3), default=0, type=int)
    args = parser.parse_args()
    listenPort = args.port_number
    serverType = args.t

    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s PID:%(process)d %(threadName)s %(message)s',
                        datefmt='%H:%M:%S',
                        filename='server.log')

    # create a console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    logging.getLogger('').addHandler(ch)

    try:
        server = FTPServer(listenPort, serverType, logging.getLogger(''))
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()

