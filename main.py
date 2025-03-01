import argparse
import concurrent.futures
import socket
from pathlib import Path


HOME_ENDPOINT = "/"
ECHO_ENDPOINT = "/echo/"
USER_AGENT_ENDPOINT = "/user-agent"
FILES_ENDPOINT = "/files/"
DIRECTORY = Path("/tmp")

def client_handler(client_connection, client_address):
    try:
        request = client_connection.recv(4096).decode()
        handle_request(request, client_connection, client_address)
    except Exception as e:
        print(f"Error handling client {client_address}: {e}")
    finally:
        client_connection.close()


def handle_request(request, client_connection, client_address):
    request_parts = request.split("\r\n")
    request_line = request_parts[0]
    request_method, request_target = request_line.split(" ")[0:2]
    if request_target == HOME_ENDPOINT:
        response = "HTTP/1.1 200 OK\r\n\r\n"
    elif request_target.startswith(ECHO_ENDPOINT):
        response = get_echo_response(request_parts)
    elif request_target == USER_AGENT_ENDPOINT:
        response = get_useragent_response(request_parts)
    elif request_target.startswith(FILES_ENDPOINT):
        if request_method == "GET":
            response = get_files_response(request_parts)
        elif request_method == "POST":
            response = post_files_response(request_parts)
    else:
        response = "HTTP/1.1 404 Not Found\r\n\r\n"
    client_connection.sendall(response.encode())


def get_echo_response(request_parts):
    request_line = request_parts[0]
    request_target = request_line.split(" ")[1]
    response_body = request_target[len(ECHO_ENDPOINT):]  # extract what comes after /echo/
    response_headers = (
        f"Content-Type:text/plain\r\nContent-Length:{len(response_body)}\r\n"
    )
    response = f"HTTP/1.1 200 OK\r\n{response_headers}\r\n{response_body}"
    return response


def get_useragent_response(request_parts):
    request_headers = request_parts[1:]
    user_agent_request_header = list(
        filter(
            lambda x: x.lower().startswith("user-agent:"),
            request_headers
        )
    )[0]
    response_body = user_agent_request_header[len("user-agent:"):].strip()
    response_headers = (
        f"Content-Type:text/plain\r\nContent-Length:{len(response_body)}\r\n"
    )
    response = f"HTTP/1.1 200 OK\r\n{response_headers}\r\n{response_body}"
    return response

def get_filepath(request_line):
    request_target = request_line.split(" ")[1]
    filename = request_target[len(FILES_ENDPOINT):]
    return DIRECTORY / Path(filename)

def get_files_response(request_parts):
    request_line = request_parts[0]
    filepath = get_filepath(request_line)
    if not filepath.exists():
        response = "HTTP/1.1 404 Not Found\r\n\r\n"
    else:
        with filepath.open() as f:
            response_body = f.read()
        response_headers = (
            f"Content-Type:application/octet-stream\r\nContent-Length:{len(response_body)}\r\n"
        )
        response = f"HTTP/1.1 200 OK\r\n{response_headers}\r\n{response_body}"
    return response

def post_files_response(request_parts):
    request_line = request_parts[0]
    filepath = get_filepath(request_line)
    request_body = request_parts[-1]
    with filepath.open("w") as f:
        f.write(request_body)
    return "HTTP/1.1 201 Created\r\n\r\n"

def main():
    server_socket = socket.create_server(("localhost", 4221), reuse_port=True)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        try:
            while True:
                client_connection, client_address = server_socket.accept()
                executor.submit(
                    client_handler,
                    client_connection,
                    client_address,
                )
        except KeyboardInterrupt:
            print("Shutting down server...")
        finally:
            server_socket.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='HTTP Server',
        description='Runs a HTTP server',
    )
    parser.add_argument('--directory')
    args = parser.parse_args()
    DIRECTORY = args.directory
    main()
