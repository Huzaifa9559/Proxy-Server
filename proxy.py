import socket
import sys
import threading

BUFFER_SIZE = 8192

def send_error(client_sock, status_line, err_body):
    """Helper function to send an HTTP error response."""
    body = err_body
    content_length = len(body)
    error_response = (
        f"{status_line}\r\n"
        "Content-Type: text/plain\r\n"
        f"Content-Length: {content_length}\r\n"
        "\r\n"
        f"{body}"
    )
    client_sock.sendall(error_response.encode('utf-8'))

def handle_client(client_sock):
    try:
        # Read the client's request
        request_data = client_sock.recv(BUFFER_SIZE)
        if not request_data:
            print("No data received from client.", flush=True)
            return
        try:
            request_text = request_data.decode('utf-8', errors='replace')
        except Exception as e:
            print("Decoding error:", e, flush=True)
            return

        # Split request into lines.
        lines = request_text.splitlines()
        if len(lines) == 0:
            print("Invalid request: (empty request)", flush=True)
            send_error(client_sock, "HTTP/1.0 400 Bad Request", "Invalid Request Format")
            return

        # Use the first line for error reporting.
        request_line = lines[0]

        # Parse the request line (e.g., "GET http://www.example.com/index.html HTTP/1.0")
        parts = request_line.split()
        if len(parts) < 3:
            print(f"Invalid request: {request_line} - not enough parts.", flush=True)
            send_error(client_sock, "HTTP/1.0 400 Bad Request", "Invalid Request Format")
            return

        method, url, version = parts[0], parts[1], parts[2]

        # Only support GET requests.
        if method != "GET":
            print(f"Invalid request: {request_line} - method '{method}' not supported.", flush=True)
            send_error(client_sock, "HTTP/1.0 501 Not Implemented", "Only GET method supported")
            return

        # Check if URL is in absolute form (must start with "http://").
        http_prefix = "http://"
        if not url.startswith(http_prefix):
            print(f"Invalid request: {request_line} - URL must start with '{http_prefix}'.", flush=True)
            send_error(client_sock, "HTTP/1.0 400 Bad Request", "URL must start with http://")
            return

        # Valid request: print the first line.
        print("Received valid request:", request_line, flush=True)

        # Remove "http://" and split into hostname:port and path.
        url_without_proto = url[len(http_prefix):]
        slash_index = url_without_proto.find('/')
        if slash_index == -1:
            host_port = url_without_proto
            path = "/"
        else:
            host_port = url_without_proto[:slash_index]
            path = url_without_proto[slash_index:]

        # Determine the hostname and port (default is 80).
        if ':' in host_port:
            hostname, port_str = host_port.split(':', 1)
            try:
                remote_port = int(port_str)
            except ValueError:
                print(f"Invalid port in URL {host_port}; defaulting to 80.", flush=True)
                remote_port = 80
        else:
            hostname = host_port
            remote_port = 80

        print(f"Parsed hostname: {hostname}, port: {remote_port}, path: {path}", flush=True)

        # Build the modified request to send to the remote server.
        new_request = (
            f"GET {path} HTTP/1.0\r\n"
            f"Host: {hostname}\r\n"
            "Connection: close\r\n"
            "\r\n"
        )
        print("Forwarding request to remote server:\n", new_request, flush=True)

        # Connect to the remote server.
        remote_sock = socket.create_connection((hostname, remote_port))
        remote_sock.sendall(new_request.encode('utf-8'))

        # Relay the response from the remote server back to the client,
        # and print out the server response.
        print("Received response from remote server:", flush=True)
        while True:
            data = remote_sock.recv(BUFFER_SIZE)
            if not data:
                break
            try:
                decoded = data.decode('utf-8', errors='replace')
            except Exception:
                decoded = repr(data)
            print(decoded, flush=True)
            client_sock.sendall(data)
        remote_sock.close()
    except Exception as e:
        print("Error handling client:", e, flush=True)
    finally:
        client_sock.close()

def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <port>")
        sys.exit(1)
    try:
        port = int(sys.argv[1])
    except ValueError:
        print("Port must be a number.")
        sys.exit(1)

    listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listen_sock.bind(('', port))
    listen_sock.listen(10)
    print(f"Proxy listening on port {port}", flush=True)

    try:
        while True:
            client_sock, client_addr = listen_sock.accept()
            print("Accepted connection from", client_addr, flush=True)
            # Use a new thread to handle each client connection.
            thread = threading.Thread(target=handle_client, args=(client_sock,))
            thread.daemon = True  # Ensure threads exit when main thread exits.
            thread.start()
    except KeyboardInterrupt:
        print("Shutting down proxy...", flush=True)
    finally:
        listen_sock.close()

if __name__ == "__main__":
    main()
