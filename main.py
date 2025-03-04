import argparse
import concurrent.futures
import gzip
import socket
from pathlib import Path


HOME_ENDPOINT = "/"
ECHO_ENDPOINT = "/echo/"
USER_AGENT_ENDPOINT = "/user-agent"
FILES_ENDPOINT = "/files/"
DIRECTORY = Path("/tmp")

HTTP_200_OK = "HTTP/1.1 200 OK\r\n"
HTTP_201_CREATED = "HTTP/1.1 201 Created\r\n"
HTTP_404_NOT_FOUND = "HTTP/1.1 404 Not Found\r\n"

SUPPORTED_COMPRESSION_SCHEMES = {"gzip"}

def client_handler(client_connection, client_address):
    try:
        request = client_connection.recv(4096).decode()
        handle_request(request, client_connection, client_address)
    except Exception as e:
        print(f"Error handling client {client_address}: {e}")
    finally:
        client_connection.close()


def handle_request(request, client_connection, client_address):
    request_data = parse_http_request(request)
    if request_data["target"] == HOME_ENDPOINT:
        response = build_response(HTTP_200_OK, request_data["headers"])
    elif request_data["target"].startswith(ECHO_ENDPOINT):
        response = get_echo_response(request_data)
    elif request_data["target"] == USER_AGENT_ENDPOINT:
        response = get_useragent_response(request_data)
    elif request_data["target"].startswith(FILES_ENDPOINT):
        if request_data["method"] == "GET":
            response = get_files_response(request_data)
        elif request_data["method"] == "POST":
            response = post_files_response(request_data)
    else:
        response = build_response(HTTP_404_NOT_FOUND, request_data["headers"])
    client_connection.sendall(response)


def get_echo_response(request_data):
    response_body = request_data["target"][len(ECHO_ENDPOINT):]
    response_headers = {
        "Content-Type": "text/plain",
        "Content-Length": len(response_body)
    }
    return build_response(HTTP_200_OK, request_data["headers"], response_headers, response_body)


def get_useragent_response(request_data):
    request_headers = request_data["headers"]
    response_body = request_headers["user-agent"]
    response_headers = {
        "Content-Type": "text/plain",
        "Content-Length": len(response_body)
    }
    return build_response(HTTP_200_OK, request_headers, response_headers, response_body)


def get_files_response(request_data):
    filepath = DIRECTORY / request_data["target"][len(FILES_ENDPOINT):]
    if not filepath.exists():
        return build_response(HTTP_404_NOT_FOUND, request_data["headers"])
    else:
        with filepath.open() as f:
            response_body = f.read()
        response_headers = {
            "Content-Type": "application/octet-stream",
            "Content-Length": len(response_body)
        }
        return build_response(HTTP_200_OK, request_data["headers"], response_headers, response_body)

def post_files_response(request_data):
    filename = request_data["target"][len(FILES_ENDPOINT):]
    filepath = DIRECTORY / Path(filename)
    request_body = request_data["body"]
    with filepath.open("w") as f:
        f.write(request_body)
    return build_response(HTTP_201_CREATED, request_headers=request_data["headers"])

def build_response(status_code, request_headers, response_headers=None, body=None):
    if response_headers is None:
        response_headers = {}

    response = status_code
    body_compressed = None
    if "accept-encoding" in request_headers:
        accepted_encodings = {enc.strip() for enc in request_headers["accept-encoding"].lower().split(",")}
        mutually_supported_encodings = accepted_encodings.intersection(SUPPORTED_COMPRESSION_SCHEMES)
        if len(mutually_supported_encodings):
            scheme = next(iter(mutually_supported_encodings))
            if body is not None:
                if scheme == "gzip":
                    response += f"Content-Encoding: {scheme}\r\n"
                    body_compressed = gzip.compress(body.encode())
                    response_headers["Content-Length"] = len(body_compressed)
                else:
                    pass

    for header_name, header_value in response_headers.items():
        response += f"{header_name}: {header_value}\r\n"

    response += "\r\n"

    if body_compressed is not None:
        return b"".join([response.encode(), body_compressed])
    elif body is not None:
        return b"".join([response.encode() + body.encode()])
    else:
        return response.encode()

def parse_http_request(request_data):
    request_parts = request_data.split("\r\n")
    request_line = request_parts[0]
    request_line_parts = request_line.split(" ")

    if len(request_line_parts) < 3:
        return None

    method, target, _ = request_line_parts

    # Find the empty line that separates headers from body
    try:
        body_start = request_parts.index("") + 1
        headers = request_parts[1:body_start-1]
        body = request_parts[body_start] if body_start < len(request_parts) else ""
    except ValueError:
        headers = request_parts[1:]
        body = ""

    # Parse headers into a dictionary
    headers_dict = {}
    for header in headers:
        if ":" in header:
            name, value = header.split(":", 1)
            headers_dict[name.strip().lower()] = value.strip()

    return {
        "method": method,
        "target": target,
        "headers": headers_dict,
        "body": body
    }

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
    DIRECTORY = Path(args.directory) if args.directory else DIRECTORY
    main()
