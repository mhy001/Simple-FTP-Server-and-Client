"""cli.py
MUST IMPORT protocol.py
DESCRIPTION:
    Simplified FTP client
    
    Supported commands are:
        'get <file name>' downloads file <file name> from the server
        'put <file name>' uploads file <file name> to the server
        'ls' lists files on the server
        'quit' disconnects from the server and exits
    Additionally on the client side:
        'lls' lists files on the client
        'help' prints the help string

    Basic usage:
        python cli.py <server_address> <port_number>
"""
import argparse
import sys
import socket
import subprocess
import threading
from os.path import isfile
from os.path import getsize
from os.path import splitext
from os.path import basename
from protocol import *

class FTPClient(object):
    """FTPClient
    @attribute address: server address, host, port) pair for the AF_INET family
    @attribute commandSock: socket for issuing commands to the server
    """
    def __init__(self, host, port):
        """Constructor
        @param host: FTP server host name or IPv4 address
        @param port: FTP server port number
        @raise RuntimeError
        """
        self.server = (host, port)
        self.commandSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            self.connect_to_server()
        except socket.error as e:
            raise RuntimeError('connection error {}'.format(e))

    def __del__(self):
        """Deconstructor
        Explicitly closes open socket
        """
        self.commandSock.close()

    def connect_to_server(self):
        """Connects to the FTP server
        """
        self.commandSock.connect(self.server)
        self.start()

    def start(self):
        """Start the FTP client
        """
        while True:
            try:
                userInput = raw_input('ftp>')
            except KeyboardInterrupt:
                self.commandSock.close()
                break

            if userInput != '':
                tokens = userInput.split()
                command = tokens[0].lower()

                if command == 'get' and len(tokens) == 2:
                    self.retrieve_file(userInput, tokens[1])
                elif command == 'put' and len(tokens) == 2:
                    if not isfile(tokens[1]):
                        print "'%s' is not a valid file" % tokens[1]
                        continue
                    self.send_file(userInput, tokens[1])
                elif command == 'ls' and len(tokens) == 1:
                    self.list_server_files(userInput)
                elif command == 'lls' and len(tokens) == 1:
                    subprocess.call(['ls', '-1'])
                elif command == 'quit':
                    self.quit(userInput)
                    break
                else:
                    if not command == 'help':
                        print 'Invalid input: %s' % userInput
                    print HELP_STRING

    def retrieve_file(self, command, filename):
        """Get a file from the server
        @param command: user input of type 'get <file name>'
        @param filename: name of file to send
        @raise RuntimeError
        """
        _, err = sendAll(self.commandSock, command)
        if err:
            raise RuntimeError(err)

        dataPortStr, err = recvAll(self.commandSock)
        if err:
            raise RuntimeError(err)

        dataPort = int(dataPortStr)
        if dataPort == -1:
            print "'%s' is not a valid file" % filename
        else:
            threading.Thread(target=self._retrieve_file, args=(dataPort, filename)).start()

    def _retrieve_file(self, dataPort, filename):
        """Get file over ephermal data socket
        @param dataPort: server port for data transfer
        @param filename: name of file to retrieve
        """
        # if a file named filename already exists in the current directory,
        # rename the transfer file
        root, ext = splitext(basename(filename))
        tmp = root + ext
        count = 0
        while isfile(tmp):
            count += 1
            tmp = "%s(%d)%s" % (root, count, ext)

        dataSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        dataSock.connect((self.server[0], dataPort))

        numRead, filesize, err = recvFile(tmp, dataSock)

        print "\rRetrieved %s of %s bytes for '%s' and saved as '%s'" % (numRead, filesize, filename, tmp)
        print 'ftp>',
        sys.stdout.flush()
        dataSock.close()

    def send_file(self, command, filename):
        """Send a file to the server in a separate thread
        @param command: user input of type 'put <file name>'
        @param filename: name of file to send
        @raise RuntimeError
        """
        _, err = sendAll(self.commandSock, command)
        if err:
            raise RuntimeError(err)

        dataPortStr, err = recvAll(self.commandSock)
        if err:
            raise RuntimeError(err)

        dataPort = int(dataPortStr)
        threading.Thread(target=self._send_file, args=(dataPort, filename)).start()

    def _send_file(self, dataPort, filename):
        """Send file over ephermal data socket
        @param dataPort: server port for data transfer
        @param filename: name of file to send
        """
        dataSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        dataSock.connect((self.server[0], dataPort))

        numSent, _ = sendFile(dataSock, filename)
        filesize = getsize(filename)

        print "\rSent %s of %s bytes for '%s'" % (numSent, filesize, filename)
        print 'ftp>',
        sys.stdout.flush()
        dataSock.close()

    def list_server_files(self, command):
        """Print the list of files in the server's current working directory
        @param command: user input of type 'ls'
        @raise RuntimeError
        """
        _, err = sendAll(self.commandSock, command)
        if err:
            raise RuntimeError(err)

        file_list, err = recvAll(self.commandSock)
        if err:
            raise RuntimeError(err)

        print file_list

    def quit(self, command):
        """Close the command socket
        @param command: user input of type 'quit'
        """
        sendAll(self.commandSock, command)
        self.commandSock.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('server_machine', help='host name or IPv4 address of the FTP server')
    parser.add_argument('port_number', help='server port number', type=int)
    args = parser.parse_args()
    host = args.server_machine
    port = args.port_number

    try:
        client = FTPClient(host, port)
    except RuntimeError as e:
        print '%s:%s %s' % (host, port, e)

if __name__ == '__main__':
    main()

