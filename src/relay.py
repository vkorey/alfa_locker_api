import asyncio
from collections import deque
import contextlib
from datetime import datetime
from datetime import timedelta
import time
from typing import Any, Deque, Dict, Optional, Tuple

from config import CONFIG
from logger_config import setup_logger

logger = setup_logger()


class DeviceC:
    def __init__(self, ip_address: str, board_count: int):
        self.ip = ip_address
        self.port = 23
        self.board_count = board_count
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.semaphore = asyncio.Semaphore(1)
        self.command_queue: Deque[Tuple[bytes, int]] = deque()
        self.queue_lock = asyncio.Lock()
        self.cache: Dict[bytes, Dict[str, Any]] = {}
        self.timeout = 2
        self.retry_delay = 2

    async def connect(self) -> None:
        logger.debug(f"Connecting to device: {self.ip}")
        self.reader, self.writer = await asyncio.open_connection(self.ip, self.port)

    async def disconnect(self) -> None:
        if self.writer:
            logger.debug(f"Disconnecting from device: {self.ip}")
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except ConnectionResetError:
                logger.warning(f"Connection to {self.ip} already closed.")
            finally:
                self.reader = None
                self.writer = None

    async def status_send(self, command: bytes, retries: int = 3) -> Optional[bytes]:
        cached_response = self._get_cached_response(command)
        if cached_response:
            return cached_response

        return await self._attempt_send_command(command, retries)

    def _get_cached_response(self, command: bytes) -> Optional[bytes]:
        if command in self.cache:
            cache_entry = self.cache[command]
            if datetime.now() - cache_entry["timestamp"] < timedelta(seconds=5):
                logger.debug("Using cached response")
                return cache_entry["response"]
        return None

    async def _attempt_send_command(self, command: bytes, retries: int) -> Optional[bytes]:
        async with self.semaphore:
            for attempt in range(retries):
                try:
                    await self._write_command(command)
                    response = await self._read_response()
                    if response is not None:
                        self._cache_response(command, response)
                    return response
                except (ConnectionResetError, asyncio.IncompleteReadError) as e:
                    logger.warning(f"Attempt {attempt + 1}/{retries} failed for device {self.ip}: {str(e)}. Retrying...")
                    await self._handle_connect_error()
                except Exception as e:  # noqa
                    logger.error(f"Unhandled exception for device {self.ip}: {str(e)}")
                    break
            return None

    def _cache_response(self, command: bytes, response: bytes) -> None:
        self.cache[command] = {"response": response, "timestamp": datetime.now()}

    async def unlock_send(self, board: int, lock: int, retries: int = 3) -> None:
        command = self._build_unlock_command(board, lock)
        async with self.queue_lock:
            self.command_queue.append((command, retries))
        asyncio.create_task(self._process_command_queue())

    def _build_unlock_command(self, board: int, lock: int) -> bytes:
        stx = 0x02
        etx = 0x03
        cmd = 0x51
        lock -= 1
        sum_value = (stx + board + lock + cmd + etx) & 0xFF
        return bytes([stx, board, lock, cmd, etx, sum_value])

    async def _process_command_queue(self) -> None:
        async with self.queue_lock:
            while self.command_queue:
                command, retries = self.command_queue.popleft()
                await self._attempt_command(command, retries)
                await asyncio.sleep(0.5)

    async def _attempt_command(self, command: bytes, retries: int) -> None:
        for attempt in range(retries):
            try:
                await self._write_command(command)
                logger.info(f"Command sent successfully to device {self.ip}")
                break
            except (ConnectionResetError, asyncio.IncompleteReadError) as e:
                logger.warning(f"Attempt {attempt + 1}/{retries} failed for device {self.ip}: {str(e)}. Retrying...")
                await self._handle_connect_error()
            except Exception as e:  # noqa
                logger.error(f"Unhandled exception for device {self.ip}: {str(e)}")
                break

    async def _write_command(self, command: bytes) -> None:
        logger.debug(f"Writing command to device {self.ip}")
        if self.writer:
            self.writer.write(command)
            await self.writer.drain()
        else:
            logger.error("Writer is not initialized")

    async def _read_response(self) -> Optional[bytes]:
        if not self.reader:
            logger.error("Reader is not initialized")
            return None

        full_response = bytearray()
        expected_length = 12
        with contextlib.suppress(asyncio.TimeoutError):
            while len(full_response) < expected_length:
                response = await self._read_partial_response(expected_length - len(full_response))
                if response:
                    full_response.extend(response)
                else:
                    break
        return bytes(full_response)

    async def _handle_connect_error(self) -> None:
        await self.disconnect()
        await asyncio.sleep(self.retry_delay)
        await self.connect()

    async def _read_partial_response(self, length: int) -> Optional[bytes]:
        if not self.reader:
            logger.error("Reader is not initialized")
            return None
        try:
            response = await asyncio.wait_for(self.reader.read(length), timeout=self.timeout)
            return response if response else None
        except asyncio.TimeoutError:
            return None

    async def get_status(self) -> dict:
        combined_status = {}
        for board in range(self.board_count):
            command = self._build_status_command(board)
            responses = await self.status_send(command)
            if responses is None:
                logger.error(f"Failed to get status for board {board} on {self.ip}")
                continue
            module_responses = [responses[i : i + 12] for i in range(0, len(responses), 12)]
            logger.debug(f"Module responses from board {board}: {module_responses}")
            for module_response in module_responses:
                module_status = await self.parse_status(module_response)
                combined_status[board] = module_status
        logger.debug(f"Combined status for {self.ip}: {combined_status}")
        return combined_status

    def _build_status_command(self, board: int) -> bytes:
        stx = 0x02
        etx = 0x03
        cmd = 0x50
        sum_value = (stx + board + cmd + etx) & 0xFF
        return bytes([stx, board, 0x00, cmd, etx, sum_value])

    async def parse_status(self, response: bytes) -> dict:
        if not response or len(response) != 12:
            logger.error("Invalid response")
            return {}

        statuses = response[4:10]
        module_status = {}

        for i in range(48):
            byte_index = i // 8
            bit_index = i % 8
            lock_status = bool(statuses[byte_index] & (1 << bit_index))
            module_status[i + 1] = {"lock": lock_status}

        return module_status


class DeviceManager:
    def __init__(self) -> None:
        self.devices: Dict[str, DeviceC] = {}
        self.lock_lookup: Dict[str, Tuple[str, int, int]] = {}

    async def connect_device(self, ip: str, details: Dict[str, Any]) -> None:
        board_count = details["boards"]
        dev = DeviceC(ip_address=ip, board_count=board_count)
        await dev.connect()
        self.devices[ip] = dev

        for lock in details["locks"]:
            self.lock_lookup[lock["id"]] = (ip, lock["board"], lock["lock"])

        logger.info(f"Device {ip} initialized successfully")

    async def initialize_single_device(self, ip: str, details: Dict[str, Any]) -> bool:
        if ip in self.devices:
            return True  # Already initialized

        try:
            await self.connect_device(ip, details)
            return True
        except Exception as e:  # noqa
            logger.error(f"Failed to initialize device {ip}: {str(e)}")
            return False

    async def initialize_devices(self, config: Dict[str, Any]) -> bool:
        tasks = [self.initialize_single_device(ip, details) for ip, details in config.items()]
        results = await asyncio.gather(*tasks)
        return all(results)

    async def initialize_devices_background(self, config: Dict[str, Any]) -> None:
        while True:
            all_initialized = await self.initialize_devices(config)

            if all_initialized:
                logger.info("All devices initialized successfully")
                break

            await asyncio.sleep(10)

        logger.info(f"Devices initialized: {self.devices}")

    def get_devices(self) -> Dict[str, DeviceC]:
        return self.devices

    async def pulse_lock(self, lock_id: str) -> dict:
        if lock_id in self.lock_lookup:
            ip, board, lock_number = self.lock_lookup[lock_id]
            device = self.devices[ip]
            logger.info(f"Unlocking locker # {lock_number} on board {board} of device {ip}")
            await device.unlock_send(board, lock_number)
            logger.info(f"Locker # {lock_id} opened on board {board} of device {ip}")
            return {"message": f"Locker # {lock_id} opened successfully"}

        logger.error(f"Locker # {lock_id} not found")
        return {"error": f"Locker # {lock_id} not found"}

    async def relaystatus(self) -> dict:
        start_time = time.time()
        status_result: dict = {"id": {}}

        tasks = [device.get_status() for device in self.devices.values()]
        all_statuses = await asyncio.gather(*tasks)

        for ip, gateway_status in zip(self.devices.keys(), all_statuses):
            for lock in CONFIG[ip]["locks"]:
                board = lock["board"]
                lock_number = lock["lock"]
                status = gateway_status.get(board, {}).get(lock_number, {}).get("lock", False)
                status_result["id"][lock["id"]] = {"status": status}
        end_time = time.time()
        duration = end_time - start_time
        logger.info(f"Request took {duration:.2f} seconds")
        return status_result


device_manager = DeviceManager()
