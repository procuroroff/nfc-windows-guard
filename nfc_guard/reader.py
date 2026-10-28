"""Hardware Interface for ACS ACR122U NFC Reader.
Handles card detection, UID extraction (APDU FF CA 00 00 00), debouncing,
and hardware LED/Buzzer control.
"""

import time
import threading
from typing import Optional, Callable, List
from smartcard.System import readers
from smartcard.util import toHexString
from smartcard.Exceptions import CardConnectionException, NoCardException
from smartcard.scard import (
    SCardEstablishContext,
    SCardReleaseContext,
    SCardConnect,
    SCardDisconnect,
    SCardControl,
    SCARD_SCOPE_USER,
    SCARD_SHARE_DIRECT,
    SCARD_SHARE_SHARED,
    SCARD_PROTOCOL_UNDEFINED,
    SCARD_PROTOCOL_T0,
    SCARD_PROTOCOL_T1,
    SCARD_LEAVE_CARD,
)

# APDU to get Card UID (works for MIFARE Classic, Ultralight, NTAG, DESFire, etc.)
APDU_GET_UID = [0xFF, 0xCA, 0x00, 0x00, 0x00]

# ACR122U Windows IOCTL for direct control (SCARD_CTL_CODE(3500))
IOCTL_ACR122_ESCAPE = 0x003136B0


def format_uid(data: List[int]) -> str:
    """Formats byte list to uppercase colon-separated string: 04:A1:B2:C3."""
    return ":".join(f"{b:02X}" for b in data)


class ACR122UReader:
    """Manages communication with ACS ACR122U NFC Reader."""

    def __init__(
        self,
        on_card_detected: Optional[Callable[[str], None]] = None,
        on_card_removed: Optional[Callable[[], None]] = None,
        on_status_change: Optional[Callable[[bool, str], None]] = None,
    ):
        self.on_card_detected = on_card_detected
        self.on_card_removed = on_card_removed
        self.on_status_change = on_status_change

        self.reader_name: Optional[str] = None
        self.reader_obj = None
        self.is_connected = False
        self.last_card_uid: Optional[str] = None
        self.last_card_time: float = 0
        self.cooldown_seconds: float = 1.0

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def find_reader(self) -> Optional[str]:
        """Finds ACR122U or any compatible PC/SC reader."""
        try:
            available = readers()
            if not available:
                return None
            for r in available:
                if "ACR122" in str(r).upper():
                    return str(r)
            # Fallback to first smartcard reader found
            return str(available[0])
        except Exception as e:
            print(f"[Reader] Error discovering readers: {e}")
            return None

    def start_listening(self):
        """Starts background monitoring thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._thread.start()

    def stop_listening(self):
        """Stops background monitoring thread."""
        with self._lock:
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)

    def _monitor_loop(self):
        """Continuous polling loop for reader presence and card placement."""
        card_present = False

        while self._running:
            try:
                current_reader_name = self.find_reader()

                if not current_reader_name:
                    if self.is_connected:
                        self.is_connected = False
                        self.reader_name = None
                        if self.on_status_change:
                            self.on_status_change(False, "Считыватель не найден")
                    time.sleep(1.0)
                    continue

                if not self.is_connected or current_reader_name != self.reader_name:
                    self.reader_name = current_reader_name
                    self.is_connected = True
                    # Find smartcard reader object
                    for r in readers():
                        if str(r) == self.reader_name:
                            self.reader_obj = r
                            break
                    if self.on_status_change:
                        self.on_status_change(True, self.reader_name)

                # Try to read card
                uid = self._read_uid_now()

                if uid:
                    if not card_present or (uid != self.last_card_uid and (time.time() - self.last_card_time > self.cooldown_seconds)):
                        card_present = True
                        self.last_card_uid = uid
                        self.last_card_time = time.time()
                        if self.on_card_detected:
                            try:
                                self.on_card_detected(uid)
                            except Exception as e:
                                print(f"[Reader] Error in on_card_detected callback: {e}")
                else:
                    if card_present:
                        card_present = False
                        self.last_card_uid = None
                        if self.on_card_removed:
                            try:
                                self.on_card_removed()
                            except Exception as e:
                                print(f"[Reader] Error in on_card_removed callback: {e}")

            except Exception as e:
                # Small pause on unexpected exceptions
                time.sleep(0.5)

            time.sleep(0.2)  # Fast 200ms polling

    def _read_uid_now(self) -> Optional[str]:
        """Attempts to connect to card and read UID via APDU."""
        if not self.reader_obj:
            return None

        try:
            conn = self.reader_obj.createConnection()
            conn.connect()
            data, sw1, sw2 = conn.transmit(APDU_GET_UID)
            if sw1 == 0x90 and sw2 == 0x00 and data:
                return format_uid(data)
            return None
        except (NoCardException, CardConnectionException):
            return None
        except Exception:
            return None

    def read_single_card(self, timeout_seconds: float = 10.0) -> Optional[str]:
        """One-shot blocking read. Useful for 'Scan Card' dialogs in Settings."""
        start = time.time()
        while time.time() - start < timeout_seconds:
            reader_name = self.find_reader()
            if reader_name:
                for r in readers():
                    if str(r) == reader_name:
                        try:
                            conn = r.createConnection()
                            conn.connect()
                            data, sw1, sw2 = conn.transmit(APDU_GET_UID)
                            if sw1 == 0x90 and sw2 == 0x00 and data:
                                return format_uid(data)
                        except Exception:
                            pass
            time.sleep(0.25)
        return None

    def send_control_command(self, cmd_bytes: List[int]) -> bool:
        """Sends ACR122U pseudo-APDU direct control command via SCardControl."""
        try:
            hresult, hcontext = SCardEstablishContext(SCARD_SCOPE_USER)
            if hresult != 0:
                return False

            r_name = self.reader_name or self.find_reader()
            if not r_name:
                SCardReleaseContext(hcontext)
                return False

            hresult, hcard, _ = SCardConnect(
                hcontext, r_name, SCARD_SHARE_DIRECT, SCARD_PROTOCOL_UNDEFINED
            )
            if hresult != 0:
                SCardReleaseContext(hcontext)
                return False

            hresult, resp = SCardControl(hcard, IOCTL_ACR122_ESCAPE, cmd_bytes)
            SCardDisconnect(hcard, SCARD_LEAVE_CARD)
            SCardReleaseContext(hcontext)
            return hresult == 0
        except Exception as e:
            # Silently catch buzzer errors so app never crashes if unsupported
            return False

    def beep_success(self):
        """Buzzer: 1 pleasant short beep, Green LED blink (100ms)."""
        # FF 00 40 [LED=0x50: Green T1 blink] 04 [T1=1] [T2=1] [Repeat=1] [Buzzer=1]
        cmd = [0xFF, 0x00, 0x40, 0x50, 0x04, 0x01, 0x01, 0x01, 0x01]
        threading.Thread(target=self.send_control_command, args=(cmd,), daemon=True).start()

    def beep_error(self):
        """Buzzer: 2 short warning buzzes, Red LED blink."""
        # FF 00 40 [LED=0x60: Red T1 blink] 04 [T1=1] [T2=1] [Repeat=2] [Buzzer=1]
        cmd = [0xFF, 0x00, 0x40, 0x60, 0x04, 0x01, 0x01, 0x02, 0x01]
        threading.Thread(target=self.send_control_command, args=(cmd,), daemon=True).start()

    def beep_lockout(self):
        """Buzzer: 1 long alarm buzz (500ms), Red LED."""
        cmd = [0xFF, 0x00, 0x40, 0x60, 0x04, 0x05, 0x01, 0x01, 0x01]
        threading.Thread(target=self.send_control_command, args=(cmd,), daemon=True).start()
