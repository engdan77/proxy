import asyncio
from asyncio import StreamReader, StreamWriter
import logging
from re import search, MULTILINE
import argparse

__version__ = "2025.9.2"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('proxy')


async def pipe(r: StreamReader, w: StreamWriter):
    message: bytes = b''
    try:
        while not r.at_eof():
            buffer = await r.read(4096)
            message += buffer
            w.write(buffer)
    finally:
        logger.debug(f'RESPONSE:\n{message.decode()}')
        w.close()

# handle every connection


async def conn_handler(lr: StreamReader, lw: StreamWriter):
    data = None
    try:
        data = (await lr.read(4096)).decode()
        logger.debug(f'REQUEST:\n{data}')
    except UnicodeDecodeError as e:
        logger.warning(e)
    logger.debug(f'Got connection from {lw.get_extra_info("peername")[0]}')
    if not data:
        lw.close()
        return
    try:
        # for HTTPS or any except HTTP
        if data.startswith('CONNECT'):
            host, port = data.splitlines()[0].split(' ')[1].split(':')
            rr, rw = await asyncio.open_connection(host, port)
            lw.write(b'HTTP/1.1 200 Connection Established\r\n\r\n')
            await lw.drain()
            await asyncio.gather(pipe(lr, rw), pipe(rr, lw))
        # for HTTP
        else:
            m = search(r"^Host:\s*([^:\r\n]+)(?::(\d+))?\s*\r?$", data, flags=MULTILINE)
            if not m:
                raise ValueError("Host header not found")
            host, port_str = m.group(1), m.group(2)
            port = int(port_str) if port_str else 80
            rr, rw = await asyncio.open_connection(host, port)
            rw.write(bytes(data, 'utf-8'))
            await rw.drain()
            await asyncio.gather(pipe(lr, rw), pipe(rr, lw))
    except ConnectionResetError as e:
        logging.error(e)
    except Exception as e:
        logging.error(e)
    finally:
        lw.close()


async def amain(port: int):
    server = await asyncio.start_server(conn_handler, '0.0.0.0', port)
    logger.info(
        f'Server ready listen at port {server.sockets[0].getsockname()[1]}')
    await server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description="Simple Python proxy server")
    parser.add_argument("-p", "--port", type=int, default=9876, help="Port to listen on (default: 9876)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose (DEBUG) logging")
    args = parser.parse_args()

    logger.setLevel(level=(logging.DEBUG if args.verbose else logging.INFO))

    try:
        asyncio.run(amain(args.port))
    except KeyboardInterrupt:
        exit(1)
    except Exception as e:
        logging.error(e)
    logging.info('Server closed')


if __name__ == "__main__":
    main()
